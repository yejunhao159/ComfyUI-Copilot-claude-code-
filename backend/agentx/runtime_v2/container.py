"""
RuntimeContainer - Runtime Environment for Agent Instances

Ported from @agentxjs/runtime/src/internal/RuntimeContainer.ts

Container is a runtime isolation boundary where Agents live and work.
Each Container manages multiple Agents, tracking image → agent mapping.

Architecture:
    Container
      └── Image 1 ──→ Agent 1
      └── Image 2 ──→ (offline)
      └── Image 3 ──→ Agent 3

Key Concepts:
    - Image: Persistent entity (conversation definition)
    - Agent: Transient runtime instance of an Image
    - Container: Tracks imageId → agentId mapping
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any

from .system_bus import SystemBus
from .types import AgentSession, SessionState
from .agent import RuntimeAgent, AgentConfig

from ...utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Image Record
# =============================================================================


@dataclass
class ImageRecord:
    """
    Image Record - Persistent agent definition.

    An Image defines what an Agent will be when instantiated.
    """
    image_id: str
    name: str
    created_at: datetime
    updated_at: datetime

    # Agent Configuration
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    mcp_servers: Optional[Dict[str, Any]] = None
    allowed_tools: Optional[List[str]] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# LLM Configuration
# =============================================================================


@dataclass
class LLMConfig:
    """LLM configuration."""
    api_key: str
    base_url: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"
    timeout: int = 30000  # ms


# =============================================================================
# Runtime Container
# =============================================================================


class RuntimeContainer:
    """
    RuntimeContainer - Manages Agent instances.

    Features:
    - Image → Agent lifecycle (runImage, stopImage)
    - Runtime isolation between Containers
    - Agent lookup and management
    """

    def __init__(
        self,
        container_id: str,
        bus: SystemBus,
        llm_config: LLMConfig,
    ):
        self.container_id = container_id
        self.created_at = int(time.time() * 1000)

        self._bus = bus
        self._llm_config = llm_config

        # Agents by agent_id
        self._agents: Dict[str, RuntimeAgent] = {}

        # Image → Agent mapping
        self._image_to_agent: Dict[str, str] = {}

        # Sessions by session_id
        self._sessions: Dict[str, AgentSession] = {}

        # Locks for thread safety
        self._lock = asyncio.Lock()

        logger.info(f"RuntimeContainer created: {container_id}")

    @property
    def agent_count(self) -> int:
        """Get number of agents."""
        return len(self._agents)

    # =========================================================================
    # Image → Agent Lifecycle
    # =========================================================================

    async def run_image(
        self,
        image: ImageRecord,
        cwd: Optional[str] = None,
    ) -> tuple[RuntimeAgent, bool]:
        """
        Run an Image - create or reuse an Agent.

        Args:
            image: ImageRecord to run
            cwd: Working directory for agent

        Returns:
            (agent, reused) - The agent and whether it was reused
        """
        async with self._lock:
            # Check if already running
            if image.image_id in self._image_to_agent:
                agent_id = self._image_to_agent[image.image_id]
                agent = self._agents.get(agent_id)
                if agent:
                    logger.debug(f"Reusing agent {agent_id} for image {image.image_id}")
                    return agent, True

            # Create new agent
            agent_id = f"agent_{uuid.uuid4().hex[:8]}"
            session_id = f"session_{uuid.uuid4().hex[:8]}"

            # Create session
            session = AgentSession(
                session_id=session_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                state=SessionState.IDLE,
            )
            self._sessions[session_id] = session

            # Build agent config
            config = AgentConfig(
                agent_id=agent_id,
                container_id=self.container_id,
                session_id=session_id,
                api_key=self._llm_config.api_key,
                base_url=self._llm_config.base_url,
                model=image.model or self._llm_config.model,
                system_prompt=image.system_prompt,
                cwd=cwd,
                timeout=self._llm_config.timeout,
                mcp_servers=image.mcp_servers,
                allowed_tools=image.allowed_tools,
                resume_session_id=image.metadata.get("claude_sdk_session_id"),
            )

            # Create agent
            agent = RuntimeAgent(config, self._bus, session)

            # Track
            self._agents[agent_id] = agent
            self._image_to_agent[image.image_id] = agent_id

            logger.info(f"Created agent {agent_id} for image {image.image_id}")
            return agent, False

    async def stop_image(self, image_id: str) -> bool:
        """
        Stop an Image - destroy the Agent but keep the Image.

        Args:
            image_id: Image to stop

        Returns:
            True if agent was found and destroyed
        """
        async with self._lock:
            agent_id = self._image_to_agent.get(image_id)
            if not agent_id:
                return False

            agent = self._agents.get(agent_id)
            if agent:
                await agent.destroy()
                del self._agents[agent_id]

            del self._image_to_agent[image_id]
            logger.info(f"Stopped image {image_id} (destroyed agent {agent_id})")
            return True

    def get_agent_id_for_image(self, image_id: str) -> Optional[str]:
        """Get agent ID for an image (if running)."""
        return self._image_to_agent.get(image_id)

    def is_image_online(self, image_id: str) -> bool:
        """Check if an image has a running agent."""
        return image_id in self._image_to_agent

    # =========================================================================
    # Agent Operations
    # =========================================================================

    def get_agent(self, agent_id: str) -> Optional[RuntimeAgent]:
        """Get an Agent by ID."""
        return self._agents.get(agent_id)

    def list_agents(self) -> List[RuntimeAgent]:
        """List all Agents in this container."""
        return list(self._agents.values())

    async def destroy_agent(self, agent_id: str) -> bool:
        """
        Destroy an Agent by ID.

        Args:
            agent_id: Agent to destroy

        Returns:
            True if agent was found and destroyed
        """
        async with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False

            # Remove from image mapping
            for image_id, aid in list(self._image_to_agent.items()):
                if aid == agent_id:
                    del self._image_to_agent[image_id]
                    break

            await agent.destroy()
            del self._agents[agent_id]
            logger.info(f"Destroyed agent {agent_id}")
            return True

    async def destroy_all_agents(self) -> None:
        """Destroy all Agents in this container."""
        async with self._lock:
            for agent in list(self._agents.values()):
                await agent.destroy()
            self._agents.clear()
            self._image_to_agent.clear()
            logger.info(f"Destroyed all agents in container {self.container_id}")

    # =========================================================================
    # Session Operations
    # =========================================================================

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[AgentSession]:
        """List all sessions in this container."""
        return list(self._sessions.values())

    # =========================================================================
    # Container Lifecycle
    # =========================================================================

    async def dispose(self) -> None:
        """Dispose the container and all its Agents."""
        await self.destroy_all_agents()
        self._sessions.clear()
        logger.info(f"Container disposed: {self.container_id}")
