# Feature Specification: ComfyUI-AgentX 完整运行时

**Feature Branch**: `002-comfyui-agentx-runtime`
**Created**: 2026-01-02
**Status**: Draft
**Input**: User description: "Complete AgentX runtime implementation in ComfyUI with MCP protocol support, event-driven architecture, and persistent session management"

## 概述

在 ComfyUI 中实现完整的 AgentX 运行时环境,将 TypeScript AgentX Web 应用的核心架构迁移到 Python。这将为用户提供本地 Claude Code 环境,通过模型上下文协议(MCP)与 ComfyUI 工作流无缝集成。

### 背景

AgentX 是一个基于 Web 的 Claude Code 实现,具有事件驱动架构、MCP 工具集成和持久化会话管理功能。目前,ComfyUI 用户无法访问 Claude 的高级推理能力来进行工作流调试、节点管理和自动化问题解决。本实现将把 AgentX 的全部功能直接带入 ComfyUI 环境。

### 目标

- 在 ComfyUI 中提供完整的 Claude Code 能力
- 支持自然语言交互进行工作流调试和修改
- 通过 MCP 协议支持可扩展的工具生态系统
- 跨会话维护对话历史
- 通过事件驱动架构提供实时反馈

### 非目标

- 复制 AgentX 的 Web 用户界面(将使用 ComfyUI 现有前端)
- 云端 AgentX 功能或多用户协作
- Docker 容器化(使用进程级隔离)

## User Scenarios & Testing

### User Story 1 - 交互式工作流调试 (Priority: P1)

ComfyUI 用户在工作流中遇到错误。他们打开 AgentX 聊天界面,用自然语言描述问题,Claude 会自动通过检查工作流结构、读取错误日志并提供修复建议来进行调查。用户审查建议的更改并一键接受。

**Why this priority**: 这是核心价值主张 - 将用户调试时间从数小时减少到几分钟。它展示了将 Claude 集成到 ComfyUI 的直接效用。

**Independent Test**: 可以通过创建一个已知错误的工作流(例如无效参数值),打开 AgentX 聊天,输入"修复这个错误",并验证 Claude 识别并纠正问题而无需手动干预来完全测试。

**Acceptance Scenarios**:

1. **Given** 工作流有无效参数值, **When** 用户询问"这个工作流有什么问题?", **Then** Claude 识别出导致错误的特定节点和参数
2. **Given** Claude 已识别错误, **When** 用户确认建议的修复, **Then** 工作流自动更新并解决错误
3. **Given** 工作流验证错误, **When** 用户向 Claude 提供错误详情, **Then** Claude 读取相关日志,在 30 秒内诊断根本原因并提出解决方案

---

### User Story 2 - 带工具调用的多轮对话 (Priority: P1)

用户需要大幅修改工作流。他们与 Claude 进行来回对话,Claude 会提出澄清问题、搜索合适的节点、检查模型可用性,并迭代构建所需的工作流修改。所有工具调用(搜索节点、读取文件、更新工作流)都实时可见。

**Why this priority**: 展示事件驱动架构和 MCP 集成协同工作。这对于用户信任和理解 Claude 正在做什么至关重要。

**Independent Test**: 可以通过请求复杂的工作流修改("在图像生成后添加面部修复步骤"),观察 UI 中的工具调用流,并验证最终工作流包含所有请求的更改来测试。

**Acceptance Scenarios**:

1. **Given** 与 Claude 的持续对话, **When** Claude 需要搜索节点, **Then** 用户看到显示搜索查询和结果的实时通知
2. **Given** Claude 正在修改工作流, **When** 需要多个工具调用, **Then** 每个工具调用及其结果在聊天界面中按顺序显示
3. **Given** 多步骤工作流修改, **When** Claude 遇到歧义, **Then** Claude 在继续之前向用户寻求澄清

---

### User Story 3 - 会话持久化和恢复 (Priority: P2)

用户与 Claude 进行了长时间的调试会话,在修复工作流方面取得了进展,但需要关闭 ComfyUI 一天。第二天,他们重新打开 ComfyUI,与 Claude 的整个对话历史都被保留。他们可以从上次停止的地方继续或参考以前的修复。

**Why this priority**: 对于实际使用至关重要,因为调试会话通常跨越多天。没有这个功能,用户会失去上下文并浪费时间重新解释问题。

**Independent Test**: 可以通过与 Claude 对话、记录会话 ID、关闭并重新打开 ComfyUI,并验证恢复会话时所有消息、工具调用和结果都已恢复来测试。

**Acceptance Scenarios**:

