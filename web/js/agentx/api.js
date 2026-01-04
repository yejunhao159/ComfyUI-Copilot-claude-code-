/**
 * AgentX API Client
 */

const API_BASE = "/api/agentx";

export async function createSession() {
    const response = await fetch(`${API_BASE}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "ComfyUI Chat" })
    });
    return response.json();
}

export async function sendMessage(sessionId, content, system) {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, system })
    });
    return response.json();
}

/**
 * Create WebSocket connection for streaming
 * @param {string} sessionId - Session ID
 * @param {object} callbacks - Event callbacks
 * @returns {WebSocket}
 */
export function createStreamConnection(sessionId, callbacks) {
    const { onText, onToolCall, onToolResult, onDone, onError, onOpen } = callbacks;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}${API_BASE}/sessions/${sessionId}/stream`;

    console.log("[AgentX] Connecting to WebSocket:", wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("[AgentX] WebSocket connected");
        onOpen?.();
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleStreamEvent(data, callbacks);
        } catch (e) {
            console.warn("[AgentX] Failed to parse WS message:", event.data);
        }
    };

    ws.onerror = (error) => {
        console.error("[AgentX] WebSocket error:", error);
        onError?.(error);
    };

    ws.onclose = () => {
        console.log("[AgentX] WebSocket closed");
        onDone?.();
    };

    return ws;
}

/**
 * Send message via WebSocket
 * @param {WebSocket} ws - WebSocket connection
 * @param {string} content - User message
 * @param {string} system - System prompt
 */
export function sendViaWebSocket(ws, content, system) {
    if (ws.readyState !== WebSocket.OPEN) {
        throw new Error("WebSocket not connected");
    }

    ws.send(JSON.stringify({
        type: "message",
        content: content,
        system: system
    }));
}

function handleStreamEvent(event, callbacks) {
    const { onText, onToolCall, onToolResult, onTurnComplete } = callbacks;

    // Handle different event types based on backend format
    switch (event.type) {
        case "stream":
            // Text streaming event - data is the text string directly
            if (event.data) {
                const text = typeof event.data === 'string' ? event.data : event.data.text;
                if (text) {
                    onText?.(text);
                }
            }
            break;

        case "state":
            // State change event (thinking, tool_calling, etc.)
            console.log("[AgentX] State:", event.data?.state);
            break;

        case "message":
            // Complete message event
            if (event.data?.content) {
                onText?.(event.data.content);
            }
            break;

        case "turn":
            // Turn complete event - always call to finish the message
            // executed_tools may be empty array or undefined if no tools were called
            onTurnComplete?.(event.data || {});
            break;

        case "tool_use":
        case "tool_call":
            onToolCall?.({
                id: event.data?.id || event.id,
                name: event.data?.name || event.name,
                arguments: event.data?.input || event.input
            });
            break;

        case "tool_result":
            onToolResult?.({
                id: event.data?.tool_use_id || event.tool_use_id,
                result: event.data?.content || event.content
            });
            break;

        case "error":
            callbacks.onError?.(new Error(event.data?.message || event.message || "Unknown error"));
            break;

        default:
            console.log("[AgentX] Unknown event type:", event.type, event);
    }
}

/**
 * Sync workflow from frontend canvas to backend
 * @param {Object} workflowData - Complete workflow data from getFullWorkflow()
 * @returns {Promise<Object>} - Sync result
 */
export async function syncWorkflowToBackend(workflowData) {
    const response = await fetch(`${API_BASE}/sync/workflow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(workflowData)
    });
    return response.json();
}

/**
 * Get the current workflow from backend (Claude's working state)
 * @returns {Promise<Object>} - Current workflow data
 */
export async function getWorkflowFromBackend() {
    const response = await fetch(`${API_BASE}/sync/workflow`);
    return response.json();
}

export function buildSystemPrompt(workflowContext, fullWorkflow = null) {
    let workflowSection = `## Current Workflow Summary:\n${workflowContext}`;

    if (fullWorkflow && fullWorkflow.workflow && Object.keys(fullWorkflow.workflow).length > 0) {
        workflowSection = `## Current Workflow (${fullWorkflow.node_count} nodes):
\`\`\`json
${JSON.stringify(fullWorkflow.workflow, null, 2)}
\`\`\``;
    }

    return `You are AgentX, an expert AI assistant for ComfyUI workflows.

## Your Capabilities:
1. **Design Workflows**: Create complete text-to-image, image-to-image, upscaling workflows
2. **Modify Workflows**: Add/remove/modify nodes, adjust parameters, fix connections
3. **Execute & Debug**: Run workflows, analyze results, fix errors
4. **Autonomous Testing**: Design → Execute → Analyze → Iterate

## Available Tools (USE THEM!):
### Workflow Management:
- get_workflow: Get current workflow state
- update_workflow: Create or replace entire workflow (auto-syncs to canvas!)
- clear_workflow: Clear all nodes

### Node Operations:
- add_node: Add a single node
- remove_node: Remove a node
- modify_node: Change a node's parameter
- connect_nodes: Connect output of one node to input of another
- disconnect_input: Remove a connection

### Discovery:
- search_nodes: Find nodes by keywords
- get_node_info: Get detailed info about node types
- list_node_categories: Browse available node categories

### Execution:
- execute_workflow: Run the workflow in ComfyUI
- get_execution_result: Check execution status/results (use wait=true)
- interrupt_execution: Stop current execution

${workflowSection}

## Workflow Format (ComfyUI API):
\`\`\`json
{
  "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
  "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt", "clip": ["1", 1]}},
  "3": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], ...}}
}
\`\`\`
- Node IDs are strings ("1", "2", etc.)
- Connections: ["source_node_id", output_slot_index]
- _meta.title for custom display names

## Rules:
1. When user asks to CREATE a workflow → use update_workflow with complete workflow
2. When modifying existing workflow → use modify_node, add_node, connect_nodes
3. After update_workflow → workflow auto-syncs to canvas
4. To test workflow → use execute_workflow, then get_execution_result with wait=true
5. Always take ACTION with tools, don't just describe what you would do
6. Be thorough with connections - every input that needs data must be connected`;
}
