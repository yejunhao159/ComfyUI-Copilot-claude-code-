"""
Workflow Management Tools

Tools for getting, updating, and managing entire workflows.
"""

from typing import Dict, Any, Optional

from .base import BaseTool, registry
from .workflow_state import state
from ....utils.logger import get_logger

logger = get_logger(__name__)


class GetWorkflowTool(BaseTool):
    """Get the current workflow."""

    name = "get_workflow"
    description = "Get the current ComfyUI workflow data. Use this to see what nodes and connections exist."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Optional workflow ID. Returns current workflow if not provided.",
                }
            },
        }

    async def execute(self, workflow_id: Optional[str] = None) -> Dict[str, Any]:
        logger.info("get_workflow called", workflow_id=workflow_id)

        workflow = state.workflow
        if workflow:
            return {
                "workflow_id": workflow_id or "current",
                "workflow": workflow,
                "node_count": len(workflow),
                "nodes": state.get_node_list(),
            }

        return {
            "workflow_id": workflow_id or "current",
            "workflow": {},
            "node_count": 0,
            "message": "No workflow loaded. Use update_workflow or add_node to create one.",
        }


class UpdateWorkflowTool(BaseTool):
    """Update/replace the entire workflow."""

    name = "update_workflow"
    description = "Update or replace the entire ComfyUI workflow. The workflow will be loaded into the canvas."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow_data": {
                    "type": "object",
                    "description": "Complete workflow in ComfyUI API format.",
                },
            },
            "required": ["workflow_data"],
        }

    async def execute(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("update_workflow called", node_count=len(workflow_data))

        state.workflow = workflow_data

        return {
            "success": True,
            "workflow_id": "current",
            "node_count": len(workflow_data),
            "nodes": state.get_node_list(),
            "message": "Workflow updated successfully. It will be loaded into the canvas.",
        }


class ClearWorkflowTool(BaseTool):
    """Clear the current workflow."""

    name = "clear_workflow"
    description = "Clear the current workflow, removing all nodes."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> Dict[str, Any]:
        logger.info("clear_workflow called")

        old_count = len(state.workflow)
        state.clear()

        return {
            "success": True,
            "removed_nodes": old_count,
            "message": "Workflow cleared.",
        }


class WorkflowTools:
    """Container for workflow management tools."""

    @staticmethod
    def register_all():
        """Register all workflow tools."""
        registry.register_tool(GetWorkflowTool())
        registry.register_tool(UpdateWorkflowTool())
        registry.register_tool(ClearWorkflowTool())
