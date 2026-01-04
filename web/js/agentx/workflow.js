/**
 * Workflow utilities for AgentX
 */

import { app } from "/scripts/app.js";

/**
 * Get a brief summary of the current workflow (for quick context)
 */
export function getWorkflowContext() {
    try {
        const graph = app.graph;
        if (!graph || !graph._nodes || graph._nodes.length === 0) {
            return "No workflow loaded (empty canvas).";
        }

        const nodes = graph._nodes;
        const nodeTypes = {};
        nodes.forEach(n => {
            nodeTypes[n.type] = (nodeTypes[n.type] || 0) + 1;
        });

        const summary = Object.entries(nodeTypes)
            .map(([type, count]) => `${type}: ${count}`)
            .join(", ");

        return `Workflow has ${nodes.length} nodes: ${summary}`;
    } catch (e) {
        return "Unable to get workflow context.";
    }
}

/**
 * Get the complete workflow in ComfyUI API format
 * This includes all nodes, their parameters, and connections
 * @returns {Object} Complete workflow data ready for Claude to analyze/modify
 */
export function getFullWorkflow() {
    try {
        const graph = app.graph;
        if (!graph || !graph._nodes || graph._nodes.length === 0) {
            return { workflow: {}, node_count: 0, message: "Empty canvas" };
        }

        // Use ComfyUI's built-in method to get API format
        // This is the most accurate way to get the workflow
        if (typeof app.graphToPrompt === 'function') {
            // graphToPrompt returns a Promise with { output, workflow }
            // output is the API format, workflow is the graph format
            const result = app.graphToPrompt();

            // Handle both sync and async returns
            if (result && result.then) {
                // It's a Promise - we'll handle this in the async wrapper
                return result.then(data => ({
                    workflow: data.output,
                    node_count: Object.keys(data.output).length,
                    graph_format: data.workflow,  // Include for reference
                    message: "Workflow loaded from canvas"
                }));
            } else if (result && result.output) {
                return {
                    workflow: result.output,
                    node_count: Object.keys(result.output).length,
                    graph_format: result.workflow,
                    message: "Workflow loaded from canvas"
                };
            }
        }

        // Fallback: manually convert graph to API format
        const workflow = {};
        const nodes = graph._nodes;

        nodes.forEach(node => {
            const nodeId = String(node.id);
            const nodeData = {
                class_type: node.type,
                inputs: {}
            };

            // Get widget values (parameters)
            if (node.widgets) {
                node.widgets.forEach(widget => {
                    if (widget.name && widget.value !== undefined) {
                        nodeData.inputs[widget.name] = widget.value;
                    }
                });
            }

            // Get connections (inputs from other nodes)
            if (node.inputs) {
                node.inputs.forEach((input, slotIndex) => {
                    if (input.link !== null && input.link !== undefined) {
                        // Find the source of this link
                        const link = graph.links[input.link];
                        if (link) {
                            // link format: [link_id, origin_id, origin_slot, target_id, target_slot, type]
                            const sourceNodeId = link.origin_id;
                            const sourceSlot = link.origin_slot;
                            nodeData.inputs[input.name] = [String(sourceNodeId), sourceSlot];
                        }
                    }
                });
            }

            // Add metadata
            if (node.title && node.title !== node.type) {
                nodeData._meta = { title: node.title };
            }

            workflow[nodeId] = nodeData;
        });

        return {
            workflow: workflow,
            node_count: Object.keys(workflow).length,
            message: "Workflow loaded from canvas (fallback method)"
        };

    } catch (e) {
        console.error("[AgentX] Failed to get full workflow:", e);
        return { workflow: {}, node_count: 0, error: e.message };
    }
}

/**
 * Async version of getFullWorkflow that properly handles Promises
 */
export async function getFullWorkflowAsync() {
    try {
        const result = getFullWorkflow();

        // If it's a Promise, await it
        if (result && result.then) {
            return await result;
        }

        return result;
    } catch (e) {
        console.error("[AgentX] Failed to get full workflow async:", e);
        return { workflow: {}, node_count: 0, error: e.message };
    }
}

