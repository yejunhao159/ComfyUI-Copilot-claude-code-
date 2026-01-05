"""
Basic Usage Example for AgentX Runtime V2

This example demonstrates how to use the new AgentX Runtime V2
with true Agentic Loop capability via claude-agent-sdk.

Prerequisites:
    pip install claude-agent-sdk

Environment Variables:
    ANTHROPIC_API_KEY: Your Anthropic API key

Usage:
    python -m backend.agentx.runtime_v2.examples.basic_usage
"""

import asyncio
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Basic usage example."""
    # Import runtime
    from backend.agentx.runtime_v2 import (
        create_runtime,
        RuntimeConfig,
    )

    # Get API key from environment
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        return

    # Create runtime
    logger.info("Creating AgentX Runtime V2...")
    runtime = await create_runtime(RuntimeConfig(
        api_key=api_key,
        model="claude-sonnet-4-20250514",
        system_prompt="""You are a helpful AI assistant for ComfyUI workflow development.
You can help users create, modify, and debug ComfyUI workflows.
When asked to perform tasks, use the available tools to accomplish them.""",
    ))

    # Quick start - creates container and agent
    logger.info("Starting agent...")
    container, agent = await runtime.quick_start()

    # Subscribe to events
    def on_text_delta(event):
        """Handle text streaming."""
        text = event.data.get("text", "") if isinstance(event.data, dict) else ""
        print(text, end="", flush=True)

    def on_state_change(event):
        """Handle state changes."""
        state = event.data.state if hasattr(event.data, "state") else event.data.get("state", "")
        logger.debug(f"State: {state}")

    def on_tool_use(event):
        """Handle tool usage."""
        if hasattr(event.data, "tool_name"):
            logger.info(f"Using tool: {event.data.tool_name}")
        elif isinstance(event.data, dict) and "tool_name" in event.data:
            logger.info(f"Using tool: {event.data['tool_name']}")

    # Register event handlers
    runtime.events.on("text_delta", on_text_delta)
    runtime.events.on("state_change", on_state_change)
    runtime.events.on("tool_use_content_block_start", on_tool_use)

    # Send a message
    print("\n" + "=" * 50)
    print("Agent Response:")
    print("=" * 50)

    await agent.receive("What is 2 + 2? Explain your reasoning.")

    # Wait a moment for async processing
    await asyncio.sleep(2)

    print("\n" + "=" * 50)

    # Cleanup
    await runtime.shutdown()
    logger.info("Done!")


async def example_with_mcp_tools():
    """Example with MCP tools integration."""
    from backend.agentx.runtime_v2 import (
        create_runtime,
        RuntimeConfig,
        create_comfyui_mcp_server,
    )

    # Mock ComfyUI client for example
    class MockComfyClient:
        async def get_workflow(self):
            return {"nodes": [], "links": []}

        async def search_nodes(self, query, limit):
            return [
                {"type": "KSampler", "description": "Sampler node"},
                {"type": "CLIPTextEncode", "description": "Text encoder"},
            ]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        return

    # Create MCP server with ComfyUI tools
    comfy_client = MockComfyClient()
    mcp_server = create_comfyui_mcp_server(comfy_client)

    if not mcp_server:
        logger.warning("MCP server not created (claude-agent-sdk not installed)")
        return

    # Create runtime with MCP server
    runtime = await create_runtime(RuntimeConfig(
        api_key=api_key,
        model="claude-sonnet-4-20250514",
        system_prompt="You are a ComfyUI workflow assistant.",
        mcp_servers={"comfyui": mcp_server},
    ))

    container, agent = await runtime.quick_start()

    # Subscribe to events
    runtime.events.on("text_delta", lambda e: print(e.data.get("text", ""), end="", flush=True))

    # Ask about workflow
    print("\nAsking agent to get workflow...")
    await agent.receive("Please get the current workflow and describe what nodes are available.")

    await asyncio.sleep(5)

    await runtime.shutdown()


if __name__ == "__main__":
    # Run basic example
    asyncio.run(main())

    # Uncomment to run MCP example
    # asyncio.run(example_with_mcp_tools())
