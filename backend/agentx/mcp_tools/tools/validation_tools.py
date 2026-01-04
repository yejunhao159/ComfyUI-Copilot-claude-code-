"""
Workflow Validation and Analysis Tools

Tools for validating workflow integrity and providing optimization suggestions.
"""

from typing import Dict, Any, List, Set, Optional
from .base import BaseTool, registry
from .workflow_state import state
from .comfy_client import get_client
from ....utils.logger import get_logger

logger = get_logger(__name__)


class ValidateWorkflowTool(BaseTool):
    """Validate workflow integrity and correctness."""

    name = "validate_workflow"
    description = """Validate the current workflow for errors and issues.
    Checks for: missing connections, invalid node types, disconnected nodes,
    circular dependencies, and missing required inputs."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow": {
                    "type": "object",
                    "description": "Optional workflow to validate. Uses current workflow if not provided.",
                },
            },
        }

    async def execute(self, workflow: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info("validate_workflow called")

        workflow_to_check = workflow or state.workflow
        if not workflow_to_check:
            return {
                "valid": False,
                "errors": ["No workflow to validate. Create a workflow first."],
                "warnings": [],
            }

        errors = []
        warnings = []

        # Get node definitions from ComfyUI
        client = get_client()
        object_info = await client.get_object_info()

        # Check each node
        for node_id, node_data in workflow_to_check.items():
            class_type = node_data.get("class_type")
            inputs = node_data.get("inputs", {})

            # Check if node type exists
            if class_type not in object_info:
                errors.append(f"Node {node_id}: Unknown node type '{class_type}'")
                continue

            node_def = object_info[class_type]
            required_inputs = node_def.get("input", {}).get("required", {})

            # Check required inputs
            for input_name, input_spec in required_inputs.items():
                if input_name not in inputs:
                    errors.append(f"Node {node_id} ({class_type}): Missing required input '{input_name}'")
                else:
                    input_value = inputs[input_name]
                    # Check if it's a connection reference
                    if isinstance(input_value, list) and len(input_value) == 2:
                        source_node_id = str(input_value[0])
                        if source_node_id not in workflow_to_check:
                            errors.append(
                                f"Node {node_id} ({class_type}): Input '{input_name}' references "
                                f"non-existent node '{source_node_id}'"
                            )

        # Check for disconnected nodes (no outputs used)
        used_nodes: Set[str] = set()
        for node_id, node_data in workflow_to_check.items():
            inputs = node_data.get("inputs", {})
            for input_value in inputs.values():
                if isinstance(input_value, list) and len(input_value) == 2:
                    used_nodes.add(str(input_value[0]))

        # Find terminal nodes (output nodes like SaveImage, PreviewImage)
        terminal_classes = {"SaveImage", "PreviewImage", "VHS_VideoCombine", "SaveAnimatedWEBP"}
        terminal_nodes = set()
        for node_id, node_data in workflow_to_check.items():
            if node_data.get("class_type") in terminal_classes:
                terminal_nodes.add(node_id)

        # Nodes that are neither used by others nor terminal
        for node_id in workflow_to_check.keys():
            if node_id not in used_nodes and node_id not in terminal_nodes:
                warnings.append(f"Node {node_id}: Output not used by any other node")

        # Check for circular dependencies
        def has_cycle(start_node: str, visited: Set[str], path: Set[str]) -> bool:
            if start_node in path:
                return True
            if start_node in visited:
                return False

            visited.add(start_node)
            path.add(start_node)

            node_data = workflow_to_check.get(start_node, {})
            inputs = node_data.get("inputs", {})

            for input_value in inputs.values():
                if isinstance(input_value, list) and len(input_value) == 2:
                    source_node = str(input_value[0])
                    if has_cycle(source_node, visited, path):
                        return True

            path.remove(start_node)
            return False

        visited: Set[str] = set()
        for node_id in workflow_to_check.keys():
            if has_cycle(node_id, visited, set()):
                errors.append(f"Circular dependency detected involving node {node_id}")
                break

        return {
            "valid": len(errors) == 0,
            "node_count": len(workflow_to_check),
            "errors": errors,
            "warnings": warnings,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }


class AnalyzeWorkflowTool(BaseTool):
    """Analyze workflow and provide optimization suggestions."""

    name = "analyze_workflow"
    description = """Analyze the current workflow structure and provide insights.
    Returns: node statistics, connection graph, bottlenecks, and optimization suggestions."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow": {
                    "type": "object",
                    "description": "Optional workflow to analyze. Uses current workflow if not provided.",
                },
            },
        }

    async def execute(self, workflow: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info("analyze_workflow called")

        workflow_to_analyze = workflow or state.workflow
        if not workflow_to_analyze:
            return {"error": "No workflow to analyze. Create a workflow first."}

        # Node type statistics
        type_counts: Dict[str, int] = {}
        category_counts: Dict[str, int] = {}

        # Get node definitions
        client = get_client()
        object_info = await client.get_object_info()

        for node_id, node_data in workflow_to_analyze.items():
            class_type = node_data.get("class_type", "unknown")
            type_counts[class_type] = type_counts.get(class_type, 0) + 1

            if class_type in object_info:
                category = object_info[class_type].get("category", "unknown")
                category_counts[category] = category_counts.get(category, 0) + 1

        # Connection analysis
        connections: List[Dict[str, str]] = []
        connection_counts: Dict[str, int] = {}  # node_id -> output connection count

        for node_id, node_data in workflow_to_analyze.items():
            inputs = node_data.get("inputs", {})
            for input_name, input_value in inputs.items():
                if isinstance(input_value, list) and len(input_value) == 2:
                    source_node_id = str(input_value[0])
                    connections.append({
                        "from": source_node_id,
                        "to": node_id,
                        "input": input_name,
                    })
                    connection_counts[source_node_id] = connection_counts.get(source_node_id, 0) + 1

        # Find bottlenecks (nodes with many outputs)
        bottlenecks = [
            {"node_id": node_id, "output_count": count}
            for node_id, count in connection_counts.items()
            if count > 2
        ]
        bottlenecks.sort(key=lambda x: x["output_count"], reverse=True)

        # Optimization suggestions
        suggestions: List[str] = []

        # Check for duplicate loaders
        loader_types = ["CheckpointLoaderSimple", "CheckpointLoader", "VAELoader", "LoraLoader"]
        for loader_type in loader_types:
            if type_counts.get(loader_type, 0) > 1:
                suggestions.append(
                    f"Multiple {loader_type} nodes detected. Consider reusing a single loader."
                )

        # Check for missing VAE
        if "VAEDecode" in type_counts and "VAELoader" not in type_counts:
            has_vae_from_checkpoint = any(
                node.get("class_type") == "CheckpointLoaderSimple"
                for node in workflow_to_analyze.values()
            )
            if has_vae_from_checkpoint:
                suggestions.append(
                    "Using VAE from checkpoint. Consider a dedicated VAE for better quality."
                )

        # Check for high step counts
        for node_id, node_data in workflow_to_analyze.items():
            if node_data.get("class_type") == "KSampler":
                steps = node_data.get("inputs", {}).get("steps", 20)
                if isinstance(steps, int) and steps > 50:
                    suggestions.append(
                        f"Node {node_id}: High step count ({steps}). "
                        "Consider reducing for faster generation."
                    )

        return {
            "node_count": len(workflow_to_analyze),
            "connection_count": len(connections),
            "node_types": type_counts,
            "categories": category_counts,
            "bottlenecks": bottlenecks[:5],  # Top 5
            "suggestions": suggestions,
            "complexity_score": len(workflow_to_analyze) + len(connections),
        }


class ValidationTools:
    """Container for validation and analysis tools."""

    @staticmethod
    def register_all():
        """Register all validation tools."""
        registry.register_tool(ValidateWorkflowTool())
        registry.register_tool(AnalyzeWorkflowTool())
