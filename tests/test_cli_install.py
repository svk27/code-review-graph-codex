from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import pytest

from code_review_graph.cli import main

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib


def _run_cli(*args: str) -> None:
    main(list(args))


def test_install_default_still_targets_claude(tmp_path, capsys):
    _run_cli("install", "--repo", str(tmp_path))

    mcp_path = tmp_path / ".mcp.json"
    codex_path = tmp_path / ".codex" / "config.toml"

    assert mcp_path.exists()
    assert not codex_path.exists()

    config = mcp_path.read_text()
    assert '"code-review-graph"' in config
    assert "Restart Claude Code" in capsys.readouterr().out


def test_install_codex_dry_run(tmp_path, capsys):
    _run_cli("install", "--client", "codex", "--repo", str(tmp_path), "--dry-run")

    output = capsys.readouterr().out
    assert "[dry-run] Would write managed block to" in output
    assert ".codex/config.toml" in output
    assert "AGENTS.md" in output
    assert ".agents/skills/code-review-graph-build-graph/SKILL.md" in output
    assert not (tmp_path / ".codex").exists()
    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / ".agents").exists()


def test_install_codex_on_clean_repo(tmp_path, capsys):
    _run_cli("install", "--client", "codex", "--repo", str(tmp_path))

    output = capsys.readouterr().out
    config_path = tmp_path / ".codex" / "config.toml"
    agents_path = tmp_path / "AGENTS.md"

    assert config_path.exists()
    assert agents_path.exists()
    assert "Restart Codex or start a new session" in output

    config = tomllib.loads(config_path.read_text())
    assert config["mcp_servers"]["code-review-graph"]["command"] == "uvx"
    assert config["mcp_servers"]["code-review-graph"]["args"] == [
        "code-review-graph",
        "serve",
    ]

    agents_text = agents_path.read_text()
    assert "<!-- BEGIN code-review-graph managed block -->" in agents_text
    assert "$code-review-graph-build-graph" in agents_text

    for skill_name in (
        "code-review-graph-build-graph",
        "code-review-graph-review-delta",
        "code-review-graph-review-pr",
    ):
        skill_path = tmp_path / ".agents" / "skills" / skill_name / "SKILL.md"
        assert skill_path.exists()
        assert skill_name in skill_path.read_text()


def test_install_codex_is_idempotent(tmp_path, capsys):
    _run_cli("install", "--client", "codex", "--repo", str(tmp_path))
    first_config = (tmp_path / ".codex" / "config.toml").read_text()
    first_agents = (tmp_path / "AGENTS.md").read_text()
    capsys.readouterr()

    _run_cli("install", "--client", "codex", "--repo", str(tmp_path))
    output = capsys.readouterr().out
    config_text = (tmp_path / ".codex" / "config.toml").read_text()
    agents_text = (tmp_path / "AGENTS.md").read_text()

    assert "Already configured in" in output
    assert config_text == first_config
    assert agents_text == first_agents
    assert config_text.count("[mcp_servers.code-review-graph]") == 1
    assert agents_text.count("<!-- BEGIN code-review-graph managed block -->") == 1


def test_install_all_writes_both_client_configs(tmp_path):
    _run_cli("install", "--client", "all", "--repo", str(tmp_path))

    assert (tmp_path / ".mcp.json").exists()
    assert (tmp_path / ".codex" / "config.toml").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_invalid_existing_codex_config_fails_safely(tmp_path, capsys):
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("[mcp_servers\nbroken = true\n")

    with pytest.raises(SystemExit) as exc:
        _run_cli("install", "--client", "codex", "--repo", str(tmp_path))

    assert exc.value.code == 1
    assert "invalid TOML" in capsys.readouterr().err
    assert config_path.read_text() == "[mcp_servers\nbroken = true\n"
    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / ".agents").exists()


def test_agents_block_replacement_preserves_user_content(tmp_path):
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# Team Notes",
                "",
                "Local guidance stays here.",
                "",
                "<!-- BEGIN code-review-graph managed block -->",
                "old block",
                "<!-- END code-review-graph managed block -->",
                "",
                "Closing note.",
            ]
        )
        + "\n"
    )

    _run_cli("install", "--client", "codex", "--repo", str(tmp_path))

    agents_text = agents_path.read_text()
    assert "# Team Notes" in agents_text
    assert "Closing note." in agents_text
    assert "old block" not in agents_text
    assert agents_text.count("<!-- BEGIN code-review-graph managed block -->") == 1


def test_existing_skill_directories_are_preserved(tmp_path, capsys):
    existing_dir = tmp_path / ".agents" / "skills" / "code-review-graph-build-graph"
    existing_dir.mkdir(parents=True)
    existing_skill = existing_dir / "SKILL.md"
    existing_skill.write_text("custom skill\n")

    _run_cli("install", "--client", "codex", "--repo", str(tmp_path))

    output = capsys.readouterr().out
    assert "Skipped existing Codex skill" in output
    assert existing_skill.read_text() == "custom skill\n"
    assert (
        tmp_path
        / ".agents"
        / "skills"
        / "code-review-graph-review-delta"
        / "SKILL.md"
    ).exists()


def test_codex_skill_templates_are_packaged():
    template_root = files("code_review_graph").joinpath("templates", "codex")

    for skill_name in (
        "code-review-graph-build-graph",
        "code-review-graph-review-delta",
        "code-review-graph-review-pr",
    ):
        skill_path = template_root.joinpath(skill_name, "SKILL.md")
        assert skill_path.is_file()
        assert skill_name in skill_path.read_text()
