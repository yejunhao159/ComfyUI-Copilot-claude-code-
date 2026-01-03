# Python MCP Implementation Guide for ComfyUI-Copilot

**Quick Reference for Developers**
**Date**: January 2, 2026

---

## Quick Start: Adding MCP Support to ComfyUI-Copilot

### Step 1: Enable Tool Caching for Existing SSE Servers

**File**: `/home/yejh0725/ComfyUI-Copilot-claude-code-/backend/service/mcp_client.py`

**Current (Line 127)**:
```python
cache_tools_list=True,  # Already enabled ✓
```

**Status**: Already implemented correctly.

---

### Step 2: Add Stdio Server Support (Future Enhancement)

**Create**: `backend/service/stdio_mcp_server.py`

```python
"""
Stdio-based MCP server for local ComfyUI plugins.
Uses subprocess to run local MCP server implementations.
"""

import subprocess
import asyncio
from typing import List, Optional
from agents.mcp import MCPServerStdio
from mcp import StdioServerParameters
from ..utils.logger import log


class LocalComfyUIMCPServer:
    """Wrapper for local Stdio-based MCP servers."""

    def __init__(
        self,
        server_name: str,
        server_script: str,
        cache_tools: bool = True,
        timeout_seconds: float = 300.0
    ):
        """
        Initialize local MCP server.

        Args:
            server_name: Name of the MCP server
            server_script: Path to Python script running the server
            cache_tools: Whether to cache tool list
            timeout_seconds: Connection timeout
        """
        self.server_name = server_name
        self.server_script = server_script
        self.cache_tools = cache_tools
        self.timeout_seconds = timeout_seconds
        self._mcp_server = None

    async def connect(self) -> MCPServerStdio:
        """Connect to the local MCP server."""
        try:
            server_params = StdioServerParameters(
                command="python",
                args=[self.server_script]
            )

            self._mcp_server = MCPServerStdio(
                server_params,
                cache_tools_list=self.cache_tools,
                client_session_timeout_seconds=self.timeout_seconds
            )

            log.info(f"[MCP] Connecting to local server: {self.server_name}")
            await self._mcp_server.__aenter__()

            # Verify connection by listing tools
            tools = await self._mcp_server.list_tools()
            log.info(f"[MCP] {self.server_name}: {len(tools)} tools discovered")

            return self._mcp_server

        except Exception as e:
            log.error(f"[MCP] Failed to connect to {self.server_name}: {e}")
            raise

    async def disconnect(self):
        """Disconnect from the local MCP server."""
        if self._mcp_server:
            try:
                await self._mcp_server.__aexit__(None, None, None)
                log.info(f"[MCP] Disconnected from {self.server_name}")
            except Exception as e:
                log.error(f"[MCP] Error disconnecting from {self.server_name}: {e}")

    async def list_tools(self) -> List[dict]:
        """List available tools from the server."""
        if not self._mcp_server:
            raise RuntimeError("Server not connected")
        return await self._mcp_server.list_tools()

    async def call_tool(self, tool_name: str, arguments: dict):
        """Call a tool on the server."""
        if not self._mcp_server:
            raise RuntimeError("Server not connected")
        return await self._mcp_server.call_tool(tool_name, arguments)
```

**Usage in mcp_client.py**:
```python
import os
from .stdio_mcp_server import LocalComfyUIMCPServer

# In comfyui_agent_invoke function, after existing SSE servers:

local_server = None
if os.getenv("COMFYUI_LOCAL_MCP_SERVER"):
    local_server = LocalComfyUIMCPServer(
        server_name="ComfyUI Local Plugin",
        server_script=os.getenv("COMFYUI_LOCAL_MCP_SERVER"),
        cache_tools=True
    )
    await local_server.connect()
    server_list.append(local_server)

try:
    # ... existing agent code ...
finally:
    if local_server:
        await local_server.disconnect()
```

---

### Step 3: Implement Tool Message Handler

**Create**: `backend/service/mcp_message_handler.py`

