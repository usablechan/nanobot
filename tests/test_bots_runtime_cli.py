import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from nanobot.bots import get_registry_path
from nanobot.bus.events import OutboundMessage
from nanobot.cli.commands import app
from tests.bot_test_support import patched_config_paths, runner


def test_bots_run_and_compare_use_registered_bot_configs(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(
            app,
            ["bots", "create", "Research Bot", "--role", "Research", "--tag", "strategy", "--skill", "summarize"],
        )
        second = runner.invoke(
            app,
            ["bots", "create", "Writer Bot", "--role", "Writing", "--tag", "marketing", "--custom-skill", "thread-writing"],
        )

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        async def _fake_synthesize(config, user_message, results):
            return f"synth:{user_message}:{','.join(item['id'] for item in results)}"

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once), \
             patch("nanobot.cli.commands._synthesize_bot_results", side_effect=_fake_synthesize):
            run_result = runner.invoke(
                app,
                ["bots", "run", research_id, "--message", "hello", "--no-markdown"],
            )
            assert run_result.exit_code == 0, run_result.stdout
            assert "Research Bot" in run_result.stdout
            assert f"{research_id}:hello:False" in run_result.stdout

            compare_result = runner.invoke(
                app,
                ["bots", "compare", research_id, writer_id, "--message", "brief", "--json"],
            )
            assert compare_result.exit_code == 0, compare_result.stdout
            payload = json.loads(compare_result.stdout)
            assert [item["id"] for item in payload] == [research_id, writer_id]
            assert payload[0]["session_id"] == f"cli:compare:{research_id}"
            assert payload[1]["session_id"] == f"cli:compare:{writer_id}"
            assert isinstance(payload[0]["elapsed_ms"], int)
            assert isinstance(payload[1]["elapsed_ms"], int)

            dispatch_result = runner.invoke(
                app,
                ["bots", "dispatch", "--tag", "marketing", "--message", "brief", "--json"],
            )
            assert dispatch_result.exit_code == 0, dispatch_result.stdout
            dispatched = json.loads(dispatch_result.stdout)
            assert [item["id"] for item in dispatched] == [writer_id]
            assert dispatched[0]["session_id"] == f"cli:dispatch:{writer_id}"

            orchestrate_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--bot", research_id, "--bot", writer_id,
                    "--message", "launch", "--json", "--run-label", "launch-v1",
                ],
            )
            assert orchestrate_result.exit_code == 0, orchestrate_result.stdout
            orchestrated = json.loads(orchestrate_result.stdout)
            assert orchestrated["run_id"].startswith("orchestrate:")
            assert orchestrated["run_label"] == "launch-v1"
            assert orchestrated["started_at"].endswith("+00:00")
            assert orchestrated["finished_at"].endswith("+00:00")
            assert isinstance(orchestrated["duration_ms"], int)
            assert orchestrated["duration_ms"] >= 0
            assert orchestrated["execution"]["policy"] == "default"
            assert orchestrated["execution"]["retries"] == 0
            assert orchestrated["selected_ids"] == [research_id, writer_id]
            assert orchestrated["summary"] == {"total": 2, "ok": 2, "error": 0, "timeout": 0}
            assert orchestrated["synthesis"] == f"synth:launch:{research_id},{writer_id}"

            team_create = runner.invoke(
                app,
                ["bots", "team", "create", "marketing-squad", "--tag", "marketing", "--max-bots", "1"],
            )
            assert team_create.exit_code == 0, team_create.stdout
            assert "Created team:" in team_create.stdout

            team_list = runner.invoke(app, ["bots", "team", "list", "--json"])
            assert team_list.exit_code == 0, team_list.stdout
            teams = json.loads(team_list.stdout)
            assert teams[0]["id"] == "marketing-squad"

            team_run = runner.invoke(
                app,
                [
                    "bots", "team", "run", "marketing-squad", "--message", "campaign",
                    "--json", "--run-label", "campaign-v1",
                ],
            )
            assert team_run.exit_code == 0, team_run.stdout
            team_payload = json.loads(team_run.stdout)
            assert team_payload["run_id"].startswith("team:marketing-squad:")
            assert team_payload["run_label"] == "campaign-v1"
            assert team_payload["started_at"].endswith("+00:00")
            assert team_payload["finished_at"].endswith("+00:00")
            assert isinstance(team_payload["duration_ms"], int)
            assert team_payload["duration_ms"] >= 0
            assert team_payload["execution"]["policy"] == "default"
            assert team_payload["execution"]["retries"] == 0
            assert team_payload["team_id"] == "marketing-squad"
            assert team_payload["selected_ids"] == [writer_id]
            assert team_payload["summary"] == {"total": 1, "ok": 1, "error": 0, "timeout": 0}
            assert team_payload["synthesis"] == f"synth:campaign:{writer_id}"


