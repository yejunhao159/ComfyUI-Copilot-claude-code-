# Research: ComfyUI-AgentX 完整运行时

**Feature**: ComfyUI-AgentX Runtime
**Date**: 2026-01-02
**Status**: Complete

## 研究目标

1. AgentX 架构核心设计模式的 Python 移植方案
2. Python 中 MCP (Model Context Protocol) 的最佳实践
3. 事件驱动架构在 Python/asyncio 中的实现
4. 会话持久化和 SQLite 存储策略

---

## R1: AgentX 架构核心设计

### Decision

采用分层架构设计,将 AgentX 的 4 层事件系统(Stream/State/Message/Turn)移植到 Python,使用 asyncio 原生支持。

### Rationale

**AgentX TypeScript 架构分析**:
- **事件驱动**: 使用 RxJS Observable 实现响应式事件流
- **分层设计**: Runtime → Agent → MCP → Environment 清晰分离
- **流式处理**: Stream 事件实时传递 LLM token,State 事件跟踪工具调用

**Python 移植策略**:
- RxJS Observable → Python AsyncIterator/AsyncGenerator
- TypeScript Event Emitter → Python asyncio.Queue + Pub/Sub
- Promise → Python Coroutine/Task
- 保留 4 层事件分类,便于前端理解和调试

### Alternatives Considered

**方案 A**: 使用 RxPY (Python 的 RxJS 移植)
- ❌ 引入额外依赖,学习曲线陡峭
- ❌ 与 asyncio 集成不够自然
- ✅ 与 AgentX TypeScript 语义一致

**方案 B**: 使用纯 asyncio (选择)
- ✅ Python 标准库,无额外依赖
- ✅ 与 aiohttp 无缝集成
- ✅ 性能更好,内存占用更小
- ❌ 需要手动实现 Pub/Sub 模式

**方案 C**: 使用 Celery 任务队列
- ❌ 过度工程化,引入 Redis/RabbitMQ
- ❌ 不适合实时流式场景

### Python Implementation Notes

**事件总线实现**:
```python
class EventBus:
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._queue: asyncio.Queue = asyncio.Queue()

    async def publish(self, event: AgentEvent):
        await self._queue.put(event)
        for handler in self._subscribers[event.type]:
            asyncio.create_task(handler(event))

    async def consume(self) -> AsyncIterator[AgentEvent]:
        while True:
            event = await self._queue.get()
            yield event
```

**流式生成器**:
```python
async def process_message(message: str) -> AsyncIterator[AgentEvent]:
    # Stream 事件
    async for token in claude_api.stream(message):
        yield AgentEvent(type=EventType.STREAM, data=token)

    # State 事件 (工具调用)
    yield AgentEvent(type=EventType.STATE, data={"state": "calling_tool"})

    # Message 事件 (完成)
    yield AgentEvent(type=EventType.MESSAGE, data=full_message)
```

---

## R2: Python MCP 最佳实践

### Decision

使用 `fastmcp` 库作为基础,扩展支持 stdio 和 SSE 两种 MCP 服务器类型,复用现有的 `mcp_client.py`(SSE 客户端)。

### Rationale

**现状分析**:
- ComfyUI-Copilot 已有 `backend/service/mcp_client.py`,实现了 SSE MCP 客户端
- 使用 `MCPServerSse` 类连接远程 MCP 服务器
- 缺少 stdio MCP 服务器管理能力

**MCP 协议核心**:
- **Tools**: `tools/list`, `tools/call` - 工具发现和调用
- **Resources**: `resources/list`, `resources/read` - 资源访问
- **Prompts**: `prompts/list`, `prompts/get` - 提示模板

**Python 生态**:
- `fastmcp` - MCP 服务器框架,类似 FastAPI
- `anthropic-sdk` - Claude API,原生支持 MCP 工具格式
- 手动实现 stdio 服务器管理(subprocess)

### Alternatives Considered

**方案 A**: 完全手动实现 MCP 协议
- ❌ 重复造轮子,维护成本高
- ❌ 协议规范更新需要同步跟进
- ✅ 完全控制,无依赖

**方案 B**: 使用 fastmcp + 手动 stdio 管理 (选择)
- ✅ MCP 服务器注册简单(装饰器风格)
- ✅ 自动生成 JSON Schema
- ✅ 复用现有 SSE 客户端代码
- ❌ stdio 服务器需要手动实现生命周期管理

**方案 C**: 等待官方 Python MCP SDK
- ❌ 时间线不确定
- ❌ 可能不符合 ComfyUI 集成需求

### Python Implementation Notes

