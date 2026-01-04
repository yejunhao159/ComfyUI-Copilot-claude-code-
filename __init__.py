"""
ComfyUI-AgentX: AI Agent for ComfyUI workflow debugging and manipulation.

Based on Deepractice AgentX runtime with Claude integration.
"""
# Copyright (C) 2025 Deepractice
# Licensed under the MIT License.

import os

# Load .env file from plugin directory
from dotenv import load_dotenv
plugin_dir = os.path.dirname(__file__)
env_path = os.path.join(plugin_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# Initialize logging system FIRST (before other imports)
from .backend.utils.logger import configure_logging, get_logger

# Configure logging based on environment
log_level = os.getenv("AGENTX_LOG_LEVEL", "INFO")
log_dir = os.path.join(plugin_dir, "backend", "logs")
configure_logging(log_level=log_level, log_dir=log_dir)

logger = get_logger(__name__)
logger.info("AgentX logging initialized", log_level=log_level)

# Now import other modules
import server
from aiohttp import web
import folder_paths

from .backend.agentx.api.server import create_agentx_routes

# Configuration
NODE_CLASS_MAPPINGS = {}
__all__ = ['NODE_CLASS_MAPPINGS']
version = "V3.0.0"

# Web extension directory - ComfyUI will auto-discover and load JS files
WEB_DIRECTORY = "web"

# Paths
workspace_path = os.path.join(os.path.dirname(__file__))
comfy_path = os.path.dirname(folder_paths.__file__)
db_dir_path = os.path.join(workspace_path, "db")

# Register AgentX API routes
try:
    agentx_routes = create_agentx_routes()
    server.PromptServer.instance.app.add_routes(agentx_routes)
    logger.info("AgentX API routes registered", endpoint="/api/agentx/", version=version)
except Exception as e:
    logger.exception("Failed to register AgentX API routes")

# Note: UI is embedded in ComfyUI via WEB_DIRECTORY extension system
# The JS extension at web/js/agentx_extension.js adds a sidebar panel
