"""
AgentX Runtime Configuration

从环境变量加载配置，提供默认值。
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class AgentConfig:
    """Agent runtime configuration"""

    # Claude API
    anthropic_api_key: str
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4096
    temperature: float = 1.0

    # Database
    database_url: str = "sqlite:///agentx_sessions.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # MCP Servers
    mcp_servers: List[Dict[str, Any]] = field(default_factory=list)
    mcp_servers_file: Optional[str] = None

    # WebSocket
    websocket_heartbeat_interval: int = 30  # seconds
    websocket_timeout: int = 300  # seconds

    # Performance
    event_queue_maxsize: int = 1000
    message_load_page_size: int = 100
    tool_timeout: int = 120  # seconds

    # Debugging
    enable_event_logging: bool = False
    log_level: str = "INFO"
    mcp_log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables"""
        import json

        # Read API key (required)
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("AGENTX_ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY or AGENTX_ANTHROPIC_API_KEY environment variable is required"
            )

        # Load MCP servers from JSON file if specified
        mcp_servers = []
        mcp_servers_file = os.getenv("AGENTX_MCP_SERVERS_FILE")
        if mcp_servers_file and os.path.exists(mcp_servers_file):
            with open(mcp_servers_file, "r") as f:
                mcp_servers = json.load(f)

        return cls(
            anthropic_api_key=api_key,
            model=os.getenv("AGENTX_MODEL", "claude-3-5-sonnet-20241022"),
            max_tokens=int(os.getenv("AGENTX_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("AGENTX_TEMPERATURE", "1.0")),
            database_url=os.getenv("AGENTX_DATABASE_URL", "sqlite:///agentx_sessions.db"),
            db_pool_size=int(os.getenv("AGENTX_DB_POOL_SIZE", "5")),
            db_max_overflow=int(os.getenv("AGENTX_DB_MAX_OVERFLOW", "10")),
            mcp_servers=mcp_servers,
            mcp_servers_file=mcp_servers_file,
            websocket_heartbeat_interval=int(os.getenv("AGENTX_WEBSOCKET_HEARTBEAT", "30")),
            websocket_timeout=int(os.getenv("AGENTX_WEBSOCKET_TIMEOUT", "300")),
            event_queue_maxsize=int(os.getenv("AGENTX_EVENT_QUEUE_MAXSIZE", "1000")),
            message_load_page_size=int(os.getenv("AGENTX_MESSAGE_LOAD_PAGE_SIZE", "100")),
            tool_timeout=int(os.getenv("AGENTX_TOOL_TIMEOUT", "120")),
            enable_event_logging=os.getenv("AGENTX_ENABLE_EVENT_LOGGING", "false").lower() == "true",
            log_level=os.getenv("AGENTX_LOG_LEVEL", "INFO"),
            mcp_log_level=os.getenv("AGENTX_MCP_LOG_LEVEL", "INFO"),
        )

    def validate(self) -> None:
        """Validate configuration on startup (fail fast if invalid)"""
        if not self.anthropic_api_key:
            raise ValueError("anthropic_api_key is required")

        if self.max_tokens < 1 or self.max_tokens > 100000:
            raise ValueError("max_tokens must be between 1 and 100000")

        if self.temperature < 0 or self.temperature > 2:
            raise ValueError("temperature must be between 0 and 2")

        if self.event_queue_maxsize < 1:
            raise ValueError("event_queue_maxsize must be at least 1")

        if self.tool_timeout < 1:
            raise ValueError("tool_timeout must be at least 1 second")
