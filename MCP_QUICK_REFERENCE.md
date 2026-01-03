# Python MCP Quick Reference Guide

**For**: Developers implementing or maintaining MCP integration in ComfyUI-Copilot
**Format**: Quick lookup guide with code snippets
**Last Updated**: January 2, 2026

---

## 1. SSE MCP Client Configuration

### Basic Setup (Current ComfyUI-Copilot Pattern)

```python
from agents.mcp import MCPServerSse

# Remote MCP server configuration
mcp_server = MCPServerSse(
    params={
        "url": "https://example.com/mcp/sse",
        "timeout": 300.0,
        "headers": {
            "Authorization": f"Bearer {api_key}",
            "X-Session-Id": session_id,
            "User-Agent": "ComfyUI-Copilot/2.0"
        }
    },
    cache_tools_list=True,                    # Cache discovered tools
    client_session_timeout_seconds=300.0      # Overall session timeout
)
```

### Using with Agent

```python
async with mcp_server:
    agent = create_agent(
        name="ComfyUI-Copilot",
        mcp_servers=[mcp_server],
        tools=[local_tools],
        ...
    )

    result = await agent.run(messages)
```

---

## 2. Tool Definition & Registration

### Simple Tool

```python
from agents.tool import function_tool

@function_tool
def search_nodes(query: str, limit: int = 5) -> dict:
    """
    Search for ComfyUI nodes.

    Args:
        query: Search term
        limit: Max results (default: 5)

    Returns:
        Dictionary with matching nodes
    """
    # Implementation
    return {"nodes": [...]}
```

### Tool with Complex Validation

```python
from typing import Optional, List
from pydantic import BaseModel

class Node(BaseModel):
    name: str
    class_name: str
    category: str

class NodeList(BaseModel):
    count: int
    nodes: List[Node]

@function_tool
def get_available_nodes(category: Optional[str] = None) -> NodeList:
    """Get available nodes, optionally filtered by category."""
    nodes = [...]
    return NodeList(count=len(nodes), nodes=nodes)
```

---

## 3. Tool Discovery

### List Available Tools

```python
async with mcp_server:
    # Automatically called on connection
    tools = await mcp_server.list_tools()

    for tool in tools:
        print(f"Tool: {tool.name}")
        print(f"  Schema: {tool.inputSchema}")
```

### Tool Schema Example

```json
{
  "name": "search_nodes",
  "description": "Search for ComfyUI nodes",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},
      "limit": {"type": "integer", "default": 5}
    },
    "required": ["query"]
  }
}
```

---

## 4. Tool Invocation

### Call a Tool

```python
result = await mcp_server.call_tool(
    name="search_nodes",
    arguments={
        "query": "load image",
        "limit": 10
    }
)
```

### Parse Tool Result

```python
import json

try:
    # Tool result is typically wrapped
    if isinstance(result, str):
        data = json.loads(result)
    else:
        data = result

    # Extract components
    success = data.get("success", True)
    nodes = data.get("data", [])
    ext = data.get("ext", [])  # Extension data

except json.JSONDecodeError:
    # Handle non-JSON response
    log.error(f"Invalid JSON response: {result}")
```

---

## 5. Error Handling

### Retryable Errors

```python
import asyncio
from openai import APIError, RateLimitError

retryable_errors = (
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
    RateLimitError,
)

try:
    result = await mcp_server.call_tool(...)
except retryable_errors as e:
    # Implement retry logic
    await asyncio.sleep(exponential_backoff_delay)
    # Retry...
except APIError as e:
    # Handle API errors
    log.error(f"API Error: {e}")
except Exception as e:
    # Non-retryable errors
    raise
```

### Timeout Handling

```python
import asyncio

try:
    result = await asyncio.wait_for(
        mcp_server.call_tool("tool_name", {}),
        timeout=30.0  # Override default timeout
    )
except asyncio.TimeoutError:
    log.error("Tool call timed out")
    # Fallback behavior
```

---

## 6. Message Serialization

### JSON-RPC Request Format

```python
import json
import uuid

request = {
    "jsonrpc": "2.0",
    "id": str(uuid.uuid4()),
    "method": "tools/call",
    "params": {
        "name": "tool_name",
        "arguments": {"arg1": "value1"}
    }
}

request_json = json.dumps(request)
```

### JSON-RPC Response Format

```python
response = {
    "jsonrpc": "2.0",
    "id": "same-as-request",
    "result": {
        "content": [
            {
                "type": "text",
                "text": '{"data": [...], "ext": [...]}'
            }
        ]
    }
}
```

### Error Response Format

