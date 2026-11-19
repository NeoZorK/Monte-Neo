"""Try one fix and show before and after. The fix pays a trial and is never trusted without a full re-verification."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.repair import plan
from monte_neo.repair.findings import FINDINGS
from monte_neo.verify.fixes import suggest_fixes
from monte_neo.verify.ingest import load_ohlcv, load_signal_fn
from monte_neo.verify.limits import read_source

NOTE = "The after-numbers come from a full re-verification that counted this fix as one more trial; a fix never raises a verdict by itself."


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    m = report.get("metrics", {})
    return {"verdict": report["verdict"], "failed": [c["id"] for c in report["checks"] if c["status"] == "fail"],
            "total_return": m.get("total_return"), "sharpe": m.get("sharpe_annualized"), "deflated_sharpe": m.get("deflated_sharpe")}


def preview_fix(
    finding: str, ohlcv: str | Path | pd.DataFrame, strategy: str | Path, *, model: ExecutionModel | None = None, n_trials: int | None = None,
) -> dict[str, Any]:
    """Apply the fix of ``finding`` (``F01`` ...) and return before/after. ``manual`` findings return what you must do instead."""
    from monte_neo.verify import verify_strategy
    from monte_neo.verify.verdict import _default_model  # the model verify itself would use

    if finding not in FINDINGS:
        raise ValueError(f"unknown finding {finding!r}; choose one of {', '.join(FINDINGS)}")
    f = FINDINGS[finding]
    if f["fix"] == "manual":
        return {"finding": finding, "title": f["title"], "applied": False, "reason": "no automatic fix is honest here", "next_actions": f["next"]}
    spec = str(strategy)
    path = spec.rsplit(":", 1)[0] if ":" in spec and not Path(spec).exists() else spec
    source = read_source(Path(path))
    fn, _ = load_signal_fn(spec)
    df = load_ohlcv(ohlcv)
    base_trials = int(n_trials or 1)
    base_model = model or _default_model(len(df))
    before = verify_strategy(df, signal_fn=fn, source=source, model=base_model, n_trials=base_trials, probe_checks=12)
    paid = base_trials + 1
    diff, after_fn, after_src, after_model, after_trials = "", fn, source, base_model, paid
    kind, p = f["fix"], f["params"]
    if kind == "source":
        patch = suggest_fixes(source)
        if not patch["changes"]:
            return {"finding": finding, "title": f["title"], "applied": False, "reason": "the leak is not in a pattern the causal rewriter knows: fix it by hand", "next_actions": f["next"]}
        diff, after_src = patch["diff"], patch["patched"]
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "patched.py"
            target.write_text(after_src, encoding="utf-8")
            after_fn, _ = load_signal_fn(str(target))
            after = verify_strategy(df, signal_fn=after_fn, source=after_src, model=base_model, n_trials=after_trials, probe_checks=12)
    else:
        if kind == "steps":
            steps = [(n, dict(kw)) for n, kw in p["steps"]]
            after_fn = plan.apply_steps(fn, steps)
            diff = f"+ transform(s): {steps}\n"
        elif kind == "costs":
            after_model = replace(base_model, commission_bps=max(base_model.commission_bps, p["commission_bps"]), slippage_bps=max(base_model.slippage_bps, p["slippage_bps"]))
            diff = f"- commission {base_model.commission_bps} bps, slippage {base_model.slippage_bps} bps\n+ commission {after_model.commission_bps} bps, slippage {after_model.slippage_bps} bps\n"
        else:  # trials
            after_trials = max(paid, int(p["n_trials"]))
            diff = f"- n_trials {base_trials}\n+ n_trials {after_trials} (assumed: the real count must come from your ledger or tracker)\n"
        after = verify_strategy(df, signal_fn=after_fn, source=after_src if kind == "source" else source, model=after_model, n_trials=after_trials, probe_checks=12)
    return {"finding": finding, "title": f["title"], "kind": kind, "applied": True, "diff": diff, "before": _summary(before), "after": _summary(after),
            "trials": {"before": base_trials, "after": after_trials}, "note": NOTE}