**Stdio MCP Server 生命周期**:
```python
class StdioMCPServer:
    async def start(self):
        self.process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

    async def call_tool(self, name: str, args: Dict) -> Any:
        request = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": name, "arguments": args}}
        self.process.stdin.write((json.dumps(request) + "\n").encode())
        await self.process.stdin.drain()

        response = await self.process.stdout.readline()
        return json.loads(response)

    async def stop(self):
        self.process.terminate()
        await self.process.wait()
```

**ComfyUI 工具注册**:
```python
from fastmcp import FastMCP

mcp = FastMCP("comfyui")

@mcp.tool()
async def get_workflow() -> str:
    """获取当前工作流"""
    from ...service.workflow_rewrite_tools import get_current_workflow
    return await get_current_workflow()

@mcp.tool()
async def update_workflow(workflow_data: str, description: str = "") -> str:
    """更新工作流并创建检查点"""
    from ...service.workflow_rewrite_tools import update_workflow
    return await update_workflow(workflow_data, description)
```

**工具桥接到 Claude**:
```python
def mcp_to_claude_tools(mcp_tools: List[MCPTool]) -> List[Dict]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema  # 直接使用 MCP JSON Schema
        }
        for tool in mcp_tools
    ]
```

---

## R3: 事件驱动 Python 模式

### Decision

使用 `asyncio.Queue` + 自定义 Pub/Sub 实现事件总线,配合 `AsyncIterator` 实现流式事件生成和消费。

### Rationale

**需求分析**:
- 实时事件流: LLM token 逐个推送
- 多订阅者: WebSocket 客户端、日志系统、持久化
- 背压处理: 慢消费者不应阻塞生产者
- 错误隔离: 单个订阅者异常不影响其他订阅者

**Python 异步模式对比**:

| 模式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| asyncio.Queue | 标准库,简单 | 单消费者 | 点对点通信 |
| Pub/Sub (custom) | 多订阅者,解耦 | 需要手动实现 | 事件广播 |
| AsyncIterator | 流式,惰性 | 只能迭代一次 | 生成器模式 |
| aiohttp.web.Application.on_* | 集成 aiohttp | 耦合框架 | HTTP 生命周期 |

**选择 Queue + Pub/Sub 组合**:
- Queue: 事件缓冲,防止丢失
- Pub/Sub: 广播给多个订阅者
- AsyncIterator: 流式生成事件

### Alternatives Considered

**方案 A**: RxPY (Reactive Extensions for Python)
- ✅ 功能强大,操作符丰富
- ❌ 学习曲线陡峭
- ❌ 依赖较大,不适合插件环境

**方案 B**: asyncio 原生 (选择)
- ✅ 零依赖,与 aiohttp 完美集成
- ✅ 性能优秀,内存占用低
- ❌ 需要手动实现 Pub/Sub

**方案 C**: Redis Pub/Sub
- ❌ 引入外部依赖(Redis)
- ❌ 网络开销,不适合本地场景
- ✅ 跨进程通信能力(未来可能需要)

### Python Implementation Notes

**背压处理**:
```python
class EventBus:
    async def publish(self, event: AgentEvent):
        # 有界队列,防止内存溢出
        try:
            await asyncio.wait_for(self._queue.put(event), timeout=1.0)
        except asyncio.TimeoutError:
            # 队列满,丢弃事件或记录警告
            logger.warning(f"Event queue full, dropping {event.type}")

        # 异步通知订阅者,不阻塞生产者
        for handler in self._subscribers[event.type]:
            asyncio.create_task(self._safe_call(handler, event))

    async def _safe_call(self, handler, event):
        try:
            await handler(event)
        except Exception as e:
            # 隔离订阅者异常
            logger.error(f"Subscriber error: {e}")
```

**WebSocket 事件推送**:
```python
async def forward_events_to_websocket(session_id: str, ws: web.WebSocketResponse):
    async for event in event_bus.consume():
        if event.session_id == session_id:
            await ws.send_json({
                "type": "agent_event",
                "event": event.to_dict()
            })
```

---

## R4: SQLite 会话持久化

### Decision

使用 SQLAlchemy 2.0 ORM + SQLite,设计 3 表结构: `agent_sessions`, `agent_messages`, `agent_events`(可选)。

### Rationale

**持久化需求**:
- 会话管理: 创建、加载、列表、删除
- 消息历史: 完整对话记录(用户+助手+工具调用)
- 事件日志: (可选)调试和回放

**SQLite 优势**:
- ✅ 零配置,单文件数据库
- ✅ 支持并发读,串行写(适合单用户场景)
- ✅ ACID 事务,数据安全
- ✅ Python 标准库内置

