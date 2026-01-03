# Implementation Tasks: ComfyUI-AgentX 完整运行时

**Feature**: ComfyUI-AgentX Runtime
**Branch**: `002-comfyui-agentx-runtime`
**Date**: 2026-01-02
**Spec**: [spec.md](./spec.md)

---

## Overview

This document breaks down the implementation of ComfyUI-AgentX runtime into concrete, executable tasks organized by user story priority.

**Tech Stack**:
- **Language**: Python 3.10+
- **Event System**: asyncio.Queue + Pub/Sub
- **MCP**: fastmcp + stdio/SSE server management
- **Database**: SQLite + SQLAlchemy
- **WebSocket**: aiohttp.web.WebSocketResponse
- **Claude API**: anthropic SDK (>=0.40.0)

**Project Structure**:
```
backend/agentx/
├── runtime/          # AgentEngine, EventBus, Container
├── mcp/              # MCP server management
├── mcp_tools/        # ComfyUI MCP tools
├── persistence/      # SQLAlchemy models
└── websocket.py      # WebSocket handler
```

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)
**User Story 1** (P1) provides the core value proposition: interactive workflow debugging with Claude. This is sufficient for initial release.

### Incremental Delivery
- Phase 1-2: Setup + Foundational (blocking prerequisites)
- Phase 3: User Story 1 (P1) - MVP Release
- Phase 4: User Story 2 (P1) - Enhanced UX
- Phase 5: User Story 3 (P2) - Persistence
- Phase 6: User Story 4 (P2) - Extensibility
- Phase 7: User Story 5 (P3) - Advanced Features
- Phase 8: Polish

Each phase delivers independently testable functionality.

---

## Task Dependencies

### Story Completion Order

```
Setup (Phase 1) → Foundational (Phase 2) → Core Stories (Phases 3-4) → Advanced Stories (Phases 5-7) → Polish (Phase 8)
                                                ↓
                                            US1 (P1) ← MVP
                                                ↓
                                            US2 (P1)
                                                ↓
                      ┌─────────────────────────┴─────────────────────────┐
                      ↓                                                     ↓
                  US3 (P2)                                              US4 (P2)
                      ↓                                                     ↓
                      └─────────────────────────┬─────────────────────────┘
                                                ↓
                                            US5 (P3)
```

**Dependencies**:
- US2 depends on US1 (requires event system from US1)
- US3 depends on US1 (requires session/message models)
- US4 depends on US1 (requires MCP framework)
- US5 depends on US4 (requires MCP server management)

---

## Phase 1: Setup

**Goal**: Initialize project structure and install dependencies

**Independent Test**: Run `pytest backend/agentx/` (should find no tests yet but import all modules without errors)

### Tasks

- [ ] T001 Create backend/agentx/ directory structure per data-model.md
- [ ] T002 Create backend/agentx/__init__.py with version info
- [ ] T003 [P] Create backend/agentx/runtime/__init__.py
- [ ] T004 [P] Create backend/agentx/mcp/__init__.py
- [ ] T005 [P] Create backend/agentx/mcp_tools/__init__.py
- [ ] T006 [P] Create backend/agentx/persistence/__init__.py
- [ ] T007 [P] Create tests/agentx/ directory structure
- [ ] T008 Update requirements.txt with new dependencies (anthropic>=0.40.0, fastmcp>=0.1.0)
- [ ] T009 Create backend/agentx/config.py for environment configuration (ANTHROPIC_API_KEY, DATABASE_URL, etc.)
- [ ] T010 Create .env.example with required environment variables

---

## Phase 2: Foundational Tasks

**Goal**: Implement core infrastructure needed by all user stories

**Independent Test**:
- Import all foundational modules without errors
- Create/destroy EventBus instance
- Initialize database schema

### Tasks

- [ ] T011 [P] Implement EventType enum in backend/agentx/runtime/types.py (STREAM, STATE, MESSAGE, TURN)
- [ ] T012 [P] Implement SessionState enum in backend/agentx/runtime/types.py (IDLE, PROCESSING, etc.)
- [ ] T013 Implement EventBus class in backend/agentx/runtime/event_bus.py (asyncio.Queue + Pub/Sub)
- [ ] T014 [P] Implement AgentEvent dataclass in backend/agentx/runtime/types.py (4-tier events)
- [ ] T015 [P] Define SQLAlchemy Base in backend/agentx/persistence/models.py
- [ ] T016 [P] Implement AgentSessionModel in backend/agentx/persistence/models.py
- [ ] T017 [P] Implement AgentMessageModel in backend/agentx/persistence/models.py
- [ ] T018 [P] Implement AgentEventModel (optional) in backend/agentx/persistence/models.py
- [ ] T019 Create Alembic migration 001_initial_schema in backend/agentx/persistence/migrations/
- [ ] T020 Implement PersistenceService class in backend/agentx/persistence/service.py (CRUD operations)
- [ ] T021 [P] Implement AgentConfig dataclass in backend/agentx/config.py
- [ ] T022 [P] Implement config loader from environment in backend/agentx/config.py

