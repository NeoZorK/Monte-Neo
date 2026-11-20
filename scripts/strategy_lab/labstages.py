"""Stages of the Strategy Lab: prepare -> discovery -> validation -> (freeze, by hand) -> holdout. Each returns a JSON-able record."""

from __future__ import annotations

import json
import subprocess
import threading
from datetime import UTC, datetime
from typing import Any

import labcore as lc
import labecon
import numpy as np
import pandas as pd

_REG_LOCK = threading.Lock()  # the registry chain is not thread-safe: one registration at a time
ACCEPT = ("PASS", "PASS_WITH_WARNINGS")  # what "passes all gates" means in the final holdout certificate


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=lc.ROOT)


def stage_prepare(name: str, threads: int = 1) -> dict[str, Any]:
    """Write the data slices and register the hypothesis (written down BEFORE any test)."""
    from monte_neo.verify.register import Registry

    mod = lc.load_module(name)
    info = lc.prepare(name)
    src = (lc.STRATS / name / "strategy.py").read_text()
    card = (lc.STRATS / name / "card.md").read_text() if (lc.STRATS / name / "card.md").exists() else mod.META["title"]
    reg = Registry(lc.MNDIR / ".monte-neo" / "registrations.jsonl")
    with _REG_LOCK:
        entry = _register(reg, mod, card, src)
    return {"slices": info, "registration": entry["id"], "planned_trials": lc.lab_trials()}


def _register(reg, mod, card: str, src: str) -> dict[str, Any]:
    return reg.register(f"{mod.META['title']}: {card.splitlines()[0] if card else ''}", source=src, params=mod.META["params"], n_trials=lc.lab_trials())


def _registration(name: str) -> list[str]:
    p = lc.RES / name / "prepare.json"
    return ["--registration", json.loads(p.read_text())["registration"]] if p.exists() and lc.load_module(name).META["kind"] == "verify" else []


def _sharpe(r: np.ndarray) -> float:
    return float(np.mean(r) / np.std(r) * np.sqrt(lc.PPY)) if len(r) > 2 and np.std(r) > 0 else float("nan")


def stage_discovery(name: str, threads: int = 1) -> dict[str, Any]:
    """Declared parameter grid on discovery data only: plateau, walk-forward, trials counted. Candidate params stay the a-priori ones."""
    mod = lc.load_module(name)
    meta, grid = mod.META, lc.combos(mod.META["grid"])
    if meta["kind"] == "verify":
        rec = lc.run_verify(name, "disc", len(grid), ["--grid", json.dumps(meta["grid"]), "--folds", "4", *_registration(name)], threads, "disc", html=False)
        return {**rec, "grid_size": len(grid)}
    table = []
    if meta["kind"] == "returns":
        pan = lc.panel(meta, lc.VAL_START)
        for g in grid:
            r = mod.returns(pan, **{**meta["params"], **g})
            table.append({**g, "sharpe": round(_sharpe(r.to_numpy()), 3)})
    rec = lc.run_verify(name, "disc", len(grid), [], threads, "disc", html=False)
    return {**rec, "grid_size": len(grid), "grid_sharpes": table}


def _brief(r: subprocess.CompletedProcess) -> dict[str, Any]:
    """Verdict and one line per check of a monte-neo JSON answer (never the raw output)."""
    try:
        d = json.loads(r.stdout)
        return {"exit_code": r.returncode, "verdict": d["verdict"], "certificate_id": d.get("certificate_id"),
                "checks": [f"{c['id']} [{c['status']}]: {c['summary']}" for c in d["checks"]]}
    except (ValueError, KeyError):
        return {"exit_code": r.returncode, "verdict": "ERROR", "checks": [(r.stderr or r.stdout)[-400:]]}


def edge(rec: dict[str, Any]) -> float:
    """Sharpe for return and signal certificates, the IC t-statistic for cross-sectional scores."""
    v = rec.get("sharpe") if rec.get("sharpe") is not None else rec.get("ic_t_stat")
    return float(v) if v is not None else 0.0


def passes(rec: dict[str, Any], kind: str) -> bool:
    """All gates of the final (holdout) certificate. Signal files: verdict PASS/PASS_WITH_WARNINGS and ARL >= 6 (survives the search).
    Return series (carry, pairs) cannot reach ARL > 3 by construction: they need PASS-class verdict, deflated Sharpe >= 0.95,
    and for pairs a passing legs check and null test."""
    ok = rec["verdict"] in ACCEPT and edge(rec) > 0
    if kind == "verify":
        return bool(ok and rec["arl"] >= 6)
    if kind == "alpha":
        return bool(ok and rec["arl"] >= 6)
    pair = rec.get("pair")
    pair_ok = pair is None or all(pair[k]["verdict"] in ACCEPT for k in ("legs", "null_test", "pairs_checks"))
    return bool(ok and (rec.get("deflated_sharpe") or 0) >= 0.95 and pair_ok)


