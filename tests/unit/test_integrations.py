"""Agent integration files stay in sync with the package."""

from __future__ import annotations

import json
import subprocess
import sys
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


HOOK = INTEG / "claude-code" / "hooks" / "remind_verify.py"


def _hook(payload: str, tmp_path: Path) -> str:
    env = {"TMPDIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, env=env, check=True).stdout


def test_plugin_hook_config() -> None:
    hooks = json.loads((INTEG / "claude-code" / "hooks" / "hooks.json").read_text())
    entry = hooks["hooks"]["PostToolUse"][0]
    assert entry["matcher"] == "Write|Edit"
    assert "${CLAUDE_PLUGIN_ROOT}/hooks/remind_verify.py" in entry["hooks"][0]["command"]


def test_reminder_hook(tmp_path: Path) -> None:
    strat = tmp_path / "strat.py"
    strat.write_text("def signal(df):\n    return df.close * 0\n")
    other = tmp_path / "util.py"
    other.write_text("x = 1\n")
    payload = json.dumps({"session_id": "s/1", "tool_input": {"file_path": str(strat)}})
    out = json.loads(_hook(payload, tmp_path))
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "verify_strategy" in out["hookSpecificOutput"]["additionalContext"]
    assert _hook(payload, tmp_path) == ""  # once per file per session
    assert _hook(json.dumps({"tool_input": {"file_path": str(other)}}), tmp_path) == ""
    assert _hook(json.dumps({"tool_input": {"file_path": str(tmp_path / "x.txt")}}), tmp_path) == ""
    assert _hook("not json", tmp_path) == ""


def test_mcp_registry_server_json() -> None:
    server = json.loads((ROOT / "server.json").read_text())
    assert server["version"] == PKG_VERSION
    pkg = server["packages"][0]
    assert (pkg["registryType"], pkg["identifier"], pkg["version"]) == ("pypi", "monte-neo", PKG_VERSION)
    assert pkg["packageArguments"] == [{"type": "positional", "value": "mcp"}]
    assert f"mcp-name: {server['name']}" in (ROOT / "README.md").read_text()
    # Registry validation limits (422 otherwise)
    assert len(server["description"]) <= 100
