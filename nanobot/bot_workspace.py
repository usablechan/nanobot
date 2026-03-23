"""Bot workspace scaffolding and CRUD helpers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from nanobot.bot_core import (
    _UNSET,
    _normalize_items,
    _utcnow,
    get_bot_configs_dir,
    get_bot_workspaces_dir,
    load_registry,
    save_registry,
    slugify,
)
from nanobot.bot_scaffold import (
    _assert_workspace_available,
    _build_identity_files,
    _scaffold_custom_skills,
    _seed_identity_files,
    _workspace_has_files,
    _write_bot_config,
)
from nanobot.bot_team import list_bots, resolve_team_bots
from nanobot.config.loader import load_config
from nanobot.utils.helpers import ensure_dir, sync_workspace_templates


def _unique_bot_id(preferred: str) -> str:
    """Ensure bot ids are unique in the registry."""
    existing = {bot.get("id") for bot in list_bots()}
    if preferred not in existing:
        return preferred
    i = 2
    while f"{preferred}-{i}" in existing:
        i += 1
    return f"{preferred}-{i}"



def create_bot(
    *,
    name: str,
    role: str,
    description: str = "",
    model: str | None = None,
    provider: str | None = None,
    workspace: str | Path | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    skills: list[str] | tuple[str, ...] | None = None,
    custom_skills: list[str] | tuple[str, ...] | None = None,
    memory_seed: str = "",
    force: bool = False,
) -> dict[str, Any]:
    """Create a new isolated bot workspace and registry entry."""
    bot_id = _unique_bot_id(slugify(name))
    workspace_path = Path(workspace).expanduser() if workspace else get_bot_workspaces_dir() / bot_id
    had_existing_files = _workspace_has_files(workspace_path)
    _assert_workspace_available(workspace_path, force=force)
    workspace_path.mkdir(parents=True, exist_ok=True)

    sync_workspace_templates(workspace_path, silent=True)
    ensure_dir(workspace_path / "sessions")

    tag_list = _normalize_items(list(tags or []))
    skill_list = _normalize_items(list(skills or []))
    custom_skill_list = _normalize_items(list(custom_skills or []))
    _seed_identity_files(
        workspace_path,
        name=name,
        role=role,
        description=description,
        tags=tag_list,
        skills=skill_list,
        memory_seed=memory_seed,
        overwrite=force or not had_existing_files,
    )
    created_skills = _scaffold_custom_skills(
        workspace_path,
        custom_skill_list,
        overwrite=force,
    )

    base_config = load_config()
    selected_model = model or base_config.agents.defaults.model
    selected_provider = provider or base_config.agents.defaults.provider
    config_path = get_bot_configs_dir() / f"{bot_id}.json"
    _write_bot_config(
        config_path,
        workspace_path,
        model=selected_model,
        provider=selected_provider,
        base_config=base_config,
    )

    entry = {
        "id": bot_id,
        "name": name,
        "role": role,
        "description": description,
        "workspace": str(workspace_path.resolve()),
        "config_path": str(config_path.resolve()),
        "model": selected_model,
        "provider": selected_provider,
        "tags": tag_list,
        "skills": skill_list,
        "custom_skills": custom_skill_list,
        "created_skill_stubs": created_skills,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }

    registry = load_registry()
    bots = registry.setdefault("bots", [])
    bots.append(entry)
    save_registry(registry)
    return entry


def update_bot(
    bot_id: str,
    *,
    name: str | None = None,
    role: str | None = None,
    description: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    tags: list[str] | tuple[str, ...] | None | object = _UNSET,
    skills: list[str] | tuple[str, ...] | None | object = _UNSET,
    custom_skills: list[str] | tuple[str, ...] | None | object = _UNSET,
    rewrite_files: bool = False,
    memory_seed: str | None = None,
) -> dict[str, Any]:
    """Update registry/config metadata for one bot."""
    registry = load_registry()
    bots = [bot for bot in registry.get("bots", []) if isinstance(bot, dict)]
    index = next((i for i, bot in enumerate(bots) if bot.get("id") == bot_id), None)
    if index is None:
        raise ValueError(f"Unknown bot: {bot_id}")

    current = dict(bots[index])
    next_bot = {
        **current,
        "name": name or current.get("name", ""),
        "role": role or current.get("role", ""),
        "description": description if description is not None else current.get("description", ""),
        "model": model or current.get("model", ""),
        "provider": provider or current.get("provider", ""),
        "tags": current.get("tags", []) if tags is _UNSET else _normalize_items(list(tags or [])),
        "skills": current.get("skills", []) if skills is _UNSET else _normalize_items(list(skills or [])),
        "custom_skills": (
            current.get("custom_skills", [])
            if custom_skills is _UNSET
            else _normalize_items(list(custom_skills or []))
        ),
        "updated_at": _utcnow(),
    }
    bots[index] = next_bot
    registry["bots"] = bots
    save_registry(registry)

    workspace = Path(str(next_bot["workspace"]))
    config_path = Path(str(next_bot["config_path"]))
    base_config = load_config()
    _write_bot_config(
        config_path,
        workspace,
        model=str(next_bot["model"]),
        provider=str(next_bot["provider"]),
        base_config=base_config,
    )
    _scaffold_custom_skills(workspace, list(next_bot.get("custom_skills", [])), overwrite=False)

    if rewrite_files:
        identity_files = _build_identity_files(
            workspace,
            name=str(next_bot["name"]),
            role=str(next_bot["role"]),
            description=str(next_bot.get("description", "")),
            tags=list(next_bot.get("tags", [])),
            skills=list(next_bot.get("skills", [])),
        )
        for path, content in identity_files.items():
            path.write_text(content, encoding="utf-8")
        if memory_seed is not None:
            _seed_identity_files(
                workspace,
                name=str(next_bot["name"]),
                role=str(next_bot["role"]),
                description=str(next_bot.get("description", "")),
                tags=list(next_bot.get("tags", [])),
                skills=list(next_bot.get("skills", [])),
                memory_seed=memory_seed,
                overwrite=True,
            )

    return next_bot


def delete_bot(
    bot_id: str,
    *,
    purge_files: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Delete a bot from the registry, optionally removing its generated files."""
    registry = load_registry()
    bots = [bot for bot in registry.get("bots", []) if isinstance(bot, dict)]
    removed = next((bot for bot in bots if bot.get("id") == bot_id), None)
    if removed is None:
        raise ValueError(f"Unknown bot: {bot_id}")

    teams = [team for team in registry.get("teams", []) if isinstance(team, dict)]
    referencing = [team for team in teams if bot_id in (team.get("bot_ids") or [])]
    if referencing and not force:
        refs = ", ".join(str(team.get("id")) for team in referencing)
        raise ValueError(
            f"Bot {bot_id} is referenced by saved team(s): {refs}. "
            "Delete/update those teams first or pass force=True."
        )

    registry["bots"] = [bot for bot in bots if bot.get("id") != bot_id]
    if teams:
        updated_teams: list[dict[str, Any]] = []
        for team in teams:
            explicit = [item for item in (team.get("bot_ids") or []) if item != bot_id]
            next_team = {**team, "bot_ids": explicit}
            next_team["preview_bot_ids"] = [bot["id"] for bot in resolve_team_bots(next_team)]
            next_team["updated_at"] = _utcnow()
            updated_teams.append(next_team)
        registry["teams"] = updated_teams
    save_registry(registry)

    if purge_files:
        workspace = Path(str(removed.get("workspace", "")))
        config_path = Path(str(removed.get("config_path", "")))
        if workspace.exists():
            shutil.rmtree(workspace)
        if config_path.exists():
            config_path.unlink()

    return removed


__all__ = [
    "create_bot",
    "delete_bot",
    "update_bot",
]