```python
"""
Standardized MCP message serialization and deserialization.
Ensures consistent JSON-RPC 2.0 message format across ComfyUI-Copilot.
"""

import json
import uuid
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict
from ..utils.logger import log


@dataclass
class MCPToolResult:
    """Standardized MCP tool result."""
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    ext: Optional[List[Dict]] = None

    def to_json(self) -> str:
        """Serialize to JSON with ext wrapper."""
        data = asdict(self)
        data["ext"] = data["ext"] or []
        return json.dumps(data, ensure_ascii=False)


@dataclass
class MCPToolCall:
    """Represents an MCP tool call."""
    id: str
    tool_name: str
    arguments: Dict[str, Any]

    @classmethod
    def from_json(cls, json_str: str) -> "MCPToolCall":
        """Parse from JSON-RPC format."""
        data = json.loads(json_str)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            tool_name=data["params"]["name"],
            arguments=data["params"]["arguments"]
        )


class MCPMessageHandler:
    """Handles MCP message serialization with validation."""

    @staticmethod
    def serialize_request(
        method: str,
        params: Dict[str, Any],
        msg_id: Optional[str] = None
    ) -> str:
        """
        Serialize request to JSON-RPC 2.0 format.

        Args:
            method: RPC method name (e.g., "tools/call")
            params: Method parameters
            msg_id: Optional message ID

        Returns:
            JSON-RPC formatted request string
        """
        return json.dumps({
            "jsonrpc": "2.0",
            "id": msg_id or str(uuid.uuid4()),
            "method": method,
            "params": params
        })

    @staticmethod
    def serialize_response(
        result: Any,
        msg_id: str
    ) -> str:
        """
        Serialize response to JSON-RPC 2.0 format.

        Args:
            result: Response data
            msg_id: Message ID to match request

        Returns:
            JSON-RPC formatted response string
        """
        return json.dumps({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result
        })

    @staticmethod
    def serialize_error(
        code: int,
        message: str,
        msg_id: str,
        data: Optional[Dict] = None
    ) -> str:
        """
        Serialize error to JSON-RPC 2.0 format.

        Args:
            code: Error code
            message: Error message
            msg_id: Message ID to match request
            data: Additional error data

        Returns:
            JSON-RPC formatted error response string
        """
        error = {
            "code": code,
            "message": message
        }
        if data:
            error["data"] = data

        return json.dumps({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": error
        })

    @staticmethod
    def parse_response(
        response_str: str,
        tool_name: str
    ) -> MCPToolResult:
        """
        Parse tool response with robust error handling.

        Args:
            response_str: Response string (JSON or plain text)
            tool_name: Name of tool for context

        Returns:
            MCPToolResult with parsed data
        """
        try:
            data = json.loads(response_str)

            # Handle direct result format
            if isinstance(data, dict):
                return MCPToolResult(
                    tool_name=tool_name,
                    success=data.get("success", True),
                    result=data.get("result") or data.get("data"),
                    error=data.get("error"),
                    ext=data.get("ext")
                )

            # Fallback for unexpected format
            return MCPToolResult(
                tool_name=tool_name,
                success=True,
                result=data
            )

        except json.JSONDecodeError as e:
            log.warning(f"Failed to parse JSON response from {tool_name}: {e}")
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=f"JSON parsing failed: {str(e)}",
                result={"raw_response": response_str}
            )

        except Exception as e:
            log.error(f"Unexpected error parsing {tool_name} response: {e}")
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                result={"raw_response": response_str}
            )

    @staticmethod
    def validate_tool_arguments(
        arguments: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate tool arguments against JSON schema.

        Args:
            arguments: Arguments to validate
            schema: JSON schema definition

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Basic validation: check required fields
            required = schema.get("required", [])
            for field in required:
                if field not in arguments:
                    return False, f"Missing required field: {field}"

            # Check property types
            properties = schema.get("properties", {})
            for field, value in arguments.items():
                if field in properties:
                    prop_schema = properties[field]
                    expected_type = prop_schema.get("type")

                    # Simple type checking
                    if expected_type == "string" and not isinstance(value, str):
                        return False, f"Field {field} must be string, got {type(value).__name__}"
                    elif expected_type == "number" and not isinstance(value, (int, float)):
                        return False, f"Field {field} must be number, got {type(value).__name__}"
                    elif expected_type == "integer" and not isinstance(value, int):
                        return False, f"Field {field} must be integer, got {type(value).__name__}"
                    elif expected_type == "boolean" and not isinstance(value, bool):
                        return False, f"Field {field} must be boolean, got {type(value).__name__}"
                    elif expected_type == "array" and not isinstance(value, list):
                        return False, f"Field {field} must be array, got {type(value).__name__}"
                    elif expected_type == "object" and not isinstance(value, dict):
                        return False, f"Field {field} must be object, got {type(value).__name__}"

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"
```

