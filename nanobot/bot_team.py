"""Saved team CRUD helpers built on top of lookup/selection APIs."""

from __future__ import annotations

from nanobot.bot_core import (
    _UNSET,
    _normalize_items,
    _utcnow,
    load_registry,
    save_registry,
    slugify,
)
from nanobot.bot_directory import get_bot, get_team, list_bots, list_teams, select_bots


def _unique_team_id(preferred: str) -> str:
    """Ensure team ids are unique in the registry."""
    existing = {team.get("id") for team in list_teams()}
    if preferred not in existing:
        return preferred
    i = 2
    while f"{preferred}-{i}" in existing:
        i += 1
    return f"{preferred}-{i}"


def create_team(
    *,
    name: str,
    description: str = "",
    bot_ids: list[str] | tuple[str, ...] | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    skills: list[str] | tuple[str, ...] | None = None,
    query: str = "",
    max_bots: int | None = None,
    execution_policy: str = "default",
) -> dict[str, object]:
    """Create and persist a reusable saved team definition."""
    explicit_bot_ids = [bot_id for bot_id in list(bot_ids or []) if bot_id]
    tag_list = _normalize_items(list(tags or []))
    skill_list = _normalize_items(list(skills or []))
    if not explicit_bot_ids and not tag_list and not skill_list and not query.strip():
        raise ValueError("Provide at least one selector: --bot, --tag, --skill, or --query.")

    team_id = _unique_team_id(slugify(name))
    preview = resolve_team_bots({
        "bot_ids": explicit_bot_ids,
        "tags": tag_list,
        "skills": skill_list,
        "query": query,
        "max_bots": max_bots,
    })
    entry = {
        "id": team_id,
        "name": name,
        "description": description,
        "bot_ids": explicit_bot_ids,
        "tags": tag_list,
        "skills": skill_list,
        "query": query,
        "max_bots": max_bots,
        "execution_policy": execution_policy,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
        "preview_bot_ids": [bot["id"] for bot in preview],
    }

    registry = load_registry()
    teams = registry.setdefault("teams", [])
    teams.append(entry)
    save_registry(registry)
    return entry


def resolve_team_bots(team: dict[str, object]) -> list[dict[str, object]]:
    """Resolve the current bot membership for a saved team definition."""
    selected = select_bots(
        bot_ids=team.get("bot_ids") or [],
        tags=team.get("tags") or [],
        skills=team.get("skills") or [],
        query=team.get("query") or "",
    )
    max_bots = team.get("max_bots")
    if isinstance(max_bots, int):
        selected = selected[:max_bots]
    return selected


def update_team(
    team_id: str,
    *,
<<<<<<< ours
    name: str | None = None,
=======
>>>>>>> theirs
    description: str | None = None,
    bot_ids: list[str] | tuple[str, ...] | None | object = _UNSET,
    tags: list[str] | tuple[str, ...] | None | object = _UNSET,
    skills: list[str] | tuple[str, ...] | None | object = _UNSET,
    query: str | None | object = _UNSET,
    max_bots: int | None | object = _UNSET,
    execution_policy: str | None | object = _UNSET,
) -> dict[str, object]:
    """Update a saved team definition."""
    registry = load_registry()
    teams = [team for team in registry.get("teams", []) if isinstance(team, dict)]
    index = next((i for i, team in enumerate(teams) if team.get("id") == team_id), None)
    if index is None:
        raise ValueError(f"Unknown team: {team_id}")

    current = dict(teams[index])
    next_team = {
        **current,
<<<<<<< ours
        "name": name if name is not None else current.get("name", ""),
=======
>>>>>>> theirs
        "description": description if description is not None else current.get("description", ""),
        "bot_ids": current.get("bot_ids", []) if bot_ids is _UNSET else [item for item in list(bot_ids or []) if item],
        "tags": current.get("tags", []) if tags is _UNSET else _normalize_items(list(tags or [])),
        "skills": current.get("skills", []) if skills is _UNSET else _normalize_items(list(skills or [])),
        "query": current.get("query", "") if query is _UNSET else str(query or ""),
        "max_bots": current.get("max_bots") if max_bots is _UNSET else max_bots,
        "execution_policy": (
            current.get("execution_policy", "default")
            if execution_policy is _UNSET
            else str(execution_policy or "default")
        ),
        "updated_at": _utcnow(),
    }
    next_team["preview_bot_ids"] = [bot["id"] for bot in resolve_team_bots(next_team)]
    teams[index] = next_team
    registry["teams"] = teams
    save_registry(registry)
    return next_team


def delete_team(team_id: str) -> dict[str, object]:
    """Delete a saved team definition and return the removed entry."""
    registry = load_registry()
    teams = [team for team in registry.get("teams", []) if isinstance(team, dict)]
    removed = next((team for team in teams if team.get("id") == team_id), None)
    if removed is None:
        raise ValueError(f"Unknown team: {team_id}")
    registry["teams"] = [team for team in teams if team.get("id") != team_id]
    save_registry(registry)
    return removed


__all__ = [
    "create_team",
    "delete_team",
    "get_bot",
    "get_team",
    "list_bots",
    "list_teams",
    "resolve_team_bots",
    "select_bots",
    "update_team",
]