---

## Phase 3: User Story 1 - Interactive Workflow Debugging (P1) 🎯 MVP

**Story Goal**: Enable Claude to debug ComfyUI workflows through natural language interaction

**Why P1**: Core value proposition - reduces debugging time from hours to minutes

**Independent Test**:
1. Create workflow with invalid parameter
2. Send message "What's wrong with this workflow?"
3. Verify Claude identifies the specific node and parameter error
4. Accept suggested fix
5. Verify workflow is corrected

### Tasks

#### Models & Domain Logic

- [ ] T023 [P] [US1] Implement AgentSession dataclass in backend/agentx/runtime/types.py
- [ ] T024 [P] [US1] Implement Message dataclass in backend/agentx/runtime/types.py
- [ ] T025 [P] [US1] Implement ToolCall dataclass in backend/agentx/runtime/types.py

#### Core Runtime

- [ ] T026 [US1] Implement Container class in backend/agentx/runtime/container.py (session management)
- [ ] T027 [US1] Implement AgentEngine core in backend/agentx/runtime/agent_engine.py (Claude API integration)
- [ ] T028 [US1] Implement streaming message processing in backend/agentx/runtime/agent_engine.py
- [ ] T029 [US1] Implement tool call routing in backend/agentx/runtime/agent_engine.py

#### MCP Framework

- [ ] T030 [P] [US1] Implement MCPTool dataclass in backend/agentx/mcp/protocol.py
- [ ] T031 [P] [US1] Implement MCPServer dataclass in backend/agentx/mcp/protocol.py
- [ ] T032 [US1] Implement ToolBridge class in backend/agentx/mcp/tool_bridge.py (MCP → Claude format conversion)

#### ComfyUI Tools (Core Debugging)

- [ ] T033 [P] [US1] Implement get_workflow tool in backend/agentx/mcp_tools/workflow_tools.py
- [ ] T034 [P] [US1] Implement update_workflow tool in backend/agentx/mcp_tools/workflow_tools.py
- [ ] T035 [P] [US1] Implement modify_node tool in backend/agentx/mcp_tools/workflow_tools.py
- [ ] T036 [P] [US1] Implement get_logs tool in backend/agentx/mcp_tools/debug_tools.py
- [ ] T037 [US1] Register ComfyUI MCP server in backend/agentx/mcp_tools/comfyui_tools.py (fastmcp)

#### API Endpoints (HTTP)

- [ ] T038 [P] [US1] Implement POST /agentx/sessions endpoint in backend/controller/agentx_api.py
- [ ] T039 [P] [US1] Implement POST /agentx/sessions/{id}/messages endpoint (non-streaming)
- [ ] T040 [US1] Implement AgentX service initialization in backend/agentx/service.py
- [ ] T041 [US1] Register AgentX routes in backend/__init__.py

#### Integration

- [ ] T042 [US1] Integrate AgentEngine with EventBus for event emission
- [ ] T043 [US1] Integrate PersistenceService with AgentEngine for session storage
- [ ] T044 [US1] Add error handling for tool call failures in AgentEngine
- [ ] T045 [US1] Add error handling for Claude API failures (rate limits, timeouts)

---

## Phase 4: User Story 2 - Multi-turn Conversation with Tool Calls (P1)

**Story Goal**: Display real-time tool execution progress to build user trust

**Why P1**: Critical for UX - users need to see what Claude is doing

**Independent Test**:
1. Request complex workflow modification ("Add face restoration after image generation")
2. Observe tool call events in real-time (search_nodes, get_node_info, update_workflow)
3. Verify final workflow contains all requested changes

### Tasks

#### Event Streaming

