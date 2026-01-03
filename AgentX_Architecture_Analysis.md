# AgentX 核心架构分析报告

> 研究对象: https://github.com/Deepractice/AgentX
> 分析日期: 2026-01-02
> 关键目标: 提取可移植到 Python 的核心设计模式和最佳实践

---

## 目录

1. [事件驱动架构 - 4层事件系统](#事件驱动架构---4层事件系统)
2. [MCP 集成 - 服务器管理](#mcp-集成---服务器管理)
3. [会话管理 - 持久化策略](#会话管理---持久化策略)
4. [WebSocket 通信 - 实时事件流](#websocket-通信---实时事件流)
5. [核心设计模式总结](#核心设计模式总结)
6. [Python 实现指南](#python-实现指南)

---

## 1. 事件驱动架构 - 4层事件系统

### 核心概念

AgentX 采用**分层事件驱动架构**，事件在两个域中流转:

```
┌─────────────────────────────────────────────────────────────┐
│                   AgentEngine 域 (轻量级)                     │
│  ┌─────────────┐                                              │
│  │StreamEvent  │ (LLM驱动的原始事件)                          │
│  └──────┬──────┘                                              │
│         │ 通过 MealyMachine 转换                              │
│         ▼                                                     │
│  ┌─────────────────────────────────────────┐                │
│  │        AgentOutput (聚合三类事件)         │                │
│  │  ├─ StateEvent (状态转换)                │                │
│  │  ├─ MessageEvent (消息组装)             │                │
│  │  └─ TurnEvent (轮次分析)                │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
└──────────────────────────┬───────────────────────────────────┘
                           │ 上升至 Runtime 域
┌──────────────────────────▼───────────────────────────────────┐
│              Runtime 域 (完整上下文)                          │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │      SystemEvent (扩展事件信息)           │               │
│  │  ├─ source (事件来源)                    │               │
│  │  ├─ category (分类标签)                  │               │
│  │  ├─ intent (执行意图)                    │               │
│  │  └─ context (完整上下文)                 │               │
│  └──────────────────────────────────────────┘               │
│                                                              │
│  衍生事件类型:                                              │
│  ├─ CommandEvent (命令事件/请求-响应)                      │
│  ├─ ConnectionEvent (连接事件)                            │
│  └─ DriveableEvent (驱动事件)                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 四层事件详解

#### 第1层: StreamEvent (流层)

**来源**: LLM 提供商 (Claude API)

**特征**:
- 原始流式数据
- 类型包括: `text_delta`, `tool_use`, `tool_result`
- 无状态上下文，仅包含增量数据

**示例结构**:
```typescript
interface StreamEvent {
  type: 'text_delta' | 'tool_use' | 'tool_result' | 'stop'
  timestamp: number
  data: {
    // 增量内容
  }
}
```

#### 第2层: StateEvent (状态层)

**生成器**: StateEventProcessor (Mealy机器内部)

**职责**: 驱动代理状态机转换

**状态映射** (11个事件 → 6个代理状态):
```
StreamEvent 输入      →  AgentState 输出
─────────────────────────────────────
thinking_started      →  thinking
thinking_finished     →  idle
response_started      →  responding
response_finished     →  idle
tool_call             →  planning_tool
tool_result_received  →  awaiting_tool_result
error_occurred        →  error
```

**设计特点**:
- 仅处理状态转换映射
- 不处理事件逻辑本身
- 订阅模式支持动态监听
- 错误隔离: 单个处理器故障不影响其他

#### 第3层: MessageEvent (消息层)

**生成器**: MessageAssembler (Mealy机器内部)

**职责**: 组装流式文本为完整消息

**数据结构**:
```typescript
interface Message {
  role: 'user' | 'assistant'
  content: Array<ContentPart>
  // ContentPart 包括:
  // - TextContent
  // - ThinkingContent
  // - ToolUseContent
  // - ToolResultContent
  // - ImageContent
  // - FileContent
}
```

**关键优化**:
- 流式文本增量缓冲
- 智能边界检测 (工具调用切分)
- 脏数据处理: 验证消息格式，确保返回数组

#### 第4层: TurnEvent (轮次层)

**生成器**: TurnTracker (Mealy机器内部)

**职责**: 分析单个请求-响应周期

**数据内容**:
```typescript
interface TurnEvent {
  turnId: string
  messageId: string
  inputTokens: number    // 计费统计
  outputTokens: number   // 计费统计
  duration: number       // 执行耗时
  toolCalls: ToolCall[]  // 工具调用追踪
  errors?: AgentError[]  // 错误记录
}
```

**用途**:
- 费用计算
- 性能分析
- 使用统计
- 调试追踪

### Mealy机器: 事件转换引擎

**核心原理**: `(state, input) → (state, output)`

**关键特性**:

1. **多代理隔离**
   - 单个MealyMachine实例为每个agentId维护独立状态
   - 通过MemoryStore实现安全的并发处理

2. **链式事件处理**
   ```
   StreamEvent
     ↓ MessageAssembler 处理
     ├→ MessageEvent (聚合消息)
     │
     └→ StateEventProcessor 处理
     │   ├→ StateEvent (状态转换)
     │   │
     │   └→ TurnTracker 处理
     │       └→ TurnEvent (轮次分析)
   ```

3. **状态与持久化分离**
   - 临时处理状态 (pendingContents等) 在机器内管理
   - 业务数据持久化由上层AgentEngine负责
   - 实现关注点清晰分离

4. **纯函数式设计**
   ```typescript
   process(agentId: string, event: StreamEvent): AgentOutput[] {
     // 无副作用纯函数
     // 输入 + 当前状态 → 新状态 + 输出事件数组
   }
   ```

### Decision

**事件驱动四层设计**通过Mealy机器实现流式事件的分层转换，每层承担特定职责。

#### Rationale

1. **关注点分离**: 每层处理特定的抽象级别
2. **可测试性**: 无副作用纯函数，易于单元测试
3. **组合性**: 处理器可灵活组合构建自定义流程
4. **隔离性**: 单个处理器故障不影响其他层级
5. **扩展性**: 支持注入自定义处理器

#### Alternatives considered

- **单层事件**: 无法处理流式事件的复杂性，无法追踪状态转换
- **嵌套回调**: 易陷入回调地狱，难以维护
- **Redux状态管理**: 过度设计，增加复杂性，不适合流式处理
- **观察者直连**: 无法实现事件的有序处理和链式转换

#### Python implementation notes

```python
# Python中的Mealy机器实现方向

from typing import Any, List, Tuple, Dict, Callable
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod

# 1. 事件基类 (支持四层结构)
@dataclass
class StreamEvent:
    """第1层: 原始流事件"""
    type: str
    timestamp: float
    data: Dict[str, Any]

@dataclass
class StateEvent:
    """第2层: 状态事件"""
    state: str
    timestamp: float
    source_event_id: str

@dataclass
class MessageEvent:
    """第3层: 消息事件"""
    message_id: str
    role: str
    content: List[Dict[str, Any]]
    timestamp: float

@dataclass
class TurnEvent:
    """第4层: 轮次事件"""
    turn_id: str
    input_tokens: int
    output_tokens: int
    duration: float
    metadata: Dict[str, Any]

# 2. Mealy机器处理器接口
class Processor(ABC):
    """处理器基类"""

    @abstractmethod
    def process(self, state: Dict[str, Any], event: StreamEvent) -> Tuple[Dict[str, Any], List[Any]]:
        """
        输入: (当前状态, 事件)
        输出: (新状态, 输出事件列表)
        """
        pass

# 3. 具体处理器实现
class MessageAssembler(Processor):
    """消息组装处理器"""

    def process(self, state: Dict[str, Any], event: StreamEvent) -> Tuple[Dict[str, Any], List[MessageEvent]]:
        new_state = state.copy()

        if event.type == 'text_delta':
            # 缓冲文本增量
            buffer = new_state.get('text_buffer', '')
            buffer += event.data.get('text', '')
            new_state['text_buffer'] = buffer

            # 检查是否应该生成消息
            if self._should_emit_message(event):
                message = MessageEvent(
                    message_id=self._generate_id(),
                    role='assistant',
                    content=[{'type': 'text', 'text': buffer}],
                    timestamp=event.timestamp
                )
                new_state['text_buffer'] = ''
                return new_state, [message]

        return new_state, []

    def _should_emit_message(self, event: StreamEvent) -> bool:
        # 判断消息是否应该生成 (例如: 流结束、工具调用边界)
        return event.data.get('is_final', False)

# 4. 事件流管道
class MealyMachine:
    """Mealy机器: 组合多个处理器"""

    def __init__(self, processors: List[Processor]):
        self.processors = processors
        self.agent_states: Dict[str, Dict[str, Any]] = {}  # 多代理隔离

    def process(self, agent_id: str, event: StreamEvent) -> List[Any]:
        """处理单个事件，返回所有生成的输出事件"""

        # 获取或初始化代理状态
        if agent_id not in self.agent_states:
            self.agent_states[agent_id] = self._init_state()

        state = self.agent_states[agent_id]
        outputs = []

        # 链式处理: 前一个处理器的输出作为后一个处理器的输入
        current_events = [event]

        for processor in self.processors:
            next_events = []
            for evt in current_events:
                state, processor_outputs = processor.process(state, evt)
                outputs.extend(processor_outputs)
                next_events.extend(processor_outputs)
            current_events = next_events

        # 保存更新的状态
        self.agent_states[agent_id] = state

        return outputs

    def _init_state(self) -> Dict[str, Any]:
        """初始化单个代理的状态"""
        return {
            'text_buffer': '',
            'current_state': 'idle',
            'turn_id': None,
            'tool_calls': []
        }

# 5. 处理器组合模式
class ChainedProcessor(Processor):
    """链式处理器: 串联多个处理器"""

    def __init__(self, *processors: Processor):
        self.processors = processors

    def process(self, state: Dict[str, Any], event: StreamEvent) -> Tuple[Dict[str, Any], List[Any]]:
        outputs = []
        current_events = [event]

        for processor in self.processors:
            next_events = []
            for evt in current_events:
                state, processor_outputs = processor.process(state, evt)
                outputs.extend(processor_outputs)
                next_events.extend(processor_outputs)
            current_events = next_events

        return state, outputs

# 6. 订阅机制
from typing import Callable

class EventBus:
    """事件总线: 支持多种订阅模式"""

    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = {}  # 类型 -> 处理器列表
        self.global_handlers: List[Callable] = []  # 全局处理器

    def on(self, event_type: str, handler: Callable) -> Callable:
        """订阅特定类型事件"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)

        # 返回取消订阅函数
        return lambda: self.handlers[event_type].remove(handler)

    def on_any(self, handler: Callable) -> Callable:
        """订阅所有事件"""
        self.global_handlers.append(handler)
        return lambda: self.global_handlers.remove(handler)

    def emit(self, event: Any) -> None:
        """发送事件"""
        event_type = type(event).__name__

        # 调用类型特定处理器 (O(1) 查找)
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"Handler error: {e}")  # 错误隔离

        # 调用全局处理器
        for handler in self.global_handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Global handler error: {e}")

# 使用示例
if __name__ == '__main__':
    # 创建处理器
    message_assembler = MessageAssembler()

    # 创建Mealy机器
    mealy = MealyMachine([message_assembler])

    # 创建事件总线
    bus = EventBus()

    # 订阅事件
    def on_message_event(event: MessageEvent):
        print(f"Message: {event.content}")

    bus.on('MessageEvent', on_message_event)

    # 处理流事件
    stream_event = StreamEvent(
        type='text_delta',
        timestamp=1.0,
        data={'text': 'Hello', 'is_final': True}
    )

    outputs = mealy.process('agent_1', stream_event)
    for output in outputs:
        bus.emit(output)
```

---

## 2. MCP 集成 - 服务器管理

### 架构概览

AgentX通过**Claude SDK集成**处理MCP服务器，而非直接管理MCP协议。架构模式为:

```
┌──────────────────────────────────────────────────┐
│           AgentX Runtime                          │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │  ClaudeEnvironment                      │   │
│  │  ├─ ClaudeReceptor (输入适配器)       │   │
│  │  └─ ClaudeEffector (输出适配器)       │   │
│  └─────────┬───────────────────────────────┘   │
│            │                                   │
│            │ 双向通信                         │
│            ▼                                   │
│  ┌─────────────────────────────────────────┐   │
│  │   SystemBus (RxJS Event Stream)         │   │
│  │   ├─ emit(event)                        │   │
│  │   ├─ on(type, handler)                  │   │
│  │   └─ request(command) → Promise         │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
└──────────────────┬───────────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │  Claude Agent SDK   │
        │                    │
        │ ┌────────────────┐ │
        │ │ MCP Servers    │ │  ← 配置通过 mcpServers
        │ │ ├─ Stdio型     │ │
        │ │ └─ SSE型       │ │
        │ └────────────────┘ │
        │                    │
        └────────────────────┘
```

### MCP 服务器配置

**配置来源**: RuntimeEnvironment → ClaudeEffector

**数据流**:
```typescript
// 1. 用户配置
const config: AgentConfig = {
  mcpServers?: {
    'server-name': {
      command: 'python -m server.py',
      args?: [],
      env?: {},
      // 或 SSE 配置:
      url: 'https://api.example.com/mcp'
    }
  }
}

// 2. 传递给 SDK
const sdkOptions = {
  mcpServers: config.mcpServers
}

// 3. SDK 初始化时处理
const query = await client.query({
  prompt: promptStream,
  options: sdkOptions
})
```

### MCP 服务器类型管理

#### Stdio 型 MCP 服务器

**特征**:
- 本地可执行文件
- 通过标准输入/输出通信
- 需要子进程管理

**AgentX处理方式**:
- 委托给Claude SDK
- SDK负责: 进程启动、stdin/stdout管理、生命周期
- Runtime仅配置参数

**示例**:
```typescript
{
  mcpServers: {
    'filesystem': {
      command: 'npx',
      args: ['@modelcontextprotocol/server-filesystem', '/home/user']
    }
  }
}
```

#### SSE 型 MCP 服务器

**特征**:
- HTTP(S) 端点
- 支持Server-Sent Events
- 远程服务

**AgentX处理方式**:
- 配置URL供SDK使用
- SDK管理HTTP连接和SSE订阅

**示例**:
```typescript
{
  mcpServers: {
    'web-api': {
      url: 'https://api.example.com/mcp'
    }
  }
}
```

### ClaudeEffector: 消息转发机制

**职责**: 桥接SystemBus和Claude SDK

**关键流程**:

```python
# 伪代码表示

class ClaudeEffector:
    def __init__(self, config):
        self.query = None  # SDK query对象
        self.mcp_servers = config.get('mcpServers', {})

    async def initialize(self, system_bus):
        """初始化时创建SDK query"""
        # 仅在首次消息时初始化 (惰性初始化)
        sdk_options = {
            'mcpServers': self.mcp_servers,
            # 其他选项...
        }

        # 创建query对象 (SDK负责启动MCP服务器)
        self.query = await client.query({
            prompt: user_messages_stream,
            options: sdk_options
        })

    async def send_message(self, message):
        """发送消息到Claude SDK"""
        await self.prompt_subject.next(message)

    async def listen_responses(self):
        """监听SDK响应"""
        async for event in self.query.events:
            if event.type == 'stream_event':
                # 转发LLM流事件到SystemBus
                self.bus.emit(event)
            elif event.type == 'tool_use':
                # MCP工具调用事件
                self.bus.emit(tool_call_event)
            elif event.type == 'tool_result':
                # MCP工具结果
                self.bus.emit(tool_result_event)
```

### Decision

**通过Claude SDK集成MCP，而非自实现MCP客户端**

#### Rationale

1. **卸载复杂性**: MCP协议管理委托给成熟的SDK
2. **减少维护**: 无需维护Stdio/SSE客户端代码
3. **支持多类型**: SDK支持Stdio和SSE，无需独立实现
4. **生命周期管理**: SDK自动处理服务器启动、关闭、错误恢复
5. **功能一致性**: 用户MCP配置与Claude官方工具一致

#### Alternatives considered

- **自实现MCP客户端**: 增加维护负担，需要处理Stdio/SSE细节、超时、错误恢复
- **直接文件IO**: 无法支持SSE型远程服务器
- **RPC代理**: 过度设计，增加网络往返

#### Python implementation notes

```python
# Python中的MCP集成策略

from typing import Dict, Any, Optional
from dataclasses import dataclass
import asyncio
from abc import ABC, abstractmethod

@dataclass
class MCPServerConfig:
    """MCP服务器配置"""
    name: str

    # Stdio型
    command: Optional[str] = None
    args: Optional[list] = None
    env: Optional[Dict[str, str]] = None

    # SSE型
    url: Optional[str] = None

class MCPServerManager:
    """MCP服务器管理器 (推荐: 委托给Claude SDK)"""

    def __init__(self, config: Dict[str, MCPServerConfig]):
        self.servers = config
        self.initialized = False

    def get_sdk_config(self) -> Dict[str, Any]:
        """
        转换为Claude SDK可理解的格式
        返回给SDK初始化，由SDK负责真实管理
        """
        sdk_config = {}

        for server_name, server_config in self.servers.items():
            if server_config.command:
                # Stdio型
                sdk_config[server_name] = {
                    'command': server_config.command,
                    'args': server_config.args or [],
                    'env': server_config.env or {}
                }
            elif server_config.url:
                # SSE型
                sdk_config[server_name] = {
                    'url': server_config.url
                }

        return sdk_config

class ClaudeEffectorAdapter:
    """
    适配器模式: 包装Claude SDK
    负责: 配置转发、消息路由、生命周期管理
    """

    def __init__(self, system_bus, mcp_config: Dict[str, MCPServerConfig]):
        self.bus = system_bus
        self.mcp_manager = MCPServerManager(mcp_config)
        self.sdk_client = None  # 初始化时获取
        self.query = None

    async def initialize(self, sdk_client):
        """初始化适配器"""
        self.sdk_client = sdk_client

        # 获取MCP SDK配置
        mcp_sdk_config = self.mcp_manager.get_sdk_config()

        # SDK初始化时自动启动MCP服务器
        # (这是Claude SDK的职责)
        self.query = await sdk_client.query(
            prompt=self._create_prompt_stream(),
            options={
                'mcpServers': mcp_sdk_config,
                # 其他选项
            }
        )

        # 启动响应监听
        asyncio.create_task(self._listen_responses())

    async def send_user_message(self, message: str):
        """向Claude SDK发送用户消息"""
        await self.prompt_subject.send(message)

    async def _listen_responses(self):
        """监听Claude SDK的所有响应"""
        try:
            async for event in self.query.events:
                if event.type == 'stream_event':
                    # LLM流事件
                    self.bus.emit(event)
                elif event.type == 'tool_use':
                    # MCP工具调用 (由SDK自动触发)
                    self.bus.emit({
                        'type': 'tool_call',
                        'data': event.data
                    })
                elif event.type == 'tool_result':
                    # MCP工具结果
                    self.bus.emit({
                        'type': 'tool_result',
                        'data': event.data
                    })
        except Exception as e:
            self.bus.emit({
                'type': 'error',
                'error': str(e)
            })

    async def dispose(self):
        """清理资源 (SDK负责关闭MCP服务器)"""
        if self.query:
            await self.query.close()

# 使用示例
if __name__ == '__main__':
    # 配置MCP服务器
    mcp_config = {
        'filesystem': MCPServerConfig(
            name='filesystem',
            command='python',
            args=['-m', 'mcp_servers.filesystem'],
            env={'MCP_PATH': '/home/user'}
        ),
        'web_api': MCPServerConfig(
            name='web_api',
            url='https://api.example.com/mcp'
        )
    }

    # 创建适配器
    effector = ClaudeEffectorAdapter(system_bus, mcp_config)

    # 初始化 (SDK自动启动MCP服务器)
    await effector.initialize(sdk_client)

    # 发送消息
    await effector.send_user_message("What files are in my home directory?")
```

---

## 3. 会话管理 - 持久化策略

### 核心数据模型

AgentX采用**Image-First**模型:

```
┌──────────────────────────────────────────────────┐
│         持久化数据结构                            │
│                                                  │
│  ┌───────────────┐                              │
│  │  Image        │ (对话模板/历史记录)           │
│  │  (persistent) │                              │
│  │               │                              │
│  │ ├─ id         │                              │
│  │ ├─ config     │ (Agent配置)                  │
│  │ ├─ messages[] │ (完整对话历史)               │
│  │ └─ metadata   │                              │
│  └───────┬───────┘                              │
│          │ 1:1 映射在容器中                     │
│  ┌───────▼──────────┐                           │
│  │  Agent           │ (运行时实例)              │
│  │  (ephemeral)     │                           │
│  │                  │                           │
│  │ ├─ id            │                           │
│  │ ├─ imageId       │ (来源Image)              │
│  │ ├─ state         │ (当前状态: idle/thinking) │
│  │ ├─ sandbox       │ (执行环境)               │
│  │ └─ session       │                           │
│  └──────────────────┘                           │
│                                                  │
│  ┌──────────────────┐                           │
│  │  Session         │ (当前轮次数据)            │
│  │  (runtime-local) │                           │
│  │                  │                           │
│  │ ├─ id            │                           │
│  │ ├─ messages[]    │ (本轮新消息)             │
│  │ ├─ tokens        │ (计费统计)               │
│  │ └─ timestamp     │                           │
│  └──────────────────┘                           │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 存储驱动架构

**设计模式**: 驱动程序模式 + 仓储模式

```python
# 存储驱动接口
class PersistenceDriver(ABC):
    @abstractmethod
    async def createStorage(self) -> Storage:
        """返回标准化Storage实例"""
        pass

# 支持的后端驱动
drivers = {
    'memory': MemoryDriver(),           # 开发/测试
    'sqlite': SQLiteDriver(),           # 本地部署
    'redis': RedisDriver(),             # 缓存层
    'mongodb': MongoDBDriver(),         # NoSQL
    'mysql': MySQLDriver(),             # 关系型
    'postgresql': PostgreSQLDriver(),   # 关系型
}
```

#### 关键驱动特性

**Memory驱动** (开发专用):
- 仅内存存储，无持久化
- 零配置，即插即用
- 用于单元测试

**SQLite驱动** (推荐本地部署):
- 文件级数据库
- 配置最小化 (仅path参数)
- 支持Bun优化

**Redis驱动** (缓存优化):
- 高性能键值存储
- 适合会话缓存
- 支持过期策略

**关系型数据库** (生产级):
- MySQL/PostgreSQL
- ACID事务保证
- 企业级特性

### StorageSessionRepository: 会话持久化策略

**三重存储模式**:

```
会话数据结构:
├─ sessions:{sessionId}           (主记录)
│  └─ {id, imageId, messages, metadata}
│
├─ messages:{sessionId}           (消息列表)
│  └─ [{role, content[], timestamp}]
│
├─ idx:sessions:image:{imageId}:{sessionId}     (正向索引)
│  └─ 快速定位: imageId → sessionId
│
└─ idx:sessions:container:{containerId}:{sessionId} (反向索引)
   └─ 快速定位: containerId → [sessionId]
```

**查询优化**:

```python
async def find_session_by_image_id(self, image_id: str) -> Optional[Session]:
    """
    通过 Index 快速定位会话
    ├─ 键前缀查询: "idx:sessions:image:{image_id}:*"
    └─ 返回第一个匹配的 sessionId

    时间复杂度: O(1) 前缀查询
    """
    pass

async def find_sessions_by_container_id(self, container_id: str) -> List[Session]:
    """
    一对多关系查询
    ├─ 键前缀查询: "idx:sessions:container:{container_id}:*"
    └─ 返回所有匹配的 sessionId

    时间复杂度: O(n) n=该容器的会话数
    """
    pass

async def find_all_sessions(self) -> List[Session]:
    """
    全表扫描 (优化: 跳过索引键)
    ├─ 扫描所有键
    ├─ 过滤 idx: 前缀 (仅保留主记录)
    └─ 聚合结果

    时间复杂度: O(k) k=所有键数量
    """
    pass
```

**数据一致性保证**:

```python
async def save_session(self, session: Session):
    """原子性保存: 主记录 + 索引同时更新"""

    # 1. 主记录
    await storage.set_item(
        f'sessions:{session.id}',
        json.dumps(session)
    )

    # 2. 消息列表
    await storage.set_item(
        f'messages:{session.id}',
        json.dumps(session.messages)
    )

    # 3. 正向索引
    await storage.set_item(
        f'idx:sessions:image:{session.image_id}:{session.id}',
        'true'
    )

    # 4. 反向索引
    for container_id in session.container_ids:
        await storage.set_item(
            f'idx:sessions:container:{container_id}:{session.id}',
            'true'
        )

async def delete_session(self, session_id: str):
    """级联删除: 清理主记录和所有索引"""

    # 1. 获取会话 (找到所有引用)
    session = await self.get_session(session_id)

    # 2. 删除主记录
    await storage.delete_item(f'sessions:{session_id}')

    # 3. 删除消息
    await storage.delete_item(f'messages:{session_id}')

    # 4. 删除所有正向索引
    await storage.delete_item(
        f'idx:sessions:image:{session.image_id}:{session_id}'
    )

    # 5. 删除所有反向索引
    for container_id in session.container_ids:
        await storage.delete_item(
            f'idx:sessions:container:{container_id}:{session_id}'
        )
```

### 生命周期管理

```
┌─────────────────────────────────────────┐
│  Persistence 初始化                      │
│  ├─ 驱动创建存储 (可能涉及DB连接)      │
│  ├─ ImageRepository 初始化              │
│  ├─ ContainerRepository 初始化          │
│  └─ SessionRepository 初始化            │
│     (所有仓储共享同一个Storage实例)    │
└──────────┬──────────────────────────────┘
           │
┌──────────▼──────────────────────────────┐
│  运行时操作                              │
│  ├─ runImage() → Image加载到Container  │
│  │  └─ 自动创建/复用 Agent 实例        │
│  ├─ receiveMessage() → 消息入队        │
│  │  └─ 如需自动激活, 使用 imageId     │
│  └─ save() → 更新 Session 和 Image    │
│     └─ 三重存储同步更新               │
└──────────┬──────────────────────────────┘
           │
┌──────────▼──────────────────────────────┐
│  销毁时的资源清理                       │
│  ├─ disposeSession() → 删除Session     │
│  ├─ disposeAgent() → 删除Agent但保留Image │
│  ├─ disposeContainer() → 级联清理       │
│  └─ dispose() → 关闭存储驱动           │
└─────────────────────────────────────────┘
```

### Decision

**多后端驱动 + 仓储模式 + 三重索引存储**

#### Rationale

1. **灵活部署**: 支持从开发(内存)到生产(关系型DB)的全生命周期
2. **查询性能**: 三重索引加速查询，权衡空间换时间
3. **数据一致性**: 三重存储同步更新保证完整性
4. **关注点分离**: 驱动处理存储细节，仓储处理业务逻辑
5. **可扩展性**: 新驱动只需实现PersistenceDriver接口

#### Alternatives considered

- **单一后端**: 部署灵活性受限
- **ORM模式**: 增加复杂性，不适合多后端场景
- **双索引**: 不足以支持所有查询模式，需要全表扫描
- **文件序列化**: 无法扩展，难以支持关系型查询

#### Python implementation notes

```python
# Python中的持久化实现

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from abc import ABC, abstractmethod
from datetime import datetime
import json
import asyncio

# 1. 数据模型
@dataclass
class ContentPart:
    type: str  # 'text', 'tool_use', 'tool_result', 'image', 'file'
    data: Dict[str, Any]

@dataclass
class Message:
    role: str  # 'user', 'assistant'
    content: List[ContentPart]
    timestamp: float

@dataclass
class Image:
    """持久化的对话模板"""
    id: str
    config: Dict[str, Any]  # Agent配置
    messages: List[Message]  # 完整对话历史
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Session:
    """运行时会话数据"""
    id: str
    image_id: str
    container_id: str
    messages: List[Message]  # 本轮新消息
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = field(default_factory=dict)

# 2. 存储接口
class Storage(ABC):
    """统一存储接口"""

    @abstractmethod
    async def get_item(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    async def set_item(self, key: str, value: str) -> None:
        pass

    @abstractmethod
    async def delete_item(self, key: str) -> None:
        pass

    @abstractmethod
    async def keys(self, prefix: Optional[str] = None) -> List[str]:
        """支持前缀查询"""
        pass

# 3. 驱动接口
class PersistenceDriver(ABC):

    @abstractmethod
    async def create_storage(self) -> Storage:
        pass

# 4. 具体驱动实现
class MemoryStorage(Storage):
    """内存存储 (开发/测试)"""

    def __init__(self):
        self.data: Dict[str, str] = {}

    async def get_item(self, key: str) -> Optional[str]:
        return self.data.get(key)

    async def set_item(self, key: str, value: str) -> None:
        self.data[key] = value

    async def delete_item(self, key: str) -> None:
        self.data.pop(key, None)

    async def keys(self, prefix: Optional[str] = None) -> List[str]:
        if prefix:
            return [k for k in self.data.keys() if k.startswith(prefix)]
        return list(self.data.keys())

class MemoryDriver(PersistenceDriver):
    async def create_storage(self) -> Storage:
        return MemoryStorage()

# SQLite驱动 (生产推荐)
class SQLiteStorage(Storage):
    """SQLite存储"""

    def __init__(self, db_path: str):
        import sqlite3
        self.db = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS storage (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.db.commit()

    async def get_item(self, key: str) -> Optional[str]:
        cursor = self.db.cursor()
        cursor.execute('SELECT value FROM storage WHERE key = ?', (key,))
        result = cursor.fetchone()
        return result[0] if result else None

    async def set_item(self, key: str, value: str) -> None:
        cursor = self.db.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO storage (key, value)
            VALUES (?, ?)
        ''', (key, value))
        self.db.commit()

    async def delete_item(self, key: str) -> None:
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM storage WHERE key = ?', (key,))
        self.db.commit()

    async def keys(self, prefix: Optional[str] = None) -> List[str]:
        cursor = self.db.cursor()
        if prefix:
            cursor.execute(
                'SELECT key FROM storage WHERE key LIKE ?',
                (f'{prefix}%',)
            )
        else:
            cursor.execute('SELECT key FROM storage')
        return [row[0] for row in cursor.fetchall()]

class SQLiteDriver(PersistenceDriver):
    def __init__(self, path: str):
        self.path = path

    async def create_storage(self) -> Storage:
        return SQLiteStorage(self.path)

# 5. 仓储模式实现
class SessionRepository:
    """会话仓储: 三重存储策略"""

    def __init__(self, storage: Storage):
        self.storage = storage

    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取单个会话"""
        data = await self.storage.get_item(f'sessions:{session_id}')
        if not data:
            return None
        return self._deserialize_session(json.loads(data))

    async def get_session_messages(self, session_id: str) -> List[Message]:
        """获取会话消息"""
        data = await self.storage.get_item(f'messages:{session_id}')
        if not data:
            return []

        # 防御性编程: 确保返回数组
        messages_data = json.loads(data)
        if not isinstance(messages_data, list):
            return []

        return [self._deserialize_message(m) for m in messages_data]

    async def find_session_by_image_id(self, image_id: str) -> Optional[Session]:
        """O(1) 查询: 通过Image快速定位会话"""
        # 前缀查询
        index_keys = await self.storage.keys(
            f'idx:sessions:image:{image_id}:'
        )

        if not index_keys:
            return None

        # 提取sessionId (格式: idx:sessions:image:{imageId}:{sessionId})
        session_id = index_keys[0].split(':')[-1]
        return await self.get_session(session_id)

    async def find_sessions_by_container_id(self, container_id: str) -> List[Session]:
        """O(n) 查询: 一对多关系"""
        # 前缀查询
        index_keys = await self.storage.keys(
            f'idx:sessions:container:{container_id}:'
        )

        sessions = []
        for index_key in index_keys:
            # 提取sessionId
            session_id = index_key.split(':')[-1]
            session = await self.get_session(session_id)
            if session:
                sessions.append(session)

        return sessions

    async def find_all_sessions(self) -> List[Session]:
        """全表扫描 (优化: 跳过索引键)"""
        all_keys = await self.storage.keys()

        sessions = []
        for key in all_keys:
            # 过滤: 仅处理主记录 (不包含 idx: 前缀)
            if key.startswith('sessions:') and not key.startswith('idx:'):
                session = await self.get_session(key.split(':')[1])
                if session:
                    sessions.append(session)

        return sessions

    async def save_session(self, session: Session) -> None:
        """原子性保存: 主记录 + 三个索引同步更新"""

        # 1. 主记录
        await self.storage.set_item(
            f'sessions:{session.id}',
            json.dumps(self._serialize_session(session))
        )

        # 2. 消息列表
        await self.storage.set_item(
            f'messages:{session.id}',
            json.dumps([self._serialize_message(m) for m in session.messages])
        )

        # 3. 正向索引: image → session
        await self.storage.set_item(
            f'idx:sessions:image:{session.image_id}:{session.id}',
            'true'
        )

        # 4. 反向索引: container → session
        await self.storage.set_item(
            f'idx:sessions:container:{session.container_id}:{session.id}',
            'true'
        )

    async def delete_session(self, session_id: str) -> None:
        """级联删除: 主记录 + 所有索引"""

        # 1. 获取会话 (找到所有引用)
        session = await self.get_session(session_id)
        if not session:
            return

        # 2. 删除主记录
        await self.storage.delete_item(f'sessions:{session_id}')

        # 3. 删除消息
        await self.storage.delete_item(f'messages:{session_id}')

        # 4. 删除索引
        await self.storage.delete_item(
            f'idx:sessions:image:{session.image_id}:{session_id}'
        )
        await self.storage.delete_item(
            f'idx:sessions:container:{session.container_id}:{session_id}'
        )

    # 序列化/反序列化工具
    def _serialize_session(self, session: Session) -> Dict:
        return {
            'id': session.id,
            'image_id': session.image_id,
            'container_id': session.container_id,
            'messages': [self._serialize_message(m) for m in session.messages],
            'input_tokens': session.input_tokens,
            'output_tokens': session.output_tokens,
            'created_at': session.created_at,
            'metadata': session.metadata
        }

    def _deserialize_session(self, data: Dict) -> Session:
        return Session(
            id=data['id'],
            image_id=data['image_id'],
            container_id=data['container_id'],
            messages=[self._deserialize_message(m) for m in data['messages']],
            input_tokens=data.get('input_tokens', 0),
            output_tokens=data.get('output_tokens', 0),
            created_at=data.get('created_at', datetime.now().timestamp()),
            metadata=data.get('metadata', {})
        )

    def _serialize_message(self, msg: Message) -> Dict:
        return {
            'role': msg.role,
            'content': [
                {'type': part.type, 'data': part.data}
                for part in msg.content
            ],
            'timestamp': msg.timestamp
        }

    def _deserialize_message(self, data: Dict) -> Message:
        return Message(
            role=data['role'],
            content=[
                ContentPart(type=p['type'], data=p['data'])
                for p in data['content']
            ],
            timestamp=data['timestamp']
        )

# 6. Persistence 工厂
class Persistence:
    """持久化层工厂"""

    def __init__(self, storage: Storage):
        self.session_repo = SessionRepository(storage)
        self.image_repo = ImageRepository(storage)
        self.container_repo = ContainerRepository(storage)

    async def dispose(self):
        """清理资源"""
        if hasattr(self.storage, 'close'):
            self.storage.close()

async def create_persistence(driver: PersistenceDriver) -> Persistence:
    """异步初始化持久化层"""
    storage = await driver.create_storage()
    return Persistence(storage)

# 使用示例
if __name__ == '__main__':
    async def main():
        # 创建持久化层
        driver = SQLiteDriver('./agent.db')
        persistence = await create_persistence(driver)

        # 创建会话
        session = Session(
            id='session_1',
            image_id='image_1',
            container_id='container_1',
            messages=[
                Message(
                    role='user',
                    content=[ContentPart(type='text', data={'text': 'Hello'})],
                    timestamp=1.0
                )
            ]
        )

        # 保存会话 (三重索引同步)
        await persistence.session_repo.save_session(session)

        # 查询会话 (O(1) 查询)
        found = await persistence.session_repo.find_session_by_image_id('image_1')
        print(f"Found session: {found.id}")

        # 列表查询
        all_sessions = await persistence.session_repo.find_sessions_by_container_id('container_1')
        print(f"Container sessions: {len(all_sessions)}")

        # 清理
        await persistence.dispose()

    asyncio.run(main())
```

---

## 4. WebSocket 通信 - 实时事件流

### 通信架构

```
┌─────────────────────────────────────────────┐
│          客户端 (浏览器/React)               │
│  ┌────────────────────────────────────────┐│
│  │  EventBus (RxJS pub/sub)              ││
│  │  ├─ on(type, handler)                 ││
│  │  └─ emit(event)                       ││
│  └────────────┬─────────────────────────┬┘│
│               │                         │  │
│       自动重连│                         │ WebSocket │
│       管理   │                         │ 序列化   │
│               ▼                         ▼  │
│  ┌────────────────────────────────────────┐│
│  │  BrowserWebSocketClient                ││
│  │  ├─ reconnecting-websocket (自动重连) ││
│  │  ├─ onMessage/onOpen/onClose/onError  ││
│  │  └─ 连接状态: 0=连接中 1=开启        ││
│  │           2=关闭中 3=已关闭           ││
│  └────────────────────────────────────────┘│
└─────────────────────┬──────────────────────┘
                      │ WebSocket双向流
                      │
                      ▼
┌─────────────────────────────────────────────┐
│      服务端 (Node.js)                       │
│  ┌──────────────────────────────────────┐  │
│  │  WebSocketServer                     │  │
│  │  ├─ 心跳机制 (ping/pong)             │  │
│  │  ├─ 连接管理 (Set<WebSocketConn>)    │  │
│  │  └─ broadcast(message)               │  │
│  └──────────────────────────────────────┘  │
│           ▲                                 │
│           │ 消息入站                        │
│           │                                 │
│  ┌────────┴──────────────────────────────┐  │
│  │  SystemBus (事件分发)                 │  │
│  │  ├─ emit(SystemEvent)                │  │
│  │  ├─ on(type, handler)                │  │
│  │  └─ request(command) → Promise       │  │
│  └────────┬───────────────────────────┬┘  │
│           │                           │   │
│    ┌──────▼───────┐         ┌────────▼──┐ │
│    │ CommandHandler       │ ClaudeEffector │
│    │                       │(Agent执行)   │
│    └──────────────┘        └──────────────┘
│                                            │
└────────────────────────────────────────────┘
```

### WebSocket 连接生命周期

**客户端状态机**:

```
连接中 (readyState=0)
  │
  ├─ 成功 → 开启 (readyState=1)
  │          ├─ 接收消息
  │          ├─ 发送消息
  │          └─ 心跳 (ping)
  │
  ├─ 失败 → 重连等待 (自动)
  │          └─ 指数退避延迟
  │
  └─ 超时 → 关闭中 (readyState=2)
             └─ 已关闭 (readyState=3)
```

**服务端心跳机制**:

```python
# 服务端
定时任务 (可配置间隔, 默认30秒):
  for each connection:
    if connection.alive:
      connection.ping()  # 发送ping帧
      connection.alive = False
      set_timeout(timeout_duration):
        if connection.alive == False:
          connection.close()  # 超时关闭
    else:
      connection.close()  # pong超时则关闭

# 客户端
on_ping():
  connection.pong()  # 自动响应
  set_alive_flag()
```

### 消息序列化协议

**JSON序列化格式**:

```typescript
interface WebSocketMessage {
  // 消息头
  type: string           // 'event', 'command', 'response'
  id?: string            // 请求ID (用于匹配响应)

  // 消息体
  event?: SystemEvent    // 事件对象
  command?: {
    type: string
    payload: any
  }

  // 响应
  response?: {
    success: boolean
    data?: any
    error?: string
  }

  // 元数据
  timestamp: number
  source: string        // 'client' | 'server'
}
```

**示例消息**:

```json
// 客户端发送消息
{
  "type": "event",
  "event": {
    "type": "receive_message",
    "source": "client",
    "data": {
      "agentId": "agent_1",
      "message": "What is 2+2?"
    },
    "timestamp": 1704110400000
  }
}

// 服务端响应流事件
{
  "type": "event",
  "event": {
    "type": "stream_event",
    "source": "claude",
    "data": {
      "type": "text_delta",
      "text": "The answer is 4"
    },
    "timestamp": 1704110401000
  }
}

// 请求-响应命令
{
  "type": "command",
  "id": "cmd_123",
  "command": {
    "type": "run_image",
    "payload": {
      "imageId": "image_1"
    }
  }
}

// 响应
{
  "type": "response",
  "id": "cmd_123",
  "response": {
    "success": true,
    "data": {
      "agentId": "agent_1"
    }
  }
}
```

### 访问控制 (AsConsumer/AsProducer)

**设计模式**: 代理模式

```typescript
// 完整总线 (内部使用)
interface SystemBus {
  emit(event): void
  on(type, handler): Unsubscribe
  request(command): Promise
}

// 消费者视图 (客户端)
interface Consumer {
  on(type, handler): Unsubscribe
  // 只能监听, 不能发送
}

// 生产者视图 (扩展)
interface Producer {
  emit(event): void
  // 只能发送, 不能监听
}

// 工厂方法
const consumerView = bus.asConsumer()  // 限制视图
const producerView = bus.asProducer()
```

### Decision

**WebSocket + 心跳 + 自动重连 + 访问控制**

#### Rationale

1. **双向实时流**: WebSocket支持服务器主动推送，适合流式场景
2. **连接可靠性**: 心跳检测断连，自动重连恢复
3. **浏览器兼容**: BrowserWebSocketClient自动选择实现
4. **安全隔离**: 访问控制防止误用总线
5. **消息顺序**: TCP保证消息顺序

#### Alternatives considered

- **Server-Sent Events (SSE)**: 仅单向，不支持客户端发送
- **轮询**: 低效，延迟高，浪费带宽
- **gRPC**: 二进制协议，浏览器不兼容
- **Socket.IO**: 过度包装，增加复杂性

#### Python implementation notes

```python
# Python中的WebSocket实现

import asyncio
import json
import time
from typing import Dict, Callable, Optional, Set
from dataclasses import dataclass
from enum import Enum
import websockets

# 1. 连接状态枚举
class ConnectionState(Enum):
    CONNECTING = 0      # 正在连接
    OPEN = 1            # 已连接
    CLOSING = 2         # 关闭中
    CLOSED = 3          # 已关闭

# 2. WebSocket消息格式
@dataclass
class WSMessage:
    type: str           # 'event', 'command', 'response'
    event: Optional[Dict] = None
    command: Optional[Dict] = None
    response: Optional[Dict] = None
    msg_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            'type': self.type,
            'id': self.msg_id,
            'event': self.event,
            'command': self.command,
            'response': self.response,
            'timestamp': self.timestamp
        })

    @classmethod
    def from_json(cls, data: str) -> 'WSMessage':
        d = json.loads(data)
        return cls(
            type=d['type'],
            msg_id=d.get('id'),
            event=d.get('event'),
            command=d.get('command'),
            response=d.get('response'),
            timestamp=d.get('timestamp', time.time())
        )

# 3. 连接对象
class WebSocketConnection:
    """单个WebSocket连接"""

    def __init__(self, websocket):
        self.ws = websocket
        self.state = ConnectionState.OPEN
        self.message_handlers: Set[Callable] = set()
        self.close_handlers: Set[Callable] = set()
        self.error_handlers: Set[Callable] = set()
        self.alive = True
        self.last_pong = time.time()

    async def send(self, message: WSMessage):
        """发送消息"""
        if self.state == ConnectionState.OPEN:
            try:
                await self.ws.send(message.to_json())
            except Exception as e:
                await self._on_error(e)

    async def receive_loop(self):
        """接收消息循环"""
        try:
            async for message_str in self.ws:
                message = WSMessage.from_json(message_str)

                # 调用消息处理器
                for handler in self.message_handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        print(f"Handler error: {e}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self._on_close()

    async def ping(self):
        """发送ping帧"""
        try:
            await self.ws.ping()
        except Exception as e:
            await self._on_error(e)

    def on_message(self, handler: Callable) -> Callable:
        """订阅消息事件"""
        self.message_handlers.add(handler)
        return lambda: self.message_handlers.discard(handler)

    def on_close(self, handler: Callable) -> Callable:
        """订阅关闭事件"""
        self.close_handlers.add(handler)
        return lambda: self.close_handlers.discard(handler)

    def on_error(self, handler: Callable) -> Callable:
        """订阅错误事件"""
        self.error_handlers.add(handler)
        return lambda: self.error_handlers.discard(handler)

    async def _on_close(self):
        """处理连接关闭"""
        self.state = ConnectionState.CLOSED
        for handler in self.close_handlers:
            try:
                await handler()
            except Exception as e:
                print(f"Close handler error: {e}")

    async def _on_error(self, error: Exception):
        """处理错误"""
        for handler in self.error_handlers:
            try:
                await handler(error)
            except Exception as e:
                print(f"Error handler error: {e}")

    async def close(self):
        """关闭连接"""
        self.state = ConnectionState.CLOSING
        await self.ws.close()

# 4. WebSocket服务器
class WebSocketServer:
    """WebSocket服务器"""

    def __init__(self, host: str = '0.0.0.0', port: int = 8080,
                 heartbeat_interval: float = 30, heartbeat_timeout: float = 5):
        self.host = host
        self.port = port
        self.connections: Set[WebSocketConnection] = set()
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.message_handlers: Dict[str, Set[Callable]] = {}
        self.wildcard_handlers: Set[Callable] = set()

    async def start(self):
        """启动服务器"""

        # 启动心跳任务
        asyncio.create_task(self._heartbeat_loop())

        # 启动WebSocket服务器
        async with websockets.serve(self._handle_connection, self.host, self.port):
            print(f"WebSocket server listening on ws://{self.host}:{self.port}")
            await asyncio.Future()  # 永久运行

    async def _handle_connection(self, websocket, path):
        """处理新连接"""
        connection = WebSocketConnection(websocket)
        self.connections.add(connection)

        try:
            # 转发消息到总线
            async def on_message(message: WSMessage):
                await self._dispatch_message(message)

            connection.on_message(on_message)

            # 接收消息
            await connection.receive_loop()
        finally:
            self.connections.discard(connection)

    async def _heartbeat_loop(self):
        """心跳循环 (检测死连接)"""
        while True:
            await asyncio.sleep(self.heartbeat_interval)

            dead_connections = []
            for conn in self.connections:
                # 发送ping
                await conn.ping()

                # 检查超时
                if time.time() - conn.last_pong > self.heartbeat_timeout:
                    dead_connections.append(conn)

            # 关闭死连接
            for conn in dead_connections:
                await conn.close()

    async def _dispatch_message(self, message: WSMessage):
        """分发消息到处理器"""

        # 类型特定处理器
        if message.type in self.message_handlers:
            for handler in self.message_handlers[message.type]:
                try:
                    await handler(message)
                except Exception as e:
                    print(f"Handler error: {e}")

        # 通配符处理器
        for handler in self.wildcard_handlers:
            try:
                await handler(message)
            except Exception as e:
                print(f"Wildcard handler error: {e}")

    def on_message(self, msg_type: str, handler: Callable) -> Callable:
        """订阅特定消息类型"""
        if msg_type not in self.message_handlers:
            self.message_handlers[msg_type] = set()
        self.message_handlers[msg_type].add(handler)
        return lambda: self.message_handlers[msg_type].discard(handler)

    def on_any_message(self, handler: Callable) -> Callable:
        """订阅所有消息"""
        self.wildcard_handlers.add(handler)
        return lambda: self.wildcard_handlers.discard(handler)

    async def broadcast(self, message: WSMessage):
        """广播消息到所有连接"""
        disconnected = []
        for conn in self.connections:
            try:
                await conn.send(message)
            except Exception:
                disconnected.append(conn)

        # 清理断开的连接
        for conn in disconnected:
            self.connections.discard(conn)

# 5. 客户端 (带自动重连)
class WebSocketClient:
    """WebSocket客户端 (带自动重连)"""

    def __init__(self, url: str,
                 max_reconnect_delay: float = 30,
                 initial_reconnect_delay: float = 1):
        self.url = url
        self.state = ConnectionState.CLOSED
        self.ws = None

        # 重连参数
        self.max_reconnect_delay = max_reconnect_delay
        self.reconnect_delay = initial_reconnect_delay
        self.reconnect_multiplier = 1.5

        # 事件处理
        self.message_handlers: Set[Callable] = set()
        self.open_handlers: Set[Callable] = set()
        self.close_handlers: Set[Callable] = set()
        self.error_handlers: Set[Callable] = set()

    async def connect(self):
        """连接到服务器"""
        while self.state != ConnectionState.OPEN:
            try:
                self.state = ConnectionState.CONNECTING
                self.ws = await websockets.connect(self.url)
                self.state = ConnectionState.OPEN
                self.reconnect_delay = 1  # 重置延迟

                # 通知打开处理器
                for handler in self.open_handlers:
                    try:
                        await handler()
                    except Exception as e:
                        print(f"Open handler error: {e}")

                # 启动接收循环
                await self._receive_loop()

            except Exception as e:
                self.state = ConnectionState.CLOSED

                # 通知错误处理器
                for handler in self.error_handlers:
                    try:
                        await handler(e)
                    except Exception as inner_e:
                        print(f"Error handler error: {inner_e}")

                # 指数退避重连
                print(f"Connection failed, retrying in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(
                    self.reconnect_delay * self.reconnect_multiplier,
                    self.max_reconnect_delay
                )

    async def _receive_loop(self):
        """接收消息循环"""
        try:
            async for message_str in self.ws:
                message = WSMessage.from_json(message_str)

                for handler in self.message_handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        print(f"Message handler error: {e}")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.state = ConnectionState.CLOSED
            for handler in self.close_handlers:
                try:
                    await handler()
                except Exception as e:
                    print(f"Close handler error: {e}")

    async def send(self, message: WSMessage):
        """发送消息"""
        if self.state == ConnectionState.OPEN and self.ws:
            try:
                await self.ws.send(message.to_json())
            except Exception as e:
                print(f"Send error: {e}")

    def on_message(self, handler: Callable) -> Callable:
        self.message_handlers.add(handler)
        return lambda: self.message_handlers.discard(handler)

    def on_open(self, handler: Callable) -> Callable:
        self.open_handlers.add(handler)
        return lambda: self.open_handlers.discard(handler)

    def on_close(self, handler: Callable) -> Callable:
        self.close_handlers.add(handler)
        return lambda: self.close_handlers.discard(handler)

    def on_error(self, handler: Callable) -> Callable:
        self.error_handlers.add(handler)
        return lambda: self.error_handlers.discard(handler)

    async def close(self):
        """关闭连接"""
        self.state = ConnectionState.CLOSING
        if self.ws:
            await self.ws.close()

# 6. 使用示例
async def main():
    # 启动服务器
    server = WebSocketServer()
    server_task = asyncio.create_task(server.start())

    # 等待服务器启动
    await asyncio.sleep(1)

    # 创建客户端
    client = WebSocketClient('ws://127.0.0.1:8080')

    # 订阅事件
    async def on_message(msg: WSMessage):
        print(f"Client received: {msg.type}")

    client.on_message(on_message)

    async def on_open():
        print("Client connected!")
        # 发送消息
        message = WSMessage(
            type='event',
            event={'type': 'hello', 'data': 'test'}
        )
        await client.send(message)

    client.on_open(on_open)

    # 连接并运行
    await client.connect()

# asyncio.run(main())
```

---

## 5. 核心设计模式总结

### 1. Mealy机器模式

**应用场景**: 事件驱动系统、流式处理

```
优点:
✓ 无副作用纯函数，易于测试
✓ 确定性输出，可重现
✓ 支持并发处理 (多代理隔离)
✓ 组合性强

缺点:
✗ 需要状态管理基础设施
✗ 不适合复杂的同步操作
```

### 2. 驱动程序模式

**应用场景**: 存储、网络、日志等基础设施

```
优点:
✓ 后端无关，支持多种实现
✓ 灵活部署 (开发/生产)
✓ 易于测试 (mock驱动)
✓ 零依赖初始化

缺点:
✗ 初始化异步复杂
```

### 3. 仓储模式

**应用场景**: 数据持久化、查询优化

```
优点:
✓ 关注点分离
✓ 索引加速查询
✓ 一致性保证
✓ 易于扩展

缺点:
✗ 索引维护开销
```

### 4. 事件总线模式

**应用场景**: 模块间通信、全局事件分发

```
优点:
✓ 解耦组件
✓ 类型安全
✓ 支持多订阅
✓ 错误隔离

缺点:
✗ 隐式依赖
✗ 调试困难
```

### 5. 适配器模式

**应用场景**: 接口集成、SDK包装

```
优点:
✓ 隐藏复杂性
✓ 统一接口
✓ 便于扩展

缺点:
✗ 增加层级
```

### 6. 代理/访问控制模式

**应用场景**: 权限管理、接口限制

```
优点:
✓ 防止误用
✓ 安全隔离
✓ 清晰职责

缺点:
✗ 运行时开销
```

---

## 6. Python 实现指南

### 核心库选择

| 功能 | TypeScript/Node.js | Python |
|------|-------------------|--------|
| 事件驱动 | RxJS | asyncio + python-asyncio或 Twisted |
| WebSocket | ws库 | websockets, asyncio |
| 数据库 | better-sqlite3 | sqlite3, sqlalchemy |
| HTTP | Node.js http | aiohttp, fastapi |
| 类型系统 | TypeScript | typing, dataclasses, pydantic |

### 架构对应关系

```
AgentX (TypeScript)          →  Python实现
─────────────────────────────────────────
@agentxjs/agent             →  agent/core.py
  ├─ Mealy机器             →  mealy_machine.py
  ├─ 处理器                 →  processors.py
  └─ 状态机                 →  state_machine.py

@agentxjs/runtime           →  runtime/core.py
  ├─ SystemBus             →  event_bus.py
  ├─ 容器管理               →  container.py
  └─ 环境适配               →  environment.py

@agentxjs/persistence       →  persistence/core.py
  ├─ 驱动                   →  drivers/
  ├─ 仓储                   →  repository.py
  └─ 存储接口               →  storage.py

@agentxjs/network           →  network/websocket.py

@agentxjs/types             →  types.py
```

### 项目结构建议

```
python-agentx/
├── agent/
│   ├── __init__.py
│   ├── core.py              # Agent主类
│   ├── mealy_machine.py     # Mealy机器实现
│   ├── processors.py        # 事件处理器
│   ├── state_machine.py     # 状态机
│   └── engine/
│       ├── message_assembler.py
│       ├── state_event_processor.py
│       └── turn_tracker.py
│
├── runtime/
│   ├── __init__.py
│   ├── core.py              # Runtime主类
│   ├── event_bus.py         # SystemBus实现
│   ├── container.py         # 容器管理
│   ├── sandbox.py           # 沙箱环境
│   └── environment/
│       ├── claude_environment.py
│       ├── claude_receptor.py
│       └── claude_effector.py
│
├── persistence/
│   ├── __init__.py
│   ├── core.py              # Persistence工厂
│   ├── repository.py        # 仓储实现
│   ├── storage.py           # 存储接口
│   └── drivers/
│       ├── __init__.py
│       ├── memory.py        # 内存驱动
│       ├── sqlite.py        # SQLite驱动
│       ├── redis.py         # Redis驱动
│       └── postgresql.py    # PostgreSQL驱动
│
├── network/
│   ├── __init__.py
│   ├── websocket.py         # WebSocket实现
│   ├── client.py            # 客户端
│   └── server.py            # 服务器
│
├── types.py                 # 类型定义
├── logger.py                # 日志
└── tests/
    ├── test_mealy_machine.py
    ├── test_event_bus.py
    ├── test_persistence.py
    └── test_websocket.py
```

### 关键实现注意事项

#### 1. 异步编程 (async/await)

```python
# ✓ 推荐: 使用 asyncio
async def process_event(self, event):
    result = await self.processor.process(event)
    return result

# ✗ 避免: 同步阻塞
def process_event(self, event):
    result = self.processor.process(event)  # 阻塞
    return result
```

#### 2. 类型注解

```python
# ✓ 推荐: 使用类型注解和Pydantic
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class StreamEvent(BaseModel):
    type: str
    timestamp: float
    data: Dict[str, Any]

# ✗ 避免: 动态类型
event = {'type': 'text_delta', 'data': ...}
```

#### 3. 错误处理和隔离

```python
# ✓ 推荐: 错误隔离，防止级联故障
async def dispatch_message(self, message):
    for handler in self.handlers:
        try:
            await handler(message)
        except Exception as e:
            logger.error(f"Handler error: {e}", exc_info=True)
            # 继续执行其他处理器

# ✗ 避免: 未捕获异常传播
async def dispatch_message(self, message):
    for handler in self.handlers:
        await handler(message)  # 一个失败全部失败
```

#### 4. 资源管理

```python
# ✓ 推荐: 使用上下文管理器
class WebSocketServer:
    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# 使用
async with WebSocketServer() as server:
    await server.handle_connections()

# ✗ 避免: 手动管理
server = WebSocketServer()
server.start()
try:
    ...
finally:
    server.close()  # 容易遗漏
```

#### 5. 并发控制

```python
# ✓ 推荐: 使用 asyncio.Lock
class MealyMachine:
    def __init__(self):
        self.locks: Dict[str, asyncio.Lock] = {}

    async def process(self, agent_id: str, event):
        # 为每个代理创建独立锁
        if agent_id not in self.locks:
            self.locks[agent_id] = asyncio.Lock()

        async with self.locks[agent_id]:
            # 原子性更新状态
            state = self.agent_states[agent_id]
            new_state, outputs = self._process(state, event)
            self.agent_states[agent_id] = new_state

        return outputs

# ✗ 避免: 竞态条件
async def process(self, agent_id, event):
    state = self.agent_states[agent_id]
    # 其他协程可能在这里修改state
    new_state, outputs = self._process(state, event)
    self.agent_states[agent_id] = new_state
```

---

## 总结

AgentX的核心优势在于:

1. **分层事件驱动**: 四层事件系统清晰、可测试、可扩展
2. **生态集成**: 通过SDK集成MCP，卸载复杂性
3. **灵活部署**: 驱动程序模式支持多种存储和部署场景
4. **实时通信**: WebSocket + 自动重连确保连接可靠性
5. **模块化设计**: 各层职责清晰，易于理解和扩展

**移植到Python时的关键成功因素**:

- 充分利用 asyncio 异步编程模型
- 使用 Pydantic 进行类型验证和序列化
- 建立完善的错误隔离和日志机制
- 参考现有Python异步库的最佳实践
- 逐模块验证和集成测试

