"""
Node Manipulation Tools

Tools for adding, removing, modifying, and connecting nodes in workflows.
"""

from typing import Dict, Any, Optional, List

from .base import BaseTool, registry
from .workflow_state import state
from ....utils.logger import get_logger

logger = get_logger(__name__)


class AddNodeTool(BaseTool):
    """Add a new node to the workflow."""

    name = "add_node"
    description = "Add a new node to the workflow. Returns the node ID for connecting to other nodes."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "class_type": {
                    "type": "string",
                    "description": "Node class type (e.g., 'KSampler', 'CheckpointLoaderSimple')",
                },
                "inputs": {
                    "type": "object",
                    "description": "Input parameters. Use [node_id, output_slot] for connections.",
                },
                "node_id": {
                    "type": "string",
                    "description": "Optional specific node ID. Auto-generated if not provided.",
                },
                "title": {
                    "type": "string",
                    "description": "Optional display title for the node.",
                },
            },
            "required": ["class_type"],
        }

    async def execute(
        self,
        class_type: str,
        inputs: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info("add_node", class_type=class_type, node_id=node_id)

        new_id = state.add_node(
            class_type=class_type,
            inputs=inputs,
            node_id=node_id,
            title=title,
        )

        return {
            "success": True,
            "node_id": new_id,
            "class_type": class_type,
            "message": f"Added node {new_id} ({class_type})",
        }


class RemoveNodeTool(BaseTool):
    """Remove a node from the workflow."""

    name = "remove_node"
    description = "Remove a node from the workflow. Connections to this node will be cleaned up."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {
                    "type": "string",
                    "description": "The node ID to remove.",
                },
            },
            "required": ["node_id"],
        }

    async def execute(self, node_id: str) -> Dict[str, Any]:
        logger.info("remove_node", node_id=node_id)

        removed = state.remove_node(node_id)
        if removed:
            return {
                "success": True,
                "node_id": node_id,
                "removed_node": removed,
                "message": f"Removed node {node_id}",
            }
        else:
            return {
                "success": False,
                "error": f"Node {node_id} not found",
            }


class ModifyNodeTool(BaseTool):
    """Modify a node's input parameter."""

    name = "modify_node"
    description = "Modify a specific input parameter on a node."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {
                    "type": "string",
                    "description": "The node ID to modify.",
                },
                "input_name": {
                    "type": "string",
                    "description": "The input/parameter name to change.",
                },
                "value": {
                    "description": "The new value. Use [source_node_id, output_slot] for connections.",
                },
            },
            "required": ["node_id", "input_name", "value"],
        }

    async def execute(
        self,
        node_id: str,
        input_name: str,
        value: Any,
    ) -> Dict[str, Any]:
        logger.info("modify_node", node_id=node_id, input_name=input_name, value=value)

        node = state.get_node(node_id)
        if not node:
            return {"success": False, "error": f"Node {node_id} not found"}

        old_value = node.get("inputs", {}).get(input_name)
        success = state.update_node_input(node_id, input_name, value)

        return {
            "success": success,
            "node_id": node_id,
            "input_name": input_name,
            "old_value": old_value,
            "new_value": value,
        }


class ConnectNodesTool(BaseTool):
    """Connect two nodes together."""

    name = "connect_nodes"
    description = "Connect an output of one node to an input of another node."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_node_id": {
                    "type": "string",
                    "description": "The source node ID.",
                },
                "source_output": {
                    "type": "integer",
                    "description": "The output slot index on the source node (0-based).",
                },
                "target_node_id": {
                    "type": "string",
                    "description": "The target node ID.",
                },
                "target_input": {
                    "type": "string",
                    "description": "The input name on the target node.",
                },
            },
            "required": ["source_node_id", "source_output", "target_node_id", "target_input"],
        }

    async def execute(
        self,
        source_node_id: str,
        source_output: int,
        target_node_id: str,
        target_input: str,
    ) -> Dict[str, Any]:
        logger.info("connect_nodes", source_node_id=source_node_id, source_output=source_output, target_node_id=target_node_id, target_input=target_input)

        success = state.connect_nodes(
            source_node_id=source_node_id,
            source_output=source_output,
            target_node_id=target_node_id,
            target_input=target_input,
        )

        if success:
            return {
                "success": True,
                "connection": {
                    "source": f"{source_node_id}[{source_output}]",
                    "target": f"{target_node_id}.{target_input}",
                },
                "message": f"Connected {source_node_id} -> {target_node_id}",
            }
        else:
            return {
                "success": False,
                "error": "Failed to connect nodes. Check that both nodes exist.",
            }


class DisconnectInputTool(BaseTool):
    """Disconnect an input on a node."""

    name = "disconnect_input"
    description = "Disconnect a specific input on a node."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {
                    "type": "string",
                    "description": "The node ID.",
                },
                "input_name": {
                    "type": "string",
                    "description": "The input name to disconnect.",
                },
            },
            "required": ["node_id", "input_name"],
        }

    async def execute(self, node_id: str, input_name: str) -> Dict[str, Any]:
        logger.info("disconnect_input", node_id=node_id, input_name=input_name)

        success = state.disconnect_input(node_id, input_name)
        return {
            "success": success,
            "node_id": node_id,
            "input_name": input_name,
            "message": f"Disconnected {node_id}.{input_name}" if success else "Input not found",
        }


class NodeTools:
    """Container for node manipulation tools."""

    @staticmethod
    def register_all():
        """Register all node tools."""
        registry.register_tool(AddNodeTool())
        registry.register_tool(RemoveNodeTool())
        registry.register_tool(ModifyNodeTool())
        registry.register_tool(ConnectNodesTool())
        registry.register_tool(DisconnectInputTool())
