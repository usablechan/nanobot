"""Registration helpers for `nanobot bots team` commands."""

from __future__ import annotations

import asyncio
import json

import typer
from rich.table import Table

from nanobot.bots import (
    _UNSET,
    create_team,
    delete_team,
    get_team,
    list_teams,
    resolve_team_bots,
    update_team,
)
from nanobot.cli.bot_cli_shared import (
    BotCliContext,
    enforce_all_success,
    enforce_synthesis_quorum,
    render_bot_results,
    run_bot_orchestration,
    summarize_bot_results,
    write_json_artifact,
)


def register_team_commands(team_app: typer.Typer, ctx: BotCliContext) -> None:
    """Register team-focused commands on the provided Typer app."""

    @team_app.command("create")
    def team_create(
        name: str = typer.Argument(..., help="Display name for the saved team"),
        description: str = typer.Option("", "--description", help="Short description of the team"),
        bot: list[str] | None = typer.Option(None, "--bot", help="Explicit bot id(s); repeat or use CSV"),
        tag: list[str] | None = typer.Option(None, "--tag", help="Require bot tag(s); repeat or use CSV"),
        skill: list[str] | None = typer.Option(None, "--skill", help="Require associated/custom skill(s); repeat or use CSV"),
        query: str = typer.Option("", "--query", help="Substring match against id/name/role/description"),
        max_bots: int | None = typer.Option(None, "--max-bots", help="Limit how many matched bots to execute"),
    ):
        """Create a reusable saved team definition."""
        try:
            entry = create_team(
                name=name,
                description=description,
                bot_ids=bot or [],
                tags=tag or [],
                skills=skill or [],
                query=query,
                max_bots=max_bots,
            )
        except ValueError as exc:
            ctx.console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        preview = resolve_team_bots(entry)
        ctx.console.print(f"[green]Created team:[/green] {entry['name']} ({entry['id']})")
        ctx.console.print(f"Preview bots: {', '.join(bot['name'] for bot in preview) or 'none'}")

    @team_app.command("list")
    def team_list(
        as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a rich table"),
    ):
        """List saved team definitions."""
        teams = list_teams()
        if as_json:
            ctx.console.print_json(json.dumps(teams, ensure_ascii=False, indent=2))
            return

        table = Table(title="Saved Bot Teams")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Selectors", style="magenta")
        table.add_column("Preview", style="yellow")

        for team in teams:
            selectors = []
            if team.get("bot_ids"):
                selectors.append(f"bot:{len(team['bot_ids'])}")
            if team.get("tags"):
                selectors.append(f"tag:{','.join(team['tags'])}")
            if team.get("skills"):
                selectors.append(f"skill:{','.join(team['skills'])}")
            if team.get("query"):
                selectors.append(f"query:{team['query']}")
            table.add_row(
                str(team["id"]),
                str(team["name"]),
                " | ".join(selectors) or "none",
                ", ".join(team.get("preview_bot_ids", [])) or "none",
            )

        ctx.console.print(table)

    @team_app.command("show")
    def team_show(
        team_id: str = typer.Argument(..., help="Saved team id from `nanobot bots team list`"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of text"),
    ):
        """Show one saved team definition and current resolved bots."""
        team = get_team(team_id)
        if not team:
            ctx.console.print(f"[red]Unknown team:[/red] {team_id}")
            raise typer.Exit(1)

        resolved = resolve_team_bots(team)
        payload = {**team, "resolved_bot_ids": [bot["id"] for bot in resolved]}
        if as_json:
            ctx.console.print_json(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        ctx.console.print(f"[bold cyan]{team['name']}[/bold cyan] ({team['id']})")
        ctx.console.print(f"Description: {team.get('description') or 'No description yet.'}")
        ctx.console.print(f"Explicit bots: {', '.join(team.get('bot_ids', [])) or 'none'}")
        ctx.console.print(f"Tags: {', '.join(team.get('tags', [])) or 'none'}")
        ctx.console.print(f"Skills: {', '.join(team.get('skills', [])) or 'none'}")
        ctx.console.print(f"Query: {team.get('query') or 'none'}")
        ctx.console.print(f"Max bots: {team.get('max_bots') if team.get('max_bots') is not None else 'none'}")
        ctx.console.print(f"Resolved bots: {', '.join(bot['id'] for bot in resolved) or 'none'}")

    @team_app.command("delete")
    def team_delete(
        team_id: str = typer.Argument(..., help="Saved team id from `nanobot bots team list`"),
    ):
        """Delete a saved team definition."""
        try:
            removed = delete_team(team_id)
        except ValueError as exc:
            ctx.console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        ctx.console.print(f"[green]Deleted team:[/green] {removed['name']} ({removed['id']})")

    @team_app.command("update")
    def team_update(
        team_id: str = typer.Argument(..., help="Saved team id from `nanobot bots team list`"),
        description: str | None = typer.Option(None, "--description", help="Update team description"),
        bot: list[str] | None = typer.Option(None, "--bot", help="Replace explicit bot id(s); repeat or use CSV"),
        tag: list[str] | None = typer.Option(None, "--tag", help="Replace tag selector(s); repeat or use CSV"),
        skill: list[str] | None = typer.Option(None, "--skill", help="Replace skill selector(s); repeat or use CSV"),
        query: str | None = typer.Option(None, "--query", help="Replace substring query; pass empty string to clear"),
        max_bots: int | None = typer.Option(None, "--max-bots", help="Replace max bot limit"),
        clear_max_bots: bool = typer.Option(False, "--clear-max-bots", help="Remove any saved max bot limit"),
    ):
        """Update a saved team definition."""
        if clear_max_bots and max_bots is not None:
            ctx.console.print("[red]Choose either --max-bots or --clear-max-bots, not both.[/red]")
            raise typer.Exit(1)

        try:
            updated = update_team(
                team_id,
                description=description,
                bot_ids=bot if bot is not None else _UNSET,
                tags=tag if tag is not None else _UNSET,
                skills=skill if skill is not None else _UNSET,
                query=query if query is not None else _UNSET,
                max_bots=None if clear_max_bots else (max_bots if max_bots is not None else _UNSET),
            )
        except ValueError as exc:
            ctx.console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        ctx.console.print(f"[green]Updated team:[/green] {updated['name']} ({updated['id']})")

    @team_app.command("run")
    def team_run(
        team_id: str = typer.Argument(..., help="Saved team id from `nanobot bots team list`"),
        message: str = typer.Option(..., "--message", "-m", help="Message to send to the saved team"),
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
        """Run one saved team definition."""
        team = get_team(team_id)
        if not team:
            ctx.console.print(f"[red]Unknown team:[/red] {team_id}")
            raise typer.Exit(1)
        selected = resolve_team_bots(team)
        if not selected:
            ctx.console.print("[red]This team currently resolves to zero bots.[/red]")
            raise typer.Exit(1)

        results, synthesis, synthesis_skipped_reason = asyncio.run(
            run_bot_orchestration(
                ctx,
                selected,
                message=message,
                session_prefix=f"cli:team:{team_id}",
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
            "team_id": team_id,
            "team_name": team["name"],
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

        ctx.console.print(f"[bold]Team:[/bold] {team['name']}")
        ctx.console.print(
            f"[dim]Summary:[/dim] ok={summary['ok']} timeout={summary['timeout']} error={summary['error']} total={summary['total']}"
        )
        ctx.console.print(f"[bold]Selected bots:[/bold] {', '.join(item['name'] for item in results)}")
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
