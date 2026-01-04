"""
Workflow Template Tools

Tools for saving, loading, and managing workflow templates.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from .base import BaseTool, registry
from .workflow_state import state
from ....utils.logger import get_logger

logger = get_logger(__name__)

# Template storage directory
_template_dir: Optional[str] = None


def get_template_dir() -> str:
    """Get the template storage directory."""
    global _template_dir
    if _template_dir is None:
        # Default to a templates folder in the plugin directory
        plugin_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        _template_dir = os.path.join(plugin_dir, "templates")
    os.makedirs(_template_dir, exist_ok=True)
    return _template_dir


class SaveWorkflowTemplateTool(BaseTool):
    """Save current workflow as a reusable template."""

    name = "save_workflow_template"
    description = """Save the current workflow as a reusable template.
    Templates can be loaded later to quickly recreate workflows.
    Add a name, description, and tags for easy discovery."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Template name (e.g., 'text-to-image-basic').",
                },
                "description": {
                    "type": "string",
                    "description": "Description of what this template does.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization (e.g., ['text2img', 'basic']).",
                },
                "workflow": {
                    "type": "object",
                    "description": "Optional workflow to save. Uses current workflow if not provided.",
                },
            },
            "required": ["name"],
        }

    async def execute(
        self,
        name: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        workflow: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info("save_workflow_template called", name=name)

        workflow_to_save = workflow or state.workflow
        if not workflow_to_save:
            return {
                "success": False,
                "error": "No workflow to save. Create a workflow first.",
            }

        # Sanitize name for filename
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        template_path = os.path.join(get_template_dir(), f"{safe_name}.json")

        template_data = {
            "name": name,
            "description": description,
            "tags": tags or [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "node_count": len(workflow_to_save),
            "workflow": workflow_to_save,
        }

        try:
            with open(template_path, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)

            return {
                "success": True,
                "name": name,
                "filename": f"{safe_name}.json",
                "path": template_path,
                "node_count": len(workflow_to_save),
                "message": f"Template '{name}' saved successfully.",
            }
        except Exception as e:
            logger.exception("Failed to save template", name=name)
            return {
                "success": False,
                "error": f"Failed to save template: {str(e)}",
            }


class LoadWorkflowTemplateTool(BaseTool):
    """Load a saved workflow template."""

    name = "load_workflow_template"
    description = """Load a saved workflow template into the current workspace.
    Use list_workflow_templates to see available templates."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Template name to load.",
                },
            },
            "required": ["name"],
        }

    async def execute(self, name: str) -> Dict[str, Any]:
        logger.info("load_workflow_template called", name=name)

        # Try exact match first
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        template_path = os.path.join(get_template_dir(), f"{safe_name}.json")

        if not os.path.exists(template_path):
            # Try finding by searching
            template_dir = get_template_dir()
            found = None
            for f in os.listdir(template_dir):
                if f.endswith(".json"):
                    try:
                        with open(os.path.join(template_dir, f), "r", encoding="utf-8") as fp:
                            data = json.load(fp)
                            if data.get("name", "").lower() == name.lower():
                                found = os.path.join(template_dir, f)
                                break
                    except Exception:
                        continue

            if found:
                template_path = found
            else:
                return {
                    "success": False,
                    "error": f"Template '{name}' not found.",
                }

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_data = json.load(f)

            workflow = template_data.get("workflow", {})
            state.workflow = workflow

            return {
                "success": True,
                "name": template_data.get("name"),
                "description": template_data.get("description"),
                "node_count": len(workflow),
                "tags": template_data.get("tags", []),
                "message": f"Template '{name}' loaded successfully.",
                "nodes": state.get_node_list(),
            }
        except Exception as e:
            logger.exception("Failed to load template", name=name)
            return {
                "success": False,
                "error": f"Failed to load template: {str(e)}",
            }


class ListWorkflowTemplatesTool(BaseTool):
    """List all saved workflow templates."""

    name = "list_workflow_templates"
    description = """List all saved workflow templates.
    Shows template names, descriptions, tags, and node counts."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tag": {
                    "type": "string",
                    "description": "Optional tag to filter by.",
                },
            },
        }

    async def execute(self, tag: Optional[str] = None) -> Dict[str, Any]:
        logger.info("list_workflow_templates called", tag=tag)

        template_dir = get_template_dir()
        templates = []

        for f in os.listdir(template_dir):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(template_dir, f), "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                        template_info = {
                            "name": data.get("name"),
                            "description": data.get("description", ""),
                            "tags": data.get("tags", []),
                            "node_count": data.get("node_count", 0),
                            "created_at": data.get("created_at"),
                            "filename": f,
                        }

                        # Filter by tag if specified
                        if tag:
                            if tag.lower() in [t.lower() for t in template_info["tags"]]:
                                templates.append(template_info)
                        else:
                            templates.append(template_info)
                except Exception as e:
                    logger.warning("Could not read template file", filename=f, error=str(e))

        # Sort by created_at descending
        templates.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return {
            "template_count": len(templates),
            "templates": templates,
            "template_directory": template_dir,
        }


class DeleteWorkflowTemplateTool(BaseTool):
    """Delete a saved workflow template."""

    name = "delete_workflow_template"
    description = "Delete a saved workflow template."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Template name to delete.",
                },
            },
            "required": ["name"],
        }

    async def execute(self, name: str) -> Dict[str, Any]:
        logger.info("delete_workflow_template called", name=name)

        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        template_path = os.path.join(get_template_dir(), f"{safe_name}.json")

        if not os.path.exists(template_path):
            return {
                "success": False,
                "error": f"Template '{name}' not found.",
            }

        try:
            os.remove(template_path)
            return {
                "success": True,
                "name": name,
                "message": f"Template '{name}' deleted successfully.",
            }
        except Exception as e:
            logger.exception("Failed to delete template", name=name)
            return {
                "success": False,
                "error": f"Failed to delete template: {str(e)}",
            }


class TemplateTools:
    """Container for template management tools."""

    @staticmethod
    def register_all():
        """Register all template tools."""
        registry.register_tool(SaveWorkflowTemplateTool())
        registry.register_tool(LoadWorkflowTemplateTool())
        registry.register_tool(ListWorkflowTemplatesTool())
        registry.register_tool(DeleteWorkflowTemplateTool())
