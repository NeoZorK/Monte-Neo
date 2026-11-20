"""Freeze a candidate BEFORE the holdout is opened.

    python scripts/strategy_lab/freeze.py NAME      # writes strategy_lab/results/NAME/frozen.json
    git add examples/strategies/NAME strategy_lab/results/NAME/frozen.json && git commit -m "freeze NAME"

The holdout stage refuses to run unless this file is committed, unmodified, and matches strategy.py byte for byte.
Only a candidate whose validation gate is open (verdict not REJECT, Sharpe > 0) can be frozen.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import labcore as lc
from labstages import now


def main() -> int:
    name = sys.argv[1]
    val = lc.RES / name / "validation.json"
    if not val.exists() or not json.loads(val.read_text())["gate_open"]:
        print(f"{name}: validation missing or gate closed: not frozen")
        return 2
    rec = json.loads(val.read_text())
    mod = lc.load_module(name)
    (lc.RES / name / "frozen.json").write_text(json.dumps({
        "name": name, "frozen_at": now(), "strategy_sha256": lc.sha256_file(lc.STRATS / name / "strategy.py"),
        "params": mod.META["params"], "lab_trials": lc.lab_trials(), "validation_certificate": rec["certificate_id"],
        "validation_verdict": rec["verdict"], "idea_author": lc.IDEA_AUTHOR, "process_author": lc.PROCESS_AUTHOR}, indent=1))
    print(f"frozen {name}; now commit examples/strategies/{name} and strategy_lab/results/{name}/frozen.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
