# ComfyUI-AgentX

AI Agent for ComfyUI workflow debugging and manipulation, powered by Claude.

Based on [Deepractice AgentX](https://github.com/Deepractice/AgentX) runtime.

## Features

- Claude-powered AI assistant for ComfyUI
- Workflow debugging and error analysis
- Node search and information lookup
- Workflow execution and result evaluation
- Real-time streaming responses via WebSocket

## Installation

1. Clone to ComfyUI custom_nodes:
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/user/ComfyUI-AgentX.git
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure API key:
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

4. Restart ComfyUI

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agentx/sessions` | POST | Create new session |
| `/api/agentx/sessions` | GET | List sessions |
| `/api/agentx/sessions/{id}` | GET | Get session details |
| `/api/agentx/sessions/{id}/messages` | POST | Send message |
| `/api/agentx/sessions/{id}/stream` | WS | WebSocket event stream |
| `/api/agentx/health` | GET | Health check |

## Configuration

Environment variables (`.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | Required |
| `AGENTX_MODEL` | Claude model | claude-sonnet-4-20250514 |
| `AGENTX_MAX_TOKENS` | Max response tokens | 4096 |
| `AGENTX_LOG_LEVEL` | Log level | INFO |

## Architecture

```
ComfyUI Server (localhost:8188)
├── /agentx_web/           → UI (static files)
└── /api/agentx/           → AgentX API
    ├── sessions           → Session management
    ├── messages           → Claude conversations
    └── ws/stream          → Real-time events
```

## License

MIT License