```python
error = {
    "jsonrpc": "2.0",
    "id": "same-as-request",
    "error": {
        "code": -32603,
        "message": "Internal error",
        "data": {"details": "..."}
    }
}
```

---

## 7. Performance Optimization

### Enable Tool Caching

```python
# For servers with static tools
mcp_server = MCPServerSse(
    params={...},
    cache_tools_list=True,  # Enable caching
    client_session_timeout_seconds=300.0
)
```

### Timeout Strategy

```python
# Different timeouts for different operations
TOOL_TIMEOUTS = {
    "search_nodes": 10.0,        # Fast local search
    "recall_workflow": 30.0,     # Database query
    "gen_workflow": 120.0,       # AI generation
    "validate_workflow": 15.0    # Validation
}

timeout = TOOL_TIMEOUTS.get(tool_name, 30.0)
result = await asyncio.wait_for(
    mcp_server.call_tool(tool_name, args),
    timeout=timeout
)
```

### Connection Pooling (Advanced)

```python
from aiohttp import TCPConnector, ClientSession

connector = TCPConnector(
    limit=10,              # Max concurrent connections
    limit_per_host=5,      # Per host limit
    ttl_dns_cache=300      # DNS cache time
)

# Use connector with SSE client
# (requires custom wrapper or future SDK enhancement)
```

---

## 8. Logging Best Practices

### Recommended Logging

```python
from ..utils.logger import log

# On connection
log.info(f"[MCP] Connecting to {server_name}")

# On tool discovery
log.info(f"[MCP] Discovered {len(tools)} tools from {server_name}")
for tool in tools:
    log.debug(f"  - {tool.name}: {tool.description[:50]}...")

# On tool call
log.debug(f"[MCP] Calling {tool_name} with args: {arguments}")

# On success
log.info(f"[MCP] {tool_name} completed in {duration:.2f}s")

# On error
log.error(f"[MCP] {tool_name} failed: {error}")
log.debug(f"Traceback: {traceback.format_exc()}")
```

### Structured Logging (Enhanced)

```python
log.info(f"[MCP] Tool execution", extra={
    "tool_name": tool_name,
    "server": server_name,
    "duration_ms": duration * 1000,
    "success": True,
    "arguments_count": len(arguments)
})
```

---

## 9. Multiple MCP Servers

### Server List Configuration

```python
server_list = []

# Internal server
internal_server = MCPServerSse(
    params={
        "url": BACKEND_BASE_URL + "/mcp-server/mcp",
        "timeout": 300.0,
        "headers": {...}
    },
    cache_tools_list=True
)
server_list.append(internal_server)

# Remote search server
search_server = MCPServerSse(
    params={
        "url": "https://example.com/mcp",
        "timeout": 300.0,
        "headers": {...}
    },
    cache_tools_list=True
)
server_list.append(search_server)

# Use all servers
agent = create_agent(
    mcp_servers=server_list,
    ...
)
```

### Aggregated Tool Discovery

```python
all_tools = {}

async with contextlib.AsyncExitStack() as stack:
    for server in server_list:
        await stack.enter_async_context(server)

        tools = await server.list_tools()
        for tool in tools:
            all_tools[tool.name] = (server, tool)

log.info(f"Total tools discovered: {len(all_tools)}")
```

---

## 10. Testing

### Mock Server for Tests

```python
from unittest.mock import AsyncMock, MagicMock

async def test_tool_call():
    mock_server = AsyncMock()
    mock_server.list_tools.return_value = [
        MagicMock(name="test_tool")
    ]
    mock_server.call_tool.return_value = {
        "success": True,
        "data": {"result": "value"}
    }

    result = await mock_server.call_tool(
        "test_tool",
        {"arg": "value"}
    )

    assert result["success"]
    assert result["data"]["result"] == "value"
```

### Integration Test Pattern

```python
import pytest

@pytest.mark.asyncio
async def test_mcp_integration():
    async with MCPServerSse(...) as server:
        # List tools
        tools = await server.list_tools()
        assert len(tools) > 0

        # Call tool
        result = await server.call_tool(
            "search_nodes",
            {"query": "LoadImage"}
        )

        assert result is not None
```

---

## 11. Environment Variables

### Recommended Configuration

```bash
# Server URLs
BACKEND_BASE_URL="https://api.example.com"
COMFYUI_MCP_INTERNAL_URL="${BACKEND_BASE_URL}/mcp-server/mcp"
COMFYUI_MCP_MODELSCOPE_URL="https://mcp.api-inference.modelscope.net/..."

# Timeouts
COMFYUI_MCP_TIMEOUT=300
COMFYUI_MCP_SESSION_TIMEOUT=300

# Tool caching
COMFYUI_MCP_CACHE_TOOLS=true
COMFYUI_MCP_CACHE_TTL=3600

# Retry configuration
COMFYUI_MCP_MAX_RETRIES=3
COMFYUI_MCP_INITIAL_RETRY_DELAY=1.0
COMFYUI_MCP_MAX_RETRY_DELAY=10.0

# Local server (optional)
COMFYUI_LOCAL_MCP_SERVER=""

# Logging
COMFYUI_MCP_LOG_LEVEL=INFO
COMFYUI_MCP_LOG_REQUESTS=false
```

