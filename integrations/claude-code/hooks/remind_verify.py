"""PostToolUse hook: remind the agent to verify after editing strategy / backtest code.

Reads the hook JSON on stdin. When the edited Python file looks like trading
strategy or backtest code, prints hook JSON whose ``additionalContext`` asks the
agent to run the Monte-Neo verifier. Reminds once per file per session and never
blocks the edit.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

PATTERN = re.compile(r"def\s+signal\s*\(|backtest|sharpe|drawdown|equity_curve", re.IGNORECASE)
REMINDER = (
    "This file looks like trading strategy or backtest code. Before reporting any performance, "
    "verify it with the monte-neo MCP server: verify_strategy (or verify_grid if you tuned parameters) "
    "with the OHLCV file and this strategy, honest n_trials and realistic costs. "
    "Report the verdict and certificate_id, not your own backtest numbers."
)


def _marker(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "default")
    return Path(tempfile.gettempdir()) / f"monte-neo-reminded-{safe}.txt"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_input = payload.get("tool_input") or {}
    path = str(tool_input.get("file_path") or "")
    if not path.endswith(".py") or not os.path.isfile(path):
        return 0
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    if not PATTERN.search(text):
        return 0
    marker = _marker(str(payload.get("session_id") or ""))
    seen = set(marker.read_text(encoding="utf-8").splitlines()) if marker.is_file() else set()
    if path in seen:
        return 0
    with marker.open("a", encoding="utf-8") as fh:
        fh.write(path + "\n")
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": REMINDER}}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
