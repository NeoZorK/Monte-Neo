"""ARL depth: how strongly the evidence at one level is established, 0 to 4 (rules in ``arl_rules_v2.json``).

Each level has four criteria (D1 margin, D2 breadth, D3 sample, D4 out of sample). A criterion scores one point only when
its evidence exists and meets the threshold; a criterion whose evidence was not produced scores 0 and is reported as
``not assessed`` together with the command that would produce it, never as passed. Depth never changes the level.

Invariants enforced here:

* D4 comes only from a sealed holdout (:mod:`monte_neo.verify.sealed_holdout`) that was frozen and opened exactly once;
  if it was opened more than once, D4 is 0 for every level, permanently.
* Levels 4-6 pay for the project's full ``n_trials``: p-values and t-statistics are adjusted by it (Bonferroni, the
  simplest correction, never less strict than the true count), and a Deflated Sharpe computed with fewer trials does not count.
* Level 9 D4 needs real fills (``source=real_fills``) with a custody statement.
"""

from __future__ import annotations

import math
from typing import Any

from monte_neo.arl_rules import load_rules

MET, UNMET, NA = "met", "unmet", "not assessed"
_OPS = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, "<": lambda a, b: a < b}


class Evidence:
    """The rows and numbers the criteria read: certificate, alpha and live reports, the holdout, the trial count."""

    def __init__(self, rows: dict[str, dict[str, Any]], *, metrics: dict[str, dict[str, Any]], holdout: dict[str, Any] | None,
                 n_trials: int, extra: dict[str, Any] | None = None) -> None:
        self.rows = {k: {**v, "details": v.get("details") or {}} for k, v in rows.items()}
        self.metrics, self.holdout, self.n_trials, self.extra = metrics, holdout, max(1, int(n_trials)), extra or {}
        self.hrows = {r["id"]: {**r, "details": r.get("details") or {}} for r in (holdout or {}).get("checks", []) if r.get("status") != "skip"} if holdout and holdout.get("valid") else {}

    def derived(self, name: str) -> float | None:
        m, rows = self.metrics, self.rows
        if name == "years":
            vals = [float(rows["min_backtest_length"]["details"]["years_available"])] if "min_backtest_length" in rows else []
            ds = rows.get("deflated_sharpe", {}).get("details", {})
            if ds.get("n_obs") and ds.get("periods_per_year"):
                vals.append(ds["n_obs"] / ds["periods_per_year"])
            if m.get("alpha", {}).get("n_dates"):
                vals.append(m["alpha"]["n_dates"] / 252.0)
            return max(vals) if vals else None
        if name == "observations":
            vals = [float(rows["deflated_sharpe"]["details"]["n_obs"])] if "deflated_sharpe" in rows and rows["deflated_sharpe"]["details"].get("n_obs") else []
            a = m.get("alpha", {})
            if a.get("n_dates") and a.get("n_symbols"):
                vals.append(float(a["n_dates"] * a["n_symbols"]))
            return max(vals) if vals else None
        if name == "live_span_days":
            v = m.get("live", {}).get("live_span_days")
            return None if v is None else float(v)
        if name == "live_fills":
            v = m.get("live", {}).get("n_fills")
            return None if v is None else float(v)
        if name == "custody":
            return 1.0 if m.get("live", {}).get("custody") else (0.0 if "live" in m and m["live"] else None)
        return None


