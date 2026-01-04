"""
Workflow Execution Tools

Tools for executing workflows and checking results,
including execution monitoring and log retrieval.
"""

import asyncio
from typing import Dict, Any, Optional, List

from .base import BaseTool, registry
from .workflow_state import state
from .comfy_client import get_client, get_execution_logs, clear_execution_logs
from ....utils.logger import get_logger

logger = get_logger(__name__)


class ExecuteWorkflowTool(BaseTool):
    """Execute the current workflow."""

    name = "execute_workflow"
    description = "Execute the current workflow in ComfyUI. Returns a prompt_id to check results."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow": {
                    "type": "object",
                    "description": "Optional workflow to execute. Uses current workflow if not provided.",
                },
            },
        }

    async def execute(self, workflow: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info("execute_workflow called", has_workflow_param=workflow is not None)

        workflow_to_run = workflow or state.workflow
        if not workflow_to_run:
            return {"error": "No workflow to execute. Create a workflow first."}

        client = get_client()
        result = await client.run_prompt({"prompt": workflow_to_run})

        if result.get("success"):
            prompt_id = result.get("prompt_id")
            state.store_execution_result(prompt_id, {"status": "queued"})

            return {
                "success": True,
                "prompt_id": prompt_id,
                "status": "queued",
                "message": "Workflow queued for execution",
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "node_errors": result.get("node_errors", {}),
            }


class GetExecutionResultTool(BaseTool):
    """Get the execution result for a workflow."""

    name = "get_execution_result"
    description = "Get the execution result/status for a workflow. Can wait for completion."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt_id": {
                    "type": "string",
                    "description": "The prompt ID from execute_workflow.",
                },
                "wait": {
                    "type": "boolean",
                    "description": "Wait for completion (default: false).",
                    "default": False,
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to wait (default: 60).",
                    "default": 60,
                },
            },
            "required": ["prompt_id"],
        }

    async def execute(
        self,
        prompt_id: str,
        wait: bool = False,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        logger.info("get_execution_result", prompt_id=prompt_id, wait=wait, timeout=timeout)

        client = get_client()

        if wait:
            elapsed = 0
            poll_interval = 2

            while elapsed < timeout:
                history = await client.get_history(prompt_id)

                if prompt_id in history:
                    prompt_history = history[prompt_id]
                    status = prompt_history.get("status", {})

                    if status.get("completed", False):
                        result = {
                            "prompt_id": prompt_id,
                            "status": "completed",
                            "outputs": prompt_history.get("outputs", {}),
                            "execution_time": status.get("execution_time"),
                        }
                        state.store_execution_result(prompt_id, result)
                        return result

                    elif status.get("status_str") == "error":
                        result = {
                            "prompt_id": prompt_id,
                            "status": "error",
                            "error": status.get("messages", []),
                        }
                        state.store_execution_result(prompt_id, result)
                        return result

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            return {
                "prompt_id": prompt_id,
                "status": "timeout",
                "message": f"Did not complete within {timeout} seconds",
            }
        else:
            # Just get current status
            history = await client.get_history(prompt_id)

            if prompt_id in history:
                prompt_history = history[prompt_id]
                status = prompt_history.get("status", {})

                return {
                    "prompt_id": prompt_id,
                    "status": "completed" if status.get("completed") else "running",
                    "outputs": prompt_history.get("outputs", {}),
                }
            else:
                queue = await client.get_queue_status()

                # Check running queue
                running = queue.get("queue_running", [])
                for item in running:
                    if len(item) > 1 and item[1] == prompt_id:
                        return {"prompt_id": prompt_id, "status": "running"}

                # Check pending queue
                pending = queue.get("queue_pending", [])
                for i, item in enumerate(pending):
                    if len(item) > 1 and item[1] == prompt_id:
                        return {"prompt_id": prompt_id, "status": "pending", "position": i}

                return {
                    "prompt_id": prompt_id,
                    "status": "not_found",
                    "message": "Prompt not in history or queue",
                }


class InterruptExecutionTool(BaseTool):
    """Interrupt the current execution."""

    name = "interrupt_execution"
    description = "Interrupt/cancel the currently running workflow execution."

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> Dict[str, Any]:
        logger.info("interrupt_execution called")

        import aiohttp
        client = get_client()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{client.base_url}/api/interrupt") as resp:
                    return {
                        "success": resp.status == 200,
                        "message": "Execution interrupted" if resp.status == 200 else "Failed to interrupt",
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetExecutionLogsTool(BaseTool):
    """Get detailed execution logs for a workflow run."""

    name = "get_execution_logs"
    description = """Get detailed execution logs for a workflow run.
    Returns node-by-node execution timeline with progress, timing, and errors.
    Use this after execute_workflow to understand what happened during execution."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt_id": {
                    "type": "string",
                    "description": "The prompt ID from execute_workflow.",
                },
            },
            "required": ["prompt_id"],
        }

    async def execute(self, prompt_id: str) -> Dict[str, Any]:
        logger.info("get_execution_logs", prompt_id=prompt_id)

        # First check stored logs
        logs = get_execution_logs(prompt_id)
        if logs:
            return {
                "prompt_id": prompt_id,
                "log_count": len(logs),
                "logs": logs,
                "summary": self._summarize_logs(logs)
            }

        # If no stored logs, try to reconstruct from history
        client = get_client()
        history = await client.get_history(prompt_id)

        if prompt_id not in history:
            return {
                "prompt_id": prompt_id,
                "error": "No logs found. Either the prompt hasn't been executed yet, or logs were not captured.",
                "suggestion": "Use execute_workflow with monitor=True to capture execution logs."
            }

        # Extract info from history
        prompt_history = history[prompt_id]
        status = prompt_history.get("status", {})
        outputs = prompt_history.get("outputs", {})

        logs = []

        # Add execution status
        if status.get("completed"):
            logs.append({
                "type": "execution_complete",
                "status": "completed",
                "execution_time": status.get("execution_time")
            })
        elif status.get("status_str") == "error":
            messages = status.get("messages", [])
            for msg in messages:
                if isinstance(msg, list) and len(msg) >= 2:
                    logs.append({
                        "type": "execution_error",
                        "status": "error",
                        "node_id": msg[0] if msg else None,
                        "error": msg[1] if len(msg) > 1 else str(msg)
                    })

        # Add output info
        for node_id, output in outputs.items():
            log_entry = {
                "type": "node_output",
                "node_id": node_id,
                "has_output": True
            }
            if "images" in output:
                log_entry["output_type"] = "images"
                log_entry["image_count"] = len(output.get("images", []))
            logs.append(log_entry)

        return {
            "prompt_id": prompt_id,
            "log_count": len(logs),
            "logs": logs,
            "summary": self._summarize_logs(logs),
            "note": "Logs reconstructed from history. For real-time logs, use monitor_execution."
        }

    def _summarize_logs(self, logs: List[Dict]) -> Dict[str, Any]:
        """Generate a summary of execution logs."""
        summary = {
            "total_events": len(logs),
            "nodes_executed": 0,
            "nodes_cached": 0,
            "errors": [],
            "has_output": False,
            "total_time": None
        }

        executed_nodes = set()
        cached_nodes = set()

        for log in logs:
            log_type = log.get("type")
            status = log.get("status")

            if log_type == "executing" or status == "executing":
                node_id = log.get("node_id")
                if node_id:
                    executed_nodes.add(node_id)

            elif log_type == "executed" or status == "executed":
                node_id = log.get("node_id")
                if node_id:
                    executed_nodes.add(node_id)
                if log.get("has_output"):
                    summary["has_output"] = True

            elif log_type == "execution_cached":
                cached = log.get("cached_nodes", [])
                cached_nodes.update(cached)

            elif log_type == "execution_error" or status == "error":
                summary["errors"].append({
                    "node_id": log.get("node_id"),
                    "error": log.get("error")
                })

            elif status == "complete":
                summary["total_time"] = log.get("total_time")

        summary["nodes_executed"] = len(executed_nodes)
        summary["nodes_cached"] = len(cached_nodes)
        summary["success"] = len(summary["errors"]) == 0

        return summary


class MonitorExecutionTool(BaseTool):
    """Monitor workflow execution in real-time."""

    name = "monitor_execution"
    description = """Monitor a workflow execution in real-time via WebSocket.
    Captures all execution events: node progress, timing, errors, outputs.
    Use this after execute_workflow to watch the execution progress."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt_id": {
                    "type": "string",
                    "description": "The prompt ID from execute_workflow.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to monitor (default: 120).",
                    "default": 120,
                },
            },
            "required": ["prompt_id"],
        }

    async def execute(self, prompt_id: str, timeout: int = 120) -> Dict[str, Any]:
        logger.info("monitor_execution", prompt_id=prompt_id, timeout=timeout)

        client = get_client()
        logs = []
        final_status = "unknown"
        total_time = None

        try:
            async for event in client.monitor_execution(prompt_id, timeout):
                logs.append(event)

                # Check for completion
                if event.get("status") == "complete":
                    final_status = "completed"
                    total_time = event.get("total_time")
                    break
                elif event.get("status") == "error" or event.get("type") == "execution_error":
                    final_status = "error"
                    break
                elif event.get("type") in ["timeout", "error", "ws_error"]:
                    final_status = event.get("type")
                    break

        except Exception as e:
            logger.exception("Monitor execution failed")
            return {
                "prompt_id": prompt_id,
                "status": "error",
                "error": str(e),
                "logs": logs
            }

        return {
            "prompt_id": prompt_id,
            "status": final_status,
            "total_time": total_time,
            "event_count": len(logs),
            "logs": logs,
            "summary": self._create_summary(logs)
        }

    def _create_summary(self, logs: List[Dict]) -> Dict[str, Any]:
        """Create a summary of monitored events."""
        executed = []
        cached = []
        errors = []
        progress_nodes = set()

        for log in logs:
            status = log.get("status")
            log_type = log.get("type")
            node_id = log.get("node_id")

            if status == "executing" and node_id:
                if node_id not in executed:
                    executed.append(node_id)
            elif status == "executed" and node_id:
                if node_id not in executed:
                    executed.append(node_id)
            elif log_type == "execution_cached":
                cached.extend(log.get("cached_nodes", []))
            elif log_type == "progress":
                progress_nodes.add(node_id)
            elif status == "error":
                errors.append({
                    "node_id": node_id,
                    "error": log.get("error")
                })

        return {
            "nodes_executed": executed,
            "nodes_cached": cached,
            "nodes_with_progress": list(progress_nodes),
            "errors": errors,
            "success": len(errors) == 0
        }


