"""Workspace scaffolding helpers for isolated bots."""

from __future__ import annotations

import json
from pathlib import Path

from nanobot.agent.skills import BUILTIN_SKILLS_DIR
from nanobot.bot_core import slugify
from nanobot.config.schema import Config


def _workspace_has_files(path: Path) -> bool:
    """Return True when a workspace already contains files or directories."""
    return path.exists() and any(path.iterdir())


def _assert_workspace_available(path: Path, *, force: bool) -> None:
    """Protect users from accidentally overwriting populated workspaces."""
    if _workspace_has_files(path) and not force:
        raise ValueError(
            f"Workspace already exists and is not empty: {path}. "
            "Pass force=True to reuse and overwrite seeded files."
        )


def _builtin_skill_exists(name: str) -> bool:
    """Return True when the requested skill name already exists as a bundled skill."""
    skill_path = BUILTIN_SKILLS_DIR / slugify(name) / "SKILL.md"
    return skill_path.exists()


def _build_identity_files(
    workspace: Path,
    *,
    name: str,
    role: str,
    description: str,
    tags: list[str],
    skills: list[str],
) -> dict[Path, str]:
    """Build the seeded identity file payloads for a bot workspace."""
    tags_md = ", ".join(tags) if tags else "none yet"
    skills_md = ", ".join(skills) if skills else "none yet"
    return {
        workspace / "AGENTS.md": (
            f"# {name}\n\n"
            f"You are {name}, a specialized nanobot.\n\n"
            f"## Role\n"
            f"- Primary role: {role}\n"
            f"- Mission: {description or 'Operate as a focused specialist for your domain.'}\n\n"
            "## Working Style\n"
            "- Stay within your specialty before escalating.\n"
            "- Prefer domain-specific skills and memories in this workspace.\n"
            "- Record durable facts in memory when they will help future work.\n"
        ),
        workspace / "SOUL.md": (
            f"# Personality\n\n"
            f"- Professional identity: {role}\n"
            "- Tone: concise, operational, and proactive\n"
            "- Collaboration: produce artifacts that can be handed to other bots or humans\n"
            f"- Tags: {tags_md}\n"
        ),
        workspace / "USER.md": (
            "# Operator Notes\n\n"
            f"- Preferred bot name: {name}\n"
            f"- Owned domain: {role}\n"
            f"- Suggested skills: {skills_md}\n"
            "- Escalate when a request clearly belongs to another specialist bot.\n"
        ),
    }


def _seed_identity_files(
    workspace: Path,
    *,
    name: str,
    role: str,
    description: str,
    tags: list[str],
    skills: list[str],
    memory_seed: str,
    overwrite: bool,
) -> None:
    """Write a focused persona scaffold into the workspace."""
    files = _build_identity_files(
        workspace,
        name=name,
        role=role,
        description=description,
        tags=tags,
        skills=skills,
    )
    tags_md = ", ".join(tags) if tags else "none yet"
    skills_md = ", ".join(skills) if skills else "none yet"
    files[workspace / "memory" / "MEMORY.md"] = (
        "# Long-term Memory\n\n"
        "## Bot Profile\n"
        f"- Name: {name}\n"
        f"- Role: {role}\n"
        f"- Description: {description or 'No description provided yet.'}\n"
        f"- Skills: {skills_md}\n"
        f"- Tags: {tags_md}\n\n"
        "## Seed Notes\n"
        f"{memory_seed or '- No seed memory yet.'}\n"
    )
    for path, content in files.items():
        if overwrite or not path.exists():
            path.write_text(content, encoding="utf-8")


def _scaffold_custom_skills(workspace: Path, skills: list[str], *, overwrite: bool) -> list[str]:
    """Create stub custom skills for workspace-specific guidance."""
    created: list[str] = []
    for skill in skills:
        skill_id = slugify(skill)
        if _builtin_skill_exists(skill_id):
            continue
        skill_dir = workspace / "skills" / skill_id
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists() and not overwrite:
            continue
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(
            (
                "---\n"
                f"name: {skill_id}\n"
                f"description: Workspace-specific guidance for {skill}.\n"
                "---\n\n"
                f"# {skill}\n\n"
                f"- Use this skill when handling work related to {skill}.\n"
                "- Capture domain heuristics, checklists, and repeatable prompts here.\n"
                "- Replace this stub with concrete workflow instructions.\n"
            ),
            encoding="utf-8",
        )
        created.append(skill_id)
    return created


def _write_bot_config(
    config_path: Path,
    workspace: Path,
    *,
    model: str,
    provider: str,
    base_config: Config,
) -> None:
    """Generate a dedicated config for one bot."""
    config = base_config.model_copy(deep=True)
    config.agents.defaults.workspace = str(workspace)
    config.agents.defaults.model = model
    config.agents.defaults.provider = provider
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config.model_dump(by_alias=True), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
