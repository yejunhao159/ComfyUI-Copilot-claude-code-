"""
Workflow State Management

Manages the current workflow state for the session.
This is the central state store that other tools interact with.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class WorkflowState:
    """
    Manages workflow state for a session.

    The workflow is stored in ComfyUI API format:
    {
        "node_id": {
            "class_type": "NodeClassName",
            "inputs": {
                "param1": value,
                "param2": ["source_node_id", output_slot]  # connection
            },
            "_meta": {"title": "Display Title"}
        }
    }
    """

    _instance: Optional["WorkflowState"] = None

    def __new__(cls) -> "WorkflowState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._workflow = {}
            cls._instance._execution_results = {}
            cls._instance._next_node_id = 1
        return cls._instance

    @property
    def workflow(self) -> Dict[str, Any]:
        """Get the current workflow."""
        return self._workflow

    @workflow.setter
    def workflow(self, value: Dict[str, Any]) -> None:
        """Set the entire workflow."""
        self._workflow = value
        # Update next_node_id based on existing nodes
        if value:
            max_id = max(int(k) for k in value.keys() if k.isdigit())
            self._next_node_id = max_id + 1

    def clear(self) -> None:
        """Clear the current workflow."""
        self._workflow = {}
        self._next_node_id = 1

    def get_next_node_id(self) -> str:
        """Get the next available node ID."""
        node_id = str(self._next_node_id)
        self._next_node_id += 1
        return node_id

    def add_node(
        self,
        class_type: str,
        inputs: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> str:
        """
        Add a new node to the workflow.

        Args:
            class_type: The node class type (e.g., "KSampler")
            inputs: Input parameters and connections
            node_id: Optional specific node ID (auto-generated if not provided)
            title: Optional display title

        Returns:
            The node ID of the added node
        """
        if node_id is None:
            node_id = self.get_next_node_id()

        node_data = {
            "class_type": class_type,
            "inputs": inputs or {},
        }

        if title:
            node_data["_meta"] = {"title": title}

        self._workflow[node_id] = node_data
        logger.info(f"Added node {node_id}: {class_type}")
        return node_id

    def remove_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Remove a node and clean up connections.

        Returns the removed node data or None if not found.
        """
        if node_id not in self._workflow:
            return None

        removed = self._workflow.pop(node_id)

        # Clean up connections pointing to this node
        for other_id, node_data in self._workflow.items():
            inputs = node_data.get("inputs", {})
            for input_name, input_value in list(inputs.items()):
                if isinstance(input_value, list) and len(input_value) == 2:
                    if str(input_value[0]) == node_id:
                        del inputs[input_name]
                        logger.debug(f"Removed connection {other_id}.{input_name} -> {node_id}")

        logger.info(f"Removed node {node_id}")
        return removed

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by ID."""
        return self._workflow.get(node_id)

    def update_node_input(self, node_id: str, input_name: str, value: Any) -> bool:
        """
        Update a single input on a node.

        Returns True if successful, False if node not found.
        """
        node = self._workflow.get(node_id)
        if not node:
            return False

        if "inputs" not in node:
            node["inputs"] = {}

        node["inputs"][input_name] = value
        return True

    def connect_nodes(
        self,
        source_node_id: str,
        source_output: int,
        target_node_id: str,
        target_input: str,
    ) -> bool:
        """
        Connect two nodes.

        Args:
            source_node_id: The source node ID
            source_output: The output slot index on the source
            target_node_id: The target node ID
            target_input: The input name on the target

        Returns:
            True if successful
        """
        if source_node_id not in self._workflow:
            logger.error(f"Source node {source_node_id} not found")
            return False

        if target_node_id not in self._workflow:
            logger.error(f"Target node {target_node_id} not found")
            return False

        return self.update_node_input(
            target_node_id,
            target_input,
            [source_node_id, source_output]
        )

    def disconnect_input(self, node_id: str, input_name: str) -> bool:
        """
        Disconnect an input on a node.

        Returns True if successful.
        """
        node = self._workflow.get(node_id)
        if not node or "inputs" not in node:
            return False

        if input_name in node["inputs"]:
            del node["inputs"][input_name]
            return True
        return False

    def get_node_list(self) -> List[Dict[str, Any]]:
        """Get a list of all nodes with their IDs."""
        return [
            {
                "id": node_id,
                "class_type": data.get("class_type"),
                "title": data.get("_meta", {}).get("title"),
            }
            for node_id, data in self._workflow.items()
        ]

    def store_execution_result(self, prompt_id: str, result: Dict[str, Any]) -> None:
        """Store an execution result."""
        self._execution_results[prompt_id] = result

    def get_execution_result(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get a stored execution result."""
        return self._execution_results.get(prompt_id)


# Global state instance
state = WorkflowState()
