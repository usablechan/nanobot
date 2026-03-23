"""Shared context and helpers for extracted bot/team CLI modules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Coroutine

import typer
from rich.console import Console

from nanobot.cli.runtime_support import successful_bot_results

RunAgentOnce = Callable[..., Coroutine[Any, Any, Any]]
RunBotsForMessage = Callable[..., Coroutine[Any, Any, list[dict[str, Any]]]]
SynthesizeBotResults = Callable[[Any, str, list[dict[str, Any]]], Coroutine[Any, Any, str]]
LoadRuntimeConfig = Callable[..., Any]
ResponseRenderable = Callable[[str, bool, dict | None], Any]
PrintAgentResponse = Callable[[str, bool, dict | None], None]


@dataclass(frozen=True)
class BotCliContext:
    """Runtime dependencies shared by bot/team command registrars."""

    console: Console
    load_runtime_config: LoadRuntimeConfig
    run_agent_once: RunAgentOnce
    run_bots_for_message: RunBotsForMessage
    synthesize_bot_results: SynthesizeBotResults
    response_renderable: ResponseRenderable
    print_agent_response: PrintAgentResponse


async def run_bot_fanout(
    ctx: BotCliContext,
    bots: list[dict[str, Any]],
    *,
    message: str,
    session_prefix: str,
    logs: bool = False,
    timeout_s: float | None = None,
    max_concurrency: int | None = None,
) -> list[dict[str, Any]]:
    """Execute one message across a selected bot set."""
    return await ctx.run_bots_for_message(
        bots,
        message=message,
        session_prefix=session_prefix,
        logs=logs,
        timeout_s=timeout_s,
        max_concurrency=max_concurrency,
    )


async def run_bot_orchestration(
    ctx: BotCliContext,
    bots: list[dict[str, Any]],
    *,
    message: str,
    session_prefix: str,
    logs: bool = False,
    timeout_s: float | None = None,
    max_concurrency: int | None = None,
    synthesize: bool = True,
    min_successful_bots: int = 1,
    config: str | None = None,
) -> tuple[list[dict[str, Any]], str, str | None]:
    """Execute selected bots and optionally synthesize a final response."""
    results = await run_bot_fanout(
        ctx,
        bots,
        message=message,
        session_prefix=session_prefix,
        logs=logs,
        timeout_s=timeout_s,
        max_concurrency=max_concurrency,
    )
    if not synthesize:
        return results, "", None

    successful = successful_bot_results(results)
    if len(successful) < min_successful_bots:
        return results, "", (
            f"Need at least {min_successful_bots} successful bot(s) before synthesis; got {len(successful)}."
        )

    orchestrator_config = ctx.load_runtime_config(config=config, announce=False)
    synthesis = await ctx.synthesize_bot_results(orchestrator_config, message, successful)
    return results, synthesis, None




def summarize_bot_results(results: list[dict[str, Any]]) -> dict[str, int]:
    """Summarize multi-bot execution counts by status."""
    summary = {"total": len(results), "ok": 0, "error": 0, "timeout": 0}
    for result in results:
        status = str(result.get("status") or "error")
        summary[status] = summary.get(status, 0) + 1
    return summary




def enforce_all_success(
    ctx: BotCliContext,
    summary: dict[str, int],
    *,
    require_all_success: bool,
    quiet: bool = False,
) -> None:
    """Exit non-zero when the caller requires every selected bot to succeed."""
    if not require_all_success:
        return
    if summary.get("ok", 0) == summary.get("total", 0):
        return
    if not quiet:
        ctx.console.print(
            f"[red]Command failed:[/red] ok={summary['ok']} timeout={summary['timeout']} error={summary['error']} total={summary['total']}"
        )
    raise typer.Exit(1)




def enforce_synthesis_quorum(
    ctx: BotCliContext,
    *,
    synthesis_skipped_reason: str | None,
    quiet: bool = False,
) -> None:
    """Exit non-zero when synthesis was requested but quorum requirements were not met."""
    if not synthesis_skipped_reason:
        return
    if not quiet:
        ctx.console.print(f"[yellow]Synthesis skipped:[/yellow] {synthesis_skipped_reason}")
    raise typer.Exit(1)




def write_json_artifact(
    ctx: BotCliContext,
    payload: Any,
    output_json: str | None,
    *,
    announce: bool = True,
) -> Path | None:
    """Persist structured bot command output when requested."""
    if not output_json:
        return None
    path = Path(output_json).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if announce:
        ctx.console.print(f"[dim]Saved JSON artifact:[/dim] {path}")
    return path


def render_bot_results(ctx: BotCliContext, results: list[dict[str, Any]], markdown: bool) -> None:
    """Render a consistent rich-text section for each bot result."""
    for result in results:
        ctx.console.rule(f"[cyan]{result['name']}[/cyan] ({result['session_id']})")
        if result.get("status") == "timeout":
            ctx.console.print(f"[yellow]Timeout:[/yellow] {result.get('error') or 'Bot execution timed out.'}")
        elif result.get("status") == "error":
            ctx.console.print(f"[red]Error:[/red] {result.get('error') or 'Unknown bot execution failure.'}")
        else:
            body = ctx.response_renderable(result["content"], markdown, result.get("metadata"))
            ctx.console.print(body)
        if result.get("elapsed_ms") is not None:
            ctx.console.print(f"[dim]Elapsed:[/dim] {result['elapsed_ms']}ms")
        ctx.console.print()
