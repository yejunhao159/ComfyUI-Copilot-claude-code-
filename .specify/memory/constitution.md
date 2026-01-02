<!--
=== Sync Impact Report ===
Version change: N/A → 1.0.0 (Initial)
Added sections:
  - Core Principles (5 principles)
  - Technical Constraints
  - Development Workflow
  - Governance
Removed sections: None (initial version)
Templates requiring updates:
  - .specify/templates/plan-template.md ✅ (Constitution Check section compatible)
  - .specify/templates/spec-template.md ✅ (No updates needed)
  - .specify/templates/tasks-template.md ✅ (No updates needed)
Follow-up TODOs: None
-->

# ComfyUI-Copilot Constitution

## Core Principles

### I. Claude Code 能力优先

使用 Claude API + Tool Use 作为核心智能引擎，不重复造轮子。

- MUST 使用 Claude 原生的代码理解和工具调用能力
- MUST 参考 AgentX 架构精华，用 Python 实现
- MUST NOT 使用弱于 Claude 的 Agent 方案处理复杂工作流任务
- 工作流理解、修改、调试等核心功能依赖 Claude 的代码级理解能力

### II. MCP 工具标准化

所有 ComfyUI 操作通过 MCP (Model Context Protocol) 工具暴露。

- MUST 定义标准化的 ComfyUI 工具集：
  - `read_workflow` - 读取当前画布工作流 JSON
  - `write_workflow` - 写入/替换工作流
  - `modify_node` - 修改节点参数
  - `install_node` - 安装缺失节点（git clone / pip install）
  - `run_workflow` - 执行工作流
  - `get_logs` - 获取执行日志和错误信息
  - `list_models` / `download_model` - 模型管理
- MUST 保持工具接口稳定，变更需文档记录
- SHOULD 优先复用 MCP 生态已有工具

### III. 工作流即代码

把 ComfyUI 工作流 JSON 当作代码处理，支持精确读写和版本追踪。

- MUST 支持工作流的读取、修改、diff 对比
- MUST 精确理解工作流 JSON 结构（节点、连接、参数）
- SHOULD 支持工作流片段的复用和组合
- 修改工作流时 MUST 保持未涉及部分不变

### IV. 自动化安装与修复

缺什么装什么，让工作流快速跑起来。

- MUST 自动识别缺失的节点并提供安装方案
- MUST 自动识别缺失的模型并提供下载链接
- MUST 分析执行错误并提供修复建议
- SHOULD 支持一键安装所有缺失依赖

### V. ComfyUI 原生集成

作为 ComfyUI 自定义节点无缝嵌入，不破坏原有功能。

- MUST 作为 custom_nodes 插件形式安装
- MUST NOT 修改 ComfyUI 核心代码
- MUST NOT 与 ComfyUI 原有样式/功能冲突
- MUST 通过 ComfyUI 原生 API 进行通信
- 前端样式 MUST 使用作用域隔离（Tailwind scoped）

## Technical Constraints

### 后端
- **Python**: 3.10+
- **Web 框架**: aiohttp（与 ComfyUI 一致）
- **AI**: Claude API + Tool Use（anthropic SDK）
- **协议**: MCP (Model Context Protocol)
- **数据库**: SQLAlchemy（会话/工作流持久化）

### 前端
- **框架**: React 19 + TypeScript
- **构建**: Vite 5
- **样式**: Tailwind CSS（scoped，防止样式冲突）
- **状态**: Dexie (IndexedDB)

### 集成
- **入口**: `__init__.py` 注册到 ComfyUI
- **路由**: `/copilot_web/*` 静态文件服务
- **通信**: SSE 流式响应

## Development Workflow

### 前端开发
```bash
cd ui && npm run dev    # Vite HMR，代理到 localhost:8188
npm run build           # 构建到 dist/copilot_web/
```

### 后端开发
- 后端随 ComfyUI 主进程启动
- 修改后需重启 ComfyUI 生效

### 测试
```bash
pytest                  # 后端测试
npm run lint            # 前端 ESLint
```

## Governance

- Constitution 修改需文档记录变更原因
- 版本遵循语义化版本：MAJOR.MINOR.PATCH
  - MAJOR: 原则删除或重新定义
  - MINOR: 新增原则或章节
  - PATCH: 措辞修正、澄清
- 所有 PR 需验证是否符合 Constitution 原则

**Version**: 1.0.0 | **Ratified**: 2026-01-02 | **Last Amended**: 2026-01-02
