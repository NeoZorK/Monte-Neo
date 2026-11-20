"""Write examples/strategies/<name>/report.md for every idea and strategy_lab/results/summary.json from the stage records.

    python scripts/strategy_lab/analyze.py            # all ideas
The text explains each check in plain words; failed checks get a "what it means for this idea" line. Metrics, verdicts and
hashes only: no price series are published.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import labcore as lc

DISCLAIMER = "Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns."
WHY = {
    "data_integrity": "The price table is clean (no NaN, inverted bars or duplicates). A broken table makes every other number meaningless.",
    "lookahead_truncation": "Cutting the future off the data must not change past signals. A change means the signal peeks ahead.",
    "lookahead_perturbation": "Changing only future prices must not change today's signal.",
    "repaint_history": "A signal shown at bar t must not be rewritten later.",
    "lookahead_static_lint": "Static scan of the source for shift(-1), centred windows and whole-series statistics.",
    "determinism": "The same input must give the same signal; otherwise nothing can be rechecked.",
    "costs_modeled": "Commission and slippage are charged on every position change (10 + 5 bps per side here).",
    "net_profitability": "The strategy must still earn after those costs.",
    "cost_margin": "How much worse the costs may get before the profit disappears.",
    "delay_sensitivity": "The result when every fill is one or more bars later; a real edge survives a small delay.",
    "timing_significance": "Is the timing better than random entries with the same exposure (permutation p-value)?",
    "sample_size": "Enough closed trades for statistics to mean anything.",
    "deflated_sharpe": "The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one).",
    "trials_disclosed": "The number of trials was declared and/or counted in the ledger, not left at 1.",
    "holdout_consistency": "The last part of the history must behave like the first part.",
    "period_consistency": "The profit must not come from one lucky period.",
    "walk_forward_stability": "Parameters chosen in one window must work in the next.",
    "plateau": "Neighbouring parameters should give similar results; an isolated peak is overfitting.",
    "walk_forward_oos": "Out-of-sample folds of the declared grid search.",
    "implausible_performance": "Sharpe or accuracy too good to be true is treated as a bug until proven otherwise.",
    "zero_kink": "Return-series check. A strategy that is flat most days has many exact-zero days and few small losses; for pairs and carry this warning is expected and is not a sign of manual editing.",
    "round_numbers": "Return-series check. Exactly-zero days (flat periods) count as round numbers; expected for sparse strategies, not evidence of hand-typed figures.",
    "track_record_significance": "Is the track record long enough, given its Sharpe and the number of trials, to be told apart from luck?",
    "min_backtest_length": "How many years of history the Sharpe needs after the number of trials (cross-sectional score).",
    "synthetic_market_null": "The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there.",
    "ic": "Information coefficient: does the score rank the next returns better than chance (t-statistic)?",
    "residual_alpha": "Is the return still there after market, size, momentum, reversal and low-volatility exposures?",
    "short_feasibility": "Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated.",
    "accounting_mismatch": "The reported P&out must equal quantities held times the price changes of the legs (phantom-profit check).",
    "derived_significance": "Is the P&out derived from the legs distinguishable from zero?",
    "edge_on_noise": "The pairs rule is run on independent random walks, where it must not earn.",
    "trial_ledger": "The hash-chained ledger of variants was intact.",
}


def comment(c: dict) -> str:
    base = WHY.get(c["id"], "")
    if c["status"] == "fail":
        return f"**FAILED.** {base} {c['summary']}".strip()
    return f"{base} {c['summary']}".strip()


def load(name: str, stage: str) -> dict | None:
    p = lc.RES / name / f"{stage}.json"
    return json.loads(p.read_text()) if p.exists() else None


def f(x, d=2):
    return "n/a" if x is None else (f"{x:.{d}f}" if isinstance(x, (int, float)) else str(x))


def final_record(name: str) -> tuple[str, dict | None]:
    for st in ("holdout", "validation", "discovery"):
        r = load(name, st)
        if r:
            return st, r
    return "none", None


def report(name: str) -> str:
    meta = lc.load_module(name).META
    stages = {s: load(name, s) for s in ("prepare", "discovery", "validation", "holdout")}
    out = [f"# {meta['title']}: automatic review", "", f"Idea: {lc.IDEA_AUTHOR}. Process, design and verification: {lc.PROCESS_AUTHOR}. {DISCLAIMER}", "",
         f"Family: {meta['family']}. Fixed parameters (chosen before any data was read): `{json.dumps(meta['params'])}`. "
         + ("Costs: Binance taker fees (VIP0: spot 10 bps, perpetual 5 bps) + 2-12 bps spread/slippage per coin, fills on the next bar; also doubled." if meta.get("round") == 2
          else f"Costs: {lc.COMMISSION_BPS} bps commission + {lc.SLIPPAGE_BPS} bps slippage per side, fills on the next bar."), "",
         f"Data: discovery before {lc.VAL_START.date()}, validation {lc.VAL_START.date()} to {lc.HOLD_START.date()}, sealed holdout from {lc.HOLD_START.date()}.", ""]
    if stages["prepare"]:
        out += [f"Hypothesis registered before testing: `{stages['prepare']['registration']}`; planned Lab-wide trials: {stages['prepare']['planned_trials']}.", ""]
    out += ["## Pipeline", "", "| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |", "|---|---|---|---|---|---|---|"]
    for s in ("discovery", "validation", "holdout"):
        r = stages[s]
        out.append(f"| {s} | {r['slice']} | {r['verdict']} | {r['arl']}/9 | {f(r['sharpe'])} | {f(r['deflated_sharpe'])} | {r['n_trials']} |" if r else f"| {s} | not run | | | | | |")
    out.append("")
    if stages["discovery"] and stages["discovery"].get("grid_sharpes"):
        out += ["Discovery grid (Sharpe by variant; every variant is counted as a trial):", ""] + [f"- `{ {k: v for k, v in g.items() if k != 'sharpe'} }` -> {g['sharpe']}" for g in stages["discovery"]["grid_sharpes"]] + [""]
    st, rec = final_record(name)
    if rec:
        out += [f"## Checks of the {st} certificate (`{rec['certificate_id']}`, {rec['slice']} data)", "", "| Check | Status | What it means |", "|---|---|---|"]
        out += [f"| `{c['id']}` | {c['status']} | {comment(c)} |" for c in rec["checks"]]
        out += ["", f"Verdict **{rec['verdict']}**, ARL **{rec['arl']}/9**. {rec.get('arl_summary') or ''}"]
        if rec.get("arl_scope"):
            out += ["", f"ARL scope: {rec['arl_scope']}."]
        ev = rec.get("economics")
        if ev:
            v = ev.get("validation", {})
            out += ["", "## Independent economics (validation period, net of costs, before the holdout)", "",
                    "| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |", "|---|---|---|---|---|---|---|---|---|",
                    f"| {f(v.get('sharpe'))} | {f(ev.get('cost_x2_sharpe_validation'))} | {f(v.get('total_return'))} | {f(v.get('max_drawdown'))} | {f(v.get('corr_btc'))} | "
                    f"{f(v.get('beta_share'))} | {f(v.get('alpha_t_vs_btc'))} | {f(v.get('deflated_sharpe'))} | {f(v.get('btc_buyhold_sharpe'))} |", "",
                    "By calendar year, all years before the holdout (regimes):", "", "| Year | Net Sharpe | Return | BTC return |", "|---|---|---|---|"]
            out += [f"| {y} | {f(g['sharpe'])} | {f(g['return'])} | {f(g['btc_return'])} |" for y, g in ev.get("by_year", {}).items()]
            out += ["", "Notes: " + "; ".join(ev.get("notes", [])) + "."]
        if rec.get("reasons"):
            out += ["", "Reasons given by the verifier:"] + [f"- {x}" for x in rec["reasons"]]
        for key, title in (("legs", "Legs re-derivation (--legs)"), ("null_test", "Random-walk null test (--null-test)")):
            if rec.get("pair", {}).get(key):
                q = rec["pair"][key]
                out += ["", f"### {title}: {q['verdict']}", ""] + [f"- {x}" for x in q["checks"]]
        if rec.get("oracle"):
            out += ["", f"Thresholdout oracle on the sealed holdout: `{json.dumps(rec['oracle'])}`"]
    out += ["", "## Honest conclusion", ""]
    h, v = stages["holdout"], stages["validation"]
    if h:
        out.append(f"The holdout was opened once for the candidate frozen in commit `{h['freeze_commit'][:10]}`. Result: **{h['verdict']}**, ARL {h['arl']}/9. "
                 + ("This candidate passed all gates; it is a candidate for a forward (paper) test, nothing more." if h["passes_all_gates"]
                    else "It did not pass all gates. This is a reviewed case, not a candidate; the parameters were not tuned afterwards."))
    elif v:
        out.append("Validation " + ("gate is open: the candidate may be frozen and the holdout opened once." if v["gate_open"]
                                   else "gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case."))
    else:
        out.append("Not run yet.")
    return "\n".join(out) + "\n"


def main() -> int:
    rows = []
    for n in lc.names():
        mod = lc.load_module(n)
        (lc.report_dir(n) / "report.md").write_text(report(n))
        st, rec = final_record(n)
        if rec:
            rows.append({"name": n, "title": mod.META["title"], "family": mod.META["family"], "pair": bool(mod.META.get("pair")), "stage": st,
                         "verdict": rec["verdict"], "arl": rec["arl"], "certificate_id": rec["certificate_id"], "report_sha256": rec["report_sha256"],
                         "data_slice": rec["slice"], "n_trials": rec["n_trials"], "round": mod.META.get("round", 1),
                         "sharpe": rec.get("sharpe"), "deflated_sharpe": rec.get("deflated_sharpe"), "timing_p": rec.get("timing_p"),
                         "arl_scope": rec.get("arl_scope"), "arl_depth": rec.get("arl_depth"), "arl_headline": rec.get("arl_headline"), "net_sharpe_val": ((rec.get("economics") or {}).get("validation") or {}).get("sharpe"),
                         "net_sharpe_val_cost_x2": (rec.get("economics") or {}).get("cost_x2_sharpe_validation"),
                         "corr_btc": ((rec.get("economics") or {}).get("validation") or {}).get("corr_btc"),
                         "beta_share": ((rec.get("economics") or {}).get("validation") or {}).get("beta_share"),
                         "alpha_t_vs_btc": ((rec.get("economics") or {}).get("validation") or {}).get("alpha_t_vs_btc"),
                         "gate_open": rec.get("gate_open"), "date": rec.get("finished_at"),
                         "holdout_opened": st == "holdout", "passes_all_gates": bool(rec.get("passes_all_gates", False)),
                         "idea_author": lc.IDEA_AUTHOR, "verified_by": lc.PROCESS_AUTHOR})
    lc.RES.mkdir(parents=True, exist_ok=True)
    (lc.RES / "summary.json").write_text(json.dumps({"schema": "strategy-lab-summary/1", "disclaimer": DISCLAIMER, "monte_neo": lc.load_version(),
                                                     "strategies": rows}, indent=1))
    print(f"{len(rows)} of {len(lc.names())} ideas have results; summary.json written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