def test_bots_orchestrate_survives_partial_failures(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        second = runner.invoke(app, ["bots", "create", "Writer Bot", "--role", "Writing"])

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            if workspace_name == writer_id:
                raise RuntimeError("writer bot offline")
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        async def _fake_synthesize(config, user_message, results):
            return f"synth:{user_message}:{','.join(item['id'] for item in results)}"

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once), \
             patch("nanobot.cli.commands._synthesize_bot_results", side_effect=_fake_synthesize):
            compare_result = runner.invoke(
                app,
                ["bots", "compare", research_id, writer_id, "--message", "brief", "--json"],
            )
            assert compare_result.exit_code == 0, compare_result.stdout
            compared = json.loads(compare_result.stdout)
            assert compared[0]["status"] == "ok"
            assert compared[1]["status"] == "error"
            assert compared[1]["error"] == "writer bot offline"

            orchestrate_result = runner.invoke(
                app,
                ["bots", "orchestrate", "--bot", research_id, "--bot", writer_id, "--message", "launch", "--json"],
            )
            assert orchestrate_result.exit_code == 0, orchestrate_result.stdout
            orchestrated = json.loads(orchestrate_result.stdout)
            assert orchestrated["selected_ids"] == [research_id, writer_id]
            assert orchestrated["summary"] == {"total": 2, "ok": 1, "error": 1, "timeout": 0}
            assert orchestrated["synthesis"] == f"synth:launch:{research_id}"
            assert orchestrated["results"][1]["status"] == "error"
            assert isinstance(orchestrated["results"][1]["elapsed_ms"], int)

            team_create = runner.invoke(
                app,
                ["bots", "team", "create", "mixed-team", "--bot", research_id, "--bot", writer_id],
            )
            assert team_create.exit_code == 0, team_create.stdout

            team_run = runner.invoke(
                app,
                ["bots", "team", "run", "mixed-team", "--message", "campaign", "--json"],
            )
            assert team_run.exit_code == 0, team_run.stdout
            team_payload = json.loads(team_run.stdout)
            assert team_payload["summary"] == {"total": 2, "ok": 1, "error": 1, "timeout": 0}
            assert team_payload["synthesis"] == f"synth:campaign:{research_id}"
            assert team_payload["results"][1]["error"] == "writer bot offline"


def test_bots_orchestrate_marks_timeouts_without_blocking_successful_synthesis(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        second = runner.invoke(app, ["bots", "create", "Writer Bot", "--role", "Writing"])

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            if workspace_name == writer_id:
                await asyncio.sleep(0.2)
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        async def _fake_synthesize(config, user_message, results):
            return f"synth:{user_message}:{','.join(item['id'] for item in results)}"

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once), \
             patch("nanobot.cli.commands._synthesize_bot_results", side_effect=_fake_synthesize):
            compare_result = runner.invoke(
                app,
                [
                    "bots", "compare", research_id, writer_id, "--message", "brief", "--json",
                    "--timeout", "0.1",
                ],
            )
            assert compare_result.exit_code == 0, compare_result.stdout
            compared = json.loads(compare_result.stdout)
            assert compared[0]["status"] == "ok"
            assert compared[1]["status"] == "timeout"
            assert compared[1]["error"] == "Timed out after 0.1s"

            orchestrate_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--bot", research_id, "--bot", writer_id,
                    "--message", "launch", "--json", "--timeout", "0.1",
                ],
            )
            assert orchestrate_result.exit_code == 0, orchestrate_result.stdout
            orchestrated = json.loads(orchestrate_result.stdout)
            assert orchestrated["summary"] == {"total": 2, "ok": 1, "error": 0, "timeout": 1}
            assert orchestrated["synthesis"] == f"synth:launch:{research_id}"
            assert orchestrated["results"][1]["status"] == "timeout"
            assert isinstance(orchestrated["results"][1]["elapsed_ms"], int)

            team_create = runner.invoke(
                app,
                ["bots", "team", "create", "slow-team", "--bot", research_id, "--bot", writer_id],
            )
            assert team_create.exit_code == 0, team_create.stdout

            team_run = runner.invoke(
                app,
                ["bots", "team", "run", "slow-team", "--message", "campaign", "--json", "--timeout", "0.1"],
            )
            assert team_run.exit_code == 0, team_run.stdout
            team_payload = json.loads(team_run.stdout)
            assert team_payload["summary"] == {"total": 2, "ok": 1, "error": 0, "timeout": 1}
            assert team_payload["synthesis"] == f"synth:campaign:{research_id}"
            assert team_payload["results"][1]["status"] == "timeout"


