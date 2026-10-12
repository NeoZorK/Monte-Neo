"""``repair_strategy``: repair defects without overfitting, and say so when nothing is left to repair.

Protocol:

1. **Diagnose** the original on all the data (``verify_strategy``).
2. **Stop** on defects no transform can honestly repair (bad data, survivorship, outside data, a model fitted on the
   whole file...): ``NOT_REPAIRABLE``, with what the person must do.
3. **Correct** look-ahead and repainting first: causal rewrites of the source (``suggest_fix``) and a one-bar delay.
   They have no parameters, so there is nothing to choose. If the leak remains, ``NOT_REPAIRABLE``.
4. **Choose** among a few declared repairs on the first ``dev_fraction`` of the history only, by the number of
   defects left (fail 3, warn 1), never by return. Every candidate counts as a trial.
5. **Open the lockbox once**: the chosen version on the rest of the history. ``REPAIRED`` only when it earns there
   after costs; otherwise ``REPAIRED_NO_EDGE``: the defects are gone and so is the profit. A strategy without a
   defect the catalogue addresses is ``NOTHING_TO_REPAIR`` and is not touched.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo import disclaimer
from monte_neo._version import __version__
from monte_neo.backtest.model import ExecutionModel
from monte_neo.repair import plan
from monte_neo.verify.fixes import suggest_fixes
from monte_neo.verify.ingest import load_ohlcv, load_signal_fn
from monte_neo.verify.limits import read_source

REPAIR_SCHEMA_ID = "repair-report/1"
OUTCOMES = ("REPAIRED", "REPAIRED_NO_EDGE", "NOT_REPAIRABLE", "NOTHING_TO_REPAIR")
WEIGHT = {"fail": 3, "warn": 1}
SCORED = ("economics", "statistics")


def _defects(report: dict[str, Any]) -> int:
    return sum(WEIGHT.get(c["status"], 0) for c in report["checks"] if c["category"] in SCORED)


def _bad(report: dict[str, Any], status: str = "fail") -> list[str]:
    return [c["id"] for c in report["checks"] if c["status"] == status]


def _fn_from_source(source: str, func: str, name: str) -> Any:
    namespace: dict[str, Any] = {"__name__": f"_mn_repair_{name}"}
    exec(compile(source, f"<{name}>", "exec"), namespace)  # noqa: S102 - the user's own strategy, as verify runs it
    return namespace[func]


def _split(df: pd.DataFrame, fraction: float) -> pd.Timestamp:
    stamps = pd.to_datetime(df["timestamp"]) if "timestamp" in df.columns else pd.Series(pd.RangeIndex(len(df)))
    unique = np.sort(stamps.unique())
    return unique[int(len(unique) * fraction)]


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    m = report.get("metrics", {})
    return {"certificate_id": report.get("certificate_id"), "verdict": report["verdict"], "failed": _bad(report),
            "warned": _bad(report, "warn"), "total_return": m.get("total_return"), "sharpe": m.get("sharpe_annualized"),
            "deflated_sharpe": m.get("deflated_sharpe")}


def repair_strategy(
    ohlcv: str | Path | pd.DataFrame,
    strategy: str | Path,
    *,
    out_dir: str | Path = "repair",
    model: ExecutionModel | None = None,
    n_trials: int | None = None,
    budget: int = 24,
    dev_fraction: float = 0.7,
    rebalance_every: int | None = None,
) -> dict[str, Any]:
    """Repair a strategy file; write ``strategy.repaired.py``, ``repair.diff`` and ``repair-report.json`` to ``out_dir``.

    Args:
        ohlcv: Prices (table or file), as for ``verify``.
        strategy: ``file.py[:func]``; the file is never modified.
        out_dir: Folder for the results.
        model: Execution model (costs); default as in ``verify``.
        n_trials: Variants tried before the repair (the repair adds its own candidates to this count).
        budget: Maximum number of candidate repairs tried.
        dev_fraction: Share of the history used to choose a repair; the rest is the lockbox, opened once.
        rebalance_every: The strategy rebalances every this many bars: also try staggered tranches.

    Returns:
        A ``repair-report/1`` dict with the outcome.
    """
    from monte_neo.verify import verify_strategy

    if not 0.5 <= dev_fraction <= 0.9:
        raise ValueError("dev_fraction must be between 0.5 and 0.9")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    spec = str(strategy)
    path, func = (spec.rsplit(":", 1) if ":" in spec and not Path(spec).exists() else (spec, "signal"))
    original_source = read_source(Path(path))
    fn, _ = load_signal_fn(spec)
    df = load_ohlcv(ohlcv)
    base = verify_strategy(df, signal_fn=fn, source=original_source, model=model, n_trials=n_trials, probe_checks=12)
    report: dict[str, Any] = {"schema": REPAIR_SCHEMA_ID, "engine_version": __version__, "strategy": Path(path).name,
                              "original": _summary(base), "corrections": [], "candidates": [], "chosen": None,
                              "not_repairable": [], "disclaimer": disclaimer.SHORT}
    blocked = [f"{cid}: {plan.NOT_REPAIRABLE[cid]}" for cid in _bad(base) if cid in plan.NOT_REPAIRABLE]
    if blocked:
        return _finish(report, "NOT_REPAIRABLE", out, blocked=blocked)

    source, base_steps = original_source, []
    if set(_bad(base)) & plan.LOOKAHEAD:
        fixed = suggest_fixes(original_source)
        if not fixed["changes"]:
            return _finish(report, "NOT_REPAIRABLE", out, blocked=["look-ahead: the leak is not in a pattern the causal rewriter knows; fix it by hand"])
        source = fixed["patched"]
        report["corrections"] += [{"id": "R1", "rule": c.get("rule"), "line": c.get("line"), "why": f"{c.get('before')} -> {c.get('after')}: {c.get('note')}"} for c in fixed["changes"]]
    if set(_bad(base)) & plan.REPAINT:
        base_steps = [("delay", {"bars": 1})]
        report["corrections"].append({"id": "R2", "rule": "delay", "why": "the signal changed after it was shown: act one bar later"})
    fn = plan.apply_steps(_fn_from_source(source, func, "corrected"), base_steps)

    if report["corrections"]:
        corrected = verify_strategy(df, signal_fn=fn, source=source, model=model, n_trials=n_trials, probe_checks=12)
        left = set(_bad(corrected)) & (plan.LOOKAHEAD | plan.REPAINT)
        if left:
            return _finish(report, "NOT_REPAIRABLE", out, blocked=[f"{i}: still fails after the causal rewrite" for i in sorted(left)])
        base = corrected

    if not report["corrections"] and not plan.candidates(base["checks"], rebalance_every, budget):
        report["final"] = _summary(base)
        return _finish(report, "NOTHING_TO_REPAIR", out)
    cut = _split(df, dev_fraction)
    stamps = pd.to_datetime(df["timestamp"]) if "timestamp" in df.columns else pd.Series(pd.RangeIndex(len(df)))
    dev, lockbox_rows = df[stamps < cut].reset_index(drop=True), np.asarray(stamps >= cut)
    options = plan.candidates(base["checks"], rebalance_every, budget)
    trials = int(n_trials or 1) + len(options) + 1
    quick = {"model": model, "n_trials": trials, "probe_checks": 4, "repaint": "off"}
    baseline = verify_strategy(dev, signal_fn=fn, **quick)
    best, best_score = None, _defects(baseline)
    for cand in options:
        rep = verify_strategy(dev, signal_fn=plan.apply_steps(fn, cand["steps"]), **quick)
        score = _defects(rep)
        report["candidates"].append({**cand, "dev_defects": score, "dev_verdict": rep["verdict"]})
        if score < best_score or (best is not None and score == best_score and len(cand["steps"]) < len(best["steps"])):
            best, best_score = cand, score
    report["dev"] = {"until": str(cut), "baseline_defects": _defects(baseline), "chosen_defects": best_score, "trials": trials}

    steps = base_steps + (best["steps"] if best else [])
    report["chosen"] = best
    repairs = [f"{c['id']} {c['rule']}: {c['why']}" for c in report["corrections"]] + ([f"{best['id']}: {best['why']} -> {best['steps']}"] if best else [])
    text = plan.repaired_source(source, func, steps, {"version": __version__, "name": Path(path).name, "repairs": repairs})
    target = out / "strategy.repaired.py"
    target.write_text(text, encoding="utf-8")
    (out / "repair.diff").write_text("".join(difflib.unified_diff(original_source.splitlines(True), text.splitlines(True), Path(path).name, target.name)), encoding="utf-8")

    repaired_fn, _ = load_signal_fn(str(target))
    final = verify_strategy(df, strategy=str(target), model=model, n_trials=trials)
    (out / "certificate.json").write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")
    positions = np.asarray(repaired_fn(df.copy()), dtype=float).reshape(-1)
    lock_df = df[lockbox_rows].reset_index(drop=True)
    lock = verify_strategy(lock_df, signals=positions[lockbox_rows], model=model, n_trials=trials, probe_checks=4)
    report["final"], report["lockbox"] = _summary(final), {**_summary(lock), "from": str(cut), "opened": 1}
    net = next((c for c in lock["checks"] if c["id"] == "net_profitability"), {"status": "fail"})
    # Confirmed only when the whole-history certificate passes and the untouched lockbox still earns after costs.
    earns = net["status"] in ("pass", "warn") and lock["verdict"] != "REJECT" and final["verdict"] in ("PASS", "PASS_WITH_WARNINGS")
    return _finish(report, "REPAIRED" if earns else "REPAIRED_NO_EDGE", out)


def _finish(report: dict[str, Any], outcome: str, out: Path, blocked: list[str] | None = None) -> dict[str, Any]:
    report["outcome"] = outcome
    report["not_repairable"] = blocked or []
    report["headline"] = {
        "REPAIRED": "Defects repaired; the edge is confirmed once on the lockbox.",
        "REPAIRED_NO_EDGE": "Defects repaired, and no edge is left: the profit was in the defect.",
        "NOT_REPAIRABLE": "Not repairable automatically: see what is needed from you.",
        "NOTHING_TO_REPAIR": "No defect the repair catalogue addresses: the strategy is left as it is.",
    }[outcome]
    (out / "repair-report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


__all__ = ["OUTCOMES", "REPAIR_SCHEMA_ID", "repair_strategy"]
