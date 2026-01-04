"""
Image and Execution Result Tools

Tools for getting generated images and execution outputs.
"""

import os
import base64
from typing import Dict, Any, List, Optional
from .base import BaseTool, registry
from .workflow_state import state
from .comfy_client import get_client
from ....utils.logger import get_logger

logger = get_logger(__name__)


class GetExecutionImagesTool(BaseTool):
    """Get images generated from a workflow execution."""

    name = "get_execution_images"
    description = """Get images generated from a workflow execution.
    Returns image paths and optionally base64-encoded image data.
    Use this after execute_workflow to see the results."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt_id": {
                    "type": "string",
                    "description": "The prompt ID from execute_workflow.",
                },
                "include_base64": {
                    "type": "boolean",
                    "description": "Whether to include base64-encoded image data (default: false).",
                    "default": False,
                },
                "max_images": {
                    "type": "integer",
                    "description": "Maximum number of images to return (default: 10).",
                    "default": 10,
                },
            },
            "required": ["prompt_id"],
        }

    async def execute(
        self,
        prompt_id: str,
        include_base64: bool = False,
        max_images: int = 10,
    ) -> Dict[str, Any]:
        logger.info("get_execution_images called", prompt_id=prompt_id)

        client = get_client()
        history = await client.get_history(prompt_id)

        if prompt_id not in history:
            return {
                "success": False,
                "error": "Execution not found. It may still be running or not exist.",
                "prompt_id": prompt_id,
            }

        prompt_history = history[prompt_id]
        outputs = prompt_history.get("outputs", {})

        images: List[Dict[str, Any]] = []
        total_found = 0

        for node_id, node_outputs in outputs.items():
            node_images = node_outputs.get("images", [])
            for img_info in node_images:
                if total_found >= max_images:
                    break

                filename = img_info.get("filename")
                subfolder = img_info.get("subfolder", "")
                img_type = img_info.get("type", "output")

                image_data: Dict[str, Any] = {
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": img_type,
                    "node_id": node_id,
                    "url": f"/api/view?filename={filename}&subfolder={subfolder}&type={img_type}",
                }

                # Optionally include base64
                if include_base64 and filename:
                    # Try to read the image file
                    try:
                        import folder_paths
                        if img_type == "output":
                            img_path = os.path.join(folder_paths.get_output_directory(), subfolder, filename)
                        elif img_type == "temp":
                            img_path = os.path.join(folder_paths.get_temp_directory(), subfolder, filename)
                        else:
                            img_path = None

                        if img_path and os.path.exists(img_path):
                            with open(img_path, "rb") as f:
                                image_data["base64"] = base64.b64encode(f.read()).decode("utf-8")
                    except Exception as e:
                        logger.warning("Could not read image file", filename=filename, error=str(e))

                images.append(image_data)
                total_found += 1

        return {
            "success": True,
            "prompt_id": prompt_id,
            "image_count": len(images),
            "images": images,
            "status": prompt_history.get("status", {}),
        }


class GetLatestImagesTool(BaseTool):
    """Get the latest generated images from ComfyUI output directory."""

    name = "get_latest_images"
    description = """Get the most recent images from ComfyUI output directory.
    Useful for checking what was generated without knowing the prompt ID."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of images to return (default: 5).",
                    "default": 5,
                },
                "include_base64": {
                    "type": "boolean",
                    "description": "Whether to include base64-encoded image data (default: false).",
                    "default": False,
                },
            },
        }

    async def execute(
        self,
        limit: int = 5,
        include_base64: bool = False,
    ) -> Dict[str, Any]:
        logger.info("get_latest_images called", limit=limit)

        try:
            import folder_paths
            output_dir = folder_paths.get_output_directory()
        except ImportError:
            return {
                "success": False,
                "error": "Cannot access ComfyUI output directory",
            }

        if not os.path.exists(output_dir):
            return {
                "success": False,
                "error": f"Output directory not found: {output_dir}",
            }

        # Get image files sorted by modification time
        image_files = []
        for f in os.listdir(output_dir):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                filepath = os.path.join(output_dir, f)
                mtime = os.path.getmtime(filepath)
                image_files.append((f, mtime, filepath))

        image_files.sort(key=lambda x: x[1], reverse=True)
        image_files = image_files[:limit]

        images = []
        for filename, mtime, filepath in image_files:
            from datetime import datetime
            image_data: Dict[str, Any] = {
                "filename": filename,
                "url": f"/api/view?filename={filename}&type=output",
                "modified": datetime.fromtimestamp(mtime).isoformat(),
            }

            if include_base64:
                try:
                    with open(filepath, "rb") as f:
                        image_data["base64"] = base64.b64encode(f.read()).decode("utf-8")
                except Exception as e:
                    logger.warning("Could not read image", filename=filename, error=str(e))

            images.append(image_data)

        return {
            "success": True,
            "image_count": len(images),
            "images": images,
            "output_directory": output_dir,
        }


class ImageTools:
    """Container for image tools."""

    @staticmethod
    def register_all():
        """Register all image tools."""
        registry.register_tool(GetExecutionImagesTool())
        registry.register_tool(GetLatestImagesTool())
