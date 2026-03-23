"""Registration helpers for `nanobot bots` commands."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.table import Table

from nanobot.bots import (
    _UNSET,
    bot_runtime_summary,
    create_bot,
    delete_bot,
    get_bot,
    list_bots,
    render_dashboard,
    select_bots,
    update_bot,
)
from nanobot.cli.bot_cli_shared import (
    BotCliContext,
    enforce_all_success,
    enforce_synthesis_quorum,
    render_bot_results,
    run_bot_fanout,
    run_bot_orchestration,
    summarize_bot_results,
    write_json_artifact,
)


def register_bot_commands(bots_app: typer.Typer, ctx: BotCliContext) -> None:
    """Register bot-focused commands on the provided Typer app."""

    @bots_app.command("create")
    def bots_create(
        name: str = typer.Argument(..., help="Display name for the specialist bot"),
        role: str = typer.Option(..., "--role", help="Primary responsibility for the bot"),
        description: str = typer.Option("", "--description", help="Short mission/behavior summary"),
        model: str | None = typer.Option(None, "--model", help="Optional model override"),
        provider: str | None = typer.Option(None, "--provider", help="Optional provider override for the bot config"),
        workspace: str | None = typer.Option(None, "--workspace", help="Custom workspace path"),
        tag: list[str] | None = typer.Option(None, "--tag", help="Tag(s) for grouping; repeat or use CSV"),
        skill: list[str] | None = typer.Option(None, "--skill", help="Associated skill names; repeat or use CSV"),
        custom_skill: list[str] | None = typer.Option(None, "--custom-skill", help="Create stub custom skill(s); repeat or use CSV"),
        memory_seed: str = typer.Option("", "--memory-seed", help="Seed notes written into MEMORY.md"),
        force: bool = typer.Option(False, "--force", help="Reuse a non-empty workspace and overwrite seeded files"),
    ):
        """Create a new isolated bot workspace + config."""
        try:
            entry = create_bot(
                name=name,
                role=role,
                description=description,
                model=model,
                provider=provider,
                workspace=workspace,
                tags=tag or [],
                skills=skill or [],
                custom_skills=custom_skill or [],
                memory_seed=memory_seed,
                force=force,
            )
        except ValueError as exc:
            ctx.console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        ctx.console.print(f"[green]Created bot:[/green] {entry['name']} ({entry['id']})")
        ctx.console.print(f"Workspace: {entry['workspace']}")
        ctx.console.print(f"Config: {entry['config_path']}")
        ctx.console.print(f"Associated skills: {', '.join(entry.get('skills', [])) or 'none'}")
        if entry.get("created_skill_stubs"):
            ctx.console.print(f"Custom skill stubs: {', '.join(entry['created_skill_stubs'])}")
        ctx.console.print(
            "Run locally with: "
            f"[cyan]nanobot agent --config {entry['config_path']} -m \"Hello\"[/cyan]"
        )

    @bots_app.command("list")
    def bots_list(
        as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a rich table"),
    ):
        """List all registered bots."""
        summaries = [bot_runtime_summary(bot) for bot in list_bots()]
        if as_json:
            ctx.console.print_json(json.dumps(summaries, ensure_ascii=False, indent=2))
            return

        table = Table(title="Bot Team")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Role", style="magenta")
        table.add_column("Sessions", justify="right")
        table.add_column("Skills", justify="right")
        table.add_column("Last Session", style="yellow")

        for bot in summaries:
            table.add_row(
                str(bot["id"]),
                str(bot["name"]),
                str(bot["role"]),
                str(bot["session_count"]),
                str(bot["skills_dir_count"]),
                str(bot.get("last_session_at") or "never"),
            )

        ctx.console.print(table)

    @bots_app.command("show")
    def bots_show(
        bot_id: str = typer.Argument(..., help="Bot id from `nanobot bots list`"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of markdown-like output"),
    ):
        """Show one bot's config and runtime summary."""
        bot = get_bot(bot_id)
        if not bot:
            ctx.console.print(f"[red]Unknown bot:[/red] {bot_id}")
            raise typer.Exit(1)

        summary = bot_runtime_summary(bot)
        if as_json:
            ctx.console.print_json(json.dumps(summary, ensure_ascii=False, indent=2))
            return

        ctx.console.print(f"[bold cyan]{summary['name']}[/bold cyan] ({summary['id']})")
        ctx.console.print(f"Role: {summary['role']}")
        ctx.console.print(f"Description: {summary.get('description') or 'No description yet.'}")
        ctx.console.print(f"Workspace: {summary['workspace']}")
        ctx.console.print(f"Config: {summary['config_path']}")
        ctx.console.print(f"Model: {summary['model']}")
        ctx.console.print(f"Provider: {summary['provider']}")
        ctx.console.print(f"Tags: {', '.join(summary.get('tags', [])) or 'none'}")
        ctx.console.print(f"Associated skills: {summary.get('skill_summary') or 'none'}")
        ctx.console.print(f"Custom skills: {summary.get('custom_skill_summary') or 'none'}")
        ctx.console.print(f"Sessions: {summary['session_count']}")
        ctx.console.print(f"Custom skill dirs: {summary['skills_dir_count']}")
        ctx.console.print(f"History entries: {summary['history_entries']}")
        ctx.console.print(f"Last session: {summary.get('last_session_at') or 'never'}")
        ctx.console.print("\n[bold]Memory Snapshot[/bold]")
        ctx.console.print(summary.get("memory_excerpt") or "No memory yet.")

    @bots_app.command("dashboard")
    def bots_dashboard(
        output: str | None = typer.Option(None, "--output", "-o", help="Write dashboard HTML to this file"),
    ):
        """Generate a static HTML dashboard for the current bot registry."""
        out = render_dashboard(Path(output).expanduser() if output else None)
        ctx.console.print(f"[green]Dashboard written:[/green] {out}")

    @bots_app.command("delete")
    def bots_delete(
        bot_id: str = typer.Argument(..., help="Bot id from `nanobot bots list`"),
        purge_files: bool = typer.Option(False, "--purge-files", help="Also delete the bot workspace and generated config"),
        force: bool = typer.Option(False, "--force", help="Delete even if referenced by a saved team"),
    ):
        """Delete a registered bot."""
        try:
            removed = delete_bot(bot_id, purge_files=purge_files, force=force)
        except ValueError as exc:
            ctx.console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        ctx.console.print(f"[green]Deleted bot:[/green] {removed['name']} ({removed['id']})")
        if purge_files:
            ctx.console.print("[dim]Removed generated workspace/config files.[/dim]")

    @bots_app.command("update")
    def bots_update(
        bot_id: str = typer.Argument(..., help="Bot id from `nanobot bots list`"),
        name: str | None = typer.Option(None, "--name", help="Update display name"),
        role: str | None = typer.Option(None, "--role", help="Update primary role"),
        description: str | None = typer.Option(None, "--description", help="Update description"),
        model: str | None = typer.Option(None, "--model", help="Update model"),
        provider: str | None = typer.Option(None, "--provider", help="Update provider"),
        tag: list[str] | None = typer.Option(None, "--tag", help="Replace tags; repeat or use CSV"),
        skill: list[str] | None = typer.Option(None, "--skill", help="Replace associated skills; repeat or use CSV"),
        custom_skill: list[str] | None = typer.Option(None, "--custom-skill", help="Replace custom skills; repeat or use CSV"),
        rewrite_files: bool = typer.Option(False, "--rewrite-files", help="Rewrite AGENTS/SOUL/USER (and MEMORY when --memory-seed is set)"),
        memory_seed: str | None = typer.Option(None, "--memory-seed", help="Optional new seed notes when rewriting memory"),
    ):
        """Update bot registry/config metadata."""
        try:
            updated = update_bot(
                bot_id,
                name=name,
                role=role,
                description=description,
                model=model,
                provider=provider,
                tags=tag if tag is not None else _UNSET,
                skills=skill if skill is not None else _UNSET,
                custom_skills=custom_skill if custom_skill is not None else _UNSET,
                rewrite_files=rewrite_files,
                memory_seed=memory_seed,
            )
        except ValueError as exc:
            ctx.console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        ctx.console.print(f"[green]Updated bot:[/green] {updated['name']} ({updated['id']})")

    @bots_app.command("run")
    def bots_run(
        bot_id: str = typer.Argument(..., help="Bot id from `nanobot bots list`"),
        message: str = typer.Option(..., "--message", "-m", help="Message to send to the selected bot"),
        session_id: str | None = typer.Option(None, "--session", "-s", help="Optional session id override"),
        markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
        logs: bool = typer.Option(False, "--logs/--no-logs", help="Show nanobot runtime logs during execution"),
    ):
        """Run one registered bot directly against a message."""
        bot = get_bot(bot_id)
        if not bot:
            ctx.console.print(f"[red]Unknown bot:[/red] {bot_id}")
            raise typer.Exit(1)

        resolved_session = session_id or f"cli:{bot_id}"
        bot_config = ctx.load_runtime_config(config=bot["config_path"], announce=False)

        async def run_once():
            response = await ctx.run_agent_once(
                bot_config,
                message,
                resolved_session,
                logs=logs,
            )
            ctx.console.print(f"[bold cyan]{bot['name']}[/bold cyan] [{resolved_session}]")
            ctx.print_agent_response(
                response.content if response else "",
                render_markdown=markdown,
                metadata=response.metadata if response else None,
            )

        asyncio.run(run_once())

    @bots_app.command("compare")
    def bots_compare(
        bot_ids: list[str] = typer.Argument(..., help="Two or more bot ids to compare"),
        message: str = typer.Option(..., "--message", "-m", help="Message to send to every selected bot"),
        session_prefix: str = typer.Option("cli:compare", "--session-prefix", help="Session prefix used per bot"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of rich text"),
        markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
        logs: bool = typer.Option(False, "--logs/--no-logs", help="Show nanobot runtime logs during execution"),
        timeout: float | None = typer.Option(None, "--timeout", min=0.1, help="Per-bot timeout in seconds"),
        max_concurrency: int | None = typer.Option(None, "--max-concurrency", min=1, help="Maximum number of bot runs to execute concurrently"),
        require_all_success: bool = typer.Option(False, "--require-all-success", help="Exit non-zero if any selected bot errors or times out"),
        output_json: str | None = typer.Option(None, "--output-json", help="Write structured JSON output to this file"),
    ):
        """Run the same message across multiple bots and compare outputs."""
        selected = select_bots(bot_ids=bot_ids)
        missing = [bot_id for bot_id in bot_ids if get_bot(bot_id) is None]
        if missing:
            ctx.console.print(f"[red]Unknown bot id(s):[/red] {', '.join(missing)}")
            raise typer.Exit(1)
        results = asyncio.run(
            run_bot_fanout(
                ctx,
                selected,
                message=message,
                session_prefix=session_prefix,
                logs=logs,
                timeout_s=timeout,
                max_concurrency=max_concurrency,
            )
        )
        summary = summarize_bot_results(results)
        write_json_artifact(ctx, results, output_json, announce=not as_json)
        if as_json:
            ctx.console.print_json(json.dumps(results, ensure_ascii=False, indent=2))
            enforce_all_success(ctx, summary, require_all_success=require_all_success, quiet=True)
            return

        render_bot_results(ctx, results, markdown)
        enforce_all_success(ctx, summary, require_all_success=require_all_success)

    @bots_app.command("dispatch")
    def bots_dispatch(
        message: str = typer.Option(..., "--message", "-m", help="Message to send to the selected team"),
        bot: list[str] | None = typer.Option(None, "--bot", help="Explicit bot id(s); repeat or use CSV"),
        tag: list[str] | None = typer.Option(None, "--tag", help="Require bot tag(s); repeat or use CSV"),
        skill: list[str] | None = typer.Option(None, "--skill", help="Require associated/custom skill(s); repeat or use CSV"),
        query: str = typer.Option("", "--query", help="Substring match against id/name/role/description"),
        max_bots: int | None = typer.Option(None, "--max-bots", help="Limit how many matched bots to execute"),
        session_prefix: str = typer.Option("cli:dispatch", "--session-prefix", help="Session prefix used per bot"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of rich text"),
        markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
        logs: bool = typer.Option(False, "--logs/--no-logs", help="Show nanobot runtime logs during execution"),
        timeout: float | None = typer.Option(None, "--timeout", min=0.1, help="Per-bot timeout in seconds"),
        max_concurrency: int | None = typer.Option(None, "--max-concurrency", min=1, help="Maximum number of bot runs to execute concurrently"),
        require_all_success: bool = typer.Option(False, "--require-all-success", help="Exit non-zero if any selected bot errors or times out"),
        output_json: str | None = typer.Option(None, "--output-json", help="Write structured JSON output to this file"),
    ):
        """Select bots by metadata filters and fan out one message across the team."""
        selected = select_bots(bot_ids=bot or [], tags=tag or [], skills=skill or [], query=query)
        if max_bots is not None:
            selected = selected[:max_bots]
        if not selected:
            ctx.console.print("[red]No bots matched the provided selection criteria.[/red]")
            raise typer.Exit(1)

        results = asyncio.run(
            run_bot_fanout(
                ctx,
                selected,
                message=message,
                session_prefix=session_prefix,
                logs=logs,
                timeout_s=timeout,
                max_concurrency=max_concurrency,
            )
        )
        summary = summarize_bot_results(results)
        write_json_artifact(ctx, results, output_json, announce=not as_json)
        if as_json:
            ctx.console.print_json(json.dumps(results, ensure_ascii=False, indent=2))
            enforce_all_success(ctx, summary, require_all_success=require_all_success, quiet=True)
            return

        names = ", ".join(result["name"] for result in results)
        ctx.console.print(f"[bold]Dispatched to:[/bold] {names}")
        ctx.console.print()
        render_bot_results(ctx, results, markdown)
        enforce_all_success(ctx, summary, require_all_success=require_all_success)

    @bots_app.command("orchestrate")
    def bots_orchestrate(
        message: str = typer.Option(..., "--message", "-m", help="Message to send to the selected team"),
        bot: list[str] | None = typer.Option(None, "--bot", help="Explicit bot id(s); repeat or use CSV"),
        tag: list[str] | None = typer.Option(None, "--tag", help="Require bot tag(s); repeat or use CSV"),
        skill: list[str] | None = typer.Option(None, "--skill", help="Require associated/custom skill(s); repeat or use CSV"),
        query: str = typer.Option("", "--query", help="Substring match against id/name/role/description"),
        max_bots: int | None = typer.Option(None, "--max-bots", help="Limit how many matched bots to execute"),
        session_prefix: str = typer.Option("cli:orchestrate", "--session-prefix", help="Session prefix used per bot"),
        config: str | None = typer.Option(None, "--config", "-c", help="Optional config used for synthesis"),
        synthesize: bool = typer.Option(True, "--synthesize/--no-synthesize", help="Synthesize a final merged answer"),
        show_raw: bool = typer.Option(False, "--show-raw/--no-show-raw", help="Also print each raw bot response"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of rich text"),
        markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
        logs: bool = typer.Option(False, "--logs/--no-logs", help="Show nanobot runtime logs during execution"),
        timeout: float | None = typer.Option(None, "--timeout", min=0.1, help="Per-bot timeout in seconds"),
        max_concurrency: int | None = typer.Option(None, "--max-concurrency", min=1, help="Maximum number of bot runs to execute concurrently"),
        require_all_success: bool = typer.Option(False, "--require-all-success", help="Exit non-zero if any selected bot errors or times out"),
        min_successful_bots: int = typer.Option(1, "--min-successful-bots", min=1, help="Minimum successful bot runs required before synthesis"),
        output_json: str | None = typer.Option(None, "--output-json", help="Write structured JSON output to this file"),
    ):
        """Dispatch to a selected team and optionally synthesize one final answer."""
        selected = select_bots(bot_ids=bot or [], tags=tag or [], skills=skill or [], query=query)
        if max_bots is not None:
            selected = selected[:max_bots]
        if not selected:
            ctx.console.print("[red]No bots matched the provided selection criteria.[/red]")
            raise typer.Exit(1)

        results, synthesis, synthesis_skipped_reason = asyncio.run(
            run_bot_orchestration(
                ctx,
                selected,
                message=message,
                session_prefix=session_prefix,
                logs=logs,
                timeout_s=timeout,
                max_concurrency=max_concurrency,
                synthesize=synthesize,
                min_successful_bots=min_successful_bots,
                config=config,
            )
        )
        summary = summarize_bot_results(results)
        payload = {
            "selected_ids": [item["id"] for item in results],
            "summary": summary,
            "synthesis": synthesis,
            "synthesis_skipped_reason": synthesis_skipped_reason,
            "results": results,
        }
        write_json_artifact(ctx, payload, output_json, announce=not as_json)
        if as_json:
            ctx.console.print_json(json.dumps(payload, ensure_ascii=False, indent=2))
            enforce_all_success(ctx, summary, require_all_success=require_all_success, quiet=True)
            enforce_synthesis_quorum(
                ctx,
                synthesis_skipped_reason=synthesis_skipped_reason,
                quiet=True,
            )
            return

        ctx.console.print(f"[bold]Selected bots:[/bold] {', '.join(item['name'] for item in results)}")
        ctx.console.print(
            f"[dim]Summary:[/dim] ok={summary['ok']} timeout={summary['timeout']} error={summary['error']} total={summary['total']}"
        )
        if synthesis:
            ctx.console.rule("[green]Final Synthesis[/green]")
            body = ctx.response_renderable(synthesis, markdown, None)
            ctx.console.print(body)
            ctx.console.print()
        elif synthesis_skipped_reason:
            ctx.console.print(f"[yellow]Synthesis skipped:[/yellow] {synthesis_skipped_reason}")
            ctx.console.print()

        if show_raw or not synthesis:
            render_bot_results(ctx, results, markdown)
        enforce_all_success(ctx, summary, require_all_success=require_all_success)
        enforce_synthesis_quorum(ctx, synthesis_skipped_reason=synthesis_skipped_reason)
