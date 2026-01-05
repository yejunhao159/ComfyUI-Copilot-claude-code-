"""
MCP Integration for AgentX Runtime V2

This module provides integration with MCP (Model Context Protocol) tools
for the AgentX runtime. It allows you to expose ComfyUI tools to Claude
as in-process MCP servers.

The claude-agent-sdk supports MCP servers in two modes:
1. External servers (subprocess-based)
2. SDK MCP servers (in-process, using @tool decorator)

We use SDK MCP servers for better performance and simpler deployment.

Example Usage:
    from claude_agent_sdk import tool, create_sdk_mcp_server

    @tool("get_workflow", "Get current ComfyUI workflow", {})
    async def get_workflow(args):
        workflow = await comfy_client.get_workflow()
        return {"content": [{"type": "text", "text": json.dumps(workflow)}]}

    server = create_sdk_mcp_server(
        name="comfyui",
        version="1.0.0",
        tools=[get_workflow, ...]
    )

    # Use with AgentX
    config = RuntimeConfig(
        api_key="...",
        mcp_servers={"comfyui": server},
    )
"""

import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from ...utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Tool Definition Helper
# =============================================================================


@dataclass
class ToolDefinition:
    """
    Tool definition for MCP integration.

    This is a helper class for defining tools that can be used with
    either claude-agent-sdk's @tool decorator or as raw tool definitions.
    """
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable


def create_tool_result(content: Any, is_error: bool = False) -> Dict[str, Any]:
    """
    Create a properly formatted tool result.

    Args:
        content: The result content (will be JSON-serialized if dict)
        is_error: Whether this is an error result

    Returns:
        Properly formatted tool result dict
    """
    if isinstance(content, dict):
        text = json.dumps(content, ensure_ascii=False, indent=2)
    else:
        text = str(content)

    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def create_error_result(message: str, error_code: Optional[str] = None) -> Dict[str, Any]:
    """Create an error tool result."""
    error_info = {"error": message}
    if error_code:
        error_info["code"] = error_code
    return create_tool_result(error_info, is_error=True)


# =============================================================================
# ComfyUI MCP Server Factory
# =============================================================================