export async function loadWorkflowToCanvas(workflowData) {
    try {
        console.log("[AgentX] Loading workflow to canvas, data:", workflowData);

        // Method 1: Use ComfyUI's native loadApiJson if available
        if (typeof app.loadApiJson === 'function') {
            console.log("[AgentX] Using app.loadApiJson");
            await app.loadApiJson(workflowData);
            return;
        }

        // Method 2: Convert API format to graph format
        const graphData = convertToGraphFormat(workflowData);
        console.log("[AgentX] Converted graph data:", graphData);

        if (app.graph) {
            app.graph.clear();
        }

        if (typeof app.loadGraphData === 'function') {
            console.log("[AgentX] Using app.loadGraphData");
            await app.loadGraphData(graphData);
        } else if (app.graph) {
            console.log("[AgentX] Using app.graph.configure");
            app.graph.configure(graphData);
        }

        // Force reconnection of links after loading
        if (app.graph) {
            // Trigger link recalculation
            app.graph._nodes.forEach(node => {
                if (node.onConnectionsChange) {
                    node.onConnectionsChange();
                }
            });
            app.graph.change();
        }

        if (app.canvas) {
            app.canvas.setDirty(true, true);
            app.canvas.draw(true, true);
        }

        console.log("[AgentX] Workflow loaded, nodes:", app.graph?._nodes?.length || 0);
        console.log("[AgentX] Links:", app.graph?.links);
    } catch (e) {
        console.error("[AgentX] Failed to load workflow:", e);
    }
}

function convertToGraphFormat(apiFormat) {
    const nodes = [];
    const links = [];
    let linkId = 1;
    const nodeIdMap = {}; // nodeId -> node object

    // First pass: Create all nodes with proper structure
    Object.entries(apiFormat).forEach(([nodeId, nodeData], index) => {
        const numId = parseInt(nodeId) || index + 1;

        const node = {
            id: numId,
            type: nodeData.class_type,
            pos: [100 + (index % 4) * 300, 100 + Math.floor(index / 4) * 200],
            size: { "0": 250, "1": 150 },
            flags: {},
            order: index,
            mode: 0,
            inputs: [],
            outputs: [],
            properties: { "Node name for S&R": nodeData.class_type },
            widgets_values: []
        };

        // Extract widget values (non-connection inputs)
        if (nodeData.inputs) {
            Object.entries(nodeData.inputs).forEach(([key, value]) => {
                if (!Array.isArray(value)) {
                    node.widgets_values.push(value);
                }
            });
        }

        // Set title
        if (nodeData._meta?.title) {
            node.title = nodeData._meta.title;
        }

        nodes.push(node);
        nodeIdMap[nodeId] = node;
    });

    // Second pass: Create links and properly configure inputs/outputs
    Object.entries(apiFormat).forEach(([nodeId, nodeData]) => {
        if (!nodeData.inputs) return;

        const targetNode = nodeIdMap[nodeId];
        let inputSlot = 0;

        Object.entries(nodeData.inputs).forEach(([inputName, value]) => {
            if (Array.isArray(value) && value.length >= 2) {
                const [sourceNodeId, sourceSlot] = value;
                const sourceNode = nodeIdMap[String(sourceNodeId)];

                if (sourceNode) {
                    // Determine type based on input name heuristics
                    let linkType = "*";
                    if (inputName.toLowerCase().includes("model")) linkType = "MODEL";
                    else if (inputName.toLowerCase().includes("clip")) linkType = "CLIP";
                    else if (inputName.toLowerCase().includes("vae")) linkType = "VAE";
                    else if (inputName.toLowerCase().includes("latent")) linkType = "LATENT";
                    else if (inputName.toLowerCase().includes("image")) linkType = "IMAGE";
                    else if (inputName.toLowerCase().includes("conditioning") ||
                             inputName.toLowerCase().includes("positive") ||
                             inputName.toLowerCase().includes("negative")) linkType = "CONDITIONING";

                    // Create link: [link_id, origin_id, origin_slot, target_id, target_slot, type]
                    links.push([
                        linkId,
                        sourceNode.id,
                        sourceSlot,
                        targetNode.id,
                        inputSlot,
                        linkType
                    ]);

                    // Add input slot to target node
                    targetNode.inputs.push({
                        name: inputName,
                        type: linkType,
                        link: linkId
                    });

                    // Ensure source node has output slot
                    while (sourceNode.outputs.length <= sourceSlot) {
                        sourceNode.outputs.push({
                            name: `output_${sourceNode.outputs.length}`,
                            type: "*",
                            links: []
                        });
                    }

                    // Update output slot type and add link
                    sourceNode.outputs[sourceSlot].type = linkType;
                    if (!sourceNode.outputs[sourceSlot].links) {
                        sourceNode.outputs[sourceSlot].links = [];
                    }
                    sourceNode.outputs[sourceSlot].links.push(linkId);

                    linkId++;
                }
                inputSlot++;
            }
        });
    });

    const result = {
        last_node_id: Math.max(...nodes.map(n => n.id), 0),
        last_link_id: linkId - 1,
        nodes: nodes,
        links: links,
        groups: [],
        config: {},
        extra: { ds: { scale: 1, offset: [0, 0] } },
        version: 0.4
    };

    console.log("[AgentX] Converted format - nodes:", nodes.length, "links:", links.length);
    return result;
}
