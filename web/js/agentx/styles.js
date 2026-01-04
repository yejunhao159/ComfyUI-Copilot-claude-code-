/**
 * AgentX Sidebar Styles
 */

export const STYLES = `
/* Toggle Button */
#agentx-toggle-btn {
    position: fixed !important;
    bottom: 80px !important;
    right: 20px !important;
    width: 56px !important;
    height: 56px !important;
    border-radius: 50% !important;
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
    color: white !important;
    border: none !important;
    cursor: pointer !important;
    box-shadow: 0 4px 15px rgba(79, 70, 229, 0.4) !important;
    z-index: 99999 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.3s ease !important;
}
#agentx-toggle-btn:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 20px rgba(79, 70, 229, 0.5);
}
#agentx-toggle-btn.active {
    background: linear-gradient(135deg, #4338ca 0%, #3730a3 100%);
}
#agentx-toggle-btn svg {
    width: 24px;
    height: 24px;
}

/* Sidebar Panel */
#agentx-sidebar {
    position: fixed;
    top: 0;
    right: -420px;
    width: 400px;
    height: 100vh;
    background: #1a1a2e;
    border-left: 1px solid #2d2d44;
    display: flex;
    flex-direction: column;
    z-index: 9999;
    transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    box-shadow: -5px 0 30px rgba(0, 0, 0, 0.3);
}
#agentx-sidebar.open {
    right: 0;
}

/* Header */
.agentx-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    background: linear-gradient(135deg, #1e1e3f 0%, #16162b 100%);
    border-bottom: 1px solid #2d2d44;
}
.agentx-logo {
    display: flex;
    align-items: center;
    gap: 10px;
}
.agentx-logo-icon {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.agentx-logo-icon svg {
    width: 18px;
    height: 18px;
    color: white;
}
.agentx-title {
    font-weight: 600;
    color: #fff;
    font-size: 16px;
}
.agentx-header-actions {
    display: flex;
    gap: 8px;
}
.agentx-header-actions button {
    background: rgba(255, 255, 255, 0.1);
    border: none;
    color: #a0a0b0;
    cursor: pointer;
    font-size: 16px;
    padding: 8px 12px;
    border-radius: 6px;
    transition: all 0.2s;
}
.agentx-header-actions button:hover {
    background: rgba(255, 255, 255, 0.15);
    color: #fff;
}

/* Sync Button Special Styling */
.agentx-sync-btn {
    position: relative;
}
.agentx-sync-btn svg {
    width: 16px;
    height: 16px;
    transition: transform 0.3s ease;
}
.agentx-sync-btn.syncing svg {
    animation: spin 1s linear infinite;
}
.agentx-sync-btn.syncing {
    background: rgba(99, 102, 241, 0.3) !important;
    pointer-events: none;
}

/* Messages Area */
.agentx-messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    scroll-behavior: smooth;
}
.agentx-messages::-webkit-scrollbar {
    width: 6px;
}
.agentx-messages::-webkit-scrollbar-track {
    background: transparent;
}
.agentx-messages::-webkit-scrollbar-thumb {
    background: #3d3d5c;
    border-radius: 3px;
}

/* Welcome Message */
.agentx-welcome {
    text-align: center;
    padding: 40px 20px;
}
.agentx-welcome-icon {
    width: 64px;
    height: 64px;
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 20px;
}
.agentx-welcome-icon svg {
    width: 32px;
    height: 32px;
    color: white;
}
.agentx-welcome h3 {
    color: #fff;
    font-size: 18px;
    margin: 0 0 12px 0;
}
.agentx-welcome p {
    color: #8888a0;
    font-size: 14px;
    line-height: 1.6;
    margin: 0 0 16px 0;
}
.agentx-welcome ul {
    text-align: left;
    color: #a0a0b8;
    font-size: 13px;
    line-height: 1.8;
    padding-left: 24px;
    margin: 0;
}

/* Chat Messages */
.agentx-message {
    margin-bottom: 16px;
    max-width: 90%;
    animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.agentx-message.user {
    margin-left: auto;
}
.agentx-message.assistant {
    margin-right: auto;
}
.agentx-message-content {
    padding: 12px 16px;
    border-radius: 16px;
    font-size: 14px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
}
.agentx-message.user .agentx-message-content {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
    color: white;
    border-bottom-right-radius: 4px;
}
.agentx-message.assistant .agentx-message-content {
    background: #2a2a4a;
    color: #e0e0f0;
    border-bottom-left-radius: 4px;
}

/* Typing Indicator */
.agentx-typing {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #8888a0;
    font-size: 13px;
    padding: 12px 16px;
}
.agentx-typing-dots {
    display: flex;
    gap: 4px;
}
.agentx-typing-dots span {
    width: 6px;
    height: 6px;
    background: #6366f1;
    border-radius: 50%;
    animation: bounce 1.4s infinite;
}
.agentx-typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.agentx-typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
    0%, 60%, 100% { transform: translateY(0); }
    30% { transform: translateY(-6px); }
}

/* Error & System Messages */
.agentx-error {
    color: #f87171;
    font-size: 13px;
    padding: 12px 16px;
    background: rgba(248, 113, 113, 0.1);
    border-radius: 8px;
    margin: 8px 0;
}
.agentx-system {
    text-align: center;
    color: #8888a0;
    font-size: 13px;
    padding: 8px;
}

/* Tool Calls */
.agentx-tools {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(255,255,255,0.1);
}
.agentx-tools-header {
    font-size: 11px;
    color: #888;
    margin-bottom: 8px;
}
.agentx-tool {
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 8px;
    margin-bottom: 8px;
    overflow: hidden;
}
.agentx-tool-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    cursor: pointer;
    transition: background 0.2s;
}
.agentx-tool-header:hover {
    background: rgba(99, 102, 241, 0.1);
}
.agentx-tool-left {
    display: flex;
    align-items: center;
    gap: 8px;
}
.agentx-tool-icon { font-size: 14px; }
.agentx-tool-name { font-size: 12px; font-weight: 500; color: #a5b4fc; }
.agentx-tool-badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 500;
}
.agentx-tool-badge.workflow { background: rgba(59, 130, 246, 0.2); color: #93c5fd; }
.agentx-tool-badge.node { background: rgba(34, 197, 94, 0.2); color: #86efac; }
.agentx-tool-badge.connection { background: rgba(168, 85, 247, 0.2); color: #d8b4fe; }
.agentx-tool-badge.search { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
.agentx-tool-badge.execution { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
.agentx-tool-status { display: flex; align-items: center; gap: 6px; }
.agentx-tool-status-icon { font-size: 12px; }
.agentx-tool-status-icon.success { color: #22c55e; }
.agentx-tool-status-icon.error { color: #ef4444; }
.agentx-tool-expand { color: #666; font-size: 10px; }
.agentx-tool-details {
    display: none;
    padding: 10px 12px;
    background: rgba(0,0,0,0.2);
    border-top: 1px solid rgba(99, 102, 241, 0.2);
}
.agentx-tool-details.expanded { display: block; }
.agentx-tool-details-label { font-size: 10px; color: #666; margin-bottom: 4px; }
.agentx-tool-details-content {
    font-size: 11px;
    color: #aaa;
    background: rgba(0,0,0,0.3);
    padding: 6px 8px;
    border-radius: 4px;
    overflow: auto;
    max-height: 100px;
    white-space: pre-wrap;
    word-break: break-all;
    margin-bottom: 8px;
}
.agentx-tool-details-content.success { background: rgba(34, 197, 94, 0.1); }
.agentx-tool-details-content.error { background: rgba(239, 68, 68, 0.1); color: #fca5a5; }

/* Streaming Message */
.agentx-message.streaming .agentx-message-content::after {
    content: "▋";
    animation: blink 1s infinite;
}
@keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}

/* Tool Indicator (during streaming) */
.agentx-tool-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    margin-top: 8px;
    background: rgba(99, 102, 241, 0.1);
    border-radius: 6px;
    font-size: 12px;
    color: #a5b4fc;
}
.agentx-tool-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(99, 102, 241, 0.3);
    border-top-color: #6366f1;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}
@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Input Area */
.agentx-input-area {
    display: flex;
    gap: 12px;
    padding: 16px 20px;
    background: #16162b;
    border-top: 1px solid #2d2d44;
}
#agentx-input {
    flex: 1;
    background: #1a1a2e;
    border: 1px solid #2d2d44;
    border-radius: 12px;
    padding: 12px 16px;
    color: #fff;
    font-size: 14px;
    resize: none;
    outline: none;
    transition: border-color 0.2s;
    min-height: 44px;
    max-height: 120px;
}
#agentx-input:focus {
    border-color: #6366f1;
}
#agentx-input::placeholder {
    color: #5a5a7a;
}
#agentx-send {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
    border: none;
    border-radius: 12px;
    padding: 0 20px;
    color: white;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
}
#agentx-send:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
}
#agentx-send:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
`;

export function injectStyles() {
    if (document.getElementById("agentx-styles")) return;
    const style = document.createElement("style");
    style.id = "agentx-styles";
    style.textContent = STYLES;
    document.head.appendChild(style);
}
