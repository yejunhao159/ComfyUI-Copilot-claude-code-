/**
 * ComfyUI AgentX Extension
 *
 * AI assistant sidebar for ComfyUI workflow manipulation.
 */

import { app } from "/scripts/app.js";
import { injectStyles } from "./agentx/styles.js";
import { ICONS } from "./agentx/icons.js";
import { renderToolCalls, bindToolExpanders, escapeHtml } from "./agentx/tools.js";
import { createSession, sendMessage, buildSystemPrompt, createStreamConnection, sendViaWebSocket, syncWorkflowToBackend } from "./agentx/api.js";
import { getWorkflowContext, loadWorkflowToCanvas, getFullWorkflowAsync } from "./agentx/workflow.js";

class AgentXSidebar {
    constructor() {
        this.sidebar = null;
        this.chatContainer = null;
        this.inputArea = null;
        this.sessionId = null;
        this.isOpen = false;
        this.isLoading = false;
        this.ws = null;  // WebSocket connection
        this.useStreaming = true;  // Enable streaming by default
        this.currentWorkflow = null;  // Cached workflow from canvas
    }

    init() {
        injectStyles();
        this.createToggleButton();
        this.createSidebar();
        this.bindEvents();
        console.log("[AgentX] Sidebar initialized");
    }

    createToggleButton() {
        const btn = document.createElement("button");
        btn.id = "agentx-toggle-btn";
        btn.innerHTML = ICONS.robot;
        btn.title = "Toggle AgentX Assistant";
        btn.onclick = () => this.toggle();
        document.body.appendChild(btn);
    }

    createSidebar() {
        const sidebar = document.createElement("div");
        sidebar.id = "agentx-sidebar";
        sidebar.innerHTML = `
            <div class="agentx-header">
                <div class="agentx-logo">
                    <div class="agentx-logo-icon">${ICONS.robot}</div>
                    <span class="agentx-title">AgentX</span>
                </div>
                <div class="agentx-header-actions">
                    <button id="agentx-sync" title="Sync Canvas Workflow" class="agentx-sync-btn">${ICONS.sync}</button>
                    <button id="agentx-new-chat" title="New Chat">+</button>
                    <button id="agentx-close" title="Close">×</button>
                </div>
            </div>
            <div class="agentx-messages">
                <div class="agentx-welcome">
                    <div class="agentx-welcome-icon">${ICONS.robot}</div>
                    <h3>ComfyUI Assistant</h3>
                    <p>I can help you create, modify, and debug workflows.</p>
                    <ul>
                        <li>Create text-to-image workflows</li>
                        <li>Search and add nodes</li>
                        <li>Connect nodes automatically</li>
                        <li>Debug workflow errors</li>
                    </ul>
                </div>
            </div>
            <div class="agentx-input-area">
                <textarea id="agentx-input" placeholder="Ask about workflows..." rows="1"></textarea>
                <button id="agentx-send">${ICONS.send}</button>
            </div>
        `;
        document.body.appendChild(sidebar);

        this.sidebar = sidebar;
        this.chatContainer = sidebar.querySelector(".agentx-messages");
        this.inputArea = sidebar.querySelector("#agentx-input");
    }

