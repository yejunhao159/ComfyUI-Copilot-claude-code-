# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

ComfyUI-AgentX is an AI Agent for ComfyUI workflow debugging and manipulation, powered by Claude. It runs as a ComfyUI custom node, providing Python backend with AgentX runtime.

## Architecture

```
ComfyUI-AgentX/
├── __init__.py                    # ComfyUI entry point, registers routes
├── backend/
│   ├── agentx/                    # AgentX runtime (core)
│   │   ├── runtime/               # Event-driven agent engine
│   │   │   ├── agent_engine.py    # Claude API integration
│   │   │   ├── container.py       # Session management
│   │   │   ├── event_bus.py       # Pub/Sub events
│   │   │   └── types.py           # Type definitions
│   │   ├── api/
│   │   │   └── server.py          # HTTP/WebSocket API
│   │   ├── persistence/           # SQLAlchemy + SQLite
│   │   ├── mcp_tools/             # ComfyUI tools (TODO: implement)
│   │   └── config.py              # Configuration
│   ├── dao/
│   │   └── workflow_table.py      # Workflow persistence
│   └── utils/
│       ├── comfy_gateway.py       # ComfyUI API bridge
│       ├── globals.py             # Global config
│       └── logger.py              # Logging
└── tests/                         # Unit tests
```

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

## API Endpoints

All endpoints are registered under `/api/agentx/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sessions` | POST | Create session |
| `/sessions` | GET | List sessions |
| `/sessions/{id}` | GET | Get session |
| `/sessions/{id}/messages` | POST | Send message |
| `/sessions/{id}/stream` | WS | Event stream |
| `/health` | GET | Health check |

## Configuration

Environment variables (`.env`):

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `AGENTX_MODEL` | No | Model (default: claude-sonnet-4-20250514) |
| `AGENTX_MAX_TOKENS` | No | Max tokens (default: 4096) |
| `AGENTX_LOG_LEVEL` | No | Log level (default: INFO) |

## Development Tasks

### TODO: ComfyUI Tools Implementation

The `backend/agentx/mcp_tools/comfyui_tools.py` has placeholder implementations. Need to implement:

1. `get_workflow()` - Get current workflow from ComfyUI
2. `update_workflow()` - Update workflow
3. `search_nodes()` - Search available nodes
4. `execute_workflow()` - Execute workflow
5. `get_execution_result()` - Get execution results

Reference implementation in `backend/utils/comfy_gateway.py`.

### TODO: UI Integration

Need to build and serve `@agentxjs/ui` as static files in `dist/agentx_web/`.
