"""
Node Search Tools

Tools for searching and discovering ComfyUI nodes.
"""

import copy
from typing import Dict, Any, List

from .base import BaseTool, registry
from .comfy_client import get_client
from ....utils.logger import get_logger

logger = get_logger(__name__)


class SearchNodesTool(BaseTool):
    """Search for nodes by keywords."""

    name = "search_nodes"
    description = "Search for available ComfyUI nodes by keywords. Use this to find the right node for a task."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords to search for (e.g., ['image', 'resize'])",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default: 10)",
                    "default": 10,
                },
            },
            "required": ["keywords"],
        }

    async def execute(self, keywords: List[str], limit: int = 10) -> Dict[str, Any]:
        logger.info("search_nodes", keywords=keywords, limit=limit)

        client = get_client()
        object_info = await client.get_object_info()

        if not object_info:
            return {"error": "ComfyUI not available", "results": []}

        results = []
        keywords_lower = [kw.lower() for kw in keywords if kw]

        for class_name, node_data in object_info.items():
            score = 0
            class_lower = class_name.lower()

            name = str(node_data.get("name", ""))
            display_name = str(node_data.get("display_name", ""))
            category = str(node_data.get("category", ""))
            description = str(node_data.get("description", ""))

            searchable = f"{class_lower} {name.lower()} {display_name.lower()} {category.lower()} {description.lower()}"

            for kw in keywords_lower:
                if kw in searchable:
                    score += searchable.count(kw)
                    if kw in class_lower:
                        score += 2

            if score > 0:
                results.append({
                    "class_name": class_name,
                    "display_name": display_name or name,
                    "category": category,
                    "score": score,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:limit]

        return {
            "keywords": keywords,
            "count": len(results),
            "results": results,
        }


class GetNodeInfoTool(BaseTool):
    """Get detailed information about specific node types."""

    name = "get_node_info"
    description = "Get detailed information about node types including inputs, outputs, and parameters."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_classes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of node class names to get info for.",
                },
            },
            "required": ["node_classes"],
        }

    async def execute(self, node_classes: List[str]) -> Dict[str, Any]:
        logger.info("get_node_info", node_classes=node_classes)

        client = get_client()
        object_info = await client.get_object_info()

        if not object_info:
            return {"error": "ComfyUI not available", "nodes": {}}

        nodes = {}
        not_found = []

        for class_name in node_classes:
            if class_name in object_info:
                node_data = copy.deepcopy(object_info[class_name])

                # Truncate long option lists to save tokens
                input_data = node_data.get("input", {})
                for section in ["required", "optional"]:
                    params = input_data.get(section, {})
                    if isinstance(params, dict):
                        for param_name, param_config in params.items():
                            if isinstance(param_config, list) and len(param_config) > 0:
                                if isinstance(param_config[0], list) and len(param_config[0]) > 5:
                                    param_config[0] = param_config[0][:5] + ["..."]

                nodes[class_name] = node_data
            else:
                not_found.append(class_name)

        return {
            "nodes": nodes,
            "found": list(nodes.keys()),
            "not_found": not_found,
        }


class ListNodeCategoriesTool(BaseTool):
    """List all available node categories."""

    name = "list_node_categories"
    description = "List all available node categories to help discover what types of nodes exist."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> Dict[str, Any]:
        logger.info("list_node_categories called")

        client = get_client()
        object_info = await client.get_object_info()

        if not object_info:
            return {"error": "ComfyUI not available", "categories": []}

        categories = {}
        for class_name, node_data in object_info.items():
            category = node_data.get("category", "uncategorized")
            if category not in categories:
                categories[category] = []
            categories[category].append(class_name)

        # Sort and format
        result = []
        for cat in sorted(categories.keys()):
            result.append({
                "category": cat,
                "node_count": len(categories[cat]),
                "examples": categories[cat][:3],  # Just show 3 examples
            })

        return {
            "category_count": len(result),
            "categories": result,
        }


class SearchTools:
    """Container for search tools."""

    @staticmethod
    def register_all():
        """Register all search tools."""
        registry.register_tool(SearchNodesTool())
        registry.register_tool(GetNodeInfoTool())
        registry.register_tool(ListNodeCategoriesTool())
