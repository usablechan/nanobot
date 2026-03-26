"""Shared registry/path helpers for bot and team management."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.config.paths import get_runtime_subdir
from nanobot.utils.helpers import ensure_dir

_UNSET = object()


def _default_registry() -> dict[str, Any]:
    """Return the default empty registry payload."""
    return {"version": 1, "bots": [], "teams": []}


def _utcnow() -> str:
    """Return an ISO8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    """Create a filesystem-friendly identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "bot"


def get_bots_dir() -> Path:
    """Return the instance-local bots directory."""
    return get_runtime_subdir("bots")


def get_registry_path() -> Path:
    """Return the bot registry file path."""
    return get_bots_dir() / "registry.json"


def get_bot_workspaces_dir() -> Path:
    """Return the directory that stores bot workspaces."""
    return ensure_dir(get_bots_dir() / "workspaces")


def get_bot_configs_dir() -> Path:
    """Return the directory that stores generated bot configs."""
    return ensure_dir(get_bots_dir() / "configs")


def get_bot_dashboards_dir() -> Path:
    """Return the directory that stores generated dashboards."""
    return ensure_dir(get_bots_dir() / "dashboards")


def _backup_corrupt_registry(path: Path) -> None:
    """Write a timestamped backup copy of a corrupt registry file."""
    try:
        if not path.exists():
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = path.with_name(f"{path.stem}.corrupt-{stamp}{path.suffix}")
        # Keep first backup for a given second; don't overwrite if multiple reads happen quickly.
        if backup_path.exists():
            return
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError as exc:
        logger.warning(f"Failed to back up corrupt bot registry {path}: {exc}")


def load_registry() -> dict[str, Any]:
    """Load the registry from disk."""
    path = get_registry_path()
    if not path.exists():
        return _default_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to load bot registry from {path}: {exc}")
        _backup_corrupt_registry(path)
        return _default_registry()
    if not isinstance(data, dict):
        logger.warning(f"Invalid bot registry format at {path}: expected object root")
        _backup_corrupt_registry(path)
        return _default_registry()
    if "bots" not in data:
        data["bots"] = []
    if "teams" not in data:
        data["teams"] = []
    if not isinstance(data["bots"], list):
        logger.warning(f"Invalid bot registry format at {path}: bots must be a list")
        data["bots"] = []
    if not isinstance(data["teams"], list):
        logger.warning(f"Invalid bot registry format at {path}: teams must be a list")
        data["teams"] = []
    return data


def save_registry(data: dict[str, Any]) -> None:
    """Persist the registry to disk."""
    path = get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_items(values: list[str] | tuple[str, ...] | None) -> list[str]:
    """Normalize repeated/CSV CLI values into a clean list."""
    result: list[str] = []
    for value in values or []:
        for item in value.split(","):
            cleaned = item.strip()
            if cleaned and cleaned not in result:
                result.append(cleaned)
    return result


__all__ = [
    "_UNSET",
    "_normalize_items",
    "_utcnow",
    "get_bot_configs_dir",
    "get_bot_dashboards_dir",
    "get_bot_workspaces_dir",
    "get_bots_dir",
    "get_registry_path",
    "load_registry",
    "save_registry",
    "slugify",
]