def pair_checks(name: str, tag: str, threads: int) -> dict[str, Any]:
    """Pair-specific gates: legs P&L re-derivation and the random-walk null test. Their output is stored as is."""
    mod = lc.load_module(name)
    w, out = lc.work(name), {}
    cut = lc.SLICES[tag]
    pd.DataFrame(mod.legs(lc.panel(mod.META, cut), **mod.META["params"])).to_csv(w / f"legs_{tag}.csv", index=False, float_format="%.10g")
    r = lc.mn("verify", "--legs", str(w / f"legs_{tag}.csv"), "--format", "json", threads=threads)
    out["legs"] = _brief(r)
    # econometric pairs checks (cointegration, ADF/KPSS, half-life, breaks) live on branch x/laughing-morse-208e19: use them when this CLI has them
    if "--pairs-checks" in lc.mn("verify", "--help").stdout:
        out["pairs_checks"] = _brief(lc.mn("verify", "--legs", str(w / f"legs_{tag}.csv"), "--pairs-checks", "--format", "json", threads=threads))
    else:
        out["pairs_checks"] = {"verdict": "NOT_AVAILABLE", "checks": ["cointegration, ADF/KPSS, half-life and break tests are not in this build of Monte-Neo (branch x/laughing-morse-208e19, not merged): the pair is NOT econometrically verified"]}
    r = lc.mn("verify", "--null-test", f"{lc.STRATS / name / 'strategy.py'}:pnl", "--null-paths", "100", "--null-bars", "3000", "--periods-per-year", str(lc.PPY),
              "--format", "json", threads=threads)
    out["null_test"] = _brief(r)
    return out


def stage_validation(name: str, threads: int = 1) -> dict[str, Any]:
    """The a-priori candidate on everything before the holdout, with the Lab-wide trial count. Gate: not REJECT and Sharpe > 0."""
    mod = lc.load_module(name)
    rec = lc.run_verify(name, "pre", lc.lab_trials(), _registration(name), threads, "pre")
    if mod.META.get("pair"):
        rec["pair"] = pair_checks(name, "pre", threads)
    rec["economics"] = labecon.economics(name, lc.lab_trials())
    ev = rec["economics"]
    survives_cost = all(v is None or v > 0 for v in (ev.get("validation", {}).get("sharpe"), ev.get("cost_x2_sharpe_validation")))
    rec["gate_open"] = bool(rec["verdict"] != "REJECT" and edge(rec) > 0 and survives_cost)  # also: positive net Sharpe with the costs doubled
    if mod.META.get("pair") and rec["pair"]["pairs_checks"]["verdict"] not in ACCEPT:
        rec["gate_open"] = False  # a pair is not verified without the econometric checks (cointegration, stationarity, half-life)
    return rec


def frozen_ok(name: str) -> dict[str, Any]:
    """The candidate must be frozen in a git commit BEFORE the holdout is read: frozen.json tracked, unmodified, hash matching."""
    f = lc.RES / name / "frozen.json"
    if not f.exists():
        raise RuntimeError(f"{name}: not frozen. Run: python scripts/strategy_lab/freeze.py {name}  then git commit")
    rel = str(f.relative_to(lc.ROOT))
    spath = str((lc.STRATS / name / "strategy.py").relative_to(lc.ROOT))
    if git("ls-files", "--error-unmatch", rel, spath).returncode != 0:
        raise RuntimeError(f"{name}: frozen.json or strategy.py is not committed")
    if git("diff", "--quiet", "HEAD", "--", rel, spath).returncode != 0 or git("status", "--porcelain", "--", f"examples/strategies/{name}").stdout.strip() != "":
        raise RuntimeError(f"{name}: strategy or frozen.json changed since the freeze commit")
    fr = json.loads(f.read_text())
    if fr["strategy_sha256"] != lc.sha256_file(lc.STRATS / name / "strategy.py"):
        raise RuntimeError(f"{name}: strategy.py differs from the frozen hash")
    fr["commit"] = git("log", "-1", "--format=%H", "--", rel).stdout.strip()
    return fr


def stage_holdout(name: str, threads: int = 1) -> dict[str, Any]:
    """Open the sealed holdout for the frozen candidate. The opening is logged first; a different candidate can never re-open it."""
    fr = frozen_ok(name)
    mod = lc.load_module(name)
    log = lc.RES / name / "holdout_opening.json"
    prev = json.loads(log.read_text()) if log.exists() else None
    if prev and prev["strategy_sha256"] != fr["strategy_sha256"]:
        raise RuntimeError(f"{name}: the holdout was already opened for another candidate; it is burnt")
    log.write_text(json.dumps({"at": now(), "strategy_sha256": fr["strategy_sha256"], "freeze_commit": fr["commit"], "opens": (prev or {}).get("opens", 0) + 1}, indent=1))
    rec = lc.run_verify(name, "full", lc.lab_trials(), _registration(name), threads, "full")
    rec["freeze_commit"] = fr["commit"]
    if mod.META["kind"] == "verify":  # Thresholdout oracle: is the holdout result consistent with the training result?
        from monte_neo.verify import load_ohlcv
        from monte_neo.verify.oracle import HoldoutOracle

        df = load_ohlcv(lc.work(name) / "ohlcv_full.parquet")
        frac = float((df["timestamp"] >= lc.HOLD_START).mean())
        orc = HoldoutOracle(lc.work(name) / "oracle.jsonl")
        if not orc.log.entries():
            orc.init(df, holdout=min(max(frac, 0.05), 0.5), budget=1)
        rec["oracle"] = orc.query(df, str(lc.STRATS / name / "strategy.py"))
    if mod.META.get("pair"):
        rec["pair"] = pair_checks(name, "full", threads)
    rec["passes_all_gates"] = passes(rec, mod.META["kind"])
    return rec


STAGES = {"prepare": stage_prepare, "discovery": stage_discovery, "validation": stage_validation, "holdout": stage_holdout}
