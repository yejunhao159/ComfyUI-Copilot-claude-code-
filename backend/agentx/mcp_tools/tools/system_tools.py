"""
System Information Tools

Tools for getting system status, available models, and ComfyUI configuration.
"""

import os
from typing import Dict, Any, List, Optional
from .base import BaseTool, registry
from .comfy_client import get_client
from ....utils.logger import get_logger

logger = get_logger(__name__)


class ListModelsTool(BaseTool):
    """List available models in ComfyUI."""

    name = "list_models"
    description = """List available models in ComfyUI.
    Returns checkpoints, VAEs, LoRAs, and other models by category.
    Use this to help users choose the right model for their workflow."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "model_type": {
                    "type": "string",
                    "enum": ["checkpoints", "vae", "loras", "controlnet", "embeddings", "all"],
                    "description": "Type of models to list (default: 'all').",
                    "default": "all",
                },
                "search": {
                    "type": "string",
                    "description": "Optional search filter for model names.",
                },
            },
        }

    async def execute(
        self,
        model_type: str = "all",
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info("list_models called", model_type=model_type, search=search)

        try:
            import folder_paths
        except ImportError:
            return {
                "success": False,
                "error": "Cannot access ComfyUI folder_paths module",
            }

        result: Dict[str, List[str]] = {}

        # Model folder mappings
        model_folders = {
            "checkpoints": "checkpoints",
            "vae": "vae",
            "loras": "loras",
            "controlnet": "controlnet",
            "embeddings": "embeddings",
        }

        folders_to_check = (
            list(model_folders.keys()) if model_type == "all" else [model_type]
        )

        for folder_type in folders_to_check:
            if folder_type not in model_folders:
                continue

            try:
                folder_name = model_folders[folder_type]
                model_list = folder_paths.get_filename_list(folder_name)

                # Apply search filter
                if search:
                    search_lower = search.lower()
                    model_list = [m for m in model_list if search_lower in m.lower()]

                result[folder_type] = sorted(model_list)
            except Exception as e:
                logger.warning(f"Could not list {folder_type} models", error=str(e))
                result[folder_type] = []

        total_count = sum(len(models) for models in result.values())

        return {
            "success": True,
            "model_type": model_type,
            "search": search,
            "total_count": total_count,
            "models": result,
        }


class GetSystemStatsTool(BaseTool):
    """Get ComfyUI system status and statistics."""

    name = "get_system_stats"
    description = """Get ComfyUI system status including:
    - Queue status (pending/running jobs)
    - GPU/VRAM usage
    - Available node count
    - System health"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> Dict[str, Any]:
        logger.info("get_system_stats called")

        import aiohttp

        client = get_client()
        result: Dict[str, Any] = {
            "comfyui_url": client.base_url,
        }

        # Get queue status
        try:
            queue = await client.get_queue_status()
            result["queue"] = {
                "running": len(queue.get("queue_running", [])),
                "pending": len(queue.get("queue_pending", [])),
            }
        except Exception as e:
            result["queue"] = {"error": str(e)}

        # Get system stats from ComfyUI
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{client.base_url}/api/system_stats") as resp:
                    if resp.status == 200:
                        stats = await resp.json()
                        result["system"] = stats
                    else:
                        result["system"] = {"error": f"HTTP {resp.status}"}
        except Exception as e:
            result["system"] = {"error": str(e)}

        # Get available node count
        try:
            object_info = await client.get_object_info()
            result["available_nodes"] = len(object_info)
        except Exception as e:
            result["available_nodes"] = {"error": str(e)}

        # Health check
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{client.base_url}/api/prompt", timeout=5) as resp:
                    result["health"] = "healthy" if resp.status in [200, 400] else "unhealthy"
        except Exception:
            result["health"] = "unreachable"

        return result


class GetComfyUIInfoTool(BaseTool):
    """Get ComfyUI version and configuration information."""

    name = "get_comfyui_info"
    description = """Get ComfyUI version and configuration.
    Shows installed extensions, custom nodes, and system paths."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> Dict[str, Any]:
        logger.info("get_comfyui_info called")

        result: Dict[str, Any] = {}

        try:
            import folder_paths

            result["paths"] = {
                "output": folder_paths.get_output_directory(),
                "input": folder_paths.get_input_directory(),
                "temp": folder_paths.get_temp_directory(),
            }
        except ImportError:
            result["paths"] = {"error": "folder_paths not available"}

        # Get custom nodes
        try:
            import folder_paths
            custom_nodes_path = os.path.join(os.path.dirname(folder_paths.__file__), "custom_nodes")
            if os.path.exists(custom_nodes_path):
                custom_nodes = [
                    d for d in os.listdir(custom_nodes_path)
                    if os.path.isdir(os.path.join(custom_nodes_path, d))
                    and not d.startswith(".")
                ]
                result["custom_nodes"] = sorted(custom_nodes)
                result["custom_node_count"] = len(custom_nodes)
        except Exception as e:
            result["custom_nodes"] = {"error": str(e)}

        # Get node categories
        client = get_client()
        try:
            object_info = await client.get_object_info()
            categories = set()
            for node_data in object_info.values():
                cat = node_data.get("category", "")
                if cat:
                    # Get top-level category
                    top_cat = cat.split("/")[0]
                    categories.add(top_cat)
            result["node_categories"] = sorted(categories)
            result["total_nodes"] = len(object_info)
        except Exception as e:
            result["node_info"] = {"error": str(e)}

        return result


class ClearQueueTool(BaseTool):
    """Clear the ComfyUI execution queue."""

    name = "clear_queue"
    description = "Clear all pending jobs from the ComfyUI execution queue."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> Dict[str, Any]:
        logger.info("clear_queue called")

        import aiohttp

        client = get_client()

        try:
            async with aiohttp.ClientSession() as session:
                # Clear pending queue
                async with session.post(
                    f"{client.base_url}/api/queue",
                    json={"clear": True}
                ) as resp:
                    if resp.status == 200:
                        return {
                            "success": True,
                            "message": "Queue cleared successfully",
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {resp.status}",
                        }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class SystemTools:
    """Container for system tools."""

    @staticmethod
    def register_all():
        """Register all system tools."""
        registry.register_tool(ListModelsTool())
        registry.register_tool(GetSystemStatsTool())
        registry.register_tool(GetComfyUIInfoTool())
        registry.register_tool(ClearQueueTool())