    bindEvents() {
        document.getElementById("agentx-close").onclick = () => this.close();
        document.getElementById("agentx-new-chat").onclick = () => this.newChat();
        document.getElementById("agentx-sync").onclick = () => this.syncWorkflow();
        document.getElementById("agentx-send").onclick = () => this.send();

        this.inputArea.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                this.send();
            }
        });

        // Auto-resize textarea
        this.inputArea.addEventListener("input", () => {
            this.inputArea.style.height = "auto";
            this.inputArea.style.height = Math.min(this.inputArea.scrollHeight, 120) + "px";
        });
    }

    toggle() {
        this.isOpen ? this.close() : this.open();
    }

    open() {
        this.sidebar.classList.add("open");
        document.getElementById("agentx-toggle-btn").classList.add("active");
        this.isOpen = true;
        this.inputArea.focus();
    }

    close() {
        this.sidebar.classList.remove("open");
        document.getElementById("agentx-toggle-btn").classList.remove("active");
        this.isOpen = false;
    }

    async newChat() {
        try {
            // Close existing WebSocket
            if (this.ws) {
                this.ws.close();
                this.ws = null;
            }

            const session = await createSession();
            this.sessionId = session.session_id;
            this.chatContainer.innerHTML = "";
            this.addSystemMessage("New chat started. How can I help?");

            // Setup streaming connection
            if (this.useStreaming) {
                this.setupStreamConnection();
            }
        } catch (e) {
            console.error("[AgentX] Failed to create session:", e);
            this.addErrorMessage("Failed to start chat.");
        }
    }

    /**
     * Sync current canvas workflow to backend
     * This allows Claude to read and analyze the user's workflow
     */
    async syncWorkflow() {
        const syncBtn = document.getElementById("agentx-sync");
        syncBtn.classList.add("syncing");

        try {
            // Get full workflow from canvas
            const workflowData = await getFullWorkflowAsync();
            this.currentWorkflow = workflowData;

            if (!workflowData.workflow || Object.keys(workflowData.workflow).length === 0) {
                this.addSystemMessage("Canvas is empty. Create a workflow first or ask me to design one!");
                syncBtn.classList.remove("syncing");
                return;
            }

            // Sync to backend
            const result = await syncWorkflowToBackend(workflowData);

            if (result.success) {
                this.addSystemMessage(`✓ Synced ${result.node_count} nodes from canvas. I can now analyze and modify your workflow!`);
                console.log("[AgentX] Workflow synced:", result);
            } else {
                this.addErrorMessage("Failed to sync workflow: " + (result.error || "Unknown error"));
            }
        } catch (e) {
            console.error("[AgentX] Sync failed:", e);
            this.addErrorMessage("Failed to sync workflow.");
        } finally {
            syncBtn.classList.remove("syncing");
        }
    }

    setupStreamConnection() {
        if (!this.sessionId) return;

        this.ws = createStreamConnection(this.sessionId, {
            onOpen: () => {
                console.log("[AgentX] Stream ready");
            },
            onText: (text) => {
                this.appendToCurrentMessage(text);
            },
            onToolCall: (tool) => {
                console.log("[AgentX] Tool called:", tool.name);
                this.addToolIndicator(tool);
            },
            onToolResult: (result) => {
                console.log("[AgentX] Tool result:", result);
            },
            onTurnComplete: (data) => {
                console.log("[AgentX] Turn complete:", data);
                this.finishCurrentMessage(data.executed_tools);
            },
            onError: (error) => {
                console.error("[AgentX] Stream error:", error);
                this.addErrorMessage("Connection error.");
            },
            onDone: () => {
                console.log("[AgentX] Stream ended");
            }
        });
    }

    appendToCurrentMessage(text) {
        let msg = this.chatContainer.querySelector(".agentx-message.assistant.streaming");
        if (!msg) {
            msg = document.createElement("div");
            msg.className = "agentx-message assistant streaming";
            msg.innerHTML = `<div class="agentx-message-content"></div>`;
            this.chatContainer.appendChild(msg);
        }

        const content = msg.querySelector(".agentx-message-content");
        content.textContent += text;
        this.scrollToBottom();
    }

    addToolIndicator(tool) {
        let msg = this.chatContainer.querySelector(".agentx-message.assistant.streaming");
        if (!msg) {
            msg = document.createElement("div");
            msg.className = "agentx-message assistant streaming";
            msg.innerHTML = `<div class="agentx-message-content"></div>`;
            this.chatContainer.appendChild(msg);
        }

        // Add tool indicator
        let indicator = msg.querySelector(".agentx-tool-indicator");
        if (!indicator) {
            indicator = document.createElement("div");
            indicator.className = "agentx-tool-indicator";
            msg.appendChild(indicator);
        }
        indicator.innerHTML = `<span class="agentx-tool-spinner"></span> Calling ${tool.name}...`;
        this.scrollToBottom();
    }

    finishCurrentMessage(toolCalls) {
        const msg = this.chatContainer.querySelector(".agentx-message.assistant.streaming");
        if (msg) {
            msg.classList.remove("streaming");

            // Remove tool indicator
            const indicator = msg.querySelector(".agentx-tool-indicator");
            if (indicator) indicator.remove();

            // Process workflow updates
            if (toolCalls) {
                for (const tc of toolCalls) {
                    if (tc.name === "update_workflow" && tc.arguments?.workflow_data) {
                        loadWorkflowToCanvas(tc.arguments.workflow_data);
                    }
                }

                // Add tool calls display
                const toolsHtml = renderToolCalls(toolCalls);
                if (toolsHtml) {
                    msg.insertAdjacentHTML("beforeend", toolsHtml);
                    bindToolExpanders(msg);
                }
            }
        }

        this.isLoading = false;
        document.getElementById("agentx-send").disabled = false;

        // Remove typing indicator
        const typing = this.chatContainer.querySelector(".agentx-typing");
        if (typing) typing.remove();
    }

    addSystemMessage(text) {
        const msg = document.createElement("div");
        msg.className = "agentx-system";
        msg.innerHTML = `<div class="agentx-message-content">${text}</div>`;
        this.chatContainer.appendChild(msg);
        this.scrollToBottom();
    }

    addErrorMessage(text) {
        const msg = document.createElement("div");
        msg.className = "agentx-error";
        msg.textContent = text;
        this.chatContainer.appendChild(msg);
        this.scrollToBottom();
    }

    addMessage(role, content, toolCalls = null) {
        const msg = document.createElement("div");
        msg.className = `agentx-message ${role}`;

        // Load workflow if update_workflow was called
        if (toolCalls) {
            for (const tc of toolCalls) {
                if (tc.name === "update_workflow" && tc.arguments?.workflow_data) {
                    loadWorkflowToCanvas(tc.arguments.workflow_data);
                }
            }
        }

        let html = '';
        if (content) {
            html += `<div class="agentx-message-content">${escapeHtml(content)}</div>`;
        }
        if (role === 'assistant' && toolCalls?.length > 0) {
            html += renderToolCalls(toolCalls);
        }

        msg.innerHTML = html;
        this.chatContainer.appendChild(msg);
        bindToolExpanders(msg);
        this.scrollToBottom();
    }

    scrollToBottom() {
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }

    async send() {
        const content = this.inputArea.value.trim();
        if (!content || this.isLoading) return;

        // Create session if needed
        if (!this.sessionId) {
            try {
                const session = await createSession();
                this.sessionId = session.session_id;

                // Setup streaming if enabled
                if (this.useStreaming) {
                    this.setupStreamConnection();
                }
            } catch (e) {
                this.addErrorMessage("Failed to create session.");
                return;
            }
        }

        // Clear welcome
        const welcome = this.chatContainer.querySelector(".agentx-welcome");
        if (welcome) welcome.remove();

        // Add user message
        this.addMessage("user", content);
        this.inputArea.value = "";
        this.inputArea.style.height = "auto";

        // Show typing
        const typing = document.createElement("div");
        typing.className = "agentx-typing";
        typing.innerHTML = `<div class="agentx-typing-dots"><span></span><span></span><span></span></div><span>Thinking...</span>`;
        this.chatContainer.appendChild(typing);
        this.scrollToBottom();

        this.isLoading = true;
        const sendBtn = document.getElementById("agentx-send");
        sendBtn.disabled = true;

        // Build system prompt with workflow context
        // Use cached workflow if available, otherwise get fresh
        const workflowContext = getWorkflowContext();
        const system = buildSystemPrompt(workflowContext, this.currentWorkflow);

        // Try streaming first, fall back to non-streaming
        if (this.useStreaming && this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
                sendViaWebSocket(this.ws, content, system);
                // The response will be handled by WebSocket callbacks
                return;
            } catch (e) {
                console.warn("[AgentX] WebSocket send failed, falling back to HTTP:", e);
            }
        }

        // Non-streaming fallback
        try {
            const data = await sendMessage(this.sessionId, content, system);

            typing.remove();

            if (data.error) {
                this.addErrorMessage(`Error: ${data.error}`);
            } else {
                // Process workflow updates
                if (data.executed_tools) {
                    for (const tool of data.executed_tools) {
                        if (tool.name === "update_workflow" && tool.arguments?.workflow_data) {
                            loadWorkflowToCanvas(tool.arguments.workflow_data);
                        }
                    }
                }
                this.addMessage("assistant", data.content || "", data.executed_tools);
            }
        } catch (e) {
            typing.remove();
            console.error("[AgentX] Send failed:", e);
            this.addErrorMessage("Failed to send message.");
        } finally {
            this.isLoading = false;
            sendBtn.disabled = false;
        }
    }
}

// Boot when ComfyUI is ready
function boot() {
    if (typeof LiteGraph !== "undefined" && Object.keys(LiteGraph.registered_node_types || {}).length > 0) {
        console.log("[AgentX] Initializing...");
        new AgentXSidebar().init();
    } else {
        setTimeout(boot, 500);
    }
}

app.registerExtension({
    name: "AgentX.Sidebar",
    async setup() {
        console.log("[AgentX] Extension registered");
        boot();
    }
});