1. **Given** 活跃的 AgentX 会话, **When** 用户关闭 ComfyUI, **Then** 会话与所有消息和元数据一起保存到本地数据库
2. **Given** 先前保存的会话, **When** 用户重新打开 ComfyUI, **Then** 会话列表显示所有过去的会话及时间戳和预览文本
3. **Given** 用户选择先前的会话, **When** 会话加载, **Then** 完整的对话历史以正确的顺序显示,包含所有工具调用详情

---

### User Story 4 - 自定义 MCP 工具扩展 (Priority: P2)

开发者想用自定义图片处理工具扩展 AgentX。他们创建一个带有 MCP 工具装饰器的 Python 函数,指定输入模式和描述。AgentX 自动发现这个工具,Claude 可以立即在对话中使用它,无需任何手动注册步骤。

**Why this priority**: 展示可扩展性并使生态系统能够增长。虽然对初始发布不是关键,但对长期采用至关重要。

**Independent Test**: 可以通过创建简单的 MCP 工具(例如 `get_image_dimensions`),重启 MCP 服务器管理器,要求 Claude 使用新工具,并验证它出现在工具列表中且可以成功调用来测试。

**Acceptance Scenarios**:

1. **Given** 在代码库中定义了新的 MCP 工具, **When** MCP 服务器管理器刷新, **Then** 工具出现在可用工具列表中,带有正确的名称和描述
2. **Given** 注册了自定义 MCP 工具, **When** Claude 决定使用它, **Then** 工具使用正确的参数调用并返回预期结果
3. **Given** 自定义 MCP 工具有输入模式, **When** Claude 尝试使用无效参数调用它, **Then** 工具调用失败并显示清晰的验证错误消息

---

### User Story 5 - 外部 MCP 服务器集成 (Priority: P3)

高级用户想集成外部 MCP 服务器(例如文件系统工具或网络搜索工具)。他们在 AgentX 设置中添加服务器配置,指定命令或 URL。AgentX 启动 MCP 服务器进程,发现其工具,并使它们与 ComfyUI 的内置工具一起可供 Claude 使用。

**Why this priority**: 对高级用户和未来可扩展性很有用,但对核心调试工作流不是必需的。

**Independent Test**: 可以通过配置简单的 stdio MCP 服务器(例如示例文件系统服务器),验证它成功启动,并确认 Claude 可以在对话中使用其工具来测试。

**Acceptance Scenarios**:

1. **Given** 外部 MCP 服务器配置, **When** AgentX 初始化, **Then** 服务器进程在 5 秒内启动并注册其工具
2. **Given** 外部 MCP 服务器正在运行, **When** 服务器无响应, **Then** AgentX 检测到故障并向用户显示错误消息
3. **Given** 配置了多个 MCP 服务器, **When** Claude 搜索工具, **Then** 所有服务器的工具都可用并按来源清楚标记

---

### Edge Cases

- **Claude API 速率限制被触发会发生什么?** 系统排队请求并向用户显示"Claude 正在思考"消息,在速率限制窗口到期后自动重试
- **如果用户和 Claude 同时修改工作流会发生什么?** 最近的保存获胜,如果用户的更改与 Claude 的更新冲突,用户会收到通知
- **如果 MCP 工具调用时间超过预期会发生什么?** 用户看到实时进度指示器,工具调用在 2 分钟后超时并显示清晰的错误消息
- **如果会话数据库损坏会发生什么?** 系统创建新的数据库文件并记录错误,允许用户继续工作(历史会话丢失但当前工作被保留)
- **如果用户尝试从旧版本 AgentX 恢复会话会发生什么?** 系统自动迁移会话模式,或者如果迁移不可能则显示警告

## Requirements

### Functional Requirements

#### 核心运行时

- **FR-001**: 系统必须实现 4 层事件系统(Stream、State、Message、Turn),在 Claude 对话期间实时发射事件
- **FR-002**: 系统必须支持来自 Claude API 的流式响应,在生成时显示文本令牌
- **FR-003**: 系统必须使用唯一标识符、创建时间戳和状态跟踪(空闲、处理中、等待工具)管理对话会话
- **FR-004**: 系统必须支持多轮对话,其中工具结果被反馈给 Claude 以继续推理

#### MCP 集成

- **FR-005**: 系统必须支持 stdio 和 SSE(服务器发送事件)MCP 服务器类型进行工具集成
- **FR-006**: 系统必须在初始化时自动发现并注册所有配置的 MCP 服务器的工具
- **FR-007**: 系统必须将 MCP 工具模式转换为 Claude API 工具格式而无需手动映射
- **FR-008**: 系统必须根据工具名称将来自 Claude 的工具调用路由到正确的 MCP 服务器
- **FR-009**: 系统必须优雅地处理 MCP 服务器故障,继续使用剩余的可用工具运行

