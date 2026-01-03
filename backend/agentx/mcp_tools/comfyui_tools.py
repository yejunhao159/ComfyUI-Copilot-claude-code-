"""
ComfyUI MCP Tools

Built-in tools for ComfyUI workflow debugging and manipulation.
"""

import logging
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("comfyui-tools", "ComfyUI workflow debugging and manipulation tools")


@mcp.tool()
def get_workflow(workflow_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the current ComfyUI workflow or a specific workflow by ID.

    Args:
        workflow_id: Optional workflow ID. If not provided, returns the current active workflow.

    Returns:
        Workflow object with nodes, connections, and metadata.
    """
    # TODO: Integrate with ComfyUI backend
    # For now, return a placeholder
    logger.info(f"get_workflow called with workflow_id={workflow_id}")

    return {
        "workflow_id": workflow_id or "current",
        "nodes": [],
        "links": [],
        "metadata": {
            "name": "Current Workflow",
            "description": "Active ComfyUI workflow",
        },
    }


@mcp.tool()
def update_workflow(workflow_id: str, nodes: List[Dict], links: List[Dict]) -> Dict[str, Any]:
    """
    Update a ComfyUI workflow with new nodes and connections.

    Args:
        workflow_id: Workflow ID to update
        nodes: List of node definitions
        links: List of connection definitions

    Returns:
        Updated workflow object.
    """
    logger.info(f"update_workflow called for workflow_id={workflow_id}")

    # TODO: Integrate with ComfyUI backend
    return {
        "workflow_id": workflow_id,
        "nodes": nodes,
        "links": links,
        "updated": True,
    }


@mcp.tool()
def modify_node(
    workflow_id: str,
    node_id: str,
    parameter: str,
    value: Any,
) -> Dict[str, Any]:
    """
    Modify a specific parameter of a node in the workflow.

    Args:
        workflow_id: Workflow ID
        node_id: Node ID to modify
        parameter: Parameter name to change
        value: New value for the parameter

    Returns:
        Updated node object.
    """
    logger.info(f"modify_node: workflow={workflow_id}, node={node_id}, param={parameter}")

    # TODO: Integrate with ComfyUI backend
    return {
        "workflow_id": workflow_id,
        "node_id": node_id,
        "parameter": parameter,
        "old_value": None,
        "new_value": value,
        "updated": True,
    }


@mcp.tool()
def get_execution_logs(
    workflow_id: str,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Get execution logs for a workflow.

    Args:
        workflow_id: Workflow ID
        limit: Maximum number of log entries to return

    Returns:
        Log entries with timestamps and error information.
    """
    logger.info(f"get_execution_logs: workflow={workflow_id}, limit={limit}")

    # TODO: Integrate with ComfyUI backend
    return {
        "workflow_id": workflow_id,
        "logs": [],
        "error_count": 0,
        "warning_count": 0,
    }


# Export tool definitions in Anthropic format
def get_comfyui_tools() -> List[Dict[str, Any]]:
    """
    Get ComfyUI tool definitions in Anthropic Claude format.

    Returns:
        List of tool definitions
    """
    return [
        {
            "name": "get_workflow",
            "description": "Get the current ComfyUI workflow or a specific workflow by ID",
            "input_schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Optional workflow ID. If not provided, returns the current active workflow.",
                    }
                },
            },
        },
        {
            "name": "update_workflow",
            "description": "Update a ComfyUI workflow with new nodes and connections",
            "input_schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow ID to update"},
                    "nodes": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of node definitions",
                    },
                    "links": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of connection definitions",
                    },
                },
                "required": ["workflow_id", "nodes", "links"],
            },
        },
        {
            "name": "modify_node",
            "description": "Modify a specific parameter of a node in the workflow",
            "input_schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow ID"},
                    "node_id": {"type": "string", "description": "Node ID to modify"},
                    "parameter": {"type": "string", "description": "Parameter name to change"},
                    "value": {"description": "New value for the parameter"},
                },
                "required": ["workflow_id", "node_id", "parameter", "value"],
            },
        },
        {
            "name": "get_execution_logs",
            "description": "Get execution logs for a workflow",
            "input_schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow ID"},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of log entries to return",
                        "default": 100,
                    },
                },
                "required": ["workflow_id"],
            },
        },
    ]


# Tool executor for AgentEngine integration
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
    if tool_name == "get_workflow":
        return get_workflow(**arguments)
    elif tool_name == "update_workflow":
        return update_workflow(**arguments)
    elif tool_name == "modify_node":
        return modify_node(**arguments)
    elif tool_name == "get_execution_logs":
        return get_execution_logs(**arguments)
    else:
        raise ValueError(f"Unknown tool: {tool_name}")
