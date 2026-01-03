# AgentX Runtime Quickstart

**Feature**: ComfyUI-AgentX Runtime
**Date**: 2026-01-02
**Audience**: Developers and ComfyUI users

---

## Prerequisites

Before installing AgentX Runtime, ensure you have:

- **Python**: 3.10 or higher
- **ComfyUI**: Installed and running
- **Claude API Key**: From [Anthropic Console](https://console.anthropic.com/)
- **Git**: For cloning the repository

---

## Installation

### 1. Clone Repository

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/your-org/ComfyUI-Copilot.git
cd ComfyUI-Copilot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Key Dependencies**:
- `anthropic>=0.40.0` - Claude API client
- `aiohttp>=3.8.0` - Web server and WebSocket
- `sqlalchemy>=1.4.0,<2.0` - Database ORM
- `fastmcp>=0.1.0` - MCP server framework
- `pytest>=7.0.0` - Testing (dev only)
- `pytest-asyncio>=0.21.0` - Async testing (dev only)

### 3. Configure Environment

Create `.env` file in the plugin root:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-api03-...
AGENTX_MODEL=claude-3-5-sonnet-20241022
AGENTX_DATABASE_URL=sqlite:///agentx_sessions.db
AGENTX_LOG_LEVEL=INFO
```

**Optional Configuration**:
```bash
# Advanced settings
AGENTX_MAX_TOKENS=4096
AGENTX_TEMPERATURE=1.0
AGENTX_WEBSOCKET_HEARTBEAT=30
AGENTX_EVENT_QUEUE_MAXSIZE=1000
AGENTX_ENABLE_EVENT_LOGGING=false
```

### 4. Restart ComfyUI

```bash
# From ComfyUI root directory
python main.py --listen 0.0.0.0 --port 8188
```

---

## Verification

### 1. Check AgentX Loaded

Look for initialization logs:

```
[ComfyUI-Copilot] AgentX Runtime initialized
[ComfyUI-Copilot] MCP server 'comfyui' started (8 tools registered)
[ComfyUI-Copilot] Database: agentx_sessions.db (0 sessions)
[ComfyUI-Copilot] API available at http://localhost:8188/agentx
```

### 2. Health Check

```bash
curl http://localhost:8188/agentx/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "mcp_servers": [
    {"name": "comfyui", "status": "running"}
  ],
  "database": "connected"
}
```

### 3. List Available Tools

```bash
curl http://localhost:8188/agentx/tools
```

**Expected Response**:
```json
{
  "tools": [
    {
      "name": "get_workflow",
      "description": "Retrieves the current ComfyUI workflow JSON",
      "server": "comfyui"
    },
    {
      "name": "update_workflow",
      "description": "Replaces the current workflow with provided JSON",
      "server": "comfyui"
    },
    ...
  ],
  "servers": [
    {
      "name": "comfyui",
      "type": "internal",
      "status": "running",
      "tool_count": 8
    }
  ]
}
```

---

## Basic Usage

### 1. Create a Session (HTTP)

```bash
curl -X POST http://localhost:8188/agentx/sessions \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Response**:
```json
{
  "session_id": "agx-a1b2c3d4e5f67890abcdef1234567890",
  "created_at": "2026-01-02T10:00:00Z",
  "updated_at": "2026-01-02T10:00:00Z",
  "state": "idle",
  "config": {
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 4096,
    "temperature": 1.0
  },
  "user_id": null,
  "title": null,
  "message_count": 0
}
```

**Save the `session_id` for subsequent requests.**

---

### 2. Send a Message (Non-Streaming)

```bash
SESSION_ID="agx-a1b2c3d4e5f67890abcdef1234567890"

curl -X POST "http://localhost:8188/agentx/sessions/$SESSION_ID/messages" \
  -H "Content-Type: application/json" \
  -d '{"content": "What is the current workflow?"}'
```

**Response**:
```json
{
  "user_message": {
    "message_id": "msg-user123",
    "role": "user",
    "content": "What is the current workflow?",
    "timestamp": "2026-01-02T10:01:00Z",
    "tool_calls": null
  },
  "assistant_message": {
    "message_id": "msg-asst456",
    "role": "assistant",
    "content": "Let me check the current workflow for you...\n\nI can see you have a workflow with 5 nodes: ...",
    "timestamp": "2026-01-02T10:01:15Z",
    "tool_calls": [
      {
        "id": "call-xyz789",
        "name": "get_workflow",
        "arguments": {},
        "result": {"workflow": {...}},
        "error": null
      }
    ],
    "input_tokens": 234,
    "output_tokens": 512
  },
  "turn_id": "turn-abc123"
}
```

