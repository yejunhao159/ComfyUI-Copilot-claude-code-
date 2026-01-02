# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

ComfyUI-Copilot 是一个基于 ComfyUI 的智能 AIGC 助手，提供工作流生成、调试、重写、参数调优和节点推荐功能。它是一个 ComfyUI 自定义节点，包含 Python 后端（aiohttp）和 React TypeScript 前端。

## 开发命令

### 前端 (ui/)
```bash
cd ui
npm install
npm run dev          # Vite 开发服务器，支持热更新（代理到 localhost:8188）
npm run build        # 生产构建 → dist/copilot_web/
npm run build:css    # 监听 Tailwind CSS 编译
npm run lint         # ESLint 检查（零警告容忍）
```

### 后端
```bash
pip install -r requirements.txt   # Python 3.10+
# 后端作为 ComfyUI 服务器的一部分运行（默认端口 8188）
```

### 测试
```bash
pytest                            # 运行测试
pytest-asyncio                    # 支持异步测试
```

## 架构

### 请求流程
1. **前端 (React)** → `ui/src/Api.ts` 发送请求
2. **ComfyUI Bridge** → `entry/comfyui-bridge.js` 桥接 React 到 ComfyUI JS API
3. **后端控制器** → `backend/controller/` 接收 HTTP 请求
4. **请求上下文** → 从请求头提取 LLM 配置（`Openai-Api-Key`、`Openai-Base-Url`、`Workflow-LLM-Model`）
5. **Agent 系统** → 使用 MCP 工具的 OpenAI Agents 处理请求
6. **响应** → SSE 流式返回文本和扩展数据

### 关键目录

```
backend/
├── controller/          # API 端点（conversation_api.py 是主要聊天端点）
├── service/             # 业务逻辑和 Agent
│   ├── debug_agent.py           # 工作流调试 Agent
│   ├── mcp_client.py            # MCP 集成和工具注册
│   ├── workflow_rewrite_agent.py # 工作流修改
│   └── parameter_tools.py       # 参数调优
├── dao/                 # SQLAlchemy 数据库访问层
├── utils/
│   ├── globals.py       # 全局状态管理
│   ├── comfy_gateway.py # ComfyUI API 通信
│   ├── request_context.py # 请求作用域上下文
│   └── auth_utils.py    # API Key 认证
└── data/                # 数据模型

ui/src/
├── main.tsx            # React 入口（等待 ComfyUI app 初始化）
├── App.tsx             # 主应用组件
├── Api.ts              # 后端 API 层
├── components/
│   ├── chat/           # 聊天界面
│   └── debug/          # 调试界面
├── context/            # React Context 提供者
└── hooks/              # 自定义 React Hooks

entry/
├── entry.js            # Vite 模块入口
└── comfyui-bridge.js   # ComfyUI JavaScript API 桥接
```

### Agent 系统

- **工厂模式**: `backend/agent_factory.py` 创建 OpenAI agents
- **模型优先级**: 请求配置 > kwargs > 默认值 ("gemini-2.5-flash")
- **MCP 工具**: 通过 `backend/service/mcp_client.py` 注册
- **可用工具**: 工作流执行、参数操作、节点连接、工作流重写

### 数据库 (SQLAlchemy)

- **Workflows**: 持久化用户工作流
- **Messages**: 对话历史（支持向量嵌入）
- **Experts**: 专家知识/提示词存储

## LLM 配置

配置来源（优先级从高到低）:
1. 请求头: `Openai-Api-Key`、`Openai-Base-Url`、`Workflow-LLM-Model`
2. `.env` 环境变量
3. 数据库用户配置

支持: OpenAI API、LMStudio（本地）、ModelScope

## ComfyUI 集成

- 入口点: `__init__.py` 在 `/copilot_web/` 注册 Web 路由
- 静态文件: 从 `dist/copilot_web/` 提供服务
- 安装: 克隆到 `ComfyUI/custom_nodes/`

## 前端构建说明

- Tailwind CSS 使用作用域隔离，防止与 ComfyUI 样式冲突
- 代码分割: react、markdown、UI 组件库分别打包
- 构建输出: `dist/copilot_web/`（由 ComfyUI 后端提供服务）
- 虚拟滚动: 使用 `@tanstack/react-virtual`

## AgentX Runtime (002-comfyui-agentx-runtime)

新增 AgentX 运行时，将 TypeScript AgentX 架构移植到 Python：

### 核心技术栈
- **事件驱动**: asyncio.Queue + Pub/Sub（4层事件系统：Stream/State/Message/Turn）
- **MCP 集成**: fastmcp + stdio/SSE MCP 服务器管理
- **持久化**: SQLite + SQLAlchemy（agent_sessions, agent_messages, agent_events）
- **WebSocket**: aiohttp.web.WebSocketResponse（实时事件流）
- **Claude API**: anthropic SDK（流式响应支持）

### 新增目录结构
```
backend/agentx/
├── runtime/          # 核心运行时（AgentEngine, EventBus, Container）
├── mcp/              # MCP 服务器管理（stdio/SSE）
├── mcp_tools/        # ComfyUI MCP 工具集
├── persistence/      # SQLAlchemy 模型和持久化服务
└── websocket.py      # WebSocket 处理器

specs/002-comfyui-agentx-runtime/
├── spec.md           # 功能规格（5个用户故事）
├── research.md       # 技术研究（4个关键决策）
├── data-model.md     # 数据模型设计
├── quickstart.md     # 快速开始指南
└── contracts/        # API 契约（OpenAPI 3.0）
    ├── agentx-api.yaml      # HTTP/WebSocket API
    ├── comfyui-tools.yaml   # ComfyUI 内置工具
    └── mcp-protocol.yaml    # MCP 协议规范
```

### API 端点
- `POST /agentx/sessions` - 创建会话
- `GET /agentx/sessions` - 列出会话
- `GET /agentx/sessions/{session_id}/messages` - 获取消息历史
- `POST /agentx/sessions/{session_id}/messages` - 发送消息（非流式）
- `WS /agentx/sessions/{session_id}/stream` - WebSocket 流式连接
- `GET /agentx/tools` - 列出可用 MCP 工具
- `GET /agentx/health` - 健康检查

### 性能目标
- 工具调用延迟 < 10秒 (95%)
- 会话加载 < 2秒 (100条消息)
- WebSocket 心跳间隔 30秒
- 支持 10 个并发会话