**Usage**:
```python
from .mcp_message_handler import MCPMessageHandler, MCPToolResult

# Serialize request
request = MCPMessageHandler.serialize_request(
    method="tools/call",
    params={
        "name": "recall_workflow",
        "arguments": {"query": "text-to-image"}
    }
)

# Parse response
response_str = '{"success": true, "data": [...], "ext": [...]}'
result = MCPMessageHandler.parse_response(response_str, "recall_workflow")

# Serialize result
output = result.to_json()
```

---

### Step 4: Add Tool Registry for Organization

**Create**: `backend/service/tool_registry.py`

```python
"""
Centralized tool management and discovery.
Organizes tools by category for better agent routing.
"""

from typing import Dict, List, Callable, Optional
from agents.tool import function_tool
from ..utils.logger import log


class ComfyUIToolRegistry:
    """Manages tool registration and discovery by category."""

    def __init__(self):
        """Initialize empty registry."""
        self.tools: Dict[str, List[Callable]] = {
            "workflow": [],
            "node": [],
            "parameter": [],
            "validation": [],
            "search": [],
            "analysis": []
        }
        self.tool_metadata: Dict[str, Dict] = {}

    def register(
        self,
        category: str,
        tool: Callable,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Register a tool in a category.

        Args:
            category: Tool category
            tool: Tool function (should be @function_tool decorated)
            metadata: Additional tool metadata
        """
        if category not in self.tools:
            raise ValueError(f"Unknown category: {category}")

        self.tools[category].append(tool)
        self.tool_metadata[tool.__name__] = {
            "category": category,
            "name": tool.__name__,
            "docstring": tool.__doc__,
            **(metadata or {})
        }
        log.info(f"Registered tool '{tool.__name__}' in category '{category}'")

    def get_all_tools(self) -> List[Callable]:
        """Get all registered tools."""
        all_tools = []
        for tools in self.tools.values():
            all_tools.extend(tools)
        return all_tools

    def get_tools_by_category(self, category: str) -> List[Callable]:
        """Get tools for a specific category."""
        return self.tools.get(category, [])

    def get_tools_for_agent(self, agent_type: str) -> List[Callable]:
        """
        Get recommended tools for a specific agent type.

        Args:
            agent_type: Type of agent (main, rewrite, debug, etc.)

        Returns:
            List of tools for that agent
        """
        agent_toolsets = {
            "main": ["workflow", "search", "node"],
            "rewrite": ["workflow", "parameter", "validation"],
            "debug": ["analysis", "validation", "workflow"],
            "search": ["search", "node"]
        }

        categories = agent_toolsets.get(agent_type, [])
        tools = []
        for category in categories:
            tools.extend(self.get_tools_by_category(category))

        return tools

    def get_metadata(self, tool_name: str) -> Optional[Dict]:
        """Get metadata for a tool."""
        return self.tool_metadata.get(tool_name)

    def list_categories(self) -> Dict[str, int]:
        """List all categories with tool counts."""
        return {
            category: len(tools)
            for category, tools in self.tools.items()
        }


# Global registry instance
_global_registry = ComfyUIToolRegistry()


def get_tool_registry() -> ComfyUIToolRegistry:
    """Get the global tool registry."""
    return _global_registry


# Registration decorators
def workflow_tool(func: Callable) -> Callable:
    """Decorator for workflow tools."""
    tool = function_tool(func)
    _global_registry.register("workflow", tool)
    return tool


def node_tool(func: Callable) -> Callable:
    """Decorator for node tools."""
    tool = function_tool(func)
    _global_registry.register("node", tool)
    return tool


def parameter_tool(func: Callable) -> Callable:
    """Decorator for parameter tools."""
    tool = function_tool(func)
    _global_registry.register("parameter", tool)
    return tool


def validation_tool(func: Callable) -> Callable:
    """Decorator for validation tools."""
    tool = function_tool(func)
    _global_registry.register("validation", tool)
    return tool


def search_tool(func: Callable) -> Callable:
    """Decorator for search tools."""
    tool = function_tool(func)
    _global_registry.register("search", tool)
    return tool


def analysis_tool(func: Callable) -> Callable:
    """Decorator for analysis tools."""
    tool = function_tool(func)
    _global_registry.register("analysis", tool)
    return tool
```

