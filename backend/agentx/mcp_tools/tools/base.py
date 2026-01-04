"""
Base classes and registry for ComfyUI MCP Tools.

This module provides the foundation for creating modular, reusable tools.
"""

from typing import Dict, Any, List, Optional, Callable, Awaitable
from abc import ABC, abstractmethod
from ....utils.logger import get_logger

logger = get_logger(__name__)


class BaseTool(ABC):
    """Base class for all ComfyUI tools."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool's input schema in Anthropic format."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given arguments."""
        pass

    def to_claude_tool(self) -> Dict[str, Any]:
        """Convert to Claude tool definition format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.get_schema(),
        }


class ToolRegistry:
    """
    Central registry for all ComfyUI tools.

    Provides tool discovery, registration, and execution.
    """

    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, BaseTool] = {}
    _tool_functions: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {}

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._tool_functions = {}
        return cls._instance

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool
        self._tool_functions[tool.name] = tool.execute
        logger.debug("Registered tool", tool_name=tool.name)

    def register_function(
        self,
        name: str,
        description: str,
        schema: Dict[str, Any],
        func: Callable[..., Awaitable[Dict[str, Any]]],
    ) -> None:
        """Register a standalone function as a tool."""

        class FunctionTool(BaseTool):
            def __init__(self, n, d, s, f):
                self.name = n
                self.description = d
                self._schema = s
                self._func = f

            def get_schema(self) -> Dict[str, Any]:
                return self._schema

            async def execute(self, **kwargs) -> Dict[str, Any]:
                return await self._func(**kwargs)

        tool = FunctionTool(name, description, schema, func)
        self.register_tool(tool)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all tool definitions in Claude format."""
        return [tool.to_claude_tool() for tool in self._tools.values()]

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with given arguments."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        return await tool.execute(**arguments)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())


# Global registry instance
registry = ToolRegistry()
