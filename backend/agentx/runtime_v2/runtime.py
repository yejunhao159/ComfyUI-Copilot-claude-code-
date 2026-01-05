"""
Runtime - Top-level AgentX Runtime API

Ported from @agentxjs/runtime/src/RuntimeImpl.ts

The Runtime is the entry point for the AgentX system.
It manages Containers, provides event access, and handles configuration.

Usage:
    runtime = await create_runtime(RuntimeConfig(...))

    # Create container
    container = await runtime.create_container("my-container")

    # Run agent from image
    agent, _ = await container.run_image(image)

    # Subscribe to events
    runtime.events.on("text_delta", lambda e: print(e.data.text))

    # Send message
    await agent.receive("Hello!")

    # Cleanup
    await runtime.shutdown()
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable

from .system_bus import SystemBus, SystemBusImpl, SystemBusConsumer
from .container import RuntimeContainer, LLMConfig, ImageRecord
from .types import SystemEvent

from ...utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Runtime Configuration
# =============================================================================


@dataclass
class RuntimeConfig:
    """Runtime configuration."""

    # LLM Configuration
    api_key: str
    base_url: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"
    timeout: int = 30000  # ms

    # Default system prompt
    system_prompt: Optional[str] = None

    # Default MCP servers
    mcp_servers: Optional[Dict] = None

    # Default allowed tools
    allowed_tools: Optional[List[str]] = None


# =============================================================================
# Runtime
# =============================================================================


class Runtime:
    """
    Runtime - Top-level AgentX Runtime.

    This is the main entry point for using AgentX.

    Features:
    - Container management
    - Event bus access
    - Configuration management
    """

    def __init__(self, config: RuntimeConfig):
        self._config = config
        self._bus = SystemBusImpl()
        self._containers: Dict[str, RuntimeContainer] = {}
        self._is_shutdown = False

        # Build LLM config
        self._llm_config = LLMConfig(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            timeout=config.timeout,
        )

        logger.info("Runtime initialized")

    @property
    def events(self) -> SystemBusConsumer:
        """
        Get event bus consumer for subscribing to events.

        Usage:
            runtime.events.on("text_delta", lambda e: print(e.data.text))
            runtime.events.on_any(lambda e: log(e))
        """
        return self._bus.as_consumer()

    @property
    def bus(self) -> SystemBus:
        """Get full event bus (internal use)."""
        return self._bus

    @property
    def config(self) -> RuntimeConfig:
        """Get runtime configuration."""
        return self._config

    # =========================================================================
    # Container Management
    # =========================================================================

    async def create_container(
        self,
        container_id: Optional[str] = None,
    ) -> RuntimeContainer:
        """
        Create a new container.

        Args:
            container_id: Optional container ID (auto-generated if not provided)

        Returns:
            RuntimeContainer instance
        """
        if self._is_shutdown:
            raise RuntimeError("Runtime is shutdown")

        if not container_id:
            container_id = f"container_{uuid.uuid4().hex[:8]}"

        if container_id in self._containers:
            raise ValueError(f"Container already exists: {container_id}")

        container = RuntimeContainer(
            container_id=container_id,
            bus=self._bus,
            llm_config=self._llm_config,
        )

        self._containers[container_id] = container
        logger.info(f"Container created: {container_id}")
        return container

    def get_container(self, container_id: str) -> Optional[RuntimeContainer]:
        """Get container by ID."""
        return self._containers.get(container_id)

    def list_containers(self) -> List[RuntimeContainer]:
        """List all containers."""
        return list(self._containers.values())

    async def destroy_container(self, container_id: str) -> bool:
        """
        Destroy a container.

        Args:
            container_id: Container to destroy

        Returns:
            True if container was found and destroyed
        """
        container = self._containers.get(container_id)
        if not container:
            return False

        await container.dispose()
        del self._containers[container_id]
        logger.info(f"Container destroyed: {container_id}")
        return True

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    async def quick_start(
        self,
        system_prompt: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> tuple[RuntimeContainer, "RuntimeAgent"]:
        """
        Quick start - create container and agent with minimal setup.

        This is the fastest way to get a working agent.

        Args:
            system_prompt: Optional system prompt override
            cwd: Working directory for agent

        Returns:
            (container, agent) tuple
        """
        from datetime import datetime

        # Create container
        container = await self.create_container()

        # Create default image
        image = ImageRecord(
            image_id=f"image_{uuid.uuid4().hex[:8]}",
            name="Default Agent",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            system_prompt=system_prompt or self._config.system_prompt,
            model=self._config.model,
            mcp_servers=self._config.mcp_servers,
            allowed_tools=self._config.allowed_tools,
        )

        # Run agent
        agent, _ = await container.run_image(image, cwd=cwd)

        return container, agent

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def shutdown(self) -> None:
        """Shutdown the runtime and clean up all resources."""
        if self._is_shutdown:
            return

        self._is_shutdown = True

        # Destroy all containers
        for container in list(self._containers.values()):
            await container.dispose()
        self._containers.clear()

        # Destroy bus
        self._bus.destroy()

        logger.info("Runtime shutdown complete")


# =============================================================================
# Factory Function
# =============================================================================


async def create_runtime(config: RuntimeConfig) -> Runtime:
    """
    Create and initialize a Runtime instance.

    This is the recommended way to create a Runtime.

    Args:
        config: Runtime configuration

    Returns:
        Initialized Runtime instance

    Example:
        runtime = await create_runtime(RuntimeConfig(
            api_key="your-api-key",
            model="claude-sonnet-4-20250514",
        ))

        # Quick start
        container, agent = await runtime.quick_start()

        # Subscribe to events
        runtime.events.on("text_delta", lambda e: print(e.data["text"]))

        # Send message
        await agent.receive("Hello!")
    """
    runtime = Runtime(config)
    logger.info("Runtime created successfully")
    return runtime