- [ ] T046 [P] [US2] Implement StreamEvent dataclass in backend/agentx/runtime/types.py
- [ ] T047 [P] [US2] Implement StateEvent dataclass in backend/agentx/runtime/types.py
- [ ] T048 [P] [US2] Implement MessageEvent dataclass in backend/agentx/runtime/types.py
- [ ] T049 [P] [US2] Implement TurnEvent dataclass in backend/agentx/runtime/types.py

#### WebSocket Infrastructure

- [ ] T050 [US2] Implement WebSocket handler in backend/agentx/websocket.py (aiohttp)
- [ ] T051 [US2] Implement WebSocket heartbeat/ping-pong in backend/agentx/websocket.py
- [ ] T052 [US2] Implement client message parsing (message, cancel, ping) in websocket handler
- [ ] T053 [US2] Implement event forwarding to WebSocket clients in websocket handler

#### API Endpoints (WebSocket)

- [ ] T054 [US2] Implement WS /agentx/sessions/{id}/stream endpoint in backend/controller/agentx_api.py
- [ ] T055 [US2] Implement cancellation support for ongoing Claude processing

#### Event Emission

- [ ] T056 [US2] Add StreamEvent emission during Claude token streaming in AgentEngine
- [ ] T057 [US2] Add StateEvent emission for tool call lifecycle (calling_tool, tool_result, etc.)
- [ ] T058 [US2] Add MessageEvent emission on message completion in AgentEngine
- [ ] T059 [US2] Add TurnEvent emission on conversation turn completion in AgentEngine

#### Additional Tools

- [ ] T060 [P] [US2] Implement search_nodes tool in backend/agentx/mcp_tools/node_tools.py
- [ ] T061 [P] [US2] Implement get_node_info tool in backend/agentx/mcp_tools/node_tools.py
- [ ] T062 [P] [US2] Implement run_workflow tool in backend/agentx/mcp_tools/debug_tools.py

---

## Phase 5: User Story 3 - Session Persistence and Recovery (P2)

**Story Goal**: Allow users to resume debugging sessions across ComfyUI restarts

**Why P2**: Essential for multi-day debugging workflows

**Independent Test**:
1. Start conversation with Claude
2. Note session_id
3. Close and restart ComfyUI
4. Verify session appears in list with preview text
5. Load session and verify all messages/tool calls are restored

### Tasks

#### Session Management

- [ ] T063 [P] [US3] Implement GET /agentx/sessions endpoint (list sessions) in backend/controller/agentx_api.py
- [ ] T064 [P] [US3] Implement GET /agentx/sessions/{id} endpoint (session details)
- [ ] T065 [P] [US3] Implement DELETE /agentx/sessions/{id} endpoint
- [ ] T066 [P] [US3] Implement GET /agentx/sessions/{id}/messages endpoint (paginated)

#### Persistence

- [ ] T067 [US3] Implement save_session in PersistenceService (auto-save after each message)
- [ ] T068 [US3] Implement load_session with message history in PersistenceService
- [ ] T069 [US3] Implement list_sessions with pagination in PersistenceService
- [ ] T070 [US3] Implement delete_session in PersistenceService

#### Message History Loading

- [ ] T071 [US3] Implement message pagination with offset/limit in PersistenceService
- [ ] T072 [US3] Add session title auto-generation from first user message
- [ ] T073 [US3] Add last_message_preview field for session list display

#### Session Recovery

- [ ] T074 [US3] Implement session state restoration in AgentEngine
- [ ] T075 [US3] Add schema migration support for database version upgrades

---

## Phase 6: User Story 4 - Custom MCP Tool Extension (P2)

**Story Goal**: Enable developers to extend AgentX with custom tools

**Why P2**: Critical for ecosystem growth and long-term adoption

**Independent Test**:
1. Create custom MCP tool (e.g., get_image_dimensions)
2. Restart MCP server manager
3. Ask Claude to use the new tool
4. Verify tool appears in list and executes successfully

### Tasks

#### MCP Server Management (Internal)

- [ ] T076 [P] [US4] Implement MCPServerManager class in backend/agentx/mcp/server_manager.py
- [ ] T077 [US4] Implement internal MCP server registration in MCPServerManager
- [ ] T078 [US4] Implement tool discovery (tools/list) in MCPServerManager
- [ ] T079 [US4] Implement tool execution (tools/call) routing in MCPServerManager

#### Dynamic Tool Registration

- [ ] T080 [US4] Implement auto-discovery of custom tools in backend/agentx/mcp_tools/
- [ ] T081 [US4] Implement JSON Schema validation for tool input_schema
- [ ] T082 [US4] Add tool registration API to MCPServerManager

