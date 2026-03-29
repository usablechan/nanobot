"""Interactive web dashboard server for bot management."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import uuid
import atexit
from collections import deque
from datetime import datetime, timezone
from queue import Empty, Queue
from pathlib import Path
from threading import Lock, Thread
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from nanobot.bots import (
    _UNSET,
    bot_runtime_summary,
    create_bot,
    create_team,
    delete_bot,
    delete_team,
    get_bot,
    get_team,
    list_bots,
    list_teams,
    resolve_team_bots,
    update_team,
    update_bot,
)
from nanobot.config.loader import load_config
from nanobot.config.paths import get_runtime_subdir

_ACTIVITY_LOCK = Lock()
_ACTIVITY: dict[str, Any] = {
    "running": 0,
    "last_run_at": None,
    "last_run_team": "",
    "last_run_ok": None,
    "last_run_summary": None,
    "last_error": "",
}
_RUNS_LOCK = Lock()
_MCP_STATUS_LOCK = Lock()
_MCP_STATUS: dict[str, dict[str, str]] = {}


class _BotWorkerProcess:
    """Owns one long-lived worker subprocess for a specific bot."""

    def __init__(self, bot_id: str, config_path: str):
        self.bot_id = bot_id
        self.config_path = config_path
        self.proc: subprocess.Popen[str] | None = None
        self._pending: dict[str, Queue[dict[str, Any]]] = {}
        self._pending_lock = Lock()
        self._write_lock = Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=200)
        self._reader: Thread | None = None
        self._stderr_reader: Thread | None = None

    def start(self) -> None:
        if self.proc and self.proc.poll() is None:
            return
        cmd = [
            sys.executable,
            "-m",
            "nanobot.bot_runtime_worker",
            "--bot-id",
            self.bot_id,
            "--config",
            self.config_path,
        ]
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._reader = Thread(target=self._stdout_loop, daemon=True)
        self._reader.start()
        self._stderr_reader = Thread(target=self._stderr_loop, daemon=True)
        self._stderr_reader.start()

    def stop(self) -> None:
        proc = self.proc
        if not proc:
            return
        try:
            self.request({"type": "shutdown"}, timeout=2.0)
        except Exception:
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.proc = None

    def is_running(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)

    def request(self, payload: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
        if not self.proc or self.proc.poll() is not None:
            raise RuntimeError(f"bot worker is not running: {self.bot_id}")
        req_id = uuid.uuid4().hex[:12]
        msg = dict(payload)
        msg["request_id"] = req_id
        q: Queue[dict[str, Any]] = Queue(maxsize=1)
        with self._pending_lock:
            self._pending[req_id] = q
        try:
            self._write(msg)
            return q.get(timeout=timeout)
        except Empty as exc:
            raise RuntimeError(f"worker timeout for bot `{self.bot_id}`") from exc
        finally:
            with self._pending_lock:
                self._pending.pop(req_id, None)

    def status_payload(self) -> dict[str, Any]:
        proc = self.proc
        return {
            "botId": self.bot_id,
            "running": self.is_running(),
            "pid": proc.pid if proc and proc.poll() is None else None,
            "recentEvents": list(self._events),
        }

    def _write(self, payload: dict[str, Any]) -> None:
        proc = self.proc
        if not proc or not proc.stdin:
            raise RuntimeError("worker stdin is unavailable")
        with self._write_lock:
            proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            proc.stdin.flush()

    def _stdout_loop(self) -> None:
        proc = self.proc
        if not proc or not proc.stdout:
            return
        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                self._events.append({"type": "stdout", "line": line, "ts": int(time.time() * 1000)})
                continue
            req_id = str(payload.get("request_id") or "")
            if req_id:
                with self._pending_lock:
                    q = self._pending.get(req_id)
                if q:
                    q.put(payload)
                    continue
            self._events.append({**payload, "ts": int(time.time() * 1000)})

    def _stderr_loop(self) -> None:
        proc = self.proc
        if not proc or not proc.stderr:
            return
        for raw in proc.stderr:
            line = raw.strip()
            if not line:
                continue
            self._events.append({"type": "stderr", "line": line, "ts": int(time.time() * 1000)})


class _BotRuntimeManager:
    """Tracks long-running bot workers and links for relay."""

    def __init__(self) -> None:
        self._workers: dict[str, _BotWorkerProcess] = {}
        self._links: dict[str, set[str]] = {}
        self._lock = Lock()

    def list_workers(self) -> list[dict[str, Any]]:
        with self._lock:
            return [worker.status_payload() for worker in self._workers.values()]

    def start_worker(self, bot_id: str) -> dict[str, Any]:
        bot = get_bot(bot_id)
        if not bot:
            raise ValueError(f"Unknown bot: {bot_id}")
        config_path = str(bot.get("config_path") or "").strip()
        if not config_path:
            raise ValueError(f"Missing config_path for bot: {bot_id}")
        with self._lock:
            worker = self._workers.get(bot_id)
            if not worker:
                worker = _BotWorkerProcess(bot_id, config_path)
                self._workers[bot_id] = worker
            worker.start()
            return worker.status_payload()

    def stop_worker(self, bot_id: str) -> dict[str, Any]:
        with self._lock:
            worker = self._workers.get(bot_id)
            if not worker:
                return {"botId": bot_id, "running": False, "pid": None, "recentEvents": []}
            worker.stop()
            status = worker.status_payload()
            self._workers.pop(bot_id, None)
            self._links.pop(bot_id, None)
            for targets in self._links.values():
                targets.discard(bot_id)
            return status

    def chat(self, bot_id: str, message: str, session_id: str | None = None, timeout: float = 180.0) -> dict[str, Any]:
        message = str(message or "").strip()
        if not message:
            raise ValueError("message is required")
        with self._lock:
            worker = self._workers.get(bot_id)
        if not worker:
            self.start_worker(bot_id)
            with self._lock:
                worker = self._workers.get(bot_id)
        if not worker:
            raise RuntimeError(f"failed to start worker: {bot_id}")
        status = worker.status_payload()
        reply = worker.request(
            {
                "type": "chat",
                "message": message,
                "session_id": session_id or f"runtime:{bot_id}",
            },
            timeout=timeout,
        )
        return {"worker": status, "reply": reply}

    def add_link(self, from_bot: str, to_bot: str) -> dict[str, Any]:
        if from_bot == to_bot:
            raise ValueError("fromBotId and toBotId must differ")
        if not get_bot(from_bot):
            raise ValueError(f"Unknown bot: {from_bot}")
        if not get_bot(to_bot):
            raise ValueError(f"Unknown bot: {to_bot}")
        with self._lock:
            self._links.setdefault(from_bot, set()).add(to_bot)
        return self.links_payload()

    def remove_link(self, from_bot: str, to_bot: str) -> dict[str, Any]:
        with self._lock:
            if from_bot in self._links:
                self._links[from_bot].discard(to_bot)
                if not self._links[from_bot]:
                    self._links.pop(from_bot, None)
        return self.links_payload()

    def links_payload(self) -> dict[str, list[str]]:
        with self._lock:
            return {src: sorted(targets) for src, targets in self._links.items()}

    def relay(self, from_bot: str, to_bot: str, message: str, timeout: float = 180.0) -> dict[str, Any]:
        tagged = f"[relay from {from_bot}] {message}"
        return self.chat(
            to_bot,
            tagged,
            session_id=f"relay:{from_bot}:{to_bot}",
            timeout=timeout,
        )

    def stop_all(self) -> None:
        with self._lock:
            bot_ids = list(self._workers.keys())
        for bot_id in bot_ids:
            try:
                self.stop_worker(bot_id)
            except Exception:
                continue


_RUNTIME = _BotRuntimeManager()
atexit.register(_RUNTIME.stop_all)


def _adapter_root() -> Path:
    return get_runtime_subdir("dashboard_adapter")


def _runs_dir() -> Path:
    path = _adapter_root() / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _teamspace_root() -> Path:
    path = _adapter_root() / "team_workspaces"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _tasks_dir() -> Path:
    path = _adapter_root() / "tasks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _team_memory_dir() -> Path:
    path = _adapter_root() / "team_memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_team_id(team_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (team_id or "").strip()).strip("-")
    return cleaned or "default"


def _team_workspace(team_id: str) -> Path:
    workspace = _teamspace_root() / _safe_team_id(team_id)
    workspace.mkdir(parents=True, exist_ok=True)
    docs = workspace / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    defaults = {
        docs / "PROJECT.md": "# Project\n\n- Team objective\n",
        docs / "AGENTS.md": "# Agents\n\n- Define agent responsibilities\n",
        docs / "RULES.md": "# Rules\n\n- Team operating rules\n",
        docs / "DOMAIN.md": "# Domain\n\n- Domain context\n",
        docs / "TASKS.md": "# Tasks\n\n- Task notes\n",
    }
    for path, content in defaults.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    return workspace


def _resolve_team_path(team_id: str, rel_path: str) -> Path:
    base = _team_workspace(team_id).resolve()
    candidate = (base / rel_path).resolve()
    if not str(candidate).startswith(str(base)):
        raise ValueError("Path escapes team workspace")
    return candidate


def _tasks_path(team_id: str) -> Path:
    return _tasks_dir() / f"{_safe_team_id(team_id)}.json"


def _team_memory_path(team_id: str) -> Path:
    return _team_memory_dir() / f"{_safe_team_id(team_id)}.md"


def _load_team_memory(team_id: str) -> str:
    path = _team_memory_path(team_id)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _save_team_memory(team_id: str, content: str) -> None:
    _team_memory_path(team_id).write_text(content, encoding="utf-8")


def _load_tasks(team_id: str) -> list[dict[str, Any]]:
    path = _tasks_path(team_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [item for item in data if isinstance(item, dict)]


def _save_tasks(team_id: str, tasks: list[dict[str, Any]]) -> None:
    path = _tasks_path(team_id)
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_file(run_id: str) -> Path:
    safe_id = _safe_team_id(run_id).replace(".", "-")
    return _runs_dir() / f"{safe_id}.json"


def _record_run(team_id: str, mission: str, payload: dict[str, Any], ok: bool) -> None:
    run_id = str(payload.get("run_id") or f"run:{uuid.uuid4().hex[:12]}")
    started_at = payload.get("started_at")
    updated_at = int(time.time() * 1000)
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    synthesis = str(payload.get("synthesis") or "")
    events: list[dict[str, Any]] = []
    ts_base = updated_at
    for idx, item in enumerate(results):
        agent_id = str(item.get("id") or "")
        status = str(item.get("status") or "unknown")
        text = str(item.get("content") or item.get("error") or status)
        events.append(
            {
                "id": f"{run_id}:result:{idx}",
                "ts": ts_base + idx,
                "iso": datetime.now(timezone.utc).isoformat(),
                "runId": run_id,
                "type": "status",
                "agentId": agent_id,
                "text": text,
                "toolStatus": status,
            }
        )
    if synthesis:
        events.append(
            {
                "id": f"{run_id}:synthesis",
                "ts": ts_base + len(events) + 1,
                "iso": datetime.now(timezone.utc).isoformat(),
                "runId": run_id,
                "type": "message",
                "agentId": "lead",
                "text": synthesis,
            }
        )
    record = {
        "runId": run_id,
        "teamId": team_id,
        "mission": mission,
        "updatedAt": updated_at,
        "ok": ok,
        "startedAt": started_at,
        "events": events,
    }
    with _RUNS_LOCK:
        _run_file(run_id).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _list_runs(team_id: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _runs_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        if team_id and str(data.get("teamId") or "") != team_id:
            continue
        rows.append(
            {
                "runId": str(data.get("runId") or ""),
                "mission": str(data.get("mission") or ""),
                "updatedAt": int(data.get("updatedAt") or 0),
                "teamId": str(data.get("teamId") or ""),
            }
        )
    rows.sort(key=lambda item: item["updatedAt"], reverse=True)
    return rows


def _get_run_events(run_id: str) -> dict[str, Any] | None:
    path = _run_file(run_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        "runId": str(data.get("runId") or run_id),
        "events": data.get("events") if isinstance(data.get("events"), list) else [],
    }


def _skills_payload() -> list[dict[str, Any]]:
    roots = [
        Path(__file__).resolve().parent / "skills",
        Path.home() / ".nanobot" / "skills",
    ]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("SKILL.md"):
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            name = path.parent.name
            if name in seen:
                continue
            seen.add(name)
            desc = ""
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:160]
                    break
            rows.append(
                {
                    "name": name,
                    "description": desc or "Skill",
                    "location": str(path),
                    "content": content,
                }
            )
    rows.sort(key=lambda item: str(item["name"]).lower())
    return rows


def _mcp_status_payload() -> dict[str, dict[str, str]]:
    cfg = load_config()
    base: dict[str, dict[str, str]] = {}
    for name in (cfg.tools.mcp_servers or {}).keys():
        base[name] = {"status": "configured"}
    with _MCP_STATUS_LOCK:
        for name, value in _MCP_STATUS.items():
            base[name] = value
    return base


def _parse_items(raw: str | None) -> list[str]:
    if not raw:
        return []
    items: list[str] = []
    for chunk in raw.split(","):
        value = chunk.strip()
        if value and value not in items:
            items.append(value)
    return items


def _dashboard_payload() -> list[dict[str, Any]]:
    return [bot_runtime_summary(bot) for bot in list_bots()]


def _teams_payload() -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for team in list_teams():
        resolved = resolve_team_bots(team)
        payload.append(
            {
                **team,
                "resolved_bot_ids": [str(bot.get("id", "")) for bot in resolved],
                "resolved_bot_names": [str(bot.get("name", "")) for bot in resolved],
            }
        )
    return payload


def _list_from_field(value: Any) -> list[str]:
    if isinstance(value, list):
        text = ",".join(str(item) for item in value)
        return _parse_items(text)
    return _parse_items(str(value or ""))


def _run_team(team_id: str, message: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "nanobot",
        "bots",
        "team",
        "run",
        team_id,
        "--message",
        message,
        "--json",
    ]
    options = options or {}
    if options.get("policy"):
        cmd.extend(["--policy", str(options["policy"])])
    if options.get("strategy"):
        cmd.extend(["--strategy", str(options["strategy"])])
    if options.get("strategy_k") not in {None, ""}:
        cmd.extend(["--strategy-k", str(int(options["strategy_k"]))])
    if options.get("timeout") not in {None, ""}:
        cmd.extend(["--timeout", str(float(options["timeout"]))])
    if options.get("max_concurrency") not in {None, ""}:
        cmd.extend(["--max-concurrency", str(int(options["max_concurrency"]))])
    if options.get("retries") not in {None, ""}:
        cmd.extend(["--retries", str(int(options["retries"]))])
    if options.get("min_successful_bots") not in {None, ""}:
        cmd.extend(["--min-successful-bots", str(int(options["min_successful_bots"]))])
    if options.get("fallback_bot"):
        cmd.extend(["--fallback-bot", str(options["fallback_bot"])])
    if options.get("run_label"):
        cmd.extend(["--run-label", str(options["run_label"])])
    with _ACTIVITY_LOCK:
        _ACTIVITY["running"] = int(_ACTIVITY.get("running", 0)) + 1
        _ACTIVITY["last_run_team"] = team_id
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError(proc.stderr.strip() or "team run returned empty output")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        with _ACTIVITY_LOCK:
            _ACTIVITY["running"] = max(0, int(_ACTIVITY.get("running", 1)) - 1)
            _ACTIVITY["last_error"] = f"Parse error for team `{team_id}` output"
        raise RuntimeError(f"failed to parse team run output: {stdout[:300]}") from exc
    if proc.returncode != 0:
        _record_run(team_id, message, payload, ok=False)
        with _ACTIVITY_LOCK:
            _ACTIVITY["running"] = max(0, int(_ACTIVITY.get("running", 1)) - 1)
            _ACTIVITY["last_run_at"] = int(time.time())
            _ACTIVITY["last_run_ok"] = False
            _ACTIVITY["last_run_summary"] = payload.get("summary")
            _ACTIVITY["last_error"] = (
                payload.get("synthesis_skipped_reason") or payload.get("error") or "team run failed"
            )
        raise RuntimeError(payload.get("synthesis_skipped_reason") or payload.get("error") or "team run failed")
    _record_run(team_id, message, payload, ok=True)
    with _ACTIVITY_LOCK:
        _ACTIVITY["running"] = max(0, int(_ACTIVITY.get("running", 1)) - 1)
        _ACTIVITY["last_run_at"] = int(time.time())
        _ACTIVITY["last_run_ok"] = True
        _ACTIVITY["last_run_summary"] = payload.get("summary")
        _ACTIVITY["last_error"] = ""
    return payload


def _activity_payload() -> dict[str, Any]:
    with _ACTIVITY_LOCK:
        return dict(_ACTIVITY)


def _html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>nanobot orchestrator dashboard</title>
  <style>
    :root {
      --bg: #eef2f7;
      --panel: #ffffff;
      --line: #d6dde8;
      --text: #17202b;
      --muted: #5d6a7c;
      --blue: #2962ff;
      --green: #0a8a63;
      --orange: #d27f00;
      --red: #b83232;
      --soft: #f4f7fc;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 0% -10%, #b8d2ff 0, transparent 35%),
        radial-gradient(circle at 100% 0%, #c8f1e1 0, transparent 30%),
        var(--bg);
      min-height: 100vh;
    }
    .app {
      max-width: 1360px;
      margin: 0 auto;
      padding: 16px;
      display: grid;
      gap: 12px;
    }
    .topbar {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      display: grid;
      gap: 10px;
    }
    .topline {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    h1 {
      margin: 0;
      font-size: 1.15rem;
      letter-spacing: 0.01em;
    }
    .hint { color: var(--muted); font-size: 0.86rem; }
    .chips { display: flex; gap: 8px; flex-wrap: wrap; }
    .chip {
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.75rem;
      border: 1px solid var(--line);
      background: #f9fbff;
      font-weight: 700;
      letter-spacing: 0.03em;
    }
    .chip.live { border-color: #8eb7ff; color: #1f4ecc; background: #edf3ff; }
    .chip.ok { border-color: #8fe0c8; color: #087454; background: #e9fbf4; }
    .chip.warn { border-color: #f0c66d; color: #9f5c00; background: #fff7e5; }
    button, input, textarea, select {
      font: inherit;
      border-radius: 10px;
      border: 1px solid var(--line);
      padding: 9px 10px;
      color: var(--text);
      background: white;
    }
    button {
      border: none;
      cursor: pointer;
      font-weight: 700;
      transition: transform .08s ease;
    }
    button:active { transform: translateY(1px); }
    .btn-primary { background: var(--blue); color: #eef4ff; }
    .btn-soft { background: #ecf3ff; color: #264fcf; border: 1px solid #c8d9ff; }
    .btn-green { background: #e8fbf3; color: #0b7a57; border: 1px solid #b8ecd8; }
    .btn-danger { background: #ffecec; color: #9c2f2f; border: 1px solid #f6c4c4; }
    .layout {
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 12px;
      min-height: calc(100vh - 160px);
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      display: grid;
      gap: 10px;
      min-height: 0;
    }
    .left-top {
      display: grid;
      gap: 8px;
      position: sticky;
      top: 0;
      background: var(--panel);
      z-index: 1;
      padding-bottom: 4px;
    }
    .toggle {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .toggle button.active {
      background: #1f4ecc;
      color: #eef3ff;
    }
    .list {
      display: grid;
      gap: 8px;
      overflow: auto;
      min-height: 0;
      padding-right: 2px;
    }
    .item {
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      background: var(--soft);
      display: grid;
      gap: 5px;
      cursor: pointer;
    }
    .item.active { border-color: #87aaf5; background: #edf3ff; }
    .item-title { font-weight: 700; font-size: 0.94rem; }
    .item-sub { font-size: 0.82rem; color: var(--muted); }
    .pill {
      display: inline-block;
      font-size: 0.72rem;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 7px;
      color: var(--muted);
      width: fit-content;
      background: #ffffff;
    }
    .right-grid {
      display: grid;
      gap: 10px;
      grid-template-rows: auto auto 1fr;
      min-height: 0;
    }
    .section {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      background: #fff;
      display: grid;
      gap: 8px;
    }
    .section h2 {
      margin: 0;
      font-size: 0.95rem;
      letter-spacing: 0.01em;
    }
    .forms-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .form-grid {
      display: grid;
      gap: 8px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .form-grid .full { grid-column: 1 / -1; }
    .label {
      display: grid;
      gap: 4px;
      font-size: 0.8rem;
      color: var(--muted);
    }
    .detail-empty {
      color: var(--muted);
      font-size: 0.9rem;
      padding: 20px 0;
      text-align: center;
    }
    .result-box {
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #f8fbff;
      padding: 10px;
      font-size: 0.82rem;
      white-space: pre-wrap;
      max-height: 280px;
      overflow: auto;
    }
    @media (max-width: 1040px) {
      .layout { grid-template-columns: 1fr; min-height: auto; }
      .forms-2 { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="topline">
        <div>
          <h1>nanobot Team Orchestrator Dashboard</h1>
          <div class="hint">Panel-style bot and team operations with run controls</div>
        </div>
        <div class="chips">
          <span class="chip live">LIVE LOCAL</span>
          <span class="chip ok" id="chipBots">BOTS 0</span>
          <span class="chip warn" id="chipTeams">TEAMS 0</span>
          <span class="chip" id="chipRun">RUN IDLE</span>
          <span class="chip" id="chipLast">LAST -</span>
          <span class="chip" id="chipErr">ERR -</span>
          <button class="btn-soft" id="refreshAll" type="button">Refresh</button>
        </div>
      </div>
      <div id="status" class="hint"></div>
    </header>

    <section class="layout">
      <aside class="panel">
        <div class="left-top">
          <div class="toggle">
            <button id="viewBots" class="active" type="button">Bots</button>
            <button id="viewTeams" type="button">Teams</button>
          </div>
          <input id="searchInput" placeholder="Search name / id / role / tags">
        </div>
        <div id="list" class="list"></div>
      </aside>

      <main class="panel right-grid">
        <section class="section">
          <h2>Quick Create</h2>
          <div class="forms-2">
            <form id="createBotForm" class="form-grid">
              <label class="label">Bot name<input name="name" required></label>
              <label class="label">Role<input name="role" required></label>
              <label class="label">Model<input name="model"></label>
              <label class="label">Provider<input name="provider"></label>
              <label class="label full">Description<input name="description"></label>
              <label class="label">Tags CSV<input name="tags"></label>
              <label class="label">Skills CSV<input name="skills"></label>
              <label class="label full">Custom Skills CSV<input name="custom_skills"></label>
              <label class="label full">Memory seed<textarea name="memory_seed"></textarea></label>
              <button class="btn-primary full" type="submit">Create Bot</button>
            </form>

            <form id="createTeamForm" class="form-grid">
              <label class="label">Team name<input name="name" required></label>
              <label class="label">Policy<input name="execution_policy" placeholder="default"></label>
              <label class="label full">Description<input name="description"></label>
              <label class="label">Bot IDs CSV<input name="bot_ids"></label>
              <label class="label">Tags CSV<input name="tags"></label>
              <label class="label">Skills CSV<input name="skills"></label>
              <label class="label">Max bots<input name="max_bots"></label>
              <label class="label full">Query<input name="query"></label>
              <button class="btn-primary full" type="submit">Create Team</button>
            </form>
          </div>
        </section>

        <section class="section" id="detailSection">
          <h2>Details</h2>
          <div id="detailBody" class="detail-empty">Select a bot or team from the left list.</div>
        </section>
      </main>
    </section>
  </div>

  <script>
    const state = {
      view: "bots",
      bots: [],
      teams: [],
      selectedBotId: null,
      selectedTeamId: null,
    };

    const el = {
      status: document.getElementById("status"),
      chipBots: document.getElementById("chipBots"),
      chipTeams: document.getElementById("chipTeams"),
      chipRun: document.getElementById("chipRun"),
      chipLast: document.getElementById("chipLast"),
      chipErr: document.getElementById("chipErr"),
      refreshAll: document.getElementById("refreshAll"),
      viewBots: document.getElementById("viewBots"),
      viewTeams: document.getElementById("viewTeams"),
      searchInput: document.getElementById("searchInput"),
      list: document.getElementById("list"),
      detailBody: document.getElementById("detailBody"),
      createBotForm: document.getElementById("createBotForm"),
      createTeamForm: document.getElementById("createTeamForm"),
    };

    function setStatus(message, error = false) {
      el.status.textContent = message || "";
      el.status.style.color = error ? "#b83232" : "#5d6a7c";
    }

    function parseCsv(value) {
      return String(value || "").split(",").map((v) => v.trim()).filter(Boolean);
    }

    function asText(v) {
      return v == null ? "" : String(v);
    }

    function jsonPre(v) {
      return JSON.stringify(v, null, 2);
    }

    async function api(url, options = {}) {
      const res = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.error || `${res.status} ${res.statusText}`);
      }
      return body;
    }

    async function refreshData() {
      const [botsData, teamsData] = await Promise.all([api("/api/bots"), api("/api/teams")]);
      state.bots = botsData.bots || [];
      state.teams = teamsData.teams || [];
      el.chipBots.textContent = `BOTS ${state.bots.length}`;
      el.chipTeams.textContent = `TEAMS ${state.teams.length}`;

      if (state.selectedBotId && !state.bots.some((b) => b.id === state.selectedBotId)) {
        state.selectedBotId = null;
      }
      if (state.selectedTeamId && !state.teams.some((t) => t.id === state.selectedTeamId)) {
        state.selectedTeamId = null;
      }
      renderList();
      renderDetail();
    }

    async function refreshActivity() {
      try {
        const payload = await api("/api/activity");
        const a = payload.activity || {};
        const running = Number(a.running || 0);
        const lastOk = a.last_run_ok;
        const lastTeam = asText(a.last_run_team || "-");
        const lastSummary = a.last_run_summary || null;
        const err = asText(a.last_error || "");

        el.chipRun.textContent = running > 0 ? `RUNNING ${running}` : "RUN IDLE";
        el.chipRun.className = "chip " + (running > 0 ? "warn" : "ok");
        if (lastOk === true) {
          const okCount = Number(lastSummary?.ok || 0);
          const totalCount = Number(lastSummary?.total || 0);
          el.chipLast.textContent = `LAST OK ${lastTeam} ${okCount}/${totalCount}`;
          el.chipLast.className = "chip ok";
        } else if (lastOk === false) {
          el.chipLast.textContent = `LAST FAIL ${lastTeam}`;
          el.chipLast.className = "chip warn";
        } else {
          el.chipLast.textContent = "LAST -";
          el.chipLast.className = "chip";
        }
        if (err) {
          el.chipErr.textContent = `ERR ${err.slice(0, 28)}`;
          el.chipErr.className = "chip warn";
        } else {
          el.chipErr.textContent = "ERR -";
          el.chipErr.className = "chip";
        }
      } catch {
        // keep dashboard usable even if activity poll fails
      }
    }

    function switchView(view) {
      state.view = view;
      el.viewBots.classList.toggle("active", view === "bots");
      el.viewTeams.classList.toggle("active", view === "teams");
      renderList();
      renderDetail();
    }

    function matchesSearch(item, query) {
      if (!query) return true;
      const text = JSON.stringify(item).toLowerCase();
      return text.includes(query);
    }

    function renderList() {
      const query = el.searchInput.value.trim().toLowerCase();
      el.list.innerHTML = "";
      if (state.view === "bots") {
        const rows = state.bots.filter((b) => matchesSearch(b, query));
        if (!rows.length) {
          el.list.innerHTML = '<div class="detail-empty">No bots found.</div>';
          return;
        }
        for (const bot of rows) {
          const node = document.createElement("button");
          node.type = "button";
          node.className = "item" + (state.selectedBotId === bot.id ? " active" : "");
          node.innerHTML = `
            <div class="item-title">${asText(bot.name)}</div>
            <div class="item-sub">${asText(bot.role || "no role")}</div>
            <span class="pill">${asText(bot.id)}</span>
          `;
          node.addEventListener("click", () => {
            state.selectedBotId = bot.id;
            state.selectedTeamId = null;
            renderList();
            renderDetail();
          });
          el.list.appendChild(node);
        }
      } else {
        const rows = state.teams.filter((t) => matchesSearch(t, query));
        if (!rows.length) {
          el.list.innerHTML = '<div class="detail-empty">No teams found.</div>';
          return;
        }
        for (const team of rows) {
          const node = document.createElement("button");
          node.type = "button";
          node.className = "item" + (state.selectedTeamId === team.id ? " active" : "");
          node.innerHTML = `
            <div class="item-title">${asText(team.name)}</div>
            <div class="item-sub">${asText(team.execution_policy || "default")} · ${(team.resolved_bot_ids || []).length} bots</div>
            <span class="pill">${asText(team.id)}</span>
          `;
          node.addEventListener("click", () => {
            state.selectedTeamId = team.id;
            state.selectedBotId = null;
            renderList();
            renderDetail();
          });
          el.list.appendChild(node);
        }
      }
    }

    function renderDetail() {
      el.detailBody.innerHTML = "";
      if (state.view === "bots") {
        const bot = state.bots.find((b) => b.id === state.selectedBotId);
        if (!bot) {
          el.detailBody.className = "detail-empty";
          el.detailBody.textContent = "Select a bot to edit.";
          return;
        }
        el.detailBody.className = "";
        const wrap = document.createElement("form");
        wrap.className = "form-grid";
        wrap.innerHTML = `
          <label class="label">Name<input name="name" value="${asText(bot.name)}"></label>
          <label class="label">Role<input name="role" value="${asText(bot.role)}"></label>
          <label class="label">Model<input name="model" value="${asText(bot.model || "")}"></label>
          <label class="label">Provider<input name="provider" value="${asText(bot.provider || "")}"></label>
          <label class="label full">Description<input name="description" value="${asText(bot.description || "")}"></label>
          <label class="label">Tags CSV<input name="tags" value="${asText((bot.tags || []).join(", "))}"></label>
          <label class="label">Skills CSV<input name="skills" value="${asText((bot.skills || []).join(", "))}"></label>
          <label class="label full">Custom Skills CSV<input name="custom_skills" value="${asText((bot.custom_skills || []).join(", "))}"></label>
          <label class="label full">Workspace<input value="${asText(bot.workspace)}" disabled></label>
          <label class="label full">Config<input value="${asText(bot.config_path)}" disabled></label>
          <div class="full" style="display:flex;gap:8px;flex-wrap:wrap;">
            <button class="btn-green" type="submit">Save Bot</button>
            <button class="btn-danger" type="button" id="deleteBotBtn">Delete Bot</button>
          </div>
        `;
        wrap.addEventListener("submit", async (event) => {
          event.preventDefault();
          const fd = new FormData(wrap);
          try {
            await api(`/api/bots/${encodeURIComponent(bot.id)}`, {
              method: "PATCH",
              body: JSON.stringify({
                name: fd.get("name"),
                role: fd.get("role"),
                model: fd.get("model"),
                provider: fd.get("provider"),
                description: fd.get("description"),
                tags: parseCsv(fd.get("tags")),
                skills: parseCsv(fd.get("skills")),
                custom_skills: parseCsv(fd.get("custom_skills")),
              }),
            });
            setStatus(`Updated bot ${bot.id}`);
            await refreshData();
          } catch (err) {
            setStatus(String(err), true);
          }
        });
        el.detailBody.appendChild(wrap);
        wrap.querySelector("#deleteBotBtn").addEventListener("click", async () => {
          if (!confirm(`Delete bot ${bot.id}?`)) return;
          try {
            await api(`/api/bots/${encodeURIComponent(bot.id)}?purge_files=1&force=1`, {
              method: "DELETE",
            });
            setStatus(`Deleted bot ${bot.id}`);
            state.selectedBotId = null;
            await refreshData();
          } catch (err) {
            setStatus(String(err), true);
          }
        });
      } else {
        const team = state.teams.find((t) => t.id === state.selectedTeamId);
        if (!team) {
          el.detailBody.className = "detail-empty";
          el.detailBody.textContent = "Select a team to edit and run.";
          return;
        }
        el.detailBody.className = "";
        const wrap = document.createElement("div");
        wrap.className = "form-grid";
        wrap.innerHTML = `
          <label class="label">Name<input id="tName" value="${asText(team.name)}"></label>
          <label class="label">Execution policy<input id="tPolicy" value="${asText(team.execution_policy || "default")}"></label>
          <label class="label full">Description<input id="tDesc" value="${asText(team.description || "")}"></label>
          <label class="label">Bot IDs CSV<input id="tBots" value="${asText((team.bot_ids || []).join(", "))}"></label>
          <label class="label">Tags CSV<input id="tTags" value="${asText((team.tags || []).join(", "))}"></label>
          <label class="label">Skills CSV<input id="tSkills" value="${asText((team.skills || []).join(", "))}"></label>
          <label class="label">Max bots<input id="tMax" value="${team.max_bots == null ? "" : asText(team.max_bots)}"></label>
          <label class="label full">Query<input id="tQuery" value="${asText(team.query || "")}"></label>
          <div class="full" style="display:flex;gap:8px;flex-wrap:wrap;">
            <button class="btn-green" type="button" id="saveTeamBtn">Save Team</button>
            <button class="btn-danger" type="button" id="deleteTeamBtn">Delete Team</button>
          </div>
          <hr class="full" style="border:none;border-top:1px solid var(--line);margin:4px 0;">
          <label class="label full">Run message<textarea id="rMessage">Plan a launch campaign</textarea></label>
          <label class="label">Run policy<input id="rPolicy" placeholder="default/fast/balanced/strict"></label>
          <label class="label">Run strategy<input id="rStrategy" placeholder="all/best_match/top_k"></label>
          <label class="label">Run strategy_k<input id="rStrategyK"></label>
          <label class="label">Run timeout<input id="rTimeout" placeholder="seconds"></label>
          <label class="label">Run concurrency<input id="rConcurrency"></label>
          <label class="label">Run retries<input id="rRetries"></label>
          <label class="label">Run min success<input id="rMinSuccess"></label>
          <label class="label">Run fallback bot<input id="rFallback"></label>
          <label class="label">Run label<input id="rLabel"></label>
          <button class="btn-primary full" type="button" id="runTeamBtn">Run Team</button>
          <pre class="result-box full" id="runResultBox">No run yet.</pre>
        `;
        el.detailBody.appendChild(wrap);

        wrap.querySelector("#saveTeamBtn").addEventListener("click", async () => {
          try {
            await api(`/api/teams/${encodeURIComponent(team.id)}`, {
              method: "PATCH",
              body: JSON.stringify({
                name: wrap.querySelector("#tName").value,
                description: wrap.querySelector("#tDesc").value,
                execution_policy: wrap.querySelector("#tPolicy").value,
                bot_ids: parseCsv(wrap.querySelector("#tBots").value),
                tags: parseCsv(wrap.querySelector("#tTags").value),
                skills: parseCsv(wrap.querySelector("#tSkills").value),
                query: wrap.querySelector("#tQuery").value,
                max_bots: wrap.querySelector("#tMax").value.trim() ? Number(wrap.querySelector("#tMax").value.trim()) : null,
              }),
            });
            setStatus(`Updated team ${team.id}`);
            await refreshData();
          } catch (err) {
            setStatus(String(err), true);
          }
        });

        wrap.querySelector("#deleteTeamBtn").addEventListener("click", async () => {
          if (!confirm(`Delete team ${team.id}?`)) return;
          try {
            await api(`/api/teams/${encodeURIComponent(team.id)}`, { method: "DELETE" });
            setStatus(`Deleted team ${team.id}`);
            state.selectedTeamId = null;
            await refreshData();
          } catch (err) {
            setStatus(String(err), true);
          }
        });

        wrap.querySelector("#runTeamBtn").addEventListener("click", async () => {
          const box = wrap.querySelector("#runResultBox");
          box.textContent = "Running...";
          try {
            const payload = await api(`/api/teams/${encodeURIComponent(team.id)}/run`, {
              method: "POST",
              body: JSON.stringify({
                message: wrap.querySelector("#rMessage").value,
                policy: wrap.querySelector("#rPolicy").value,
                strategy: wrap.querySelector("#rStrategy").value,
                strategy_k: wrap.querySelector("#rStrategyK").value,
                timeout: wrap.querySelector("#rTimeout").value,
                max_concurrency: wrap.querySelector("#rConcurrency").value,
                retries: wrap.querySelector("#rRetries").value,
                min_successful_bots: wrap.querySelector("#rMinSuccess").value,
                fallback_bot: wrap.querySelector("#rFallback").value,
                run_label: wrap.querySelector("#rLabel").value,
              }),
            });
            box.textContent = jsonPre(payload);
            setStatus(`Team run completed: ${team.id}`);
          } catch (err) {
            box.textContent = String(err);
            setStatus(String(err), true);
          }
        });
      }
    }

    el.viewBots.addEventListener("click", () => switchView("bots"));
    el.viewTeams.addEventListener("click", () => switchView("teams"));
    el.searchInput.addEventListener("input", renderList);
    el.refreshAll.addEventListener("click", async () => {
      try {
        await refreshData();
        await refreshActivity();
        setStatus("Refreshed.");
      } catch (err) {
        setStatus(String(err), true);
      }
    });

    el.createBotForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(el.createBotForm);
      try {
        const out = await api("/api/bots", {
          method: "POST",
          body: JSON.stringify({
            name: fd.get("name"),
            role: fd.get("role"),
            model: fd.get("model"),
            provider: fd.get("provider"),
            description: fd.get("description") || "",
            tags: parseCsv(fd.get("tags")),
            skills: parseCsv(fd.get("skills")),
            custom_skills: parseCsv(fd.get("custom_skills")),
            memory_seed: fd.get("memory_seed") || "",
          }),
        });
        el.createBotForm.reset();
        state.selectedBotId = out?.bot?.id || null;
        switchView("bots");
        await refreshData();
        setStatus("Bot created.");
      } catch (err) {
        setStatus(String(err), true);
      }
    });

    el.createTeamForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(el.createTeamForm);
      try {
        const out = await api("/api/teams", {
          method: "POST",
          body: JSON.stringify({
            name: fd.get("name"),
            description: fd.get("description") || "",
            bot_ids: parseCsv(fd.get("bot_ids")),
            tags: parseCsv(fd.get("tags")),
            skills: parseCsv(fd.get("skills")),
            query: fd.get("query") || "",
            execution_policy: fd.get("execution_policy") || "default",
            max_bots: String(fd.get("max_bots") || "").trim() ? Number(String(fd.get("max_bots")).trim()) : null,
          }),
        });
        el.createTeamForm.reset();
        state.selectedTeamId = out?.team?.id || null;
        switchView("teams");
        await refreshData();
        setStatus("Team created.");
      } catch (err) {
        setStatus(String(err), true);
      }
    });

    refreshData().catch((err) => setStatus(String(err), true));
    refreshActivity().catch(() => undefined);
    window.setInterval(() => {
      refreshActivity().catch(() => undefined);
    }, 2000);
  </script>
</body>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
    """HTTP handlers for dashboard and bot CRUD endpoints."""

    server_version = "nanobot-dashboard/1.0"

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, payload: str) -> None:
        raw = payload.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        data = self.rfile.read(length)
        if not data:
            return {}
        return json.loads(data.decode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Keep CLI output clean; this dashboard is local and interactive.
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/":
            self._send_html(_html())
            return
        if parsed.path == "/api/bots":
            self._send_json({"bots": _dashboard_payload()})
            return
        if parsed.path == "/api/teams":
            self._send_json({"teams": _teams_payload()})
            return
        if parsed.path == "/api/activity":
            self._send_json({"activity": _activity_payload()})
            return
        if parsed.path == "/api/runtime/bots":
            self._send_json({"workers": _RUNTIME.list_workers(), "links": _RUNTIME.links_payload()})
            return
        if parsed.path == "/api/runtime/links":
            self._send_json({"links": _RUNTIME.links_payload()})
            return
        if parsed.path == "/api/runtime/memory":
            team_id = str((query.get("teamId") or ["default"])[0] or "default").strip() or "default"
            self._send_json({"teamId": team_id, "memory": _load_team_memory(team_id)})
            return
        if parsed.path == "/api/runs":
            team_id = str((query.get("teamId") or [""])[0] or "").strip() or None
            self._send_json({"runs": _list_runs(team_id)})
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/events"):
            run_id = parsed.path.removeprefix("/api/runs/").removesuffix("/events").strip("/")
            if not run_id:
                self._send_json({"error": "runId is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            payload = _get_run_events(run_id)
            if not payload:
                self._send_json({"error": f"Unknown run: {run_id}"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(payload)
            return
        if parsed.path == "/api/tasks":
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            self._send_json({"tasks": _load_tasks(team_id)})
            return
        if parsed.path == "/api/team/files":
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            base = _team_workspace(team_id)
            files: list[str] = []
            dirs: list[str] = []
            for p in sorted(base.rglob("*")):
                rel = p.relative_to(base).as_posix()
                if not rel:
                    continue
                if p.is_dir():
                    dirs.append(rel)
                elif p.is_file():
                    files.append(rel)
            self._send_json({"files": files, "dirs": dirs})
            return
        if parsed.path == "/api/team/file":
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            rel_path = str((query.get("path") or [""])[0] or "").strip()
            if not rel_path:
                self._send_json({"error": "path is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                path = _resolve_team_path(team_id, rel_path)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            if not path.exists() or not path.is_file():
                self._send_json({"error": "file not found"}, status=HTTPStatus.NOT_FOUND)
                return
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            updated_at = int(path.stat().st_mtime * 1000)
            self._send_json({"path": rel_path, "content": content, "updatedAt": updated_at})
            return
        if parsed.path in {"/api/nanobot/skills", "/api/opencode/skills"}:
            self._send_json({"ok": True, "skills": _skills_payload()})
            return
        if parsed.path in {"/api/nanobot/mcp", "/api/opencode/mcp"}:
            self._send_json({"ok": True, "status": _mcp_status_payload()})
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path.startswith("/api/runtime/bots/") and parsed.path.endswith("/start"):
            bot_id = parsed.path.removeprefix("/api/runtime/bots/").removesuffix("/start").strip("/")
            if not bot_id:
                self._send_json({"error": "botId is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                status = _RUNTIME.start_worker(bot_id)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "worker": status})
            return
        if parsed.path.startswith("/api/runtime/bots/") and parsed.path.endswith("/stop"):
            bot_id = parsed.path.removeprefix("/api/runtime/bots/").removesuffix("/stop").strip("/")
            if not bot_id:
                self._send_json({"error": "botId is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            status = _RUNTIME.stop_worker(bot_id)
            self._send_json({"ok": True, "worker": status})
            return
        if parsed.path.startswith("/api/runtime/bots/") and parsed.path.endswith("/chat"):
            bot_id = parsed.path.removeprefix("/api/runtime/bots/").removesuffix("/chat").strip("/")
            if not bot_id:
                self._send_json({"error": "botId is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            team_id = str(body.get("teamId") or "").strip()
            raw_message = str(body.get("message") or "")
            shared_memory = _load_team_memory(team_id) if team_id else ""
            message = raw_message.strip()
            if shared_memory.strip():
                message = (
                    "# Team Shared Memory\n"
                    f"{shared_memory.strip()}\n\n"
                    "# Incoming Request\n"
                    f"{message}"
                ).strip()
            try:
                result = _RUNTIME.chat(
                    bot_id,
                    message,
                    session_id=str(body.get("sessionId") or "").strip() or None,
                    timeout=float(body.get("timeout") or 180.0),
                )
            except (ValueError, RuntimeError) as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "teamMemoryUsed": bool(shared_memory.strip()), **result})
            return
        if parsed.path == "/api/runtime/memory":
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            team_id = str(body.get("teamId") or "default").strip() or "default"
            mode = str(body.get("mode") or "replace").strip().lower()
            text = str(body.get("text") or "")
            if mode == "append":
                current = _load_team_memory(team_id).strip()
                next_text = f"{current}\n\n{text.strip()}".strip() if current else text.strip()
            else:
                next_text = text
            _save_team_memory(team_id, next_text)
            self._send_json({"ok": True, "teamId": team_id, "memory": next_text})
            return
        if parsed.path == "/api/runtime/relay":
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            from_bot = str(body.get("fromBotId") or "").strip()
            to_bot = str(body.get("toBotId") or "").strip()
            message = str(body.get("message") or "").strip()
            if not from_bot or not to_bot:
                self._send_json({"error": "fromBotId and toBotId are required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                result = _RUNTIME.relay(
                    from_bot,
                    to_bot,
                    message,
                    timeout=float(body.get("timeout") or 180.0),
                )
            except (ValueError, RuntimeError) as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, **result})
            return
        if parsed.path == "/api/runtime/links":
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            from_bot = str(body.get("fromBotId") or "").strip()
            to_bot = str(body.get("toBotId") or "").strip()
            if not from_bot or not to_bot:
                self._send_json({"error": "fromBotId and toBotId are required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                links = _RUNTIME.add_link(from_bot, to_bot)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "links": links})
            return
        if parsed.path == "/api/tasks":
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            title = str(body.get("title", "")).strip()
            if not title:
                self._send_json({"error": "title is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            now = int(time.time() * 1000)
            task = {
                "id": uuid.uuid4().hex[:10],
                "title": title,
                "description": str(body.get("description", "")),
                "status": "todo",
                "priority": str(body.get("priority", "P2") or "P2"),
                "assignee": str(body.get("assignee", "")),
                "createdAt": now,
                "updatedAt": now,
                "retryCount": 0,
                "retryLimit": 0,
            }
            tasks = _load_tasks(team_id)
            tasks.insert(0, task)
            _save_tasks(team_id, tasks)
            self._send_json({"task": task}, status=HTTPStatus.CREATED)
            return
        if parsed.path == "/api/team/file":
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            rel_path = str(body.get("path", "")).strip()
            if not rel_path:
                self._send_json({"error": "path is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                path = _resolve_team_path(team_id, rel_path)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            content = str(body.get("content", ""))
            path.write_text(content, encoding="utf-8")
            updated_at = int(path.stat().st_mtime * 1000)
            self._send_json({"ok": True, "path": rel_path, "updatedAt": updated_at}, status=HTTPStatus.CREATED)
            return
        if parsed.path == "/api/team/file/rename":
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            old_path = str(body.get("oldPath", "")).strip()
            new_path = str(body.get("newPath", "")).strip()
            if not old_path or not new_path:
                self._send_json({"error": "oldPath and newPath are required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                src = _resolve_team_path(team_id, old_path)
                dst = _resolve_team_path(team_id, new_path)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            if not src.exists():
                self._send_json({"error": "source file not found"}, status=HTTPStatus.NOT_FOUND)
                return
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            self._send_json({"ok": True, "path": new_path})
            return
        if parsed.path == "/api/team/dir":
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            rel_path = str(body.get("path", "")).strip()
            if not rel_path:
                self._send_json({"error": "path is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                path = _resolve_team_path(team_id, rel_path)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            path.mkdir(parents=True, exist_ok=True)
            self._send_json({"ok": True, "path": rel_path}, status=HTTPStatus.CREATED)
            return
        if (
            (parsed.path.startswith("/api/nanobot/mcp/") and parsed.path.endswith("/connect"))
            or (parsed.path.startswith("/api/opencode/mcp/") and parsed.path.endswith("/connect"))
        ):
            prefix = "/api/nanobot/mcp/" if parsed.path.startswith("/api/nanobot/mcp/") else "/api/opencode/mcp/"
            name = parsed.path.removeprefix(prefix).removesuffix("/connect").strip("/")
            if not name:
                self._send_json({"error": "name is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            with _MCP_STATUS_LOCK:
                _MCP_STATUS[name] = {"status": "connected"}
            self._send_json({"ok": True, "name": name})
            return
        if (
            (parsed.path.startswith("/api/nanobot/mcp/") and parsed.path.endswith("/disconnect"))
            or (parsed.path.startswith("/api/opencode/mcp/") and parsed.path.endswith("/disconnect"))
        ):
            prefix = "/api/nanobot/mcp/" if parsed.path.startswith("/api/nanobot/mcp/") else "/api/opencode/mcp/"
            name = parsed.path.removeprefix(prefix).removesuffix("/disconnect").strip("/")
            if not name:
                self._send_json({"error": "name is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            with _MCP_STATUS_LOCK:
                _MCP_STATUS[name] = {"status": "disabled"}
            self._send_json({"ok": True, "name": name})
            return
        if parsed.path != "/api/bots":
            if parsed.path == "/api/teams":
                try:
                    body = self._read_json_body()
                    bot_ids = _list_from_field(body.get("bot_ids"))
                    tags = _list_from_field(body.get("tags"))
                    skills = _list_from_field(body.get("skills"))
                    raw_query = str(body.get("query", ""))
                    query_text = raw_query
                    if not bot_ids and not tags and not skills and not raw_query.strip():
                        # Allow creating "empty" teams for dashboard workflows.
                        query_text = f"__team_placeholder__{uuid.uuid4().hex[:8]}"
                    created_team = create_team(
                        name=str(body.get("name", "")).strip(),
                        description=str(body.get("description", "")),
                        bot_ids=bot_ids,
                        tags=tags,
                        skills=skills,
                        query=query_text,
                        max_bots=(
                            int(body["max_bots"])
                            if body.get("max_bots") not in {None, ""}
                            else None
                        ),
                        execution_policy=str(body.get("execution_policy", "default")),
                    )
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                except json.JSONDecodeError:
                    self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                    return
                resolved = get_team(str(created_team.get("id")))
                payload = resolved or created_team
                self._send_json({"team": payload}, status=HTTPStatus.CREATED)
                return

            if parsed.path.endswith("/run") and parsed.path.startswith("/api/teams/"):
                team_id = parsed.path.removeprefix("/api/teams/").removesuffix("/run").strip("/")
                if not team_id:
                    self._send_json({"error": "Team id is required"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if not get_team(team_id):
                    self._send_json({"error": f"Unknown team: {team_id}"}, status=HTTPStatus.NOT_FOUND)
                    return
                try:
                    body = self._read_json_body()
                    message = str(body.get("message", "")).strip()
                    if not message:
                        self._send_json({"error": "message is required"}, status=HTTPStatus.BAD_REQUEST)
                        return
                    payload = _run_team(
                        team_id,
                        message,
                        options={
                            "policy": body.get("policy"),
                            "strategy": body.get("strategy"),
                            "strategy_k": body.get("strategy_k"),
                            "timeout": body.get("timeout"),
                            "max_concurrency": body.get("max_concurrency"),
                            "retries": body.get("retries"),
                            "min_successful_bots": body.get("min_successful_bots"),
                            "fallback_bot": body.get("fallback_bot"),
                            "run_label": body.get("run_label"),
                        },
                    )
                except (RuntimeError, ValueError) as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                except json.JSONDecodeError:
                    self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._send_json({"result": payload})
                return

            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            body = self._read_json_body()
            created = create_bot(
                name=str(body.get("name", "")).strip(),
                role=str(body.get("role", "")).strip(),
                description=str(body.get("description", "")),
                model=str(body["model"]).strip() if body.get("model") else None,
                provider=str(body["provider"]).strip() if body.get("provider") else None,
                tags=_list_from_field(body.get("tags")),
                skills=_list_from_field(body.get("skills")),
                custom_skills=_list_from_field(body.get("custom_skills")),
                memory_seed=str(body.get("memory_seed", "")),
                force=bool(body.get("force", False)),
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"bot": bot_runtime_summary(created)}, status=HTTPStatus.CREATED)

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path.startswith("/api/tasks/"):
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            task_id = parsed.path.rsplit("/", 1)[-1]
            if not task_id:
                self._send_json({"error": "task id is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            tasks = _load_tasks(team_id)
            target = next((item for item in tasks if str(item.get("id")) == task_id), None)
            if not target:
                self._send_json({"error": "task not found"}, status=HTTPStatus.NOT_FOUND)
                return
            for key in [
                "title",
                "description",
                "status",
                "priority",
                "assignee",
                "retryCount",
                "retryLimit",
                "failureReason",
                "lastEvent",
            ]:
                if key in body:
                    target[key] = body[key]
            target["updatedAt"] = int(time.time() * 1000)
            _save_tasks(team_id, tasks)
            self._send_json({"task": target})
            return
        if parsed.path.startswith("/api/teams/"):
            team_id = parsed.path.rsplit("/", 1)[-1]
            if not team_id:
                self._send_json({"error": "Team id is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                body = self._read_json_body()
                updated = update_team(
                    team_id,
                    name=str(body["name"]) if "name" in body else None,
                    description=str(body["description"]) if "description" in body else None,
                    bot_ids=_list_from_field(body.get("bot_ids")) if "bot_ids" in body else _UNSET,
                    tags=_list_from_field(body.get("tags")) if "tags" in body else _UNSET,
                    skills=_list_from_field(body.get("skills")) if "skills" in body else _UNSET,
                    query=str(body.get("query", "")) if "query" in body else _UNSET,
                    max_bots=(
                        None
                        if body.get("max_bots") in {None, ""}
                        else int(body["max_bots"])
                    ) if "max_bots" in body else _UNSET,
                    execution_policy=(
                        str(body.get("execution_policy", "default"))
                        if "execution_policy" in body
                        else _UNSET
                    ),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"team": updated})
            return

        if not parsed.path.startswith("/api/bots/"):
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        bot_id = parsed.path.rsplit("/", 1)[-1]
        if not bot_id:
            self._send_json({"error": "Bot id is required"}, status=HTTPStatus.BAD_REQUEST)
            return
        try:
            body = self._read_json_body()
            updated = update_bot(
                bot_id,
                name=str(body["name"]).strip() if "name" in body and body.get("name") else None,
                role=str(body["role"]).strip() if "role" in body and body.get("role") else None,
                description=str(body["description"]) if "description" in body else None,
                model=str(body["model"]).strip() if "model" in body and body.get("model") else None,
                provider=str(body["provider"]).strip() if "provider" in body and body.get("provider") else None,
                tags=_list_from_field(body.get("tags")) if "tags" in body else _UNSET,
                skills=_list_from_field(body.get("skills")) if "skills" in body else _UNSET,
                custom_skills=(
                    _list_from_field(body.get("custom_skills"))
                    if "custom_skills" in body
                    else _UNSET
                ),
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            return

        bot = get_bot(bot_id)
        payload = bot_runtime_summary(bot if bot else updated)
        self._send_json({"bot": payload})

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/team/file":
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            try:
                body = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
                return
            rel_path = str(body.get("path", "")).strip()
            if not rel_path:
                self._send_json({"error": "path is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                path = _resolve_team_path(team_id, rel_path)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            content = str(body.get("content", ""))
            path.write_text(content, encoding="utf-8")
            updated_at = int(path.stat().st_mtime * 1000)
            self._send_json({"ok": True, "path": rel_path, "updatedAt": updated_at})
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/runtime/memory":
            team_id = str((query.get("teamId") or ["default"])[0] or "default").strip() or "default"
            _save_team_memory(team_id, "")
            self._send_json({"ok": True, "teamId": team_id, "memory": ""})
            return
        if parsed.path == "/api/runtime/links":
            from_bot = str((query.get("fromBotId") or [""])[0] or "").strip()
            to_bot = str((query.get("toBotId") or [""])[0] or "").strip()
            if not from_bot or not to_bot:
                self._send_json({"error": "fromBotId and toBotId are required"}, status=HTTPStatus.BAD_REQUEST)
                return
            links = _RUNTIME.remove_link(from_bot, to_bot)
            self._send_json({"ok": True, "links": links})
            return
        if parsed.path.startswith("/api/tasks/"):
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            task_id = parsed.path.rsplit("/", 1)[-1]
            if not task_id:
                self._send_json({"error": "task id is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            tasks = _load_tasks(team_id)
            next_tasks = [item for item in tasks if str(item.get("id")) != task_id]
            if len(next_tasks) == len(tasks):
                self._send_json({"error": "task not found"}, status=HTTPStatus.NOT_FOUND)
                return
            _save_tasks(team_id, next_tasks)
            self._send_json({"ok": True, "deleted": task_id})
            return
        if parsed.path == "/api/team/file":
            team_id = str((query.get("teamId") or ["default"])[0] or "default")
            rel_path = str((query.get("path") or [""])[0] or "").strip()
            if not rel_path:
                self._send_json({"error": "path is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                path = _resolve_team_path(team_id, rel_path)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            if not path.exists():
                self._send_json({"error": "file not found"}, status=HTTPStatus.NOT_FOUND)
                return
            if path.is_dir():
                self._send_json({"error": "path is a directory"}, status=HTTPStatus.BAD_REQUEST)
                return
            path.unlink()
            self._send_json({"ok": True, "deleted": rel_path})
            return
        if parsed.path.startswith("/api/teams/"):
            team_id = parsed.path.rsplit("/", 1)[-1]
            if not team_id:
                self._send_json({"error": "Team id is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                removed = delete_team(team_id)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"deleted": removed.get("id"), "ok": True})
            return

        if not parsed.path.startswith("/api/bots/"):
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        bot_id = parsed.path.rsplit("/", 1)[-1]
        if not bot_id:
            self._send_json({"error": "Bot id is required"}, status=HTTPStatus.BAD_REQUEST)
            return
        purge = query.get("purge_files", ["0"])[0] in {"1", "true", "yes"}
        force = query.get("force", ["0"])[0] in {"1", "true", "yes"}
        try:
            removed = delete_bot(bot_id, purge_files=purge, force=force)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"deleted": removed.get("id"), "ok": True})


def serve_dashboard_web(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start a local HTTP server for interactive bot management."""
    with ThreadingHTTPServer((host, port), _Handler) as server:
        server.serve_forever()


__all__ = ["serve_dashboard_web"]