#### ComfyUI 集成

- **FR-010**: 系统必须为所有核心 ComfyUI 操作提供 MCP 工具:获取工作流、更新工作流、搜索节点、获取节点详情、运行工作流、获取日志和安装节点
- **FR-011**: 系统必须与现有的 ComfyUI 工作流存储和版本控制机制集成
- **FR-012**: 系统必须在 Claude 进行修改时维护工作流检查点历史
- **FR-013**: 系统必须访问 ComfyUI 的节点注册表以搜索并向 Claude 提供节点信息

#### 持久化

- **FR-014**: 系统必须将所有会话、消息、工具调用和工具结果持久化到本地 SQLite 数据库
- **FR-015**: 系统必须支持加载带有完整对话历史的历史会话
- **FR-016**: 系统必须允许用户查看所有过去会话的列表,包含预览文本和时间戳
- **FR-017**: 系统必须在每次消息交换后自动保存会话状态

#### WebSocket 通信

- **FR-018**: 系统必须支持双向 WebSocket 连接,以便向前端实时流式传输事件
- **FR-019**: 系统必须以 JSONL 格式向连接的 WebSocket 客户端发送所有 4 种事件类型(Stream、State、Message、Turn)
- **FR-020**: 系统必须实现 WebSocket 心跳/ping-pong 以检测断开连接
- **FR-021**: 系统必须允许客户端通过 WebSocket 消息取消正在进行的 Claude 处理

#### 配置和可扩展性

- **FR-022**: 系统必须从环境变量加载配置(ANTHROPIC_API_KEY、模型选择、数据库路径)
- **FR-023**: 系统必须支持动态 MCP 服务器注册而无需更改代码
- **FR-024**: 系统必须在注册 MCP 工具模式之前验证它们
- **FR-025**: 系统必须记录所有 MCP 服务器生命周期事件(启动、停止、崩溃)以进行调试

### Key Entities

- **AgentSession**: 表示用户与 Claude 之间的对话,包含会话 ID、用户 ID(可选)、创建/更新时间戳、当前状态、配置设置和消息历史
- **Message**: 对话中的单条消息,具有角色(用户/助手)、内容文本、时间戳以及可选的 tool_calls/tool_results 数组
- **ToolCall**: 表示 Claude 请求执行工具,包含工具名称、参数字典和执行结果
- **MCPServer**: 表示已配置的 MCP 服务器实例,具有服务器名称、类型(stdio/SSE)、连接详情(命令/URL)和当前状态(运行中/已停止/错误)
- **MCPTool**: 描述来自 MCP 服务器的可用工具,包括工具名称、描述、输入 JSON 模式和服务器来源
- **AgentEvent**: 对话处理期间发射的实时事件,具有事件类型(stream/state/message/turn)、事件数据、时间戳和会话 ID

## Success Criteria

### Measurable Outcomes

- **SC-001**: 用户平均可以在 5 分钟内调试和修复工作流错误(相比手动需要 30 分钟以上)
- **SC-002**: 95% 的工具调用在 10 秒内完成,提供近乎即时的反馈
- **SC-003**: 包含 100+ 条消息的会话可以在 2 秒内加载和显示
- **SC-004**: 系统在 10 个不同会话中处理并发对话而不会出现性能下降
- **SC-005**: 90% 的用户在第一次尝试时成功完成多轮工作流调试任务
- **SC-006**: MCP 服务器在 AgentX 初始化后 5 秒内成功启动
- **SC-007**: WebSocket 连接在持续 1 小时以上的会话中保持稳定,每 30 秒心跳一次
- **SC-008**: 会话持久化成功率为 99.9%(除灾难性数据库故障外无数据丢失)

## Assumptions

- 用户已配置有效的 ANTHROPIC_API_KEY(如果缺少,系统将显示清晰的错误)
- ComfyUI 现有的工作流存储和节点注册表 API 在开发期间保持稳定
- 平均工作流大小小于 100 个节点(较大的工作流可能有较慢的工具调用性能)
- 用户在安装了 Python 3.10+ 的本地环境中运行 ComfyUI
- 到 Claude API 的网络延迟小于 500ms(国际用户可能会经历较慢的响应)
- SQLite 足以用于会话存储(不期望数百万会话或并发写入)

## Dependencies

- **外部**: Anthropic Claude API(claude-3-5-sonnet 模型)、Python anthropic SDK(>=0.40.0)
- **内部**: 现有的 ComfyUI 工作流管理系统、节点注册表、执行引擎和日志基础设施
- **可选**: 外部 MCP 服务器(如果用户选择配置它们)

## Open Questions

无 - 规格说明完整并准备好进行实现规划。