**Usage**:
```python
# In workflow_rewrite_tools.py
from service.tool_registry import workflow_tool

@workflow_tool
def get_current_workflow() -> dict:
    """Get current workflow from session."""
    pass

# In node-related tools
from service.tool_registry import node_tool

@node_tool
def search_nodes(query: str) -> list:
    """Search for nodes by name."""
    pass

# In agent creation
from service.tool_registry import get_tool_registry

registry = get_tool_registry()
main_agent_tools = registry.get_tools_for_agent("main")

agent = create_agent(
    name="ComfyUI-Copilot",
    tools=main_agent_tools,
    ...
)
```

---

### Step 5: Enhanced Error Recovery

**Create**: `backend/service/mcp_reliability.py`

```python
"""
Reliability utilities for MCP operations with retry logic.
Implements exponential backoff for transient failures.
"""

import asyncio
from typing import Callable, TypeVar, Optional, Tuple
from functools import wraps
import time

from ..utils.logger import log

T = TypeVar('T')


class MCPRetryConfig:
    """Configuration for MCP retry logic."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential_base: float = 2.0
    ):
        """
        Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial retry delay in seconds
            max_delay: Maximum retry delay in seconds
            exponential_base: Base for exponential backoff
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base


# Retryable errors
RETRYABLE_ERRORS = (
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
    TimeoutError,
)


async def with_retry(
    fn: Callable,
    *args,
    config: MCPRetryConfig = None,
    operation_name: str = "MCP operation",
    **kwargs
) -> Optional[T]:
    """
    Execute async function with exponential backoff retry.

    Args:
        fn: Async function to execute
        config: Retry configuration
        operation_name: Name for logging
        *args, **kwargs: Arguments to pass to function

    Returns:
        Function result or None if all retries failed
    """
    config = config or MCPRetryConfig()
    delay = config.initial_delay

    for attempt in range(config.max_retries + 1):
        try:
            log.debug(f"[MCP] Executing {operation_name} (attempt {attempt + 1})")
            return await fn(*args, **kwargs)

        except RETRYABLE_ERRORS as e:
            if attempt >= config.max_retries:
                log.error(f"[MCP] {operation_name} failed after {config.max_retries + 1} attempts: {e}")
                raise

            log.warning(
                f"[MCP] {operation_name} attempt {attempt + 1} failed: {type(e).__name__}: {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)
            delay = min(delay * config.exponential_base, config.max_delay)

        except Exception as e:
            log.error(f"[MCP] Non-retryable error in {operation_name}: {type(e).__name__}: {e}")
            raise

    return None


def retry_async(
    config: MCPRetryConfig = None,
    operation_name: str = None
):
    """
    Decorator for async functions with retry logic.

    Args:
        config: Retry configuration
        operation_name: Name for logging

    Usage:
        @retry_async(operation_name="list_tools")
        async def list_tools(server):
            return await server.list_tools()
    """
    config = config or MCPRetryConfig()

    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_retry(
                func,
                *args,
                config=config,
                operation_name=op_name,
                **kwargs
            )

        return wrapper

    return decorator


class MCPCircuitBreaker:
    """
    Circuit breaker pattern for MCP servers.
    Prevents cascading failures from repeated connection attempts.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Time before attempting recovery (seconds)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    def record_success(self) -> None:
        """Record successful operation."""
        self.failure_count = 0
        if self.state != "closed":
            log.info("[MCP] Circuit breaker recovering to CLOSED")
            self.state = "closed"

    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            log.warning(f"[MCP] Circuit breaker OPEN (failures: {self.failure_count})")
            self.state = "open"

    def is_available(self) -> bool:
        """Check if circuit breaker allows requests."""
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if recovery timeout elapsed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                log.info("[MCP] Circuit breaker transitioning to HALF_OPEN")
                self.state = "half_open"
                return True
            return False

        # half_open: allow single request for recovery
        return True

    async def call_with_breaker(
        self,
        fn: Callable,
        *args,
        **kwargs
    ) -> Optional[T]:
        """
        Execute function through circuit breaker.

        Args:
            fn: Function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result or None if breaker is open
        """
        if not self.is_available():
            log.warning("[MCP] Circuit breaker is OPEN, rejecting request")
            return None

        try:
            result = await fn(*args, **kwargs)
            self.record_success()
            return result

        except Exception as e:
            self.record_failure()
            raise
```

