"""Agent integration files stay in sync with the package."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from monte_neo._version import __version__

ROOT = Path(__file__).resolve().parents[2]
INTEG = ROOT / "integrations"
PKG_VERSION = __version__.lstrip("v")


def test_rule_snippets_match_source() -> None:
    rules = (INTEG / "AGENT_RULES.md").read_text(encoding="utf-8")
    assert (INTEG / "codex" / "AGENTS.md").read_text(encoding="utf-8") == rules
    assert (INTEG / "gemini" / "GEMINI.md").read_text(encoding="utf-8") == rules
    assert (INTEG / "cursor" / "rules" / "monte-neo-verify.mdc").read_text(encoding="utf-8").endswith(rules)


def test_manifest_versions_match_package() -> None:
    plugin = json.loads((INTEG / "claude-code" / ".claude-plugin" / "plugin.json").read_text())
    gemini = json.loads((INTEG / "gemini" / "gemini-extension.json").read_text())
    assert plugin["version"] == PKG_VERSION
    assert gemini["version"] == PKG_VERSION


def test_mcp_launch_commands_agree() -> None:
    expected = ["--from", "monte-neo[mcp]>=0.18.0", "monte-neo-mcp"]
    for path in (INTEG / "claude-code" / ".mcp.json", INTEG / "cursor" / "mcp.json", INTEG / "gemini" / "gemini-extension.json"):
        server = json.loads(path.read_text())["mcpServers"]["monte-neo"]
        assert server["command"] == "uvx" and server["args"] == expected, path
    assert '"monte-neo[mcp]>=0.18.0"' in (INTEG / "codex" / "config.toml").read_text()


def test_marketplace_points_at_plugin() -> None:
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    source = market["plugins"][0]["source"]
    assert (ROOT / source / ".claude-plugin" / "plugin.json").is_file()
    skill = (ROOT / source / "skills" / "verify-strategy" / "SKILL.md").read_text()
    assert skill.startswith("---\nname: verify-strategy\n")


def test_github_action_is_valid() -> None:
    action = yaml.safe_load((ROOT / "action.yml").read_text())
    assert action["runs"]["using"] == "composite"
    assert {"ohlcv", "strategy", "signals", "n-trials"} <= set(action["inputs"])
