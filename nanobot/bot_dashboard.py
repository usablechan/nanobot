"""Bot runtime summaries and static dashboard rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nanobot.bot_core import get_bot_dashboards_dir
from nanobot.bot_dashboard_html import render_dashboard_html
from nanobot.bot_team import list_bots
from nanobot.session.manager import SessionManager


def bot_runtime_summary(bot: dict[str, Any]) -> dict[str, Any]:
    """Collect a lightweight dashboard summary for one bot."""
    workspace = Path(str(bot["workspace"]))
    sessions = SessionManager(workspace).list_sessions()
    skill_dir = workspace / "skills"
    memory_path = workspace / "memory" / "MEMORY.md"
    history_path = workspace / "memory" / "HISTORY.md"

    memory_excerpt = ""
    if memory_path.exists():
        text = memory_path.read_text(encoding="utf-8").strip()
        memory_excerpt = text[:220] + ("..." if len(text) > 220 else "")

    history_entries = 0
    if history_path.exists():
        history_entries = sum(
            1
            for line in history_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("[")
        )

    return {
        **bot,
        "workspace_exists": workspace.exists(),
        "session_count": len(sessions),
        "last_session_at": sessions[0]["updated_at"] if sessions else None,
        "skills_dir_count": len([p for p in skill_dir.iterdir() if p.is_dir()]) if skill_dir.exists() else 0,
        "memory_excerpt": memory_excerpt,
        "history_entries": history_entries,
        "skill_summary": ", ".join(bot.get("skills", [])) or "none",
        "custom_skill_summary": ", ".join(bot.get("custom_skills", [])) or "none",
    }


def render_dashboard(output: Path | None = None) -> Path:
    """Generate a static HTML dashboard for all bots."""
    summaries = [bot_runtime_summary(bot) for bot in list_bots()]
    out = output or (get_bot_dashboards_dir() / "index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_dashboard_html(summaries), encoding="utf-8")
    return out


<<<<<<< ours
def serve_dashboard(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve an interactive bot dashboard with CRUD APIs."""
    from nanobot.bot_dashboard_web import serve_dashboard_web

    serve_dashboard_web(host=host, port=port)


__all__ = [
    "bot_runtime_summary",
    "render_dashboard",
    "serve_dashboard",
=======
__all__ = [
    "bot_runtime_summary",
    "render_dashboard",
>>>>>>> theirs
]