def test_require_all_success_returns_nonzero_for_partial_failures(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        second = runner.invoke(app, ["bots", "create", "Writer Bot", "--role", "Writing"])

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            if workspace_name == writer_id:
                raise RuntimeError("writer bot offline")
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once):
            compare_result = runner.invoke(
                app,
                [
                    "bots", "compare", research_id, writer_id, "--message", "brief", "--json",
                    "--require-all-success",
                ],
            )
            assert compare_result.exit_code == 1, compare_result.stdout
            compared = json.loads(compare_result.stdout)
            assert compared[1]["status"] == "error"

            team_create = runner.invoke(
                app,
                ["bots", "team", "create", "strict-team", "--bot", research_id, "--bot", writer_id],
            )
            assert team_create.exit_code == 0, team_create.stdout

            team_run = runner.invoke(
                app,
                [
                    "bots", "team", "run", "strict-team", "--message", "campaign", "--json",
                    "--require-all-success",
                ],
            )
            assert team_run.exit_code == 1, team_run.stdout
            payload = json.loads(team_run.stdout)
            assert payload["summary"] == {"total": 2, "ok": 1, "error": 1, "timeout": 0}


def test_strict_policy_enforces_all_success_without_explicit_flag(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        second = runner.invoke(app, ["bots", "create", "Writer Bot", "--role", "Writing"])

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            if workspace_name == writer_id:
                raise RuntimeError("writer bot offline")
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once):
            orchestrate_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--bot", research_id, "--bot", writer_id,
                    "--message", "launch", "--json", "--policy", "strict",
                ],
            )
            assert orchestrate_result.exit_code == 1, orchestrate_result.stdout
            orchestrated = json.loads(orchestrate_result.stdout)
            assert orchestrated["execution"]["policy"] == "strict"
            assert orchestrated["execution"]["retries"] == 2
            assert orchestrated["summary"] == {"total": 2, "ok": 1, "error": 1, "timeout": 0}

            team_create = runner.invoke(
                app,
                [
                    "bots",
                    "team",
                    "create",
                    "strict-policy-team",
                    "--bot",
                    research_id,
                    "--bot",
                    writer_id,
                    "--execution-policy",
                    "strict",
                ],
            )
            assert team_create.exit_code == 0, team_create.stdout

            team_run = runner.invoke(
                app,
                [
                    "bots", "team", "run", "strict-policy-team", "--message", "campaign",
                    "--json",
                ],
            )
            assert team_run.exit_code == 1, team_run.stdout
            payload = json.loads(team_run.stdout)
            assert payload["execution"]["policy"] == "strict"
            assert payload["summary"] == {"total": 2, "ok": 1, "error": 1, "timeout": 0}


def test_unknown_policy_is_rejected(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        created = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        assert created.exit_code == 0, created.stdout

        bot_id = json.loads(get_registry_path().read_text(encoding="utf-8"))["bots"][0]["id"]
        result = runner.invoke(
            app,
            ["bots", "orchestrate", "--bot", bot_id, "--message", "launch", "--policy", "unknown-policy"],
        )
        assert result.exit_code == 1
        assert "Unknown execution policy" in result.stdout


def test_best_match_strategy_prioritizes_relevant_bot(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(
            app,
            ["bots", "create", "Research Bot", "--role", "Research", "--tag", "content"],
        )
        second = runner.invoke(
            app,
            ["bots", "create", "Writer Bot", "--role", "Writing", "--tag", "content"],
        )

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        async def _fake_synthesize(config, user_message, results):
            return f"synth:{user_message}:{','.join(item['id'] for item in results)}"

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once), \
             patch("nanobot.cli.commands._synthesize_bot_results", side_effect=_fake_synthesize):
            orchestrate_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--tag", "content", "--message", "Need writing style options",
                    "--strategy", "best_match", "--max-bots", "1", "--json",
                ],
            )
            assert orchestrate_result.exit_code == 0, orchestrate_result.stdout
            orchestrated = json.loads(orchestrate_result.stdout)
            assert orchestrated["strategy"] == "best_match"
            assert orchestrated["selected_ids"] == [writer_id]
            assert research_id not in orchestrated["selected_ids"]


