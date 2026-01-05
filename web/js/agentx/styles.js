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
    transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
}
#agentx-toggle-btn:hover {
    transform: scale(1.1) rotate(5deg);
    box-shadow: 0 6px 20px rgba(79, 70, 229, 0.5);
}
#agentx-toggle-btn.active {
    background: #1a1c2e !important;
    transform: scale(0.9) rotate(-90deg);
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
    background: #0f111a;
    border-left: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
    flex-direction: column;
    z-index: 9999;
    transition: right 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    box-shadow: -10px 0 50px rgba(0, 0, 0, 0.5);
}
#agentx-sidebar.open {
    right: 0;
}

/* Header */
.agentx-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    background: rgba(15, 17, 26, 0.8);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.agentx-logo {
    display: flex;
    align-items: center;
    gap: 12px;
}
.agentx-logo-icon {
    width: 34px;
    height: 34px;
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 20px rgba(99, 102, 241, 0.3);
}
.agentx-logo-icon svg {
    width: 20px;
    height: 20px;
    color: white;
}
.agentx-title {
    font-weight: 700;
    color: #fff;
    font-size: 17px;
    letter-spacing: -0.02em;
}
.agentx-header-actions {
    display: flex;
    gap: 8px;
}
.agentx-header-actions button {
    background: rgba(255, 255, 255, 0.05);
    border: none;
    color: #a0a0b0;
    cursor: pointer;
    font-size: 16px;
    padding: 8px 12px;
    border-radius: 8px;
    transition: all 0.2s;
}
.agentx-header-actions button:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
}

/* Messages Area */
.agentx-messages {
    flex: 1;
    overflow-y: auto;
    padding: 24px 20px;
    scroll-behavior: smooth;
    background-image: radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.05) 0%, transparent 50%);
}
.agentx-messages::-webkit-scrollbar {
    width: 4px;
}
.agentx-messages::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
}

/* Chat Messages */
.agentx-message {
    margin-bottom: 24px;
    max-width: 90%;
    animation: messageIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes messageIn {
    from { opacity: 0; transform: translateY(15px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}
.agentx-message.user {
    margin-left: auto;
}
.agentx-message.assistant {
    margin-right: auto;
}
.agentx-message-content {
    padding: 14px 18px;
    border-radius: 20px;
    font-size: 14.5px;
    line-height: 1.65;
    word-break: break-word;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}
.agentx-message.user .agentx-message-content {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
    color: white;
    border-bottom-right-radius: 4px;
}
.agentx-message.assistant .agentx-message-content {
    background: #1a1c2e;
    color: #d1d5db;
    border-bottom-left-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.03);
}

/* Markdown elements */
.agentx-message-content pre {
    background: #0b0c14;
    padding: 12px;
    border-radius: 12px;
    overflow-x: auto;
    margin: 12px 0;
    border: 1px solid rgba(255, 255, 255, 0.05);
}
.agentx-message-content code {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 12.5px;
}
.agentx-message-content code.inline {
    background: rgba(99, 102, 241, 0.2);
    padding: 2px 6px;
    border-radius: 6px;
    color: #a5b4fc;
    font-size: 0.9em;
}
.agentx-message.user .agentx-message-content code.inline {
    background: rgba(255, 255, 255, 0.2);
    color: #fff;
}
.agentx-message-content h3 {
    font-size: 16px;
    font-weight: 700;
    margin: 18px 0 10px 0;
    color: #fff;
}
.agentx-message-content ul {
    margin: 10px 0;
    padding-left: 22px;
}
.agentx-message-content li {
    margin-bottom: 6px;
}
.agentx-message-content a {
    color: #818cf8;
    text-decoration: none;
    font-weight: 500;
}
.agentx-message-content strong {
    color: #fff;
    font-weight: 700;
}

/* Input Area */
.agentx-input-area {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 20px;
    background: #0f111a;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
}
.agentx-input-wrapper {
    position: relative;
    display: flex;
    gap: 10px;
    align-items: flex-end;
}
#agentx-input {
    flex: 1;
    background: #161826;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    padding: 14px 18px;
    color: #fff;
    font-size: 14.5px;
    resize: none;
    outline: none;
    transition: all 0.3s;
    min-height: 48px;
    max-height: 150px;
}
#agentx-input:focus {
    border-color: #6366f1;
    background: #1a1c2e;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}
#agentx-send {
    background: #6366f1;
    border: none;
    border-radius: 14px;
    width: 48px;
    height: 48px;
    flex-shrink: 0;
    color: white;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
}
#agentx-send:hover:not(:disabled) {
    background: #4f46e5;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}
#agentx-send:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}
#agentx-send svg {
    width: 20px;
    height: 20px;
}
`;

export function injectStyles() {
    if (document.getElementById("agentx-styles")) return;
    const style = document.createElement("style");
    style.id = "agentx-styles";
    style.textContent = STYLES;
    document.head.appendChild(style);
}