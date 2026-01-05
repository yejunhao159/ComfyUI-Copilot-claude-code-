#!/usr/bin/env python3
"""
Integration test for AgentX Runtime V2.

Tests the complete flow:
1. Create Runtime
2. Create Container
3. Run Agent
4. Send message
5. Receive response via events
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.agentx import (
    Runtime,
    RuntimeConfig,
    create_runtime,
    SystemEvent,
)


async def test_runtime_v2():
    """Test the complete Runtime V2 flow."""
    print("=" * 60)
    print("AgentX Runtime V2 Integration Test")
    print("=" * 60)

    # Configuration - using empty API key since Claude CLI handles auth
    config = RuntimeConfig(
        api_key="",  # Claude CLI uses its own auth
        model="claude-opus-4-5-20251101",  # Match settings
    )

    print(f"\nConfig:")
    print(f"  Model: {config.model}")

    # Create runtime
    print("\n--- Creating Runtime ---")
    runtime = await create_runtime(config)
    print(f"Runtime created successfully")

    # Create container
    print("\n--- Creating Container ---")
    container = await runtime.create_container("test-container")
    print(f"Container created: {container.container_id}")

    # Setup event tracking
    events_received = []
    text_chunks = []
    done_event = asyncio.Event()

    def on_event(event: SystemEvent):
        """Handle all events."""
        events_received.append(event)
        print(f"  Event: {event.type}")

        if event.type == "text_delta":
            if hasattr(event.data, 'text'):
                text_chunks.append(event.data.text)
                print(f"    Text: '{event.data.text}'", end="", flush=True)
            elif isinstance(event.data, dict):
                text = event.data.get('text', '')
                text_chunks.append(text)
                print(f"    Text: '{text}'", end="", flush=True)

        elif event.type == "message_stop":
            print(f"\n    [message_stop]")
            done_event.set()

        elif event.type == "error_received":
            error_msg = getattr(event.data, 'message', str(event.data))
            print(f"    ERROR: {error_msg}")
            done_event.set()

        elif event.type == "state_change":
            state = getattr(event.data, 'state', event.data)
            print(f"    State: {state}")
            if state == "idle":
                done_event.set()

    # Subscribe to events
    unsubscribe = runtime.events.on_any(on_event)

    # Quick start agent
    print("\n--- Starting Agent ---")
    try:
        container, agent = await runtime.quick_start(
            system_prompt="You are a helpful assistant. Answer questions concisely.",
            cwd=os.getcwd(),
        )
        print(f"Agent created: {agent.agent_id}")
        print(f"Agent state: {agent.state}")

        # Send message
        print("\n--- Sending Message ---")
        prompt = "What is 2 + 2? Answer in one word."
        print(f"Prompt: {prompt}")
        print("\n--- Waiting for Response ---")

        await agent.receive(prompt)

        # Wait for response with timeout
        try:
            await asyncio.wait_for(done_event.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            print("\n[Timeout waiting for response]")

        # Print results
        print("\n\n--- Results ---")
        print(f"Events received: {len(events_received)}")
        print(f"Event types: {[e.type for e in events_received]}")
        print(f"Accumulated text: {''.join(text_chunks)}")

    except Exception as e:
        print(f"\nError: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        unsubscribe()
        print("\n--- Shutting Down ---")
        await runtime.shutdown()
        print("Done")


if __name__ == "__main__":
    asyncio.run(test_runtime_v2())