def create_comfyui_mcp_server(
    comfy_client: Any,
    server_name: str = "comfyui",
    server_version: str = "1.0.0",
) -> Any:
    """
    Create an MCP server with ComfyUI tools.

    This creates an in-process MCP server using claude-agent-sdk.

    Args:
        comfy_client: ComfyUI client instance
        server_name: Name for the MCP server
        server_version: Version string

    Returns:
        MCP server instance (or None if SDK not available)

    Example:
        from backend.agentx.mcp_tools.tools.comfy_client import ComfyUIClient

        client = ComfyUIClient("localhost", 8188)
        server = create_comfyui_mcp_server(client)

        config = RuntimeConfig(
            api_key="...",
            mcp_servers={"comfyui": server},
        )
    """
    try:
        from claude_agent_sdk import tool, create_sdk_mcp_server
    except ImportError:
        logger.warning("claude-agent-sdk not installed, MCP integration disabled")
        return None

    # Define tools using @tool decorator
    @tool(
        name="get_workflow",
        description="Get the current ComfyUI workflow. Returns the complete workflow JSON.",
        input_schema={},
    )
    async def get_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        """Get current workflow."""
        try:
            workflow = await comfy_client.get_workflow()
            return create_tool_result(workflow)
        except Exception as e:
            logger.exception("Error getting workflow")
            return create_error_result(str(e))

    @tool(
        name="update_workflow",
        description="Update the ComfyUI workflow. Pass the complete workflow JSON.",
        input_schema={
            "workflow": {"type": "object", "description": "Complete workflow JSON"},
        },
    )
    async def update_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        """Update workflow."""
        try:
            workflow = args.get("workflow", {})
            await comfy_client.update_workflow(workflow)
            return create_tool_result({"success": True, "message": "Workflow updated"})
        except Exception as e:
            logger.exception("Error updating workflow")
            return create_error_result(str(e))

    @tool(
        name="search_nodes",
        description="Search for available ComfyUI nodes by query.",
        input_schema={
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results", "default": 10},
        },
    )
    async def search_nodes(args: Dict[str, Any]) -> Dict[str, Any]:
        """Search nodes."""
        try:
            query = args.get("query", "")
            limit = args.get("limit", 10)
            nodes = await comfy_client.search_nodes(query, limit)
            return create_tool_result(nodes)
        except Exception as e:
            logger.exception("Error searching nodes")
            return create_error_result(str(e))

    @tool(
        name="get_node_info",
        description="Get detailed information about a specific ComfyUI node type.",
        input_schema={
            "node_type": {"type": "string", "description": "Node type name"},
        },
    )
    async def get_node_info(args: Dict[str, Any]) -> Dict[str, Any]:
        """Get node info."""
        try:
            node_type = args.get("node_type", "")
            info = await comfy_client.get_node_info(node_type)
            return create_tool_result(info)
        except Exception as e:
            logger.exception("Error getting node info")
            return create_error_result(str(e))

    @tool(
        name="execute_workflow",
        description="Execute the current ComfyUI workflow and wait for completion.",
        input_schema={
            "wait": {"type": "boolean", "description": "Wait for completion", "default": True},
        },
    )
    async def execute_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow."""
        try:
            wait = args.get("wait", True)
            result = await comfy_client.execute_workflow(wait=wait)
            return create_tool_result(result)
        except Exception as e:
            logger.exception("Error executing workflow")
            return create_error_result(str(e))

    @tool(
        name="get_execution_status",
        description="Get the status of workflow execution.",
        input_schema={
            "prompt_id": {"type": "string", "description": "Prompt ID to check", "default": None},
        },
    )
    async def get_execution_status(args: Dict[str, Any]) -> Dict[str, Any]:
        """Get execution status."""
        try:
            prompt_id = args.get("prompt_id")
            status = await comfy_client.get_execution_status(prompt_id)
            return create_tool_result(status)
        except Exception as e:
            logger.exception("Error getting execution status")
            return create_error_result(str(e))

    @tool(
        name="add_node",
        description="Add a new node to the workflow.",
        input_schema={
            "node_type": {"type": "string", "description": "Type of node to add"},
            "position": {
                "type": "object",
                "description": "Position {x, y}",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                },
            },
            "inputs": {"type": "object", "description": "Input values", "default": {}},
        },
    )
    async def add_node(args: Dict[str, Any]) -> Dict[str, Any]:
        """Add node."""
        try:
            node_type = args.get("node_type", "")
            position = args.get("position", {"x": 0, "y": 0})
            inputs = args.get("inputs", {})
            result = await comfy_client.add_node(node_type, position, inputs)
            return create_tool_result(result)
        except Exception as e:
            logger.exception("Error adding node")
            return create_error_result(str(e))

    @tool(
        name="connect_nodes",
        description="Connect two nodes in the workflow.",
        input_schema={
            "source_node_id": {"type": "string", "description": "Source node ID"},
            "source_slot": {"type": "integer", "description": "Source output slot index"},
            "target_node_id": {"type": "string", "description": "Target node ID"},
            "target_slot": {"type": "integer", "description": "Target input slot index"},
        },
    )
    async def connect_nodes(args: Dict[str, Any]) -> Dict[str, Any]:
        """Connect nodes."""
        try:
            result = await comfy_client.connect_nodes(
                args.get("source_node_id"),
                args.get("source_slot", 0),
                args.get("target_node_id"),
                args.get("target_slot", 0),
            )
            return create_tool_result(result)
        except Exception as e:
            logger.exception("Error connecting nodes")
            return create_error_result(str(e))

    @tool(
        name="remove_node",
        description="Remove a node from the workflow.",
        input_schema={
            "node_id": {"type": "string", "description": "Node ID to remove"},
        },
    )
    async def remove_node(args: Dict[str, Any]) -> Dict[str, Any]:
        """Remove node."""
        try:
            node_id = args.get("node_id", "")
            result = await comfy_client.remove_node(node_id)
            return create_tool_result(result)
        except Exception as e:
            logger.exception("Error removing node")
            return create_error_result(str(e))

    @tool(
        name="update_node_input",
        description="Update an input value on a node.",
        input_schema={
            "node_id": {"type": "string", "description": "Node ID"},
            "input_name": {"type": "string", "description": "Input name"},
            "value": {"type": "any", "description": "New value"},
        },
    )
    async def update_node_input(args: Dict[str, Any]) -> Dict[str, Any]:
        """Update node input."""
        try:
            result = await comfy_client.update_node_input(
                args.get("node_id"),
                args.get("input_name"),
                args.get("value"),
            )
            return create_tool_result(result)
        except Exception as e:
            logger.exception("Error updating node input")
            return create_error_result(str(e))

    # Create MCP server with all tools
    server = create_sdk_mcp_server(
        name=server_name,
        version=server_version,
        tools=[
            get_workflow,
            update_workflow,
            search_nodes,
            get_node_info,
            execute_workflow,
            get_execution_status,
            add_node,
            connect_nodes,
            remove_node,
            update_node_input,
        ],
    )

    logger.info(f"Created ComfyUI MCP server: {server_name} v{server_version}")
    return server


# =============================================================================
# Legacy Tool Definitions (for non-SDK usage)
# =============================================================================


def get_comfyui_tool_definitions() -> List[Dict[str, Any]]:
    """
    Get ComfyUI tool definitions in Anthropic API format.

    Use this if you're not using claude-agent-sdk and need raw tool definitions.

    Returns:
        List of tool definitions for Anthropic API
    """
    return [
        {
            "name": "get_workflow",
            "description": "Get the current ComfyUI workflow. Returns the complete workflow JSON.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "update_workflow",
            "description": "Update the ComfyUI workflow. Pass the complete workflow JSON.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "workflow": {
                        "type": "object",
                        "description": "Complete workflow JSON",
                    },
                },
                "required": ["workflow"],
            },
        },
        {
            "name": "search_nodes",
            "description": "Search for available ComfyUI nodes by query.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_node_info",
            "description": "Get detailed information about a specific ComfyUI node type.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "node_type": {
                        "type": "string",
                        "description": "Node type name",
                    },
                },
                "required": ["node_type"],
            },
        },
        {
            "name": "execute_workflow",
            "description": "Execute the current ComfyUI workflow and wait for completion.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "wait": {
                        "type": "boolean",
                        "description": "Whether to wait for completion",
                        "default": True,
                    },
                },
                "required": [],
            },
        },
        {
            "name": "get_execution_status",
            "description": "Get the status of workflow execution.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "prompt_id": {
                        "type": "string",
                        "description": "Prompt ID to check (optional)",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "add_node",
            "description": "Add a new node to the workflow.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "node_type": {
                        "type": "string",
                        "description": "Type of node to add",
                    },
                    "position": {
                        "type": "object",
                        "description": "Position {x, y}",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                        },
                    },
                    "inputs": {
                        "type": "object",
                        "description": "Input values",
                    },
                },
                "required": ["node_type"],
            },
        },
        {
            "name": "connect_nodes",
            "description": "Connect two nodes in the workflow.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "source_node_id": {
                        "type": "string",
                        "description": "Source node ID",
                    },
                    "source_slot": {
                        "type": "integer",
                        "description": "Source output slot index",
                    },
                    "target_node_id": {
                        "type": "string",
                        "description": "Target node ID",
                    },
                    "target_slot": {
                        "type": "integer",
                        "description": "Target input slot index",
                    },
                },
                "required": ["source_node_id", "source_slot", "target_node_id", "target_slot"],
            },
        },
        {
            "name": "remove_node",
            "description": "Remove a node from the workflow.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Node ID to remove",
                    },
                },
                "required": ["node_id"],
            },
        },
        {
            "name": "update_node_input",
            "description": "Update an input value on a node.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Node ID",
                    },
                    "input_name": {
                        "type": "string",
                        "description": "Input name",
                    },
                    "value": {
                        "description": "New value",
                    },
                },
                "required": ["node_id", "input_name", "value"],
            },
        },
    ]