def _path(obj: Any, key: str) -> Any:
    for part in key.split("."):
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            obj = obj[int(part)] if part.isdigit() and int(part) < len(obj) else None
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def _number(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _row(rule: dict[str, Any], e: Evidence) -> dict[str, Any] | None:
    return (e.hrows if rule.get("holdout") else e.rows).get(rule.get("id", ""))


def _ev(rule: dict[str, Any], e: Evidence) -> tuple[str, str]:
    t = rule["type"]
    if t in ("all", "any"):
        subs = [{**s, "holdout": True} if rule.get("holdout") else s for s in rule["of"]]  # a holdout flag covers the whole group
        parts = [(_ev(s, e), s) for s in subs]
        if t == "all":
            parts = [((MET, "optional, not run") if s.get("optional") and st == NA else (st, w), s) for (st, w), s in parts]
            bad = next((w for (st, w), _ in parts if st == UNMET), None)
            if bad:
                return UNMET, bad
            miss = next((w for (st, w), _ in parts if st == NA), None)
            return (NA, miss) if miss else (MET, "all parts hold")
        good = next((w for (st, w), _ in parts if st == MET), None)
        if good:
            return MET, good
        bad = next((w for (st, w), _ in parts if st == UNMET), None)
        return (UNMET, bad) if bad else (NA, next(w for (_, w), _ in parts))
    if t == "holdout_valid":
        h = e.holdout
        if h is None:
            return NA, "no sealed holdout was given"
        return (MET, "frozen and opened once") if h.get("valid") else (UNMET, h.get("reason") or "the holdout is not valid")
    if t == "evidence":
        return (MET, f"{rule['key']} given") if e.extra.get(rule["key"]) else (NA, f"{rule['key']} was not produced")
    if t == "derived":
        v = e.derived(rule["name"])
        if v is None:
            return NA, f"{rule['name']} is not known"
        ok = _OPS[rule["op"]](v, rule["value"])
        return (MET if ok else UNMET), f"{rule['name']} {v:g} {'meets' if ok else 'is below'} {rule['value']:g}"
    if t == "between":
        v = _number(_path({"live": e.metrics.get("live", {})}, rule["value"]))
        lo = _number(_path({"cert": e.metrics.get("cert", {})}, rule["lo"]))
        hi = _number(_path({"cert": e.metrics.get("cert", {})}, rule["hi"]))
        if v is None or lo is None or hi is None:
            return NA, "live Sharpe or the backtest interval is missing"
        return (MET if lo <= v <= hi else UNMET), f"live Sharpe {v:.2f}, backtest interval {lo:.2f}..{hi:.2f}"
    if t == "trials_declared":
        row = e.rows.get("trial_ledger")
        if row is None:
            return NA, "no trial ledger"
        d = row["details"]
        if d.get("declared") is None:
            return UNMET, "n_trials was not declared next to the ledger"
        return (MET, f"declared {d['declared']} >= counted {d['counted']}") if d["declared"] >= d["counted"] else (UNMET, f"declared {d['declared']} < counted {d['counted']}")
    if t == "ratio":
        pool = e.hrows if rule.get("holdout") else e.rows
        ra, rb = pool.get(rule["a"]["id"]), pool.get(rule["b"]["id"])
        a = _number(_path((ra or {}).get("details"), rule["a"]["key"]))
        b = _number(_path((rb or {}).get("details"), rule["b"]["key"]))
        if a is None or not b:
            return NA, f"{rule['a']['id']} / {rule['b']['id']} is not available"
        return (MET if _OPS[rule["op"]](a / b, rule["value"]) else UNMET), f"{rule['a']['key']}/{rule['b']['key']} = {a / b:.2f} (needs {rule['op']} {rule['value']:.2f})"
    row = _row(rule, e)
    if row is None:
        return NA, f"{rule['id']} {'on the holdout ' if rule.get('holdout') else ''}was not produced"
    if t == "status":
        return (MET if row["status"] in rule["allowed"] else UNMET), f"{rule['id']} is {row['status']}"
    v = _number(_path(row.get("details"), rule["key"]))
    if v is None:
        return NA, f"{rule['id']}.{rule['key']} is not available"
    n = e.n_trials
    if t == "detail":
        if rule.get("trials_key"):
            used = _number(_path(row.get("details"), rule["trials_key"])) or 1.0
            if used < n:
                return UNMET, f"computed with n_trials={used:g}, the project has {n}"
        return (MET if _OPS[rule["op"]](v, rule["value"]) else UNMET), f"{rule['id']}.{rule['key']} = {v:.4g} (needs {rule['op']} {rule['value']:g})"
    if t == "pvalue":
        p = min(1.0, v * n)
        return (MET if p < rule["max"] else UNMET), f"p = {v:.3g} x {n} trials = {p:.3g} (needs < {rule['max']:g})"
    # tstat
    p, p_min = math.erfc(abs(v) / math.sqrt(2.0)), math.erfc(rule["min_t"] / math.sqrt(2.0))
    p_adj = min(1.0, p * n)
    ok = v > 0 and p_adj <= p_min * (1 + 1e-9)
    return (MET if ok else UNMET), f"t = {v:.2f}; adjusted for {n} trials the p-value is {p_adj:.3g} (needs <= {p_min:.3g}, t >= {rule['min_t']:g} at one trial)"


def depth_for_level(level: int, e: Evidence, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    """``{"depth": 0..4, "criteria": [{id, name, state, why, needs, repair}]}`` of one level."""
    r = rules or load_rules()
    spoiled = bool(e.holdout) and not e.holdout.get("valid")
    out = []
    for c in r["depth"]["criteria"]:
        spec = r["depth"]["levels"][str(level)][c["id"]]
        state, why = _ev(spec["rule"], e)
        if c["id"] == "D4" and spoiled:
            state, why = UNMET, f"{e.holdout.get('reason') or 'the sealed holdout was opened more than once'}: D4 is 0 for every level, permanently"
        out.append({"id": c["id"], "name": c["name"], "text": spec["text"], "state": state, "why": why, "needs": spec["needs"],
                    "repair": spec.get("repair")})
    return {"depth": sum(1 for x in out if x["state"] == MET), "criteria": out}


__all__ = ["MET", "NA", "UNMET", "Evidence", "depth_for_level"]
