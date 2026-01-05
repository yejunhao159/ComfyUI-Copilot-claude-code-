# AgentX Runtime V2

完整的 Python AgentX 运行时环境，为 ComfyUI 提供 True Agentic Loop 能力。

## 特性

- **True Agentic Loop**: 基于 claude-agent-sdk 的自主智能体循环
- **事件驱动架构**: 基于 SystemBus 的 Pub/Sub 系统
- **4层事件系统**: Stream (文本流) / State (状态) / Message (消息) / Turn (对话轮次)
- **HTTP Streaming**: NDJSON 格式的实时数据流
- **Claude SDK 集成**: 支持流式生成、工具调用和 MCP 协议
- **RESTful API**: aiohttp-based HTTP 服务器

## 安装

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

关键依赖:
- `claude-agent-sdk>=0.1.18` - Claude Agent SDK (True Agentic Loop)
- `aiohttp>=3.8.0` - 异步 HTTP 服务器
- `python-dotenv` - 环境变量管理

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
AGENTX_MODEL=claude-sonnet-4-20250514
AGENTX_LOG_LEVEL=INFO
```

## 使用

### 方式 1: 作为 ComfyUI 插件

将整个目录放入 ComfyUI 的 `custom_nodes` 目录，重启 ComfyUI。

服务器启动后可访问:
- `POST /api/agentx/sessions` - 创建会话
- `POST /api/agentx/sessions/{id}/chat` - HTTP Streaming 聊天 (推荐)
- `POST /api/agentx/sessions/{id}/messages` - 发送消息 (非流式)
- `GET /api/agentx/health` - 健康检查

### 方式 2: 编程接口

```python
import asyncio
from backend.agentx.runtime_v2 import (
    create_runtime,
    RuntimeConfig,
)

async def main():
    # 创建 Runtime
    runtime = await create_runtime(RuntimeConfig(
        api_key="your-api-key",
        model="claude-sonnet-4-20250514",
        system_prompt="You are a ComfyUI workflow assistant.",
    ))

    # Quick start - 创建 Container 和 Agent
    container, agent = await runtime.quick_start()

    # 订阅事件
    def on_text(event):
        text = event.data.get("text", "") if isinstance(event.data, dict) else ""
        print(text, end="", flush=True)

    runtime.events.on("text_delta", on_text)

    # 发送消息 - SDK 自动处理 Agentic Loop
    await agent.receive("Help me create a simple image generation workflow")

    # 清理
    await runtime.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

## API 文档

### 创建会话

```http
POST /api/agentx/sessions
Content-Type: application/json

{
  "system": "Optional system prompt override"
}
```

响应:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_id": "agent_abc123",
  "created_at": "2025-01-02T10:00:00Z",
  "state": "idle"
}
```

### HTTP Streaming 聊天 (推荐)

```http
POST /api/agentx/sessions/{session_id}/chat
Content-Type: application/json

{
  "content": "Help me debug this workflow",
  "system": "Optional system prompt"
}
```

响应 (NDJSON 流):
```
{"type": "start", "turn_id": "..."}
{"type": "state", "state": "thinking"}
{"type": "text", "content": "I'll help you..."}
{"type": "tool_start", "tool_id": "...", "name": "get_workflow"}
{"type": "tool_end", "tool_id": "...", "result": {...}}
{"type": "done", "content": "Full response", "duration_ms": 1234}
```

### JavaScript 客户端示例

```javascript
async function chat(sessionId, content) {
  const response = await fetch(`/api/agentx/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const lines = decoder.decode(value).split('\n');
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);

      switch (event.type) {
        case 'text':
          process.stdout.write(event.content);
          break;
        case 'state':
          console.log('State:', event.state);
          break;
        case 'done':
          console.log('\nComplete:', event.duration_ms, 'ms');
          break;
      }
    }
  }
}
```

## 架构

```
backend/agentx/
├── config.py                 # 配置管理
├── runtime_v2/               # V2 运行时 (True Agentic Loop)
│   ├── types.py              # 核心类型定义
│   ├── system_bus.py         # 事件总线 (Pub/Sub)
│   ├── agent.py              # RuntimeAgent 实现
│   ├── container.py          # RuntimeContainer (Image → Agent)
│   ├── environment.py        # Claude SDK 集成 (Receptor/Effector)
│   ├── runtime.py            # Runtime 入口
│   └── mcp_integration.py    # MCP 工具集成
├── mcp_tools/
│   └── comfyui_tools.py      # ComfyUI 工具定义
└── api/
    └── server_v2.py          # HTTP Streaming 服务器
```

### 核心概念

- **Runtime**: 顶层入口，管理 Containers 和事件总线
- **Container**: Agent 的隔离环境，管理 Image → Agent 映射
- **Agent**: 完整的运行时实体，包含 Engine + Environment + Session
- **SystemBus**: 中央事件总线，所有组件通过它通信
- **Environment**: Receptor (感知 SDK 响应) + Effector (发送到 SDK)

### True Agentic Loop

```
┌──────────────────────────────────────────────────────────────┐
│                    claude-agent-sdk                           │
│                                                               │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐      │
│   │   Gather   │────▶│    Take    │────▶│   Verify   │──┐   │
│   │  Context   │     │   Action   │     │    Work    │  │   │
│   └────────────┘     └────────────┘     └────────────┘  │   │
│         ▲                                               │   │
│         └───────────────────────────────────────────────┘   │
│                         Repeat until done                    │
└──────────────────────────────────────────────────────────────┘
```

SDK 内部自动处理整个循环，我们只需要:
1. 订阅 SystemBus 事件
2. 发送 user_message
3. 接收流式响应

## 故障排除

### ImportError: No module named 'claude_agent_sdk'

安装 Claude Agent SDK:
```bash
pip3 install claude-agent-sdk
```

### API Key 错误

确保 `.env` 文件中设置了正确的 API Key:
```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可

MIT License
