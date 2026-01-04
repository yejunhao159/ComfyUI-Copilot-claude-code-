"""
Global utilities for managing application-wide state and configuration.
Simplified for AgentX integration.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# AgentX Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
AGENTX_MODEL = os.getenv("AGENTX_MODEL", "claude-sonnet-4-20250514")
AGENTX_MAX_TOKENS = int(os.getenv("AGENTX_MAX_TOKENS", "4096"))
AGENTX_LOG_LEVEL = os.getenv("AGENTX_LOG_LEVEL", "INFO")