def test_unknown_strategy_is_rejected(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        created = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        assert created.exit_code == 0, created.stdout

        bot_id = json.loads(get_registry_path().read_text(encoding="utf-8"))["bots"][0]["id"]
        result = runner.invoke(
            app,
            ["bots", "orchestrate", "--bot", bot_id, "--message", "launch", "--strategy", "unknown-strategy"],
        )
        assert result.exit_code == 1
        assert "Unknown selection strategy" in result.stdout


def test_top_k_strategy_and_strategy_k_validation(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(
            app,
            ["bots", "create", "Research Bot", "--role", "Research", "--tag", "content"],
        )
        second = runner.invoke(
            app,
            ["bots", "create", "Writer Bot", "--role", "Writing", "--tag", "content"],
        )
        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        async def _fake_synthesize(config, user_message, results):
            return f"synth:{user_message}:{','.join(item['id'] for item in results)}"

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once), \
             patch("nanobot.cli.commands._synthesize_bot_results", side_effect=_fake_synthesize):
            top_k_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--tag", "content", "--message", "Need writing style options",
                    "--strategy", "top_k", "--strategy-k", "1", "--json",
                ],
            )
            assert top_k_result.exit_code == 0, top_k_result.stdout
            payload = json.loads(top_k_result.stdout)
            assert payload["strategy"] == "top_k"
            assert payload["selected_ids"] == [writer_id]

            invalid_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--tag", "content", "--message", "Need writing style options",
                    "--strategy", "best_match", "--strategy-k", "1",
                ],
            )
            assert invalid_result.exit_code == 1
            assert "--strategy-k can only be used with --strategy top_k" in invalid_result.stdout


def test_run_label_is_trimmed_and_empty_value_is_rejected(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        created = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        assert created.exit_code == 0, created.stdout
        bot_id = json.loads(get_registry_path().read_text(encoding="utf-8"))["bots"][0]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        async def _fake_synthesize(config, user_message, results):
            return f"synth:{user_message}:{','.join(item['id'] for item in results)}"

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once), \
             patch("nanobot.cli.commands._synthesize_bot_results", side_effect=_fake_synthesize):
            ok_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--bot", bot_id, "--message", "launch", "--json",
                    "--run-label", "  nightly  ",
                ],
            )
            assert ok_result.exit_code == 0, ok_result.stdout
            payload = json.loads(ok_result.stdout)
            assert payload["run_label"] == "nightly"

            bad_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--bot", bot_id, "--message", "launch", "--json",
                    "--run-label", "   ",
                ],
            )
            assert bad_result.exit_code == 1
            assert "Invalid run label" in bad_result.stdout


def test_strict_policy_retries_transient_failures(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        second = runner.invoke(app, ["bots", "create", "Writer Bot", "--role", "Writing"])
        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]
        attempts: dict[str, int] = {}

        async def _flaky_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            attempts[workspace_name] = attempts.get(workspace_name, 0) + 1
            if workspace_name == writer_id and attempts[workspace_name] == 1:
                raise RuntimeError("temporary writer failure")
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        async def _fake_synthesize(config, user_message, results):
            return f"synth:{user_message}:{','.join(item['id'] for item in results)}"

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_flaky_run_agent_once), \
             patch("nanobot.cli.commands._synthesize_bot_results", side_effect=_fake_synthesize):
            result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--bot", research_id, "--bot", writer_id,
                    "--message", "launch", "--json", "--policy", "strict",
                ],
            )
            assert result.exit_code == 0, result.stdout
            payload = json.loads(result.stdout)
            assert payload["summary"] == {"total": 2, "ok": 2, "error": 0, "timeout": 0}
            assert attempts[writer_id] == 2