---

### 3. Stream with WebSocket (Recommended)

**Python Example**:
```python
import asyncio
import websockets
import json

async def chat_with_agentx():
    session_id = "agx-a1b2c3d4e5f67890abcdef1234567890"
    uri = f"ws://localhost:8188/agentx/sessions/{session_id}/stream"

    async with websockets.connect(uri) as ws:
        # Send user message
        await ws.send(json.dumps({
            "type": "message",
            "content": "Fix the error in my workflow"
        }))

        # Receive events
        async for message in ws:
            event = json.loads(message)

            if event["type"] == "stream":
                # Real-time token streaming
                print(event["data"], end="", flush=True)

            elif event["type"] == "state":
                # Tool execution status
                print(f"\n[{event['data']['state']}]", end=" ")
                if event['data'].get('tool_name'):
                    print(f"Tool: {event['data']['tool_name']}")

            elif event["type"] == "message":
                # Complete message
                print(f"\n\nMessage: {event['data']['content']}")

            elif event["type"] == "turn":
                # Turn complete
                print(f"\nTurn complete (tokens: {event['data']['total_tokens']})")
                break

            elif event["type"] == "error":
                print(f"\nError: {event['error']}")
                break

asyncio.run(chat_with_agentx())
```

**JavaScript Example**:
```javascript
const sessionId = 'agx-a1b2c3d4e5f67890abcdef1234567890';
const ws = new WebSocket(`ws://localhost:8188/agentx/sessions/${sessionId}/stream`);

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'message',
    content: 'Fix the error in my workflow'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case 'stream':
      process.stdout.write(data.data);  // Token streaming
      break;
    case 'state':
      console.log(`[${data.data.state}] ${data.data.progress || ''}`);
      break;
    case 'message':
      console.log('\nComplete message:', data.data.content);
      break;
    case 'turn':
      console.log('\nTurn complete');
      ws.close();
      break;
    case 'error':
      console.error('Error:', data.error);
      ws.close();
      break;
  }
};
```

---

### 4. List Sessions

```bash
curl http://localhost:8188/agentx/sessions
```

**Response**:
```json
{
  "sessions": [
    {
      "session_id": "agx-a1b2c3d4...",
      "created_at": "2026-01-02T10:00:00Z",
      "updated_at": "2026-01-02T10:15:00Z",
      "title": "Workflow debugging session",
      "message_count": 12,
      "last_message_preview": "The workflow error is caused by invalid..."
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 20
}
```

---

### 5. Load Message History

```bash
SESSION_ID="agx-a1b2c3d4e5f67890abcdef1234567890"

curl "http://localhost:8188/agentx/sessions/$SESSION_ID/messages?limit=50"
```

**Response**:
```json
{
  "messages": [
    {
      "message_id": "msg-001",
      "role": "user",
      "content": "What is the current workflow?",
      "timestamp": "2026-01-02T10:01:00Z",
      "tool_calls": null
    },
    {
      "message_id": "msg-002",
      "role": "assistant",
      "content": "Let me check...",
      "timestamp": "2026-01-02T10:01:15Z",
      "tool_calls": [...]
    }
  ],
  "total": 12,
  "offset": 0,
  "limit": 50
}
```

---

### 6. Delete a Session

```bash
SESSION_ID="agx-a1b2c3d4e5f67890abcdef1234567890"

curl -X DELETE "http://localhost:8188/agentx/sessions/$SESSION_ID"
```

**Response**: `204 No Content`

---

## Advanced Configuration

### External MCP Servers

Add external MCP servers to `.env`:

```bash
# Filesystem access (stdio)
AGENTX_MCP_FILESYSTEM_TYPE=stdio
AGENTX_MCP_FILESYSTEM_COMMAND=npx
AGENTX_MCP_FILESYSTEM_ARGS=-y,@modelcontextprotocol/server-filesystem,/workspace

# Remote tools (SSE)
AGENTX_MCP_REMOTE_TYPE=sse
AGENTX_MCP_REMOTE_URL=http://localhost:3000/sse
```

**Or configure via JSON**:

Create `mcp_servers.json`:
```json
[
  {
    "name": "filesystem",
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
  },
  {
    "name": "fetch",
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-fetch"]
  }
]
```

Set in `.env`:
```bash
AGENTX_MCP_SERVERS_FILE=./mcp_servers.json
```

---

### Custom Tool Development

Create custom MCP tools in `backend/agentx/mcp_tools/custom_tools.py`:

```python
from fastmcp import FastMCP

mcp = FastMCP("custom")

@mcp.tool()
async def analyze_image(image_path: str) -> str:
    """Analyze an image using computer vision"""
    # Your implementation here
    return f"Analysis of {image_path}: ..."

@mcp.tool()
async def optimize_workflow(workflow_json: str) -> str:
    """Optimize a workflow for performance"""
    # Your implementation here
    return "Optimized workflow: ..."
```

Register in `backend/agentx/config.py`:
```python
CUSTOM_MCP_MODULES = [
    "backend.agentx.mcp_tools.custom_tools"
]
```

---

## Troubleshooting

### Issue: "ANTHROPIC_API_KEY not set"

**Solution**: Create `.env` file with valid API key:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
```

---

### Issue: "Database locked"

**Cause**: Multiple ComfyUI instances accessing same SQLite database.

**Solution**: Use unique database per instance:
```bash
AGENTX_DATABASE_URL=sqlite:///agentx_sessions_instance1.db
```

---

### Issue: "MCP server 'comfyui' failed to start"

**Cause**: Missing dependencies or import errors.

**Solution**: Check logs and reinstall:
```bash
pip install --force-reinstall -r requirements.txt
```

---

### Issue: "WebSocket connection closed immediately"

**Cause**: Invalid session_id.

**Solution**: Create session first via POST `/sessions`, then connect WebSocket.

---

### Issue: Tool calls timing out

**Increase timeout in `.env`**:
```bash
AGENTX_TOOL_TIMEOUT=300  # 5 minutes
```

---

## Performance Tuning

### For Large Workspaces

```bash
# Increase queue size for high-throughput
AGENTX_EVENT_QUEUE_MAXSIZE=5000

# Enable database connection pooling
AGENTX_DB_POOL_SIZE=10
AGENTX_DB_MAX_OVERFLOW=20
```

### For Memory-Constrained Systems

```bash
# Reduce max tokens
AGENTX_MAX_TOKENS=2048

# Disable event logging
AGENTX_ENABLE_EVENT_LOGGING=false

# Limit message history loaded per session
AGENTX_MESSAGE_LOAD_PAGE_SIZE=50
```

---

## Development

### Running Tests

```bash
# Unit tests
pytest tests/agentx/

# Integration tests
pytest tests/integration/

# With coverage
pytest --cov=backend/agentx tests/
```

### Hot Reload (Development Mode)

```bash
# Start ComfyUI with auto-reload on code changes
watchmedo auto-restart --patterns="*.py" --recursive -- python main.py
```

### Debugging

Enable debug logging:
```bash
AGENTX_LOG_LEVEL=DEBUG
```

View detailed MCP messages:
```bash
AGENTX_MCP_LOG_LEVEL=DEBUG
```

---

## API Reference

Full API documentation:
- **OpenAPI Spec**: See `contracts/agentx-api.yaml`
- **Interactive Docs**: http://localhost:8188/agentx/docs (Swagger UI)
- **MCP Tools**: See `contracts/comfyui-tools.yaml`
- **Data Models**: See `data-model.md`

---

## Next Steps

- **Explore Examples**: See `examples/` directory for full workflow scenarios
- **Frontend Integration**: Connect to AgentX from React/Vue/Svelte
- **Custom Tools**: Extend functionality with your own MCP tools
- **Production Deployment**: See `deployment.md` for best practices

---

## Support

- **Issues**: https://github.com/your-org/ComfyUI-Copilot/issues
- **Discussions**: https://github.com/your-org/ComfyUI-Copilot/discussions
- **Discord**: https://discord.gg/your-invite

---

**Version**: 1.0.0
**Last Updated**: 2026-01-02
