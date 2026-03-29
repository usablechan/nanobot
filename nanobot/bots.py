"""Public bot/team management API."""

from nanobot.bot_core import (
    _UNSET,
    get_bot_configs_dir,
    get_bot_dashboards_dir,
    get_bot_workspaces_dir,
    get_bots_dir,
    get_registry_path,
    load_registry,
    save_registry,
    slugify,
)
<<<<<<< ours
from nanobot.bot_dashboard import bot_runtime_summary, render_dashboard, serve_dashboard
=======
from nanobot.bot_dashboard import bot_runtime_summary, render_dashboard
>>>>>>> theirs
from nanobot.bot_directory import get_bot, get_team, list_bots, list_teams, select_bots
from nanobot.bot_team import create_team, delete_team, resolve_team_bots, update_team
from nanobot.bot_workspace import create_bot, delete_bot, update_bot

__all__ = [
    "_UNSET",
    "bot_runtime_summary",
    "create_bot",
    "create_team",
    "delete_bot",
    "delete_team",
    "get_bot",
    "get_bot_configs_dir",
    "get_bot_dashboards_dir",
    "get_bot_workspaces_dir",
    "get_bots_dir",
    "get_registry_path",
    "get_team",
    "list_bots",
    "list_teams",
    "load_registry",
    "render_dashboard",
    "resolve_team_bots",
    "save_registry",
    "select_bots",
    "slugify",
<<<<<<< ours
    "serve_dashboard",
=======
>>>>>>> theirs
    "update_bot",
    "update_team",
]
