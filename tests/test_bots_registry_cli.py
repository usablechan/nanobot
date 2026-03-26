import json
from pathlib import Path

from nanobot.bots import get_registry_path
from nanobot.cli.commands import app
from nanobot.config.schema import Config
from tests.bot_test_support import patched_config_paths, runner


def test_bots_create_list_show_and_dashboard(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = Config.model_validate(
        {
            "agents": {"defaults": {"model": "openai/gpt-4.1-mini", "provider": "openai"}},
            "providers": {"openai": {"apiKey": "test-key"}},
        }
    )
    config_path.write_text(
        json.dumps(config.model_dump(by_alias=True), ensure_ascii=False),
        encoding="utf-8",
    )

    with patched_config_paths(config_path):
        create_result = runner.invoke(
            app,
            [
                "bots",
                "create",
                "Thread Marketing Bot",
                "--role",
                "Thread marketing specialist",
                "--description",
                "Plans and drafts social threads",
                "--tag",
                "marketing,social",
                "--skill",
                "github",
                "--skill",
                "summarize",
                "--custom-skill",
                "thread-writing",
                "--custom-skill",
                "analytics",
                "--memory-seed",
                "- Brand voice: sharp but honest.",
            ],
        )
        assert create_result.exit_code == 0, create_result.stdout
        assert "Created bot:" in create_result.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        assert len(registry["bots"]) == 1
        entry = registry["bots"][0]

        workspace = Path(entry["workspace"])
        config_file = Path(entry["config_path"])
        generated_config = json.loads(config_file.read_text(encoding="utf-8"))
        assert (workspace / "AGENTS.md").exists()
        assert (workspace / "memory" / "MEMORY.md").read_text(encoding="utf-8").find("sharp but honest") != -1
        assert (workspace / "skills" / "thread-writing" / "SKILL.md").exists()
        assert not (workspace / "skills" / "github" / "SKILL.md").exists()
        assert config_file.exists()
        assert generated_config["agents"]["defaults"]["model"] == "openai/gpt-4.1-mini"
        assert generated_config["agents"]["defaults"]["provider"] == "openai"
        assert generated_config["providers"]["openai"]["apiKey"] == "test-key"

        list_result = runner.invoke(app, ["bots", "list", "--json"])
        assert list_result.exit_code == 0, list_result.stdout
        listed = json.loads(list_result.stdout)
        assert listed[0]["id"] == entry["id"]
        assert listed[0]["session_count"] == 0
        assert listed[0]["skill_summary"] == "github, summarize"
        assert listed[0]["custom_skill_summary"] == "thread-writing, analytics"

        show_result = runner.invoke(app, ["bots", "show", entry["id"], "--json"])
        assert show_result.exit_code == 0, show_result.stdout
        shown = json.loads(show_result.stdout)
        assert shown["role"] == "Thread marketing specialist"
        assert shown["skills_dir_count"] == 2
        assert shown["provider"] == "openai"

        dashboard_path = tmp_path / "dashboard.html"
        dashboard_result = runner.invoke(
            app,
            ["bots", "dashboard", "--output", str(dashboard_path)],
        )
        assert dashboard_result.exit_code == 0, dashboard_result.stdout
        html = dashboard_path.read_text(encoding="utf-8")
        assert "nanobot team dashboard" in html
        assert "Thread Marketing Bot" in html
        assert "Session Load (per bot)" in html


def test_bots_create_ensures_unique_ids(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        second = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        data = json.loads(get_registry_path().read_text(encoding="utf-8"))
        ids = [bot["id"] for bot in data["bots"]]
        assert ids == ["research-bot", "research-bot-2"]


def test_bots_commands_recover_from_corrupt_registry(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        registry_path = get_registry_path()
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text("{not-valid-json", encoding="utf-8")

        list_result = runner.invoke(app, ["bots", "list", "--json"])
        assert list_result.exit_code == 0, list_result.stdout
        assert json.loads(list_result.stdout) == []

        create_result = runner.invoke(app, ["bots", "create", "Recovery Bot", "--role", "Support"])
        assert create_result.exit_code == 0, create_result.stdout
        created = json.loads(get_registry_path().read_text(encoding="utf-8"))
        assert [bot["id"] for bot in created["bots"]] == ["recovery-bot"]
        backups = sorted(registry_path.parent.glob("registry.corrupt-*.json"))
        assert backups, "expected corrupt registry backup to be created"
        assert "{not-valid-json" in backups[-1].read_text(encoding="utf-8")


def test_bots_create_refuses_non_empty_workspace_without_force(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")
    workspace = tmp_path / "existing-bot"
    workspace.mkdir(parents=True)
    (workspace / "AGENTS.md").write_text("keep me", encoding="utf-8")

    with patched_config_paths(config_path):
        result = runner.invoke(
            app,
            [
                "bots",
                "create",
                "Existing Bot",
                "--role",
                "Ops",
                "--workspace",
                str(workspace),
            ],
        )

    assert result.exit_code == 1
    assert "Workspace already exists and is not empty" in result.stdout
    assert (workspace / "AGENTS.md").read_text(encoding="utf-8") == "keep me"


def test_bots_and_teams_can_be_deleted_safely(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        create_result = runner.invoke(app, ["bots", "create", "Ops Bot", "--role", "Operations"])
        assert create_result.exit_code == 0, create_result.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        bot = registry["bots"][0]
        workspace = Path(bot["workspace"])
        config_file = Path(bot["config_path"])

        team_create = runner.invoke(
            app,
            ["bots", "team", "create", "ops-team", "--bot", bot["id"]],
        )
        assert team_create.exit_code == 0, team_create.stdout

        blocked_delete = runner.invoke(app, ["bots", "delete", bot["id"]])
        assert blocked_delete.exit_code == 1
        assert "referenced by saved team" in blocked_delete.stdout

        team_delete = runner.invoke(app, ["bots", "team", "delete", "ops-team"])
        assert team_delete.exit_code == 0, team_delete.stdout
        assert "Deleted team:" in team_delete.stdout

        bot_delete = runner.invoke(app, ["bots", "delete", bot["id"], "--purge-files"])
        assert bot_delete.exit_code == 0, bot_delete.stdout
        assert "Deleted bot:" in bot_delete.stdout
        assert not workspace.exists()
        assert not config_file.exists()


def test_bots_update_preserves_lists_until_replaced_and_can_rewrite_identity_files(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = Config.model_validate(
        {
            "agents": {"defaults": {"model": "openai/gpt-4.1-mini", "provider": "openai"}},
            "providers": {"openai": {"apiKey": "test-key"}},
        }
    )
    config_path.write_text(
        json.dumps(config.model_dump(by_alias=True), ensure_ascii=False),
        encoding="utf-8",
    )

    with patched_config_paths(config_path):
        create_result = runner.invoke(
            app,
            [
                "bots",
                "create",
                "Ops Bot",
                "--role",
                "Operations",
                "--description",
                "Keeps systems healthy",
                "--tag",
                "ops,infra",
                "--skill",
                "summarize",
                "--custom-skill",
                "incident-response",
                "--memory-seed",
                "- Initial note.",
            ],
        )
        assert create_result.exit_code == 0, create_result.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        bot = registry["bots"][0]
        workspace = Path(bot["workspace"])

        update_result = runner.invoke(
            app,
            [
                "bots",
                "update",
                bot["id"],
                "--name",
                "Platform Ops Bot",
                "--role",
                "Platform operations",
                "--rewrite-files",
                "--memory-seed",
                "- Updated note.",
            ],
        )
        assert update_result.exit_code == 0, update_result.stdout
        assert "Updated bot:" in update_result.stdout

        updated_bot = json.loads(get_registry_path().read_text(encoding="utf-8"))["bots"][0]
        assert updated_bot["name"] == "Platform Ops Bot"
        assert updated_bot["role"] == "Platform operations"
        assert updated_bot["tags"] == ["ops", "infra"]
        assert updated_bot["skills"] == ["summarize"]
        assert updated_bot["custom_skills"] == ["incident-response"]

        agents_text = (workspace / "AGENTS.md").read_text(encoding="utf-8")
        memory_text = (workspace / "memory" / "MEMORY.md").read_text(encoding="utf-8")
        assert "Platform Ops Bot" in agents_text
        assert "Updated note." in memory_text

        replace_lists_result = runner.invoke(
            app,
            [
                "bots",
                "update",
                bot["id"],
                "--tag",
                "platform",
                "--skill",
                "github",
                "--custom-skill",
                "deployments",
            ],
        )
        assert replace_lists_result.exit_code == 0, replace_lists_result.stdout

        replaced_bot = json.loads(get_registry_path().read_text(encoding="utf-8"))["bots"][0]
        assert replaced_bot["tags"] == ["platform"]
        assert replaced_bot["skills"] == ["github"]
        assert replaced_bot["custom_skills"] == ["deployments"]


def test_team_update_preserves_unset_selectors_and_can_clear_fields(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        create_bot_result = runner.invoke(
            app,
            ["bots", "create", "Research Bot", "--role", "Research", "--tag", "analysis", "--skill", "summarize"],
        )
        assert create_bot_result.exit_code == 0, create_bot_result.stdout

        create_team_result = runner.invoke(
            app,
            [
                "bots",
                "team",
                "create",
                "research-team",
                "--description",
                "Original description",
                "--bot",
                "research-bot",
                "--tag",
                "analysis",
                "--skill",
                "summarize",
                "--query",
                "research",
                "--max-bots",
                "2",
            ],
        )
        assert create_team_result.exit_code == 0, create_team_result.stdout

        update_description = runner.invoke(
            app,
            ["bots", "team", "update", "research-team", "--description", "Updated description"],
        )
        assert update_description.exit_code == 0, update_description.stdout

        show_result = runner.invoke(app, ["bots", "team", "show", "research-team", "--json"])
        assert show_result.exit_code == 0, show_result.stdout
        team = json.loads(show_result.stdout)
        assert team["description"] == "Updated description"
        assert team["bot_ids"] == ["research-bot"]
        assert team["tags"] == ["analysis"]
        assert team["skills"] == ["summarize"]
        assert team["query"] == "research"
        assert team["max_bots"] == 2
        assert team["execution_policy"] == "default"

        update_policy = runner.invoke(
            app,
            ["bots", "team", "update", "research-team", "--execution-policy", "strict"],
        )
        assert update_policy.exit_code == 0, update_policy.stdout
        policy_team = json.loads(runner.invoke(app, ["bots", "team", "show", "research-team", "--json"]).stdout)
        assert policy_team["execution_policy"] == "strict"

        clear_fields = runner.invoke(
            app,
            [
                "bots",
                "team",
                "update",
                "research-team",
                "--query",
                "",
                "--clear-max-bots",
                "--tag",
                "",
            ],
        )
        assert clear_fields.exit_code == 0, clear_fields.stdout

        cleared_team = json.loads(runner.invoke(app, ["bots", "team", "show", "research-team", "--json"]).stdout)
        assert cleared_team["tags"] == []
        assert cleared_team["bot_ids"] == ["research-bot"]
        assert cleared_team["skills"] == ["summarize"]
        assert cleared_team["query"] == ""
        assert cleared_team["max_bots"] is None
        assert cleared_team["execution_policy"] == "strict"


def test_team_create_rejects_unknown_execution_policy(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        create_bot_result = runner.invoke(
            app,
            ["bots", "create", "Research Bot", "--role", "Research"],
        )
        assert create_bot_result.exit_code == 0, create_bot_result.stdout

        invalid_team = runner.invoke(
            app,
            [
                "bots",
                "team",
                "create",
                "research-team",
                "--bot",
                "research-bot",
                "--execution-policy",
                "warp-speed",
            ],
        )
        assert invalid_team.exit_code == 1
        assert "Unknown execution policy" in invalid_team.stdout
