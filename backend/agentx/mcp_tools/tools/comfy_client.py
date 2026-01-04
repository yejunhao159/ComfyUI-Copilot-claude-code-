"""
ComfyUI HTTP Client

Provides async HTTP communication with ComfyUI server,
including WebSocket support for execution monitoring.
"""

import asyncio
import json
from typing import Dict, Any, Optional, List, AsyncGenerator
from ....utils.logger import get_logger

logger = get_logger(__name__)


# Execution log storage (per prompt_id)
_execution_logs: Dict[str, List[Dict[str, Any]]] = {}


class ComfyClient:
    """Async HTTP client for ComfyUI API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188"):
        self.base_url = base_url.rstrip('/')

    async def get_object_info(self) -> Dict[str, Any]:
        """Get all available node definitions."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/object_info") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {}
        except Exception as e:
            logger.error("Failed to get object_info", error=str(e))
            return {}

    async def run_prompt(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workflow prompt."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/prompt",
                    json=json_data
                ) as resp:
                    data = await resp.json()
                    return {"success": resp.status == 200, **data}
        except Exception as e:
            logger.error("Failed to run prompt", error=str(e))
            return {"success": False, "error": str(e)}

    async def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """Get execution history for a prompt."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/history/{prompt_id}") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {}
        except Exception as e:
            logger.error("Failed to get history", prompt_id=prompt_id, error=str(e))
            return {}

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/queue") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {}
        except Exception as e:
            logger.error("Failed to get queue status", error=str(e))
            return {}

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get ComfyUI system stats."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/system_stats") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {}
        except Exception as e:
            logger.error("Failed to get system stats", error=str(e))
            return {}

    async def monitor_execution(
        self,
        prompt_id: str,
        timeout: int = 300
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Monitor workflow execution via WebSocket.

        Yields execution events in real-time:
        - status: execution_start, executing, executed, progress, execution_complete
        - data: node_id, progress_value, outputs, errors
        """
        import aiohttp
        from datetime import datetime

        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws?clientId=agentx-monitor"

        logs = []
        _execution_logs[prompt_id] = logs

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url, timeout=timeout) as ws:
                    start_time = datetime.now()
                    execution_started = False
                    current_node = None

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                msg_type = data.get("type")
                                msg_data = data.get("data", {})

                                # Only track events for our prompt
                                event_prompt_id = msg_data.get("prompt_id")
                                if event_prompt_id and event_prompt_id != prompt_id:
                                    continue

                                elapsed = (datetime.now() - start_time).total_seconds()
                                log_entry = {
                                    "timestamp": datetime.now().isoformat(),
                                    "elapsed_seconds": round(elapsed, 2),
                                    "type": msg_type,
                                    "data": msg_data
                                }

                                if msg_type == "status":
                                    queue_remaining = msg_data.get("status", {}).get("exec_info", {}).get("queue_remaining", 0)
                                    log_entry["queue_remaining"] = queue_remaining

                                elif msg_type == "execution_start":
                                    execution_started = True
                                    log_entry["status"] = "started"
                                    logs.append(log_entry)
                                    yield log_entry

                                elif msg_type == "executing":
                                    node_id = msg_data.get("node")
                                    if node_id:
                                        current_node = node_id
                                        log_entry["node_id"] = node_id
                                        log_entry["status"] = "executing"
                                        logs.append(log_entry)
                                        yield log_entry
                                    else:
                                        # null node means execution complete
                                        log_entry["status"] = "complete"
                                        log_entry["total_time"] = round(elapsed, 2)
                                        logs.append(log_entry)
                                        yield log_entry
                                        return

                                elif msg_type == "progress":
                                    value = msg_data.get("value", 0)
                                    max_val = msg_data.get("max", 100)
                                    log_entry["progress"] = f"{value}/{max_val}"
                                    log_entry["progress_percent"] = round(value / max_val * 100, 1) if max_val > 0 else 0
                                    log_entry["node_id"] = current_node
                                    logs.append(log_entry)
                                    yield log_entry

                                elif msg_type == "executed":
                                    node_id = msg_data.get("node")
                                    output = msg_data.get("output", {})
                                    log_entry["node_id"] = node_id
                                    log_entry["status"] = "executed"
                                    log_entry["has_output"] = bool(output)
                                    if "images" in output:
                                        log_entry["output_images"] = len(output.get("images", []))
                                    logs.append(log_entry)
                                    yield log_entry

                                elif msg_type == "execution_error":
                                    log_entry["status"] = "error"
                                    log_entry["error"] = msg_data.get("exception_message", "Unknown error")
                                    log_entry["node_id"] = msg_data.get("node_id")
                                    log_entry["node_type"] = msg_data.get("node_type")
                                    logs.append(log_entry)
                                    yield log_entry
                                    return

                                elif msg_type == "execution_cached":
                                    cached_nodes = msg_data.get("nodes", [])
                                    log_entry["cached_nodes"] = cached_nodes
                                    log_entry["cached_count"] = len(cached_nodes)
                                    logs.append(log_entry)
                                    yield log_entry

                            except json.JSONDecodeError:
                                continue

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            yield {
                                "type": "ws_error",
                                "error": str(ws.exception())
                            }
                            return

        except asyncio.TimeoutError:
            yield {
                "type": "timeout",
                "error": f"Execution monitoring timed out after {timeout} seconds"
            }
        except Exception as e:
            logger.exception("WebSocket monitoring error")
            yield {
                "type": "error",
                "error": str(e)
            }


def get_execution_logs(prompt_id: str) -> List[Dict[str, Any]]:
    """Get stored execution logs for a prompt."""
    return _execution_logs.get(prompt_id, [])


def clear_execution_logs(prompt_id: str = None):
    """Clear execution logs."""
    global _execution_logs
    if prompt_id:
        _execution_logs.pop(prompt_id, None)
    else:
        _execution_logs.clear()


# Global client instance
_client: Optional[ComfyClient] = None


def get_client(base_url: str = "http://127.0.0.1:8188") -> ComfyClient:
    """Get or create the global ComfyUI client."""
    global _client
    if _client is None:
        _client = ComfyClient(base_url)
    return _client
