"""
ComfyUI MCP Tools

This module provides a modular tool system for ComfyUI workflow manipulation.

Tools are organized into categories:
- Workflow Tools: get_workflow, update_workflow, clear_workflow
- Node Tools: add_node, remove_node, modify_node, connect_nodes, disconnect_input
- Search Tools: search_nodes, get_node_info, list_node_categories
- Execution Tools: execute_workflow, get_execution_result, interrupt_execution
- Validation Tools: validate_workflow, analyze_workflow
- Image Tools: get_execution_images, get_latest_images
- Template Tools: save_workflow_template, load_workflow_template, list_workflow_templates, delete_workflow_template
- System Tools: list_models, get_system_stats, get_comfyui_info, clear_queue
"""

import logging
from typing import Dict, Any, List

# Import the modular tool system
from .tools.base import registry
from .tools.workflow_state import state
from .tools.workflow_tools import WorkflowTools
from .tools.node_tools import NodeTools
from .tools.search_tools import SearchTools
from .tools.execution_tools import ExecutionTools
from .tools.validation_tools import ValidationTools
from .tools.image_tools import ImageTools
from .tools.template_tools import TemplateTools
from .tools.system_tools import SystemTools

logger = logging.getLogger(__name__)

# Flag to track if tools are registered
_tools_registered = False


def _ensure_tools_registered():
    """Ensure all tools are registered."""
    global _tools_registered
    if not _tools_registered:
        # Core tools
        WorkflowTools.register_all()
        NodeTools.register_all()
        SearchTools.register_all()
        ExecutionTools.register_all()
        # Enhanced tools
        ValidationTools.register_all()
        ImageTools.register_all()
        TemplateTools.register_all()
        SystemTools.register_all()
        _tools_registered = True
        logger.info(f"Registered {len(registry.list_tools())} ComfyUI tools")


# ============================================
# Public API (backwards compatible)
# ============================================

def get_comfyui_tools() -> List[Dict[str, Any]]:
    """
    Get ComfyUI tool definitions in Anthropic Claude format.

    Returns:
        List of tool definitions
    """
    _ensure_tools_registered()
    return registry.get_all_tools()


async def execute_comfyui_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a ComfyUI tool by name.

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments

    Returns:
        Tool execution result

    Raises:
        ValueError: If tool name is not recognized
    """
    _ensure_tools_registered()
    return await registry.execute_tool(tool_name, arguments)


# ============================================
# Legacy API (for backwards compatibility)
# ============================================

def set_current_workflow(workflow: Dict[str, Any]) -> None:
    """Set the current workflow state (legacy API)."""
    state.workflow = workflow


def get_current_workflow_state() -> Dict[str, Any]:
    """Get the current workflow state (legacy API)."""
    return state.workflow


# Re-export for backwards compatibility
async def get_workflow(workflow_id=None):
    """Get current workflow (legacy API)."""
    _ensure_tools_registered()
    return await registry.execute_tool("get_workflow", {"workflow_id": workflow_id})


async def update_workflow(workflow_data):
    """Update workflow (legacy API)."""
    _ensure_tools_registered()
    return await registry.execute_tool("update_workflow", {"workflow_data": workflow_data})


async def search_nodes(keywords, limit=10):
    """Search nodes (legacy API)."""
    _ensure_tools_registered()
    return await registry.execute_tool("search_nodes", {"keywords": keywords, "limit": limit})


async def get_node_info(node_classes):
    """Get node info (legacy API)."""
    _ensure_tools_registered()
    return await registry.execute_tool("get_node_info", {"node_classes": node_classes})


async def execute_workflow(workflow=None):
    """Execute workflow (legacy API)."""
    _ensure_tools_registered()
    return await registry.execute_tool("execute_workflow", {"workflow": workflow})


async def get_execution_result(prompt_id, wait=False, timeout=60):
    """Get execution result (legacy API)."""
    _ensure_tools_registered()
    return await registry.execute_tool("get_execution_result", {
        "prompt_id": prompt_id, "wait": wait, "timeout": timeout
    })


async def modify_node(node_id, parameter, value):
    """Modify node (legacy API)."""
    _ensure_tools_registered()
    return await registry.execute_tool("modify_node", {
        "node_id": node_id, "input_name": parameter, "value": value
    })


async def add_node(node_id, class_type, inputs=None):
    """Add node (legacy API)."""
    _ensure_tools_registered()
    return await registry.execute_tool("add_node", {
        "class_type": class_type, "inputs": inputs, "node_id": node_id
    })


async def remove_node(node_id):
    """Remove node (legacy API)."""
    _ensure_tools_registered()
    return await registry.execute_tool("remove_node", {"node_id": node_id})