def test_max_concurrency_limits_parallel_bot_runs(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        for name in ["Research Bot", "Writer Bot", "Ops Bot"]:
            result = runner.invoke(app, ["bots", "create", name, "--role", name])
            assert result.exit_code == 0, result.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        bot_ids = [bot["id"] for bot in registry["bots"]]

        active = 0
        max_seen = 0

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            nonlocal active, max_seen
            active += 1
            max_seen = max(max_seen, active)
            try:
                await asyncio.sleep(0.05)
                workspace_name = Path(config.agents.defaults.workspace).name
                return OutboundMessage(
                    channel="cli",
                    chat_id="direct",
                    content=f"{workspace_name}:{session_id}:{message}:{logs}",
                    metadata={"render_as": "text"},
                )
            finally:
                active -= 1

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once):
            compare_result = runner.invoke(
                app,
                [
                    "bots", "compare", *bot_ids, "--message", "brief", "--json",
                    "--max-concurrency", "1",
                ],
            )
            assert compare_result.exit_code == 0, compare_result.stdout
            compared = json.loads(compare_result.stdout)
            assert [item["status"] for item in compared] == ["ok", "ok", "ok"]
            assert max_seen == 1


def test_min_successful_bots_blocks_synthesis_when_quorum_is_not_met(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        second = runner.invoke(app, ["bots", "create", "Writer Bot", "--role", "Writing"])

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            if workspace_name == writer_id:
                raise RuntimeError("writer bot offline")
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        async def _fake_synthesize(config, user_message, results):
            return f"synth:{user_message}:{','.join(item['id'] for item in results)}"

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once), \
             patch("nanobot.cli.commands._synthesize_bot_results", side_effect=_fake_synthesize):
            orchestrate_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--bot", research_id, "--bot", writer_id,
                    "--message", "launch", "--json", "--min-successful-bots", "2",
                ],
            )
            assert orchestrate_result.exit_code == 1, orchestrate_result.stdout
            orchestrated = json.loads(orchestrate_result.stdout)
            assert orchestrated["synthesis"] == ""
            assert orchestrated["synthesis_skipped_reason"] == "Need at least 2 successful bot(s) before synthesis; got 1."

            team_create = runner.invoke(
                app,
                ["bots", "team", "create", "quorum-team", "--bot", research_id, "--bot", writer_id],
            )
            assert team_create.exit_code == 0, team_create.stdout

            team_run = runner.invoke(
                app,
                [
                    "bots", "team", "run", "quorum-team", "--message", "campaign", "--json",
                    "--min-successful-bots", "2",
                ],
            )
            assert team_run.exit_code == 1, team_run.stdout
            team_payload = json.loads(team_run.stdout)
            assert team_payload["synthesis"] == ""
            assert team_payload["synthesis_skipped_reason"] == "Need at least 2 successful bot(s) before synthesis; got 1."


def test_fallback_bot_provides_synthesis_when_quorum_is_not_met(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        second = runner.invoke(app, ["bots", "create", "Writer Bot", "--role", "Writing"])

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            if workspace_name == writer_id:
                raise RuntimeError("writer bot offline")
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once):
            orchestrate_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--bot", research_id, "--bot", writer_id,
                    "--message", "launch", "--json", "--min-successful-bots", "2",
                    "--fallback-bot", research_id,
                ],
            )
            assert orchestrate_result.exit_code == 0, orchestrate_result.stdout
            payload = json.loads(orchestrate_result.stdout)
            assert payload["synthesis_fallback_bot"] == research_id
            assert payload["synthesis"].startswith(f"{research_id}:")
            assert payload["synthesis_skipped_reason"] is None


