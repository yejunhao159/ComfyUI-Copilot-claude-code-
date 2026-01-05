/**
 * AgentX API Client
 * Uses HTTP Streaming (NDJSON) for reliable message delivery
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

/**
 * Stream chat messages using HTTP Streaming (NDJSON format)
 * This replaces WebSocket for reliable, ordered message delivery
 *
 * @param {string} sessionId - Session ID
 * @param {string} content - User message
 * @param {string} system - System prompt
 * @param {object} callbacks - Event callbacks
 * @returns {Promise<void>}
 */
export async function streamChat(sessionId, content, system, callbacks) {
    const { onStart, onText, onToolStart, onToolEnd, onDone, onError } = callbacks;

    try {
        const response = await fetch(`${API_BASE}/sessions/${sessionId}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content, system })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error("No response body");
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (!line.trim()) continue;

                try {
                    const event = JSON.parse(line);
                    handleStreamEvent(event, callbacks);
                } catch (e) {
                    console.warn("[AgentX] Failed to parse NDJSON line:", line);
                }
            }
        }

        // Process any remaining buffer
        if (buffer.trim()) {
            try {
                const event = JSON.parse(buffer);
                handleStreamEvent(event, callbacks);
            } catch (e) {
                console.warn("[AgentX] Failed to parse final NDJSON:", buffer);
            }
        }
    } catch (e) {
        console.error("[AgentX] Stream error:", e);
        onError?.(e);
    }
}

function handleStreamEvent(event, callbacks) {
    const { onStart, onText, onToolStart, onToolEnd, onDone, onError } = callbacks;

    switch (event.type) {
        case "start":
            onStart?.();
            break;

        case "text":
            if (event.content) {
                onText?.(event.content);
            }
            break;

        case "tool_start":
            onToolStart?.({
                id: event.tool_id,
                name: event.name,
                arguments: event.input
            });
            break;

        case "tool_end":
            onToolEnd?.({
                id: event.tool_id,
                name: event.name,
                arguments: event.input,
                result: event.result,
                success: event.success
            });
            break;

        case "done":
            onDone?.(event.executed_tools || []);
            break;

        case "error":
            onError?.(new Error(event.message || "Unknown error"));
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
1. When user asks to CREATE a workflow → Output the complete workflow JSON in a \`\`\`json code block
2. When modifying existing workflow → use modify_node, add_node, connect_nodes tools
3. Workflow JSON in code blocks will be auto-loaded to canvas
4. To test workflow → use execute_workflow, then get_execution_result with wait=true
5. Always take ACTION - output workflow JSON or use tools, don't just describe
6. Be thorough with connections - every input that needs data must be connected

## IMPORTANT: When creating workflows, output them like this:
\`\`\`json
{
  "1": {"class_type": "CheckpointLoaderSimple", "inputs": {...}},
  "2": {"class_type": "CLIPTextEncode", "inputs": {...}},
  ...
}
\`\`\`
The system will automatically detect and load the workflow to the ComfyUI canvas.`;
}