---

## Deployment Configuration

### Environment Variables for MCP

**File**: `.env` or environment configuration

```bash
# Internal MCP server
COMFYUI_MCP_INTERNAL_URL="http://localhost:8888/mcp-server/mcp"
COMFYUI_MCP_INTERNAL_TIMEOUT=300

# ModelScope MCP server
COMFYUI_MCP_MODELSCOPE_URL="https://mcp.api-inference.modelscope.net/8c9fe550938e4f/sse"
COMFYUI_MCP_MODELSCOPE_TIMEOUT=300

# Local Stdio MCP server (optional)
COMFYUI_LOCAL_MCP_SERVER="/path/to/local_mcp_server.py"

# Tool caching
COMFYUI_MCP_CACHE_TOOLS=true
COMFYUI_MCP_CACHE_TTL=3600  # seconds

# Retry configuration
COMFYUI_MCP_MAX_RETRIES=3
COMFYUI_MCP_RETRY_INITIAL_DELAY=1.0
COMFYUI_MCP_RETRY_MAX_DELAY=10.0

# Circuit breaker
COMFYUI_MCP_CIRCUIT_BREAKER_ENABLED=true
COMFYUI_MCP_CIRCUIT_BREAKER_THRESHOLD=5
COMFYUI_MCP_CIRCUIT_BREAKER_TIMEOUT=60
```

---

## Testing MCP Integration

**Create**: `backend/tests/test_mcp_integration.py`

```python
"""
Unit tests for MCP integration.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from service.mcp_message_handler import MCPMessageHandler, MCPToolResult
from service.tool_registry import ComfyUIToolRegistry
from service.mcp_reliability import with_retry, MCPRetryConfig, MCPCircuitBreaker


class TestMCPMessageHandler:
    """Test message serialization."""

    def test_serialize_request(self):
        """Test JSON-RPC request serialization."""
        request = MCPMessageHandler.serialize_request(
            method="tools/call",
            params={"name": "test_tool", "arguments": {"arg1": "value"}}
        )
        assert '"jsonrpc": "2.0"' in request
        assert '"method": "tools/call"' in request
        assert '"id"' in request

    def test_parse_response_success(self):
        """Test parsing successful response."""
        response = '{"success": true, "result": {"data": "value"}}'
        result = MCPMessageHandler.parse_response(response, "test_tool")
        assert result.success is True
        assert result.result == {"data": "value"}
        assert result.error is None

    def test_parse_response_invalid_json(self):
        """Test parsing invalid JSON response."""
        result = MCPMessageHandler.parse_response("invalid json", "test_tool")
        assert result.success is False
        assert "raw_response" in result.result


class TestToolRegistry:
    """Test tool registry."""

    def test_register_and_retrieve(self):
        """Test tool registration."""
        registry = ComfyUIToolRegistry()

        def dummy_tool():
            pass

        registry.register("workflow", dummy_tool)
        tools = registry.get_tools_by_category("workflow")
        assert dummy_tool in tools

    def test_get_tools_for_agent(self):
        """Test agent-specific tool retrieval."""
        registry = ComfyUIToolRegistry()

        def tool1():
            pass

        def tool2():
            pass

        registry.register("workflow", tool1)
        registry.register("search", tool2)

        main_tools = registry.get_tools_for_agent("main")
        assert len(main_tools) > 0


@pytest.mark.asyncio
async def test_with_retry():
    """Test retry mechanism."""
    mock_fn = AsyncMock()
    mock_fn.side_effect = [
        ConnectionError("attempt 1"),
        ConnectionError("attempt 2"),
        "success"
    ]

    result = await with_retry(
        mock_fn,
        config=MCPRetryConfig(max_retries=3)
    )

    assert result == "success"
    assert mock_fn.call_count == 3


def test_circuit_breaker():
    """Test circuit breaker."""
    breaker = MCPCircuitBreaker(failure_threshold=3)

    # Record failures
    breaker.record_failure()
    assert breaker.state == "closed"

    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == "open"

    # Circuit breaker rejects requests
    assert not breaker.is_available()

    # Simulate timeout
    breaker.last_failure_time -= breaker.recovery_timeout + 1
    assert breaker.is_available()
    assert breaker.state == "half_open"
```

