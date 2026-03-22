"""Installation helpers for Claude Code and Codex integrations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib

Printer = Callable[[str], None]

CLIENT_CHOICES = ("claude", "codex", "all")
_CLAUDE_MCP_SERVER = {
    "code-review-graph": {
        "command": "code-review-graph",
        "args": ["serve"],
    }
}
_CODEX_CONFIG_START = "# BEGIN code-review-graph managed block"
_CODEX_CONFIG_END = "# END code-review-graph managed block"
_AGENTS_BLOCK_START = "<!-- BEGIN code-review-graph managed block -->"
_AGENTS_BLOCK_END = "<!-- END code-review-graph managed block -->"
_SKILL_NAMES = (
    "code-review-graph-build-graph",
    "code-review-graph-review-delta",
    "code-review-graph-review-pr",
)

_CODEX_CONFIG_BLOCK = "\n".join(
    [
        _CODEX_CONFIG_START,
        "[mcp_servers.code-review-graph]",
        'command = "code-review-graph"',
        'args = ["serve"]',
        _CODEX_CONFIG_END,
    ]
)

_AGENTS_MANAGED_BLOCK = "\n".join(
    [
        _AGENTS_BLOCK_START,
        "## code-review-graph",
        "",
        "- If `.code-review-graph/graph.db` exists, prefer the `code-review-graph` MCP tools before broad file scans.",
        "- Use the repo-local skills `$code-review-graph-build-graph`, `$code-review-graph-review-delta`, and `$code-review-graph-review-pr` for graph build and review workflows.",
        "- Before graph-dependent review work, refresh the graph if freshness is uncertain. A running `code-review-graph watch` process is the preferred auto-update path in Codex.",
        "- Fall back to normal file reads only when the graph does not exist yet or the MCP tools cannot answer the task.",
        _AGENTS_BLOCK_END,
    ]
)


class InstallError(RuntimeError):
    """Raised when installation cannot proceed safely."""


def resolve_repo_root(repo: str | None) -> Path:
    """Resolve the target repository root for install/init."""
    if repo:
        return Path(repo)
    from .incremental import find_repo_root

    found = find_repo_root()
    return Path.cwd() if not found else found


def install(
    repo_root: Path,
    client: str = "claude",
    dry_run: bool = False,
    printer: Printer = print,
) -> None:
    """Install client integrations into the repository."""
    if client not in CLIENT_CHOICES:
        raise InstallError(f"Unsupported client: {client}")

    selected = ("claude", "codex") if client == "all" else (client,)

    if "codex" in selected:
        _validate_existing_codex_config(repo_root / ".codex" / "config.toml")

    if "claude" in selected:
        _install_claude(repo_root, dry_run, printer)
    if "codex" in selected:
        _install_codex(repo_root, dry_run, printer)

    if dry_run:
        printer("")
        printer("[dry-run] No files were modified.")
        return

    _print_next_steps(selected, printer)


def _install_claude(repo_root: Path, dry_run: bool, printer: Printer) -> None:
    mcp_path = repo_root / ".mcp.json"
    mcp_config: dict[str, object] = {"mcpServers": dict(_CLAUDE_MCP_SERVER)}

    if mcp_path.exists():
        try:
            existing = json.loads(mcp_path.read_text())
            if "code-review-graph" in existing.get("mcpServers", {}):
                printer(f"Already configured in {mcp_path}")
                return
            existing.setdefault("mcpServers", {}).update(_CLAUDE_MCP_SERVER)
            mcp_config = existing
        except json.JSONDecodeError:
            printer(f"Warning: existing {mcp_path} has invalid JSON, overwriting.")
        except (KeyError, TypeError):
            printer(f"Warning: existing {mcp_path} has unexpected structure, overwriting.")

    if dry_run:
        printer(f"[dry-run] Would write to {mcp_path}:")
        printer(json.dumps(mcp_config, indent=2))
        return

    mcp_path.write_text(json.dumps(mcp_config, indent=2) + "\n")
    printer(f"Created {mcp_path}")


def _install_codex(repo_root: Path, dry_run: bool, printer: Printer) -> None:
    config_path = repo_root / ".codex" / "config.toml"
    agents_path = repo_root / "AGENTS.md"
    skills_root = repo_root / ".agents" / "skills"

    _ensure_codex_config(config_path, dry_run, printer)
    _ensure_agents_guidance(agents_path, dry_run, printer)
    _install_skill_templates(skills_root, dry_run, printer)


def _validate_existing_codex_config(config_path: Path) -> None:
    if not config_path.exists():
        return
    try:
        tomllib.loads(config_path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(
            f"Existing {config_path} has invalid TOML; refusing to overwrite it.\n"
            "Fix the TOML first, then re-run install."
        ) from exc


def _ensure_codex_config(config_path: Path, dry_run: bool, printer: Printer) -> None:
    existing_text = config_path.read_text() if config_path.exists() else ""
    if config_path.exists():
        parsed = tomllib.loads(existing_text)
        existing_servers = parsed.get("mcp_servers", {})
        if "code-review-graph" in existing_servers:
            printer(f"Already configured in {config_path}")
            return

    new_text = _upsert_managed_block(
        existing_text,
        _CODEX_CONFIG_BLOCK,
        _CODEX_CONFIG_START,
        _CODEX_CONFIG_END,
    )

    if dry_run:
        printer(f"[dry-run] Would write managed block to {config_path}:")
        printer(_CODEX_CONFIG_BLOCK)
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(new_text)
    printer(f"Updated {config_path}")


def _ensure_agents_guidance(agents_path: Path, dry_run: bool, printer: Printer) -> None:
    existing_text = agents_path.read_text() if agents_path.exists() else ""
    new_text = _upsert_managed_block(
        existing_text,
        _AGENTS_MANAGED_BLOCK,
        _AGENTS_BLOCK_START,
        _AGENTS_BLOCK_END,
    )

    if new_text == _normalize_trailing_newline(existing_text):
        printer(f"Already configured in {agents_path}")
        return

    if dry_run:
        printer(f"[dry-run] Would write managed block to {agents_path}:")
        printer(_AGENTS_MANAGED_BLOCK)
        return

    agents_path.write_text(new_text)
    printer(f"Updated {agents_path}")


def _install_skill_templates(skills_root: Path, dry_run: bool, printer: Printer) -> None:
    template_root = Path(__file__).resolve().parent / "templates" / "codex"
    for skill_name in _SKILL_NAMES:
        src = template_root / skill_name / "SKILL.md"
        dst_dir = skills_root / skill_name
        dst = dst_dir / "SKILL.md"
        if dst_dir.exists():
            printer(f"Skipped existing Codex skill {dst_dir}")
            continue

        if dry_run:
            printer(f"[dry-run] Would create {dst}")
            continue

        dst_dir.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text())
        printer(f"Created {dst}")


def _upsert_managed_block(existing_text: str, block: str, start_marker: str, end_marker: str) -> str:
    pattern = re.compile(
        rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}\n*",
        flags=re.DOTALL,
    )
    normalized_block = _normalize_trailing_newline(block)
    if pattern.search(existing_text):
        updated = pattern.sub(normalized_block, existing_text, count=1)
        return _normalize_trailing_newline(updated)

    existing = existing_text.rstrip()
    if existing:
        return f"{existing}\n\n{normalized_block}"
    return normalized_block


def _normalize_trailing_newline(text: str) -> str:
    return text.rstrip() + "\n" if text.strip() else ("" if not text else "\n")


def _print_next_steps(selected: tuple[str, ...], printer: Printer) -> None:
    printer("")
    printer("Next steps:")
    printer("  1. code-review-graph build    # build the knowledge graph")
    if "codex" in selected:
        printer("  2. code-review-graph watch    # optional watcher-first auto-update for Codex")
        printer("  3. Restart Codex or start a new session")
    elif "claude" in selected:
        printer("  2. Restart Claude Code        # to pick up the new MCP server")
