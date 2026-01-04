/**
 * Tool Rendering for AgentX
 */

// Tool metadata
const TOOL_META = {
    get_workflow: { icon: '📋', category: 'workflow', label: 'Workflow' },
    update_workflow: { icon: '📝', category: 'workflow', label: 'Workflow' },
    clear_workflow: { icon: '🗑️', category: 'workflow', label: 'Workflow' },
    add_node: { icon: '➕', category: 'node', label: 'Node' },
    remove_node: { icon: '➖', category: 'node', label: 'Node' },
    modify_node: { icon: '✏️', category: 'node', label: 'Node' },
    connect_nodes: { icon: '🔗', category: 'connection', label: 'Connection' },
    disconnect_input: { icon: '✂️', category: 'connection', label: 'Connection' },
    search_nodes: { icon: '🔍', category: 'search', label: 'Search' },
    get_node_info: { icon: 'ℹ️', category: 'search', label: 'Search' },
    list_node_categories: { icon: '📂', category: 'search', label: 'Search' },
    execute_workflow: { icon: '▶️', category: 'execution', label: 'Execution' },
    get_execution_result: { icon: '📊', category: 'execution', label: 'Execution' },
    interrupt_execution: { icon: '⏹️', category: 'execution', label: 'Execution' },
};

export function getToolMeta(name) {
    return TOOL_META[name] || { icon: '🔧', category: 'other', label: 'Other' };
}

export function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

export function renderToolCalls(toolCalls) {
    if (!toolCalls || toolCalls.length === 0) return '';

    let html = '<div class="agentx-tools">';
    html += `<div class="agentx-tools-header">🔧 ${toolCalls.length} tool${toolCalls.length > 1 ? 's' : ''} executed</div>`;

    toolCalls.forEach((tc) => {
        const meta = getToolMeta(tc.name);
        const hasResult = tc.result !== undefined && tc.result !== null;
        const hasError = !!tc.error;
        const status = hasError ? 'error' : hasResult ? 'success' : 'pending';
        const statusIcon = status === 'success' ? '✓' : status === 'error' ? '✗' : '⋯';

        html += `
            <div class="agentx-tool">
                <div class="agentx-tool-header">
                    <div class="agentx-tool-left">
                        <span class="agentx-tool-icon">${meta.icon}</span>
                        <span class="agentx-tool-name">${tc.name}</span>
                        <span class="agentx-tool-badge ${meta.category}">${meta.label}</span>
                    </div>
                    <div class="agentx-tool-status">
                        <span class="agentx-tool-status-icon ${status}">${statusIcon}</span>
                        <span class="agentx-tool-expand">▼</span>
                    </div>
                </div>
                <div class="agentx-tool-details">
                    <div class="agentx-tool-details-label">Arguments:</div>
                    <div class="agentx-tool-details-content">${escapeHtml(JSON.stringify(tc.arguments || {}, null, 2))}</div>
                    ${hasResult ? `
                    <div class="agentx-tool-details-label">Result:</div>
                    <div class="agentx-tool-details-content success">${escapeHtml(JSON.stringify(tc.result, null, 2))}</div>` : ''}
                    ${hasError ? `
                    <div class="agentx-tool-details-label">Error:</div>
                    <div class="agentx-tool-details-content error">${escapeHtml(tc.error)}</div>` : ''}
                </div>
            </div>
        `;
    });

    html += '</div>';
    return html;
}

export function bindToolExpanders(container) {
    container.querySelectorAll('.agentx-tool-header').forEach(header => {
        header.addEventListener('click', () => {
            const details = header.nextElementSibling;
            const expand = header.querySelector('.agentx-tool-expand');
            if (details) {
                details.classList.toggle('expanded');
                expand.textContent = details.classList.contains('expanded') ? '▲' : '▼';
            }
        });
    });
}