### Loading in Code

```python
import os
from dotenv import load_dotenv

load_dotenv()

MCP_TIMEOUT = float(os.getenv("COMFYUI_MCP_TIMEOUT", "300"))
MCP_CACHE_TOOLS = os.getenv("COMFYUI_MCP_CACHE_TOOLS", "true").lower() == "true"
MCP_MAX_RETRIES = int(os.getenv("COMFYUI_MCP_MAX_RETRIES", "3"))
```

---

## 12. Common Patterns

### Circuit Breaker Pattern

```python
class SimpleCircuitBreaker:
    def __init__(self, failure_threshold=5):
        self.failures = 0
        self.threshold = failure_threshold
        self.open = False

    async def call(self, fn, *args, **kwargs):
        if self.open:
            raise Exception("Circuit breaker is open")

        try:
            result = await fn(*args, **kwargs)
            self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            if self.failures >= self.threshold:
                self.open = True
            raise

breaker = SimpleCircuitBreaker()
try:
    result = await breaker.call(mcp_server.call_tool, ...)
except Exception as e:
    log.error(f"Circuit breaker active: {e}")
```

### Retry with Exponential Backoff

```python
async def call_with_retry(tool_name, args, max_retries=3):
    delay = 1.0

    for attempt in range(max_retries + 1):
        try:
            return await mcp_server.call_tool(tool_name, args)
        except asyncio.TimeoutError:
            if attempt >= max_retries:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 10.0)
```

### Timeout with Fallback

```python
async def call_with_fallback(tool_name, args, timeout=30, fallback=None):
    try:
        return await asyncio.wait_for(
            mcp_server.call_tool(tool_name, args),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        log.warning(f"Tool {tool_name} timed out, using fallback")
        return fallback or {"error": "timeout", "data": None}
```

---

## 13. Debugging

### Enable Debug Logging

```python
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

# For specific module
mcp_logger = logging.getLogger("agents.mcp")
mcp_logger.setLevel(logging.DEBUG)
```

### Inspect Tool Schemas

```python
import json

async with mcp_server:
    tools = await mcp_server.list_tools()

    for tool in tools:
        print(f"\n=== {tool.name} ===")
        print(json.dumps(tool.inputSchema, indent=2))
        print(f"Description: {tool.description}")
```

### Trace Message Flow

```python
# Wrap server calls for debugging
original_call_tool = mcp_server.call_tool

async def traced_call_tool(name, args):
    print(f"→ Calling {name}")
    print(f"  Args: {json.dumps(args, indent=2)}")

    result = await original_call_tool(name, args)

    print(f"← Result from {name}")
    print(f"  Data: {json.dumps(result, indent=2)[:200]}...")

    return result

mcp_server.call_tool = traced_call_tool
```

---

## 14. Migration Guide: SSE to Streamable HTTP (Future)

```python
# Current (SSE)
from agents.mcp import MCPServerSse

server = MCPServerSse(params={...})

# Future (Streamable HTTP)
from agents.mcp import MCPServerStreamableHttp
import httpx

async with httpx.AsyncClient() as client:
    server = MCPServerStreamableHttp(
        url="https://example.com/mcp",
        client=client,
        headers={...}
    )
```

---

## 15. Checklist: Adding New MCP Server

- [ ] Define server URL and authentication
- [ ] Configure timeout (recommend 300s for async operations)
- [ ] Set cache_tools_list based on tool volatility
- [ ] Add to server_list in mcp_client.py
- [ ] Test tool discovery
- [ ] Test tool invocation
- [ ] Add error handling for that server
- [ ] Document server purpose and tools in code
- [ ] Add to .env configuration with ENV variables
- [ ] Update agent instructions if needed
- [ ] Test with actual agent workflows

---

## References

- **Full Guide**: See `MCP_BEST_PRACTICES.md`
- **Implementation Details**: See `MCP_IMPLEMENTATION_GUIDE.md`
- **Architecture Analysis**: See `MCP_RESEARCH_SUMMARY.md`
- **Official Docs**: https://openai.github.io/openai-agents-python/mcp/

---

**Quick Reference Version**: 1.0
**Last Updated**: January 2, 2026
**Status**: Ready to Use
