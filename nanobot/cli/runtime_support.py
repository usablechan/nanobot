"""Shared runtime helpers used by CLI commands and bot/team orchestration."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

import typer
from rich.console import Console

from nanobot.config.schema import Config
from nanobot.utils.helpers import sync_workspace_templates

LoadRuntimeConfigFn = Callable[..., Config]
RunAgentOnceFn = Callable[..., Awaitable[Any]]


def warn_deprecated_config_keys(console: Console, config_path: Path | None) -> None:
    """Hint users to remove obsolete keys from their config file."""
    from nanobot.config.loader import get_config_path

    path = config_path or get_config_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if "memoryWindow" in raw.get("agents", {}).get("defaults", {}):
        console.print(
            "[dim]Hint: `memoryWindow` in your config is no longer used "
            "and can be safely removed.[/dim]"
        )


def make_provider(config: Config, console: Console):
    """Create the appropriate LLM provider from config."""
    from nanobot.providers.azure_openai_provider import AzureOpenAIProvider
    from nanobot.providers.base import GenerationSettings
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        provider = OpenAICodexProvider(default_model=model)
    elif provider_name == "custom":
        from nanobot.providers.custom_provider import CustomProvider

        provider = CustomProvider(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
            extra_headers=p.extra_headers if p else None,
        )
    elif provider_name == "azure_openai":
        if not p or not p.api_key or not p.api_base:
            console.print("[red]Error: Azure OpenAI requires api_key and api_base.[/red]")
            console.print("Set them in ~/.nanobot/config.json under providers.azure_openai section")
            console.print("Use the model field to specify the deployment name.")
            raise typer.Exit(1)
        provider = AzureOpenAIProvider(
            api_key=p.api_key,
            api_base=p.api_base,
            default_model=model,
        )
    else:
        from nanobot.providers.litellm_provider import LiteLLMProvider
        from nanobot.providers.registry import find_by_name

        spec = find_by_name(provider_name)
        if not model.startswith("bedrock/") and not (p and p.api_key) and not (
            spec and (spec.is_oauth or spec.is_local)
        ):
            console.print("[red]Error: No API key configured.[/red]")
            console.print("Set one in ~/.nanobot/config.json under providers section")
            raise typer.Exit(1)
        provider = LiteLLMProvider(
            api_key=p.api_key if p else None,
            api_base=config.get_api_base(model),
            default_model=model,
            extra_headers=p.extra_headers if p else None,
            provider_name=provider_name,
        )

    defaults = config.agents.defaults
    provider.generation = GenerationSettings(
        temperature=defaults.temperature,
        max_tokens=defaults.max_tokens,
        reasoning_effort=defaults.reasoning_effort,
    )
    return provider


def load_runtime_config(
    console: Console,
    config: str | None = None,
    workspace: str | None = None,
    *,
    announce: bool = True,
) -> Config:
    """Load config and optionally override the active workspace."""
    from nanobot.config.loader import load_config, set_config_path

    config_path = None
    if config:
        config_path = Path(config).expanduser().resolve()
        if not config_path.exists():
            console.print(f"[red]Error: Config file not found: {config_path}[/red]")
            raise typer.Exit(1)
        set_config_path(config_path)
        if announce:
            console.print(f"[dim]Using config: {config_path}[/dim]")

    loaded = load_config(config_path)
    warn_deprecated_config_keys(console, config_path)
    if workspace:
        loaded.agents.defaults.workspace = workspace
    return loaded


async def run_agent_once(
    config: Config,
    message: str,
    session_id: str,
    *,
    logs: bool = False,
):
    """Run a single direct agent turn for an already-resolved config."""
    from loguru import logger

    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.config.paths import get_cron_dir
    from nanobot.cron.service import CronService

    sync_workspace_templates(config.workspace_path)

    bus = MessageBus()
    provider = make_provider(config, Console())

    cron_store_path = get_cron_dir() / "jobs.json"
    cron = CronService(cron_store_path)

    if logs:
        logger.enable("nanobot")
    else:
        logger.disable("nanobot")

    agent_loop = AgentLoop(
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
    try:
        return await agent_loop.process_direct(message, session_id)
    finally:
        await agent_loop.close_mcp()


def _bot_result(
    bot: dict[str, Any],
    *,
    session_id: str,
    response: Any = None,
    status: str = "ok",
    error: str | None = None,
    elapsed_ms: int | None = None,
) -> dict[str, Any]:
    """Build a normalized bot execution payload for CLI output."""
    return {
        "id": str(bot["id"]),
        "name": bot["name"],
        "session_id": session_id,
        "status": status,
        "error": error,
        "elapsed_ms": elapsed_ms,
        "content": response.content if response else "",
        "metadata": response.metadata if response else {},
        "tags": bot.get("tags", []),
        "skills": bot.get("skills", []),
        "custom_skills": bot.get("custom_skills", []),
    }


async def run_bots_for_message_with(
    bots: list[dict[str, Any]],
    *,
    message: str,
    session_prefix: str,
    load_runtime_config_fn: LoadRuntimeConfigFn,
    run_agent_once_fn: RunAgentOnceFn,
    logs: bool = False,
    timeout_s: float | None = None,
    max_concurrency: int | None = None,
) -> list[dict[str, Any]]:
    """Execute multiple bots in parallel while preserving input order and failures."""

    semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency else None

    async def _run_single(bot: dict[str, Any]) -> dict[str, Any]:
        bot_id = str(bot["id"])
        resolved_session = f"{session_prefix}:{bot_id}"
        bot_config = load_runtime_config_fn(config=bot["config_path"], announce=False)
        started_at = time.perf_counter()

        async def _execute() -> Any:
            coro = run_agent_once_fn(
                bot_config,
                message,
                resolved_session,
                logs=logs,
            )
            return await asyncio.wait_for(coro, timeout=timeout_s) if timeout_s else await coro

        try:
            if semaphore:
                async with semaphore:
                    response = await _execute()
            else:
                response = await _execute()
        except TimeoutError:
            timeout_label = format(timeout_s or 0, "g")
            return _bot_result(
                bot,
                session_id=resolved_session,
                status="timeout",
                error=f"Timed out after {timeout_label}s",
                elapsed_ms=round((time.perf_counter() - started_at) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 - keep fanout alive when one bot fails
            return _bot_result(
                bot,
                session_id=resolved_session,
                status="error",
                error=str(exc) or exc.__class__.__name__,
                elapsed_ms=round((time.perf_counter() - started_at) * 1000),
            )
        return _bot_result(
            bot,
            session_id=resolved_session,
            response=response,
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )

    return list(await asyncio.gather(*(_run_single(bot) for bot in bots)))


async def run_bots_for_message(
    bots: list[dict[str, Any]],
    *,
    message: str,
    session_prefix: str,
    logs: bool = False,
    timeout_s: float | None = None,
    max_concurrency: int | None = None,
) -> list[dict[str, Any]]:
    """Execute the same message across multiple registered bots."""
    return await run_bots_for_message_with(
        bots,
        message=message,
        session_prefix=session_prefix,
        load_runtime_config_fn=lambda **kwargs: load_runtime_config(Console(), **kwargs),
        run_agent_once_fn=run_agent_once,
        logs=logs,
        timeout_s=timeout_s,
        max_concurrency=max_concurrency,
    )


def successful_bot_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only successful bot outputs suitable for synthesis."""
    return [result for result in results if result.get("status") == "ok"]


async def synthesize_bot_results(
    config: Config,
    user_message: str,
    results: list[dict[str, Any]],
) -> str:
    """Combine multiple bot outputs into one orchestrated response."""
    successful = successful_bot_results(results)
    if not successful:
        return ""
    if len(successful) == 1:
        return str(successful[0].get("content", "") or "")

    provider = make_provider(config, Console())
    compiled = "\n\n".join(
        f"## {item['name']} ({item['id']})\n{item['content']}"
        for item in successful
    )
    response = await provider.chat_with_retry(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a team orchestrator. Merge specialist bot outputs into one final answer. "
                    "Keep the response actionable, note important disagreements briefly, and avoid mentioning "
                    "internal implementation details unless they materially affect the answer."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User request:\n{user_message}\n\n"
                    f"Specialist bot outputs:\n{compiled}\n\n"
                    "Produce one synthesized final response."
                ),
            },
        ],
        model=config.agents.defaults.model,
    )
    return response.content or ""
