"""Long-lived bot worker process for dashboard runtime chat."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.cli.runtime_support import load_runtime_config, make_provider
from nanobot.config.paths import get_cron_dir
from nanobot.cron.service import CronService
from nanobot.utils.helpers import sync_workspace_templates


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


async def _create_agent(config_path: str, *, logs: bool) -> AgentLoop:
    from loguru import logger

    config = load_runtime_config(Console(), config=config_path, announce=False)
    sync_workspace_templates(config.workspace_path)

    bus = MessageBus()
    provider = make_provider(config, Console())
    cron_store_path = get_cron_dir() / "jobs.json"
    cron = CronService(cron_store_path)

    if logs:
        logger.enable("nanobot")
    else:
        logger.disable("nanobot")

    return AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        context_window_tokens=config.agents.defaults.context_window_tokens,
        web_search_config=config.tools.web.search,
        web_proxy=config.tools.web.proxy or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
    )


async def _run_worker(bot_id: str, config_path: str, *, logs: bool) -> int:
    agent = await _create_agent(config_path, logs=logs)
    _emit({"type": "ready", "botId": bot_id})

    try:
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                _emit({"type": "error", "error": "invalid_json"})
                continue

            request_id = str(payload.get("request_id") or "")
            cmd = str(payload.get("type") or "").strip().lower()
            if cmd == "shutdown":
                _emit({"type": "result", "request_id": request_id, "ok": True, "shutdown": True})
                break

            if cmd not in {"chat", "command"}:
                _emit({
                    "type": "result",
                    "request_id": request_id,
                    "ok": False,
                    "error": f"unsupported_type:{cmd}",
                })
                continue

            message = str(payload.get("message") or "").strip()
            if not message:
                _emit({
                    "type": "result",
                    "request_id": request_id,
                    "ok": False,
                    "error": "message_required",
                })
                continue

            session_key = str(payload.get("session_id") or f"runtime:{bot_id}")
            try:
                response = await agent.process_direct(
                    message,
                    session_key=session_key,
                    channel="cli",
                    chat_id=f"runtime:{bot_id}",
                )
                _emit(
                    {
                        "type": "result",
                        "request_id": request_id,
                        "ok": True,
                        "content": response.content if response else "",
                        "metadata": response.metadata if response else {},
                        "session_id": session_key,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                _emit(
                    {
                        "type": "result",
                        "request_id": request_id,
                        "ok": False,
                        "error": str(exc) or exc.__class__.__name__,
                        "session_id": session_key,
                    }
                )
    finally:
        await agent.close_mcp()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="nanobot runtime worker")
    parser.add_argument("--bot-id", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--logs", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        _emit({"type": "fatal", "error": f"config_not_found:{config_path}"})
        return 2

    return asyncio.run(_run_worker(args.bot_id, str(config_path), logs=args.logs))


if __name__ == "__main__":
    raise SystemExit(main())