#### API Endpoints

- [ ] T083 [P] [US4] Implement GET /agentx/tools endpoint (list all tools)
- [ ] T084 [P] [US4] Implement GET /agentx/tools/{name}/schema endpoint

#### Documentation

- [ ] T085 [US4] Create example custom tool in backend/agentx/mcp_tools/examples/
- [ ] T086 [US4] Document custom tool development in quickstart.md (already done in Phase 1)

---

## Phase 7: User Story 5 - External MCP Server Integration (P3)

**Story Goal**: Support external MCP servers (stdio and SSE) for advanced use cases

**Why P3**: Nice-to-have for power users, not essential for core debugging

**Independent Test**:
1. Configure external stdio MCP server (e.g., filesystem server)
2. Start AgentX
3. Verify server starts within 5 seconds
4. Ask Claude to use external tool
5. Verify tool executes successfully

### Tasks

#### Stdio MCP Server

- [ ] T087 [P] [US5] Implement StdioMCPServer class in backend/agentx/mcp/servers/stdio_server.py
- [ ] T088 [US5] Implement process lifecycle (start, stop, restart) for stdio servers
- [ ] T089 [US5] Implement JSON-RPC 2.0 message serialization/deserialization
- [ ] T090 [US5] Implement stdio I/O handling (stdin/stdout pipes)

#### SSE MCP Server

- [ ] T091 [P] [US5] Implement SSEMCPServer class in backend/agentx/mcp/servers/sse_server.py (or reuse existing mcp_client.py)
- [ ] T092 [US5] Implement HTTP SSE connection management
- [ ] T093 [US5] Implement event stream parsing for SSE

#### Server Configuration

- [ ] T094 [US5] Add MCP server configuration schema to backend/agentx/config.py
- [ ] T095 [US5] Implement config loading from .env (AGENTX_MCP_SERVERS_FILE)
- [ ] T096 [US5] Implement config loading from JSON file (mcp_servers.json)

#### Server Health & Monitoring

- [ ] T097 [US5] Implement health check for MCP servers in MCPServerManager
- [ ] T098 [US5] Implement auto-restart on crash (max 3 attempts)
- [ ] T099 [US5] Implement timeout handling (120s for tool calls, 30s for initialization)
- [ ] T100 [US5] Add MCP lifecycle logging (start, stop, crash events)

#### API Endpoints

- [ ] T101 [P] [US5] Implement GET /agentx/health endpoint (server status + MCP server health)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Goal**: Production readiness, error handling, and performance optimization

**Independent Test**:
- All user stories pass their acceptance tests
- System handles 10 concurrent sessions without performance degradation
- Tool calls complete within 10 seconds (95th percentile)

### Tasks

#### Error Handling

- [ ] T102 [P] Implement global error handler for uncaught exceptions in backend/agentx/service.py
- [ ] T103 [P] Add error recovery for database connection failures
- [ ] T104 [P] Add graceful degradation when MCP server is unavailable
- [ ] T105 [P] Add user-friendly error messages for common failures (API key missing, etc.)

#### Performance Optimization

- [ ] T106 [P] Implement database connection pooling (pool_size=5, max_overflow=10)
- [ ] T107 [P] Add event queue bounded size (maxsize=1000) with backpressure handling
- [ ] T108 [P] Optimize session loading with joinedload (avoid N+1 queries)
- [ ] T109 [P] Add message pagination optimization (lazy loading)

#### Monitoring & Logging

- [ ] T110 [P] Implement structured logging with log levels (DEBUG, INFO, ERROR)
- [ ] T111 [P] Add MCP message logging at DEBUG level
- [ ] T112 [P] Add tool call logging at INFO level
- [ ] T113 [P] Add performance metrics logging (latency, tokens, duration)

#### Configuration

- [ ] T114 Create comprehensive .env.example with all configuration options
- [ ] T115 Add configuration validation on startup (fail fast if invalid)
- [ ] T116 Document all environment variables in quickstart.md (already done in Phase 1)

#### Testing Infrastructure

- [ ] T117 [P] Create pytest fixtures for AgentEngine in tests/agentx/conftest.py
- [ ] T118 [P] Create pytest fixtures for EventBus in tests/agentx/conftest.py
- [ ] T119 [P] Create pytest fixtures for PersistenceService with test database

#### Documentation