**SQLAlchemy 优势**:
- ✅ ORM 抽象,易于维护
- ✅ 已在 ComfyUI-Copilot 中使用
- ✅ 支持迁移(alembic)

### Alternatives Considered

**方案 A**: JSON 文件存储
- ❌ 无并发控制
- ❌ 查询效率低(需要全文件读取)
- ✅ 简单,易于调试

**方案 B**: SQLite + SQLAlchemy (选择)
- ✅ 结构化查询,高效索引
- ✅ 事务支持,数据一致性
- ✅ 与现有代码库一致

**方案 C**: PostgreSQL
- ❌ 需要独立数据库服务
- ❌ 部署复杂,不适合插件
- ✅ 高并发,高性能(overkill)

### Python Implementation Notes

**数据模型设计**:
```python
class AgentSessionModel(Base):
    __tablename__ = "agent_sessions"
    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    state = Column(String(32))  # idle, processing, waiting_for_tool
    config = Column(JSON)  # model, max_tokens, etc.

class AgentMessageModel(Base):
    __tablename__ = "agent_messages"
    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), ForeignKey("agent_sessions.session_id"), index=True)
    role = Column(String(16))  # user, assistant
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    tool_calls = Column(JSON)  # [{name, arguments, result}, ...]
```

**批量加载优化**:
```python
def load_session_with_messages(session_id: str) -> AgentSession:
    with Session() as db:
        # 使用 joinedload 避免 N+1 查询
        session_model = db.query(AgentSessionModel).options(
            joinedload(AgentSessionModel.messages)
        ).filter_by(session_id=session_id).first()

        return AgentSession.from_model(session_model)
```

**消息分页**:
```python
def get_messages_paginated(session_id: str, offset: int = 0, limit: int = 100):
    with Session() as db:
        return db.query(AgentMessageModel).filter_by(
            session_id=session_id
        ).order_by(AgentMessageModel.timestamp).offset(offset).limit(limit).all()
```

---

## 集成决策汇总

### 核心技术栈

| 组件 | 技术选型 | 原因 |
|------|---------|------|
| 事件驱动 | asyncio.Queue + Pub/Sub | 零依赖,与 aiohttp 集成 |
| MCP 服务器 | fastmcp + 手动 stdio 管理 | 简化注册,自动 schema 生成 |
| MCP 客户端 | 复用现有 mcp_client.py | SSE 客户端已实现 |
| 持久化 | SQLAlchemy + SQLite | 与现有代码一致,零配置 |
| WebSocket | aiohttp.web.WebSocketResponse | 框架内置,无额外依赖 |
| Claude API | anthropic SDK | 官方 SDK,流式支持 |

### 架构映射 (TypeScript → Python)

| AgentX (TypeScript) | ComfyUI-AgentX (Python) |
|---------------------|-------------------------|
| RxJS Observable | AsyncIterator + asyncio.Queue |
| Event Emitter | Pub/Sub + asyncio.create_task |
| Promise | Coroutine + asyncio.Task |
| fetch() streaming | anthropic.messages.stream() |
| WebSocket (ws) | aiohttp.web.WebSocketResponse |
| IndexedDB | SQLite + SQLAlchemy |
| TypeScript interfaces | Python dataclasses + typing |

### 性能优化策略

1. **事件背压**: 有界队列(maxsize=1000),超时丢弃
2. **数据库连接池**: SQLAlchemy pool_size=5, max_overflow=10
3. **消息分页**: 每页 100 条,避免一次加载全部历史
4. **异步工具调用**: asyncio.gather 并发执行多个工具
5. **WebSocket 心跳**: 30 秒 ping/pong,检测断线

---

## 风险缓解

| 风险 | 缓解措施 |
|------|---------|
| 事件队列溢出 | 有界队列 + 超时丢弃 + 监控告警 |
| SQLite 写锁竞争 | 串行写入队列 + 批量提交 |
| WebSocket 断线 | 自动重连 + 会话恢复 |
| Claude API 限流 | 指数退避重试 + 请求队列 |
| MCP 服务器崩溃 | 健康检查 + 自动重启 + 降级处理 |

---

## 参考资料

- [AgentX GitHub](https://github.com/Deepractice/AgentX)
- [MCP Protocol Spec](https://github.com/anthropics/mcp)
- [fastmcp Documentation](https://github.com/jlowin/fastmcp)
- [Python asyncio Docs](https://docs.python.org/3/library/asyncio.html)
- [aiohttp WebSocket Guide](https://docs.aiohttp.org/en/stable/web_quickstart.html#websockets)
- [SQLAlchemy 2.0 Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/)

---

**Status**: ✅ Research Complete - Ready for Phase 1 Design
**Date**: 2026-01-02