def test_multi_bot_commands_can_write_json_artifacts(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research", "--tag", "analysis"])
        second = runner.invoke(app, ["bots", "create", "Writer Bot", "--role", "Writing", "--tag", "analysis"])

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        async def _fake_synthesize(config, user_message, results):
            return f"synth:{user_message}:{','.join(item['id'] for item in results)}"

        compare_out = tmp_path / "compare.json"
        orchestrate_out = tmp_path / "orchestrate.json"
        team_out = tmp_path / "team.json"

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once), \
             patch("nanobot.cli.commands._synthesize_bot_results", side_effect=_fake_synthesize):
            compare_result = runner.invoke(
                app,
                [
                    "bots", "compare", research_id, writer_id, "--message", "brief",
                    "--output-json", str(compare_out),
                ],
            )
            assert compare_result.exit_code == 0, compare_result.stdout
            compare_payload = json.loads(compare_out.read_text(encoding="utf-8"))
            assert [item["id"] for item in compare_payload] == [research_id, writer_id]

            orchestrate_result = runner.invoke(
                app,
                [
                    "bots", "orchestrate", "--bot", research_id, "--bot", writer_id,
                    "--message", "launch", "--output-json", str(orchestrate_out),
                ],
            )
            assert orchestrate_result.exit_code == 0, orchestrate_result.stdout
            orchestrate_payload = json.loads(orchestrate_out.read_text(encoding="utf-8"))
            assert orchestrate_payload["summary"] == {"total": 2, "ok": 2, "error": 0, "timeout": 0}
            assert orchestrate_payload["synthesis"] == f"synth:launch:{research_id},{writer_id}"

            team_create = runner.invoke(
                app,
                ["bots", "team", "create", "analysis-team", "--tag", "analysis"],
            )
            assert team_create.exit_code == 0, team_create.stdout

            team_run = runner.invoke(
                app,
                [
                    "bots", "team", "run", "analysis-team", "--message", "campaign",
                    "--output-json", str(team_out),
                ],
            )
            assert team_run.exit_code == 0, team_run.stdout
            team_payload = json.loads(team_out.read_text(encoding="utf-8"))
            assert team_payload["team_id"] == "analysis-team"
            assert team_payload["summary"] == {"total": 2, "ok": 2, "error": 0, "timeout": 0}


def test_json_mode_stays_machine_readable_when_exiting_nonzero_or_writing_artifacts(tmp_path):
    config_path = tmp_path / "instance" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    with patched_config_paths(config_path):
        first = runner.invoke(app, ["bots", "create", "Research Bot", "--role", "Research"])
        second = runner.invoke(app, ["bots", "create", "Writer Bot", "--role", "Writing"])

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout

        registry = json.loads(get_registry_path().read_text(encoding="utf-8"))
        research_id = registry["bots"][0]["id"]
        writer_id = registry["bots"][1]["id"]

        async def _fake_run_agent_once(config, message, session_id, *, logs=False):
            workspace_name = Path(config.agents.defaults.workspace).name
            if workspace_name == writer_id:
                raise RuntimeError("writer bot offline")
            return OutboundMessage(
                channel="cli",
                chat_id="direct",
                content=f"{workspace_name}:{session_id}:{message}:{logs}",
                metadata={"render_as": "text"},
            )

        compare_out = tmp_path / "compare.json"
        team_out = tmp_path / "team.json"

        with patch("nanobot.cli.commands._run_agent_once", side_effect=_fake_run_agent_once):
            compare_result = runner.invoke(
                app,
                [
                    "bots", "compare", research_id, writer_id, "--message", "brief", "--json",
                    "--require-all-success", "--output-json", str(compare_out),
                ],
            )
            assert compare_result.exit_code == 1, compare_result.stdout
            compare_payload = json.loads(compare_result.stdout)
            assert [item["status"] for item in compare_payload] == ["ok", "error"]
            assert compare_payload == json.loads(compare_out.read_text(encoding="utf-8"))

            team_create = runner.invoke(
                app,
                ["bots", "team", "create", "strict-json-team", "--bot", research_id, "--bot", writer_id],
            )
            assert team_create.exit_code == 0, team_create.stdout

            team_run = runner.invoke(
                app,
                [
                    "bots", "team", "run", "strict-json-team", "--message", "campaign", "--json",
                    "--require-all-success", "--output-json", str(team_out),
                ],
            )
            assert team_run.exit_code == 1, team_run.stdout
            team_payload = json.loads(team_run.stdout)
            assert team_payload["summary"] == {"total": 2, "ok": 1, "error": 1, "timeout": 0}
            assert team_payload == json.loads(team_out.read_text(encoding="utf-8"))


def test_set_config_path_is_isolated_per_async_task(tmp_path):
    from nanobot.config.loader import get_config_path, set_config_path

    original = get_config_path()
    first_path = tmp_path / "first" / "config.json"
    second_path = tmp_path / "second" / "config.json"

    async def _worker(path: Path) -> Path:
        set_config_path(path)
        await asyncio.sleep(0)
        return get_config_path()

    async def _run() -> tuple[Path, Path]:
        return await asyncio.gather(
            _worker(first_path),
            _worker(second_path),
        )

    first_seen, second_seen = asyncio.run(_run())

    assert first_seen == first_path
    assert second_seen == second_path
    assert get_config_path() == original