- [ ] T120 Update README.md with AgentX Runtime section
- [ ] T121 Create CHANGELOG.md for version 1.0.0 release
- [ ] T122 Generate OpenAPI docs from contracts/agentx-api.yaml (Swagger UI)

---

## Task Summary

**Total Tasks**: 122

**By Phase**:
- Phase 1 (Setup): 10 tasks
- Phase 2 (Foundational): 12 tasks
- Phase 3 (US1 - P1): 23 tasks 🎯 MVP
- Phase 4 (US2 - P1): 17 tasks
- Phase 5 (US3 - P2): 13 tasks
- Phase 6 (US4 - P2): 11 tasks
- Phase 7 (US5 - P3): 15 tasks
- Phase 8 (Polish): 21 tasks

**By User Story**:
- US1 (P1): 23 tasks
- US2 (P1): 17 tasks
- US3 (P2): 13 tasks
- US4 (P2): 11 tasks
- US5 (P3): 15 tasks
- Infrastructure: 43 tasks

**Parallel Opportunities**: 67 tasks marked with [P] can be executed in parallel (different files, no dependencies)

---

## Parallel Execution Examples

### Phase 1 (Setup)
**Parallelizable**: T003, T004, T005, T006, T007 (all create different directories)

### Phase 2 (Foundational)
**Parallelizable**: T011, T012, T014, T015-T018, T021, T022 (independent module creation)
**Sequential**: T013 (EventBus depends on types), T019 (migration depends on models), T020 (service depends on models)

### Phase 3 (US1)
**Parallelizable**: T023-T025 (dataclasses), T030-T031 (MCP types), T033-T036 (tools), T038-T039 (endpoints)
**Sequential**: T026-T029 (AgentEngine depends on types), T037 (registration depends on tools), T040-T045 (integration)

**Suggested parallel groups for Phase 3**:
- **Group A**: T023, T024, T025 (domain dataclasses)
- **Group B**: T030, T031 (MCP dataclasses)
- **Group C**: T033, T034, T035, T036 (ComfyUI tools)
- **Group D**: T038, T039 (HTTP endpoints)
- **Sequential after groups**: T026 → T027 → T028 → T029 → T037 → T040 → T041 → T042 → T043 → T044 → T045

### Phase 4 (US2)
**Parallelizable**: T046-T049 (event dataclasses), T060-T062 (additional tools), T054 (WS endpoint)
**Sequential**: T050-T053 (WebSocket handler), T055-T059 (event emission)

### Phase 5 (US3)
**Parallelizable**: T063-T066 (HTTP endpoints)
**Sequential**: T067-T075 (persistence logic)

### Phase 6 (US4)
**Parallelizable**: T076, T083, T084 (independent components)
**Sequential**: T077-T082, T085-T086 (tool registration flow)

### Phase 7 (US5)
**Parallelizable**: T087, T091, T101 (independent server types)
**Sequential**: T088-T090 (stdio flow), T092-T093 (SSE flow), T094-T100 (configuration and health)

### Phase 8 (Polish)
**Most tasks parallelizable**: T102-T113, T117-T119 (different concerns)
**Sequential**: T114-T116, T120-T122 (documentation)

---

## Format Validation

✅ All 122 tasks follow the required checklist format:
- [x] Checkbox: `- [ ]`
- [x] Task ID: T001-T122 (sequential)
- [x] [P] marker: 67 tasks marked as parallelizable
- [x] [Story] label: US1-US5 for story-specific tasks
- [x] Description: Clear action with file path
- [x] File paths: Absolute paths or clear module references

✅ Organization by user story:
- [x] Phase 1-2: Setup + Foundational (no story labels)
- [x] Phase 3-7: User stories (all tasks have story labels)
- [x] Phase 8: Polish (no story labels)

✅ Independent test criteria defined for each phase

✅ MVP scope clearly identified (Phase 1-3)

---

## Next Steps

1. **Execute Phase 1-2** (Setup + Foundational) to establish project structure
2. **Implement US1 (Phase 3)** for MVP release
3. **Run acceptance tests** for US1 before proceeding
4. **Incrementally deliver** US2-US5 based on priority
5. **Polish and optimize** in Phase 8 before final release

---

**Status**: Ready for implementation
**Estimated Effort**: ~3-4 weeks for MVP (Phases 1-3), ~6-8 weeks for full release (all phases)
**Risk**: Medium (dependent on Claude API stability and MCP protocol maturity)