---

## Performance Monitoring

### Add Metrics Collection

**Create**: `backend/service/mcp_metrics.py`

```python
"""
MCP performance monitoring and metrics collection.
"""

import time
from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..utils.logger import log


@dataclass
class MCPMetrics:
    """Metrics for MCP operations."""

    server_name: str
    tool_name: str
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    last_error: str = None
    last_call_time: datetime = field(default_factory=datetime.now)

    def record_call(self, duration: float, success: bool, error: str = None):
        """Record a tool call."""
        self.request_count += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.last_call_time = datetime.now()

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
            self.last_error = error

    @property
    def avg_time(self) -> float:
        """Average call duration."""
        return self.total_time / self.request_count if self.request_count > 0 else 0

    @property
    def success_rate(self) -> float:
        """Success rate percentage."""
        return (self.success_count / self.request_count * 100
                if self.request_count > 0 else 0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/monitoring."""
        return {
            "server": self.server_name,
            "tool": self.tool_name,
            "requests": self.request_count,
            "successes": self.success_count,
            "failures": self.failure_count,
            "success_rate": f"{self.success_rate:.1f}%",
            "avg_time_ms": f"{self.avg_time * 1000:.2f}",
            "min_time_ms": f"{self.min_time * 1000:.2f}",
            "max_time_ms": f"{self.max_time * 1000:.2f}",
            "last_error": self.last_error,
            "last_call": self.last_call_time.isoformat()
        }


class MCPMetricsCollector:
    """Collects MCP metrics across all servers and tools."""

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, MCPMetrics] = {}

    def get_key(self, server_name: str, tool_name: str) -> str:
        """Get metric key."""
        return f"{server_name}:{tool_name}"

    def record_tool_call(
        self,
        server_name: str,
        tool_name: str,
        duration: float,
        success: bool,
        error: str = None
    ):
        """Record a tool call."""
        key = self.get_key(server_name, tool_name)

        if key not in self.metrics:
            self.metrics[key] = MCPMetrics(server_name, tool_name)

        self.metrics[key].record_call(duration, success, error)

    def get_metrics(self, server_name: str = None) -> Dict[str, Any]:
        """Get metrics for a server or all servers."""
        if server_name:
            return {
                k: v.to_dict()
                for k, v in self.metrics.items()
                if k.startswith(server_name)
            }
        return {k: v.to_dict() for k, v in self.metrics.items()}

    def print_summary(self):
        """Print metrics summary to logs."""
        log.info("[MCP] Metrics Summary:")
        for key, metric in self.metrics.items():
            log.info(f"  {key}: {metric.to_dict()}")


# Global metrics collector
_metrics_collector = MCPMetricsCollector()


def get_metrics_collector() -> MCPMetricsCollector:
    """Get global metrics collector."""
    return _metrics_collector
```

---

## References

- See `MCP_BEST_PRACTICES.md` for detailed conceptual information
- OpenAI Agents SDK Documentation: https://openai.github.io/openai-agents-python/
- Model Context Protocol: https://modelcontextprotocol.io/
- FastMCP: https://gofastmcp.com/

---

**Document Version**: 1.0
**Last Updated**: January 2, 2026