class ExecuteAndMonitorTool(BaseTool):
    """Execute workflow and monitor in one call."""

    name = "execute_and_monitor"
    description = """Execute a workflow and monitor its execution in real-time.
    Combines execute_workflow + monitor_execution for convenience.
    Returns complete execution logs with timing and any errors."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow": {
                    "type": "object",
                    "description": "Optional workflow to execute. Uses current workflow if not provided.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to wait for completion (default: 120).",
                    "default": 120,
                },
            },
        }

    async def execute(
        self,
        workflow: Optional[Dict[str, Any]] = None,
        timeout: int = 120
    ) -> Dict[str, Any]:
        logger.info("execute_and_monitor called", has_workflow=workflow is not None)

        # First execute
        workflow_to_run = workflow or state.workflow
        if not workflow_to_run:
            return {"error": "No workflow to execute. Create a workflow first."}

        client = get_client()
        exec_result = await client.run_prompt({"prompt": workflow_to_run})

        if not exec_result.get("success"):
            return {
                "success": False,
                "phase": "execution_submit",
                "error": exec_result.get("error", "Failed to queue workflow"),
                "node_errors": exec_result.get("node_errors", {})
            }

        prompt_id = exec_result.get("prompt_id")
        logger.info("Workflow queued, starting monitor", prompt_id=prompt_id)

        # Now monitor
        logs = []
        final_status = "unknown"
        total_time = None

        try:
            async for event in client.monitor_execution(prompt_id, timeout):
                logs.append(event)
                logger.debug("Execution event", event_type=event.get("type"), status=event.get("status"))

                if event.get("status") == "complete":
                    final_status = "completed"
                    total_time = event.get("total_time")
                    break
                elif event.get("status") == "error" or event.get("type") == "execution_error":
                    final_status = "error"
                    break
                elif event.get("type") in ["timeout", "error", "ws_error"]:
                    final_status = event.get("type")
                    break

        except Exception as e:
            logger.exception("Monitor failed during execute_and_monitor")
            return {
                "success": False,
                "prompt_id": prompt_id,
                "phase": "monitoring",
                "error": str(e),
                "logs": logs
            }

        # Get final outputs from history
        outputs = {}
        if final_status == "completed":
            history = await client.get_history(prompt_id)
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})

        return {
            "success": final_status == "completed",
            "prompt_id": prompt_id,
            "status": final_status,
            "total_time": total_time,
            "event_count": len(logs),
            "logs": logs,
            "outputs": outputs
        }


class ExecutionTools:
    """Container for execution tools."""

    @staticmethod
    def register_all():
        """Register all execution tools."""
        registry.register_tool(ExecuteWorkflowTool())
        registry.register_tool(GetExecutionResultTool())
        registry.register_tool(InterruptExecutionTool())
        registry.register_tool(GetExecutionLogsTool())
        registry.register_tool(MonitorExecutionTool())
        registry.register_tool(ExecuteAndMonitorTool())
