"""
AgentX Agent Engine

Claude API integration with streaming support and tool calling.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncIterator
from anthropic import AsyncAnthropic
from anthropic.types import (
    Message as AnthropicMessage,
    MessageStreamEvent,
    ContentBlock,
    TextBlock,
    ToolUseBlock,
)

from .types import (
    Message,
    MessageRole,
    ToolCall,
    StreamEvent,
    StateEvent,
    StateEventData,
    MessageEvent,
    TurnEvent,
    TurnEventData,
    AgentState,
)
from .event_bus import EventBus
from ..config import AgentConfig

logger = logging.getLogger(__name__)


class AgentEngine:
    """
    Agent engine for Claude API integration.

    Features:
    - Streaming text generation
    - Tool calling support
    - Event emission (Stream/State/Message/Turn)
    - Token usage tracking
    """

    def __init__(self, config: AgentConfig, event_bus: EventBus):
        """
        Initialize agent engine.

        Args:
            config: Agent configuration
            event_bus: EventBus for publishing events
        """
        self.config = config
        self.event_bus = event_bus
        self.client = AsyncAnthropic(api_key=config.anthropic_api_key)
        logger.info(f"AgentEngine initialized with model {config.model}")

    async def generate(
        self,
        session_id: str,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        system: Optional[str] = None,
    ) -> Message:
        """
        Generate a response from Claude.

        Args:
            session_id: Session ID for event emission
            messages: Conversation history
            tools: Optional tool definitions
            system: Optional system prompt

        Returns:
            Assistant message with response and tool calls
        """
        turn_start = datetime.utcnow()
        message_id = str(uuid.uuid4())
        accumulated_text = ""
        tool_calls = []
        input_tokens = 0
        output_tokens = 0

        # Emit THINKING state
        await self.event_bus.publish(
            StateEvent(
                session_id=session_id,
                data=StateEventData(state=AgentState.THINKING),
            )
        )

        # Convert messages to Anthropic format
        anthropic_messages = self._convert_messages(messages)

        # Stream response from Claude
        try:
            async with self.client.messages.stream(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=anthropic_messages,
                tools=tools or [],
                system=system,
            ) as stream:
                # Emit RESPONDING state
                await self.event_bus.publish(
                    StateEvent(
                        session_id=session_id,
                        data=StateEventData(state=AgentState.RESPONDING),
                    )
                )

                async for event in stream:
                    if event.type == "content_block_delta":
                        # Stream text tokens
                        if hasattr(event.delta, "text"):
                            text = event.delta.text
                            accumulated_text += text
                            await self.event_bus.publish(
                                StreamEvent(session_id=session_id, data=text)
                            )

                    elif event.type == "content_block_start":
                        # Handle tool use blocks
                        if isinstance(event.content_block, ToolUseBlock):
                            tool_use = event.content_block
                            # Emit CALLING_TOOL state
                            await self.event_bus.publish(
                                StateEvent(
                                    session_id=session_id,
                                    data=StateEventData(
                                        state=AgentState.CALLING_TOOL,
                                        tool_name=tool_use.name,
                                        tool_call_id=tool_use.id,
                                    ),
                                )
                            )

                    elif event.type == "message_start":
                        # Track token usage
                        if hasattr(event.message, "usage"):
                            input_tokens = event.message.usage.input_tokens

                    elif event.type == "message_delta":
                        # Track output tokens
                        if hasattr(event.delta, "usage"):
                            output_tokens = event.delta.usage.output_tokens

                # Get final message with tool calls
                final_message = await stream.get_final_message()

                # Extract tool calls
                for block in final_message.content:
                    if isinstance(block, ToolUseBlock):
                        tool_calls.append(
                            ToolCall(
                                id=block.id,
                                name=block.name,
                                arguments=block.input,
                            )
                        )

        except Exception as e:
            logger.error(f"Error in agent generation: {e}", exc_info=True)
            # Emit ERROR state
            await self.event_bus.publish(
                StateEvent(
                    session_id=session_id,
                    data=StateEventData(state=AgentState.ERROR),
                )
            )
            raise

        # Create response message
        response = Message(
            message_id=message_id,
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=accumulated_text,
            timestamp=datetime.utcnow(),
            tool_calls=tool_calls if tool_calls else None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # Emit MESSAGE event
        await self.event_bus.publish(
            MessageEvent(session_id=session_id, data=response)
        )

        # Emit DONE state
        await self.event_bus.publish(
            StateEvent(
                session_id=session_id,
                data=StateEventData(state=AgentState.DONE),
            )
        )

        # Emit TURN event
        turn_duration = int((datetime.utcnow() - turn_start).total_seconds() * 1000)
        await self.event_bus.publish(
            TurnEvent(
                session_id=session_id,
                data=TurnEventData(
                    turn_id=str(uuid.uuid4()),
                    user_message_id=messages[-1].message_id if messages else "",
                    assistant_message_id=message_id,
                    total_tokens=input_tokens + output_tokens,
                    duration_ms=turn_duration,
                ),
            )
        )

        return response

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert domain messages to Anthropic API format.

        Args:
            messages: List of domain Message objects

        Returns:
            List of Anthropic message dicts
        """
        anthropic_messages = []

        for msg in messages:
            content = []

            # Add text content
            if msg.content:
                content.append({"type": "text", "text": msg.content})

            # Add tool use/result content
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.result is not None:
                        # Tool result (user message)
                        content.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": str(tc.result),
                        })
                    else:
                        # Tool use (assistant message)
                        content.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })

            anthropic_messages.append({
                "role": msg.role.value,
                "content": content if content else msg.content,
            })

        return anthropic_messages

    async def close(self) -> None:
        """Close the Anthropic client."""
        await self.client.close()
        logger.info("AgentEngine closed")
