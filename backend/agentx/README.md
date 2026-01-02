# AgentX Runtime

完整的 Python AgentX 运行时环境，为 ComfyUI 提供 Claude Code 能力。

## 特性

- **事件驱动架构**: 基于 asyncio.Queue 的 Pub/Sub 系统
- **4层事件系统**: Stream (文本流) / State (状态) / Message (消息) / Turn (对话轮次)
- **Claude API 集成**: 支持流式生成和工具调用
- **持久化会话**: SQLAlchemy + SQLite 会话管理
- **MCP 协议支持**: 内置 ComfyUI 工具集成
- **RESTful API**: aiohttp-based HTTP + WebSocket 服务器

## 安装

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

关键依赖:
- `anthropic>=0.40.0` - Claude API SDK
- `aiohttp>=3.8.0` - 异步 HTTP 服务器
- `sqlalchemy>=1.4.0,<2.0` - 数据库 ORM
- `alembic>=1.13.0` - 数据库迁移
- `fastmcp` - MCP 服务器框架

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并填入你的配置:

```bash
cp .env.example .env
```

最小配置（必需）:
```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

可选配置:
```env
AGENTX_MODEL=claude-3-5-sonnet-20241022
AGENTX_MAX_TOKENS=4096
AGENTX_DATABASE_URL=sqlite:///agentx_sessions.db
AGENTX_LOG_LEVEL=INFO
```

### 3. 初始化数据库

```bash
cd backend/agentx/persistence
alembic upgrade head
```

## 使用

### 方式 1: 独立 API 服务器

```bash
python3 -m backend.agentx.cli --host 0.0.0.0 --port 8000
```

服务器启动后可访问:
- `POST /api/agentx/sessions` - 创建会话
- `POST /api/agentx/sessions/{id}/messages` - 发送消息
- `WS /api/agentx/sessions/{id}/stream` - 事件流

### 方式 2: 编程接口

```python
import asyncio
from backend.agentx.config import AgentConfig
from backend.agentx.runtime import EventBus, AgentEngine, Container
from backend.agentx.persistence import PersistenceService

async def main():
    # 加载配置
    config = AgentConfig.from_env()

    # 初始化组件
    event_bus = EventBus(maxsize=1000)
    await event_bus.start()

    persistence = PersistenceService(config)
    agent_engine = AgentEngine(config, event_bus)
    container = Container(config, event_bus, agent_engine, persistence)

    # 创建会话
    session = await container.create_session(
        user_id="user-123",
        title="My Debug Session"
    )

    # 发送消息
    response = await container.send_message(
        session_id=session.session_id,
        content="Help me debug this ComfyUI workflow"
    )

    print(f"Response: {response.content}")

    # 清理
    await event_bus.stop()
    await agent_engine.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## API 文档

### 创建会话

```http
POST /api/agentx/sessions
Content-Type: application/json

{
  "user_id": "user-123",
  "title": "Debug Session",
  "config": {}
}
```

响应:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2025-01-02T10:00:00Z",
  "state": "idle",
  "message_count": 0
}
```

### 发送消息

```http
POST /api/agentx/sessions/{session_id}/messages
Content-Type: application/json

{
  "content": "Help me debug this workflow",
  "system": "You are a ComfyUI debugging expert"
}
```

响应:
```json
{
  "message_id": "msg-123",
  "role": "assistant",
  "content": "I'll help you debug...",
  "tool_calls": [],
  "input_tokens": 100,
  "output_tokens": 50
}
```

### WebSocket 事件流

```javascript
const ws = new WebSocket('ws://localhost:8000/api/agentx/sessions/{id}/stream');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case 'stream':
      console.log('Token:', data.data);
      break;
    case 'state':
      console.log('State:', data.data.state);
      break;
    case 'message':
      console.log('Message:', data.data.content);
      break;
    case 'turn':
      console.log('Turn complete:', data.data.duration_ms, 'ms');
      break;
  }
};
```

## 架构

```
backend/agentx/
├── config.py              # 配置管理
├── runtime/
│   ├── types.py           # 核心类型定义
│   ├── event_bus.py       # 事件总线 (Pub/Sub)
│   ├── agent_engine.py    # Claude API 集成
│   └── container.py       # 会话管理器
├── persistence/
│   ├── models.py          # SQLAlchemy ORM 模型
│   ├── service.py         # 持久化服务
│   └── migrations/        # Alembic 迁移
├── mcp_tools/
│   └── comfyui_tools.py   # 内置 ComfyUI 工具
├── api/
│   └── server.py          # HTTP/WebSocket 服务器
└── cli.py                 # 命令行入口
```

## 开发

### 运行测试

```bash
# 快速验证
python3 backend/agentx/smoke_test.py

# 单元测试 (需要 pytest)
pytest tests/agentx/unit/ -v
```

### 数据库迁移

创建新迁移:
```bash
cd backend/agentx/persistence
alembic revision --autogenerate -m "Add new table"
```

应用迁移:
```bash
alembic upgrade head
```

回滚迁移:
```bash
alembic downgrade -1
```

## 故障排除

### ImportError: No module named 'anthropic'

安装 anthropic SDK:
```bash
pip3 install anthropic>=0.40.0
```

### Database locked error

SQLite 默认不支持高并发写入。对于生产环境，考虑使用 PostgreSQL:
```env
AGENTX_DATABASE_URL=postgresql://user:pass@localhost/agentx
```

### WebSocket connection failed

检查防火墙设置，确保端口 8000 可访问。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可

MIT License
