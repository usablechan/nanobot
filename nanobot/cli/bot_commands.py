"""Bot/team CLI command group extraction for the main Typer app."""

from __future__ import annotations

import typer

from nanobot.cli.bot_cli_bots import register_bot_commands
from nanobot.cli.bot_cli_shared import BotCliContext
from nanobot.cli.bot_cli_teams import register_team_commands


def create_bots_app(**kwargs) -> typer.Typer:
    """Build the `nanobot bots` CLI tree."""
    ctx = BotCliContext(**kwargs)
    bots_app = typer.Typer(help="Manage isolated specialist bots")
    team_app = typer.Typer(help="Manage saved bot teams")
    bots_app.add_typer(team_app, name="team")

    register_bot_commands(bots_app, ctx)
    register_team_commands(team_app, ctx)
    return bots_app
