"""Read-only lookup and selection helpers for bots and teams."""

from __future__ import annotations

from typing import Any

from nanobot.bot_core import _normalize_items, load_registry


def list_bots() -> list[dict[str, Any]]:
    """Return all registered bots sorted by name."""
    registry = load_registry()
    bots = registry.get("bots", [])
    return sorted((b for b in bots if isinstance(b, dict)), key=lambda item: item.get("name", ""))


def get_bot(bot_id: str) -> dict[str, Any] | None:
    """Look up a bot by id."""
    for bot in list_bots():
        if bot.get("id") == bot_id:
            return bot
    return None


def list_teams() -> list[dict[str, Any]]:
    """Return all saved teams sorted by name."""
    registry = load_registry()
    teams = registry.get("teams", [])
    return sorted((t for t in teams if isinstance(t, dict)), key=lambda item: item.get("name", ""))


def get_team(team_id: str) -> dict[str, Any] | None:
    """Look up a saved team by id."""
    for team in list_teams():
        if team.get("id") == team_id:
            return team
    return None


def select_bots(
    *,
    bot_ids: list[str] | tuple[str, ...] | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    skills: list[str] | tuple[str, ...] | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Return bots matching explicit ids and/or registry metadata filters."""
    requested_ids = list(bot_ids or [])
    tag_filters = {item.lower() for item in _normalize_items(list(tags or []))}
    skill_filters = {item.lower() for item in _normalize_items(list(skills or []))}
    query_text = (query or "").strip().lower()

    bots = list_bots()
    if requested_ids:
        order = {bot_id: i for i, bot_id in enumerate(requested_ids)}
        bots = [bot for bot in bots if bot.get("id") in order]
        bots.sort(key=lambda bot: order.get(str(bot.get("id")), 0))

    matched: list[dict[str, Any]] = []
    for bot in bots:
        bot_tags = {str(item).lower() for item in bot.get("tags", [])}
        bot_skills = {
            str(item).lower()
            for item in [*(bot.get("skills", []) or []), *(bot.get("custom_skills", []) or [])]
        }
        searchable = " ".join(
            [
                str(bot.get("id", "")),
                str(bot.get("name", "")),
                str(bot.get("role", "")),
                str(bot.get("description", "")),
            ]
        ).lower()

        if tag_filters and not tag_filters.issubset(bot_tags):
            continue
        if skill_filters and not skill_filters.issubset(bot_skills):
            continue
        if query_text and query_text not in searchable:
            continue
        matched.append(bot)
    return matched
