"""Runtime orchestration tools for bot-to-bot workflows."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.shell import ExecTool


def _runtime_base_url() -> str:
    return (os.environ.get("NANOBOT_RUNTIME_BASE") or "http://127.0.0.1:8765").rstrip("/")


async def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{_runtime_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            if method == "GET":
                res = await client.get(url)
            elif method == "POST":
                res = await client.post(url, json=payload or {})
            elif method == "DELETE":
                res = await client.delete(url)
            else:
                return {"ok": False, "error": f"unsupported_method:{method}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"runtime_request_failed: {exc}"}

    data: dict[str, Any]
    try:
        data = res.json() if res.content else {}
    except Exception:
        data = {"raw": res.text}

    if not res.is_success:
        data.setdefault("ok", False)
        if "error" not in data:
            data["error"] = f"HTTP_{res.status_code}"
    return data


class RelayToBotTool(Tool):
    """Relay messages to another bot through runtime API."""

    @property
    def name(self) -> str:
        return "relay_to_bot"

    @property
    def description(self) -> str:
        return "Send a message from one bot to another bot using the runtime relay API."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fromBotId": {"type": "string", "description": "Source bot id"},
                "toBotId": {"type": "string", "description": "Target bot id"},
                "message": {"type": "string", "description": "Message to relay"},
                "timeout": {
                    "type": "number",
                    "description": "Optional timeout seconds (default 180)",
                    "minimum": 1,
                    "maximum": 600,
                },
            },
            "required": ["fromBotId", "toBotId", "message"],
        }

    async def execute(
        self,
        fromBotId: str,
        toBotId: str,
        message: str,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> str:
        payload = {
            "fromBotId": fromBotId,
            "toBotId": toBotId,
            "message": message,
            "timeout": timeout or 180.0,
        }
        data = await _request("POST", "/api/runtime/relay", payload)
        return json.dumps(data, ensure_ascii=False)


class RuntimeWorkersTool(Tool):
    """Inspect and control runtime worker processes."""

    @property
    def name(self) -> str:
        return "runtime_workers"

    @property
    def description(self) -> str:
        return "List runtime workers, or start/stop a specific bot worker."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "start", "stop"],
                    "description": "Operation to perform",
                },
                "botId": {
                    "type": "string",
                    "description": "Required for start/stop",
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, botId: str | None = None, **kwargs: Any) -> str:
        action = (action or "").strip().lower()
        if action == "list":
            data = await _request("GET", "/api/runtime/bots")
            return json.dumps(data, ensure_ascii=False)
        if action in {"start", "stop"}:
            if not botId:
                return "Error: botId is required for start/stop"
            data = await _request("POST", f"/api/runtime/bots/{botId}/{action}", {})
            return json.dumps(data, ensure_ascii=False)
        return "Error: invalid action"


class RuntimeLinksTool(Tool):
    """Manage runtime bot links."""

    @property
    def name(self) -> str:
        return "runtime_links"

    @property
    def description(self) -> str:
        return "List, add, or remove bot-to-bot runtime links."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "remove"],
                    "description": "Operation to perform",
                },
                "fromBotId": {"type": "string", "description": "Source bot id"},
                "toBotId": {"type": "string", "description": "Target bot id"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        fromBotId: str | None = None,
        toBotId: str | None = None,
        **kwargs: Any,
    ) -> str:
        action = (action or "").strip().lower()
        if action == "list":
            data = await _request("GET", "/api/runtime/links")
            return json.dumps(data, ensure_ascii=False)

        if action == "add":
            if not fromBotId or not toBotId:
                return "Error: fromBotId and toBotId are required"
            data = await _request(
                "POST",
                "/api/runtime/links",
                {"fromBotId": fromBotId, "toBotId": toBotId},
            )
            return json.dumps(data, ensure_ascii=False)

        if action == "remove":
            if not fromBotId or not toBotId:
                return "Error: fromBotId and toBotId are required"
            path = f"/api/runtime/links?fromBotId={fromBotId}&toBotId={toBotId}"
            data = await _request("DELETE", path)
            return json.dumps(data, ensure_ascii=False)

        return "Error: invalid action"


class TerminalTaskTool(Tool):
    """User-facing terminal helper tool backed by ExecTool."""

    def __init__(self, exec_tool: ExecTool):
        self._exec = exec_tool

    @property
    def name(self) -> str:
        return "terminal_task"

    @property
    def description(self) -> str:
        return "Run a terminal command in the workspace (alias of exec for task workflows)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "working_dir": {"type": "string", "description": "Optional working directory"},
                "timeout": {
                    "type": "integer",
                    "description": "Timeout seconds",
                    "minimum": 1,
                    "maximum": 600,
                },
            },
            "required": ["command"],
        }

    async def execute(
        self,
        command: str,
        working_dir: str | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> str:
        return await self._exec.execute(command=command, working_dir=working_dir, timeout=timeout)


class TeamMemoryTool(Tool):
    """Read/write team shared memory used by runtime chat context."""

    @property
    def name(self) -> str:
        return "team_memory"

    @property
    def description(self) -> str:
        return "Manage shared team memory (get, replace, append, clear) via runtime API."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "replace", "append", "clear"],
                },
                "teamId": {"type": "string", "description": "Team id (default: default)"},
                "text": {"type": "string", "description": "Memory content for replace/append"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        teamId: str | None = None,
        text: str | None = None,
        **kwargs: Any,
    ) -> str:
        team_id = (teamId or "default").strip() or "default"
        action = (action or "").strip().lower()
        if action == "get":
            data = await _request("GET", f"/api/runtime/memory?teamId={team_id}")
            return json.dumps(data, ensure_ascii=False)
        if action == "clear":
            data = await _request("DELETE", f"/api/runtime/memory?teamId={team_id}")
            return json.dumps(data, ensure_ascii=False)
        if action in {"replace", "append"}:
            data = await _request(
                "POST",
                "/api/runtime/memory",
                {"teamId": team_id, "mode": action, "text": text or ""},
            )
            return json.dumps(data, ensure_ascii=False)
        return "Error: invalid action"


__all__ = [
    "RelayToBotTool",
    "RuntimeWorkersTool",
    "RuntimeLinksTool",
    "TerminalTaskTool",
    "TeamMemoryTool",
]
