# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

ComfyUI-AgentX is an AI Agent for ComfyUI workflow debugging and manipulation, powered by Claude. It runs as a ComfyUI custom node, providing Python backend with AgentX runtime V2.

## Architecture (V2)

```
ComfyUI-AgentX/
├── __init__.py                    # ComfyUI entry point, registers routes
├── backend/
│   ├── agentx/                    # AgentX runtime (core)
│   │   ├── runtime_v2/            # V2 Event-driven agent engine
│   │   │   ├── runtime.py         # Top-level Runtime API
│   │   │   ├── container.py       # Container - manages Agent instances
│   │   │   ├── agent.py           # RuntimeAgent - complete agent entity
│   │   │   ├── environment.py     # Claude SDK integration (Receptor/Effector)
│   │   │   ├── system_bus.py      # Pub/Sub event bus
│   │   │   ├── types.py           # Type definitions
│   │   │   └── mcp_integration.py # MCP tools integration
│   │   ├── api/
│   │   │   └── server_v2.py       # HTTP Streaming API (NDJSON)
│   │   ├── persistence/           # SQLAlchemy + SQLite
│   │   ├── mcp_tools/             # ComfyUI tools
│   │   │   ├── comfyui_tools.py   # Tool definitions
│   │   │   └── tools/             # Individual tool implementations
│   │   └── config.py              # Configuration
│   ├── dao/
│   │   └── workflow_table.py      # Workflow persistence
│   └── utils/
│       ├── comfy_gateway.py       # ComfyUI API bridge
│       ├── globals.py             # Global config
│       └── logger.py              # Structured logging
├── web/
│   └── js/
│       └── agentx_extension.js    # ComfyUI sidebar extension
└── tests/                         # Unit tests
```

### V2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         AgentX Runtime                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────┐     ┌──────────┐     ┌──────────────────────┐   │
│   │ Runtime │────▶│Container │────▶│ Agent (RuntimeAgent) │   │
│   └─────────┘     └──────────┘     └──────────────────────┘   │
│        │               │                      │                │
│        │               │           ┌──────────┴──────────┐    │
│        │               │           │                     │    │
│        ▼               ▼           ▼                     ▼    │
│   ┌─────────┐   ┌──────────┐  ┌─────────┐      ┌──────────┐  │
│   │SystemBus│◀──│ Session  │  │ Engine  │      │Environment│  │
│   └─────────┘   └──────────┘  └─────────┘      └──────────┘  │
│        │                           │                  │       │
│        │                           │           ┌──────┴─────┐ │
│        │                           │           │            │ │
│        ▼                           ▼           ▼            ▼ │
│   ┌─────────┐              ┌──────────┐  ┌────────┐  ┌───────┐│
│   │ Events  │              │Claude SDK│  │Receptor│  │Effector│
│   │ (Pub/Sub│              │(Agentic  │  │(in)    │  │(out)   ││
│   └─────────┘              │ Loop)    │  └────────┘  └───────┘│
│                            └──────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### Key Concepts (V2)

- **Runtime**: Top-level entry point, manages Containers
- **Container**: Runtime isolation boundary, manages Agent lifecycle
- **RuntimeAgent**: Complete agent entity (LLM + Session + Environment)
- **SystemBus**: Central event bus for component communication
- **Environment**: Claude SDK integration via Receptor (perceive) + Effector (act)
- **Agentic Loop**: Handled by claude-agent-sdk (Gather Context → Take Action → Verify → Repeat)

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Initialize database
cd backend/agentx/persistence
alembic upgrade head
```

## API Endpoints (V2)

All endpoints are registered under `/api/agentx/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sessions` | POST | Create session |
| `/sessions` | GET | List sessions |
| `/sessions/{id}` | GET | Get session |
| `/sessions/{id}/messages` | GET | Get message history |
| `/sessions/{id}/messages` | POST | Send message (non-streaming) |
| `/sessions/{id}/chat` | POST | **Chat with streaming (NDJSON)** |
| `/sync/workflow` | POST | Sync workflow from frontend |
| `/sync/workflow` | GET | Get current workflow |
| `/logs` | GET | Get execution logs |
| `/logs` | DELETE | Clear logs |
| `/health` | GET | Health check |

### Streaming Response Format (NDJSON)

```json
{"type": "start", "turn_id": "..."}
{"type": "state", "state": "thinking"}
{"type": "text", "content": "partial text"}
{"type": "tool_start", "tool_id": "...", "name": "..."}
{"type": "tool_end", "tool_id": "...", "result": {...}}
{"type": "done", "content": "full text", "executed_tools": [...]}
{"type": "error", "message": "error message"}
```

## Configuration

Environment variables (`.env`):

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `ANTHROPIC_BASE_URL` | No | Custom API base URL |
| `AGENTX_MODEL` | No | Model (default: claude-sonnet-4-20250514) |
| `AGENTX_MAX_TOKENS` | No | Max tokens (default: 4096) |
| `AGENTX_LOG_LEVEL` | No | Log level (default: INFO) |

## Dependencies

Key dependencies in `requirements.txt`:
- `anthropic>=0.40.0` - Anthropic Python SDK
- `claude-agent-sdk>=0.1.18` - Claude Agent SDK for Agentic Loop
- `aiohttp>=3.8.0` - Async HTTP server
- `sqlalchemy>=1.4.0,<2.0` - Database ORM

## Development Tasks

### TODO: ComfyUI Tools Enhancement

The `backend/agentx/mcp_tools/` contains tool implementations. Current tools:

- `workflow_tools.py` - Workflow manipulation
- `node_tools.py` - Node operations
- `search_tools.py` - Node search
- `execution_tools.py` - Workflow execution
- `image_tools.py` - Image handling
- `validation_tools.py` - Workflow validation
- `system_tools.py` - System operations

Reference implementation in `backend/utils/comfy_gateway.py`.

### TODO: UI Integration

UI is embedded via ComfyUI extension system:
- `web/js/agentx_extension.js` - Sidebar panel extension
- Communicates with backend via `/api/agentx/` endpoints
