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

EXECUTION_POLICY_PRESETS: dict[str, dict[str, int | float | bool]] = {
    "default": {},
    "fast": {
        "timeout": 20.0,
        "max_concurrency": 8,
        "retries": 0,
    },
    "balanced": {
        "timeout": 45.0,
        "max_concurrency": 4,
        "min_successful_bots": 1,
        "retries": 1,
    },
    "strict": {
        "timeout": 60.0,
        "max_concurrency": 3,
        "min_successful_bots": 2,
        "require_all_success": True,
        "retries": 2,
    },
}
SELECTION_STRATEGIES = {"all", "best_match", "top_k"}


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


def resolve_execution_policy(
    ctx: BotCliContext,
    *,
    policy: str | None,
    timeout: float | None,
    max_concurrency: int | None,
    retries: int,
    min_successful_bots: int,
    require_all_success: bool,
) -> dict[str, float | int | bool]:
    """Resolve orchestration runtime options from a named policy plus explicit flags."""
    key = (policy or "default").strip().lower()
    preset = EXECUTION_POLICY_PRESETS.get(key)
    if preset is None:
        choices = ", ".join(sorted(EXECUTION_POLICY_PRESETS.keys()))
        ctx.console.print(f"[red]Unknown execution policy:[/red] {policy}. Choose one of: {choices}")
        raise typer.Exit(1)

    timeout_value = timeout if timeout is not None else preset.get("timeout")
    max_concurrency_value = max_concurrency if max_concurrency is not None else preset.get("max_concurrency")
    retries_value = retries if retries != 0 else int(preset.get("retries", 0))
    min_successful_bots_value = (
        min_successful_bots
        if min_successful_bots != 1
        else int(preset.get("min_successful_bots", min_successful_bots))
    )
    require_all_success_value = (
        require_all_success
        if require_all_success
        else bool(preset.get("require_all_success", False))
    )

    return {
        "policy": key,
        "timeout": timeout_value,
        "max_concurrency": max_concurrency_value,
        "retries": retries_value,
        "min_successful_bots": min_successful_bots_value,
        "require_all_success": require_all_success_value,
    }


def apply_selection_strategy(
    ctx: BotCliContext,
    bots: list[dict[str, Any]],
    *,
    strategy: str | None,
    message: str,
    strategy_k: int | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Order selected bots according to the requested orchestration strategy."""
    key = (strategy or "all").strip().lower()
    if key not in SELECTION_STRATEGIES:
        choices = ", ".join(sorted(SELECTION_STRATEGIES))
        ctx.console.print(f"[red]Unknown selection strategy:[/red] {strategy}. Choose one of: {choices}")
        raise typer.Exit(1)
    if key == "all" or not bots:
        if strategy_k is not None:
            ctx.console.print("[red]--strategy-k can only be used with --strategy top_k.[/red]")
            raise typer.Exit(1)
        return bots, key

    terms = [part for part in message.lower().split() if part]

    def _score(bot: dict[str, Any]) -> int:
        searchable = " ".join(
            [
                str(bot.get("name", "")),
                str(bot.get("role", "")),
                str(bot.get("description", "")),
                " ".join(str(item) for item in (bot.get("tags") or [])),
                " ".join(str(item) for item in (bot.get("skills") or [])),
                " ".join(str(item) for item in (bot.get("custom_skills") or [])),
            ]
        ).lower()
        return sum(1 for term in terms if term in searchable)

    ordered = sorted(
        enumerate(bots),
        key=lambda pair: (_score(pair[1]), -pair[0]),
        reverse=True,
    )
    ranked = [bot for _, bot in ordered]
    if key == "top_k":
        if strategy_k is None:
            strategy_k = 1
        if strategy_k < 1:
            ctx.console.print("[red]--strategy-k must be >= 1.[/red]")
            raise typer.Exit(1)
        return ranked[:strategy_k], key

    if strategy_k is not None:
        ctx.console.print("[red]--strategy-k can only be used with --strategy top_k.[/red]")
        raise typer.Exit(1)
    return ranked, key


def normalize_run_label(
    ctx: BotCliContext,
    run_label: str | None,
) -> str | None:
    """Normalize optional run labels and reject empty labels."""
    if run_label is None:
        return None
    label = run_label.strip()
    if not label:
        ctx.console.print("[red]Invalid run label:[/red] provide a non-empty value.")
        raise typer.Exit(1)
    return label


async def run_bot_fanout(
    ctx: BotCliContext,
    bots: list[dict[str, Any]],
    *,
    message: str,
    session_prefix: str,
    logs: bool = False,
    timeout_s: float | None = None,
    max_concurrency: int | None = None,
    retries: int = 0,
) -> list[dict[str, Any]]:
    """Execute one message across a selected bot set."""
    return await ctx.run_bots_for_message(
        bots,
        message=message,
        session_prefix=session_prefix,
        logs=logs,
        timeout_s=timeout_s,
        max_concurrency=max_concurrency,
        retries=retries,
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
    retries: int = 0,
    synthesize: bool = True,
    min_successful_bots: int = 1,
    fallback_bot_id: str | None = None,
    config: str | None = None,
) -> tuple[list[dict[str, Any]], str, str | None, str | None]:
    """Execute selected bots and optionally synthesize a final response."""
    results = await run_bot_fanout(
        ctx,
        bots,
        message=message,
        session_prefix=session_prefix,
        logs=logs,
        timeout_s=timeout_s,
        max_concurrency=max_concurrency,
        retries=retries,
    )
    if not synthesize:
        return results, "", None, None

    successful = successful_bot_results(results)
    if len(successful) < min_successful_bots:
        reason = f"Need at least {min_successful_bots} successful bot(s) before synthesis; got {len(successful)}."
        if not fallback_bot_id:
            return results, "", reason, None

        fallback_bot = next((bot for bot in bots if str(bot.get("id")) == fallback_bot_id), None)
        if not fallback_bot:
            return results, "", f"{reason} Fallback bot `{fallback_bot_id}` was not selected.", None

        fallback_results = await run_bot_fanout(
            ctx,
            [fallback_bot],
            message=message,
            session_prefix=f"{session_prefix}:fallback",
            logs=logs,
            timeout_s=timeout_s,
            max_concurrency=max_concurrency,
            retries=retries,
        )
        fallback = fallback_results[0]
        combined = [*results, fallback]
        if fallback.get("status") != "ok":
            fallback_error = fallback.get("error") or "unknown fallback error"
            return combined, "", f"{reason} Fallback bot `{fallback_bot_id}` failed: {fallback_error}", None
        return combined, str(fallback.get("content") or ""), None, fallback_bot_id

    orchestrator_config = ctx.load_runtime_config(config=config, announce=False)
    synthesis = await ctx.synthesize_bot_results(orchestrator_config, message, successful)
    return results, synthesis, None, None




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
