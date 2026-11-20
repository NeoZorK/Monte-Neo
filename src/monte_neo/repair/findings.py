"""The most common findings: what each means, what to do, and whether a fix can be tried automatically.

``explain(certificate)`` turns the failed and warned checks of a certificate into plain explanations with next actions.
``fix`` says how ``preview_fix`` may try the repair: ``source`` (a causal rewrite of the file), ``steps`` (a declared
transform), ``costs`` (realistic costs), ``trials`` (a larger n_trials) or ``manual`` (only you can do it).
"""

from __future__ import annotations

from typing import Any

# finding id -> (check ids, title, why it matters, next actions, fix kind, fix parameters)
FINDINGS: dict[str, dict[str, Any]] = {
    "F01": {"checks": ["lookahead_truncation"], "title": "The signal changes when later bars are removed",
            "why": "The signal at bar t used data after t (shift(-k), a future index, a centred window). Live, that data does not exist, so the backtest profit is not obtainable.",
            "next": ["Compute every feature from rows up to t only.", "Re-verify; the numbers will change."], "fix": "source", "params": {}},
    "F02": {"checks": ["lookahead_perturbation"], "title": "Past signals change when the future is rewritten",
            "why": "A statistic over the whole file (mean, std, min, max, a fit) feeds the signal: bar t knows the whole sample.",
            "next": ["Use expanding or rolling statistics that end at t.", "Fit models only on data before the decision."], "fix": "source", "params": {}},
    "F03": {"checks": ["lookahead_static_lint"], "title": "The code contains a known look-ahead form",
            "why": "The static scan found a pattern such as shift(-1), bfill, a centred rolling window or a join on a future timestamp.",
            "next": ["Apply the causal rewrite shown by repair --preview F03.", "Do not keep the old version in the results."], "fix": "source", "params": {}},
    "F04": {"checks": ["repaint_history"], "title": "A closed bar's signal changes when later bars arrive",
            "why": "Pivots, ZigZag or confirmed-later levels repaint: the backtest shows signals nobody could have acted on.",
            "next": ["Act one bar after confirmation.", "Use only confirmed values."], "fix": "steps", "params": {"steps": [["delay", {"bars": 1}]]}},
    "F05": {"checks": ["repaint_live"], "title": "The signal is declared known at the open but needs the bar's own prices",
            "why": "Execution on the signal bar: the order would be placed with a price that exists only after the bar closes.",
            "next": ["Delay the signal by one bar, or declare signal_timing close and trade the next open."], "fix": "steps", "params": {"steps": [["delay", {"bars": 1}]]}},
    "F06": {"checks": ["costs_modeled"], "title": "Trading costs are zero or missing",
            "why": "A backtest with no commission and slippage overstates every strategy, most of all the ones that trade often.",
            "next": ["Set commission and slippage to realistic values for the venue.", "Re-verify."], "fix": "costs", "params": {"commission_bps": 5.0, "slippage_bps": 5.0}},
    "F07": {"checks": ["net_profitability"], "title": "Not profitable after costs",
            "why": "The gross edge is smaller than the costs paid; turnover is the usual cause.",
            "next": ["Trade less: hold longer, add a no-trade band, or smooth the signal."], "fix": "steps", "params": {"steps": [["hold", {"bars": 5}]]}},
    "F08": {"checks": ["cost_sensitivity", "cost_margin"], "title": "The edge does not survive higher costs",
            "why": "A small rise in costs wipes out the profit: it would not survive real fills.",
            "next": ["Lower turnover or secure lower fees."], "fix": "steps", "params": {"steps": [["hold", {"bars": 20}]]}},
    "F09": {"checks": ["delay_sensitivity"], "title": "The profit lives in the next bar's fill",
            "why": "If the result collapses when the order is one bar later, it needed a fill you cannot get.",
            "next": ["Slow the signal down so a one-bar delay does not matter."], "fix": "steps", "params": {"steps": [["hold", {"bars": 10}]]}},
    "F10": {"checks": ["trials_disclosed"], "title": "The number of variants tried is not disclosed",
            "why": "The Deflated Sharpe prices selection: the more variants tried, the higher the best Sharpe by chance. Without n_trials the result is not deflated.",
            "next": ["Count every variant tried (a ledger does it for you) and pass n_trials."], "fix": "trials", "params": {"n_trials": 10}},
    "F11": {"checks": ["deflated_sharpe"], "title": "The Sharpe ratio does not survive the number of trials",
            "why": "After pricing the search, the edge is not distinguishable from luck. No transform creates evidence.",
            "next": ["Get more independent data, or test one pre-registered idea on unseen data."], "fix": "manual", "params": {}},
    "F12": {"checks": ["alpha_after_beta"], "title": "The return is market exposure, not alpha",
            "why": "Most of the profit is explained by the benchmark's move: a cheap index fund earns it.",
            "next": ["Hedge the benchmark (long-short, beta-neutral) and test the residual."], "fix": "steps", "params": {"steps": [["neutral", {}]]}},
    "F13": {"checks": ["capacity", "execution_capacity"], "title": "The size cannot be traded within the volume",
            "why": "Orders would be a large share of the bar volume: the fills in the backtest are not available.",
            "next": ["Cut the size or the participation, or trade more liquid instruments."], "fix": "steps", "params": {"steps": [["cap", {"cap": 0.1}]]}},
    "F14": {"checks": ["survivorship"], "title": "The universe contains only survivors",
            "why": "Names that were delisted or dropped are missing, so losers are missing too and the profit is overstated.",
            "next": ["Add the delisted names' prices, or declare them with delisted=..."], "fix": "manual", "params": {}},
    "F15": {"checks": ["accounting_mismatch"], "title": "The reported P&L is not what the legs earned",
            "why": "Phantom profit: the reported return cannot be reproduced from the leg positions and prices.",
            "next": ["Re-derive the return from the legs (verify --legs ... --legs-fixed-out) and use that."], "fix": "manual", "params": {}},
    "F16": {"checks": ["data_integrity", "data_quality"], "title": "The price data has errors",
            "why": "Broken bars, spikes, gaps and unadjusted splits create fake moves that a strategy can 'trade'.",
            "next": ["Fix the data first; no strategy change repairs bad data."], "fix": "manual", "params": {}},
}


def explain(certificate: dict[str, Any]) -> list[dict[str, Any]]:
    """The findings present in ``certificate`` (failed or warned checks), each with its check rows, why and next actions."""
    bad = {c["id"]: c for c in certificate.get("checks", []) if c.get("status") in ("fail", "warn")}
    out = []
    for fid, f in FINDINGS.items():
        hit = [cid for cid in f["checks"] if cid in bad]
        if hit:
            out.append({"finding": fid, "title": f["title"], "why": f["why"], "next_actions": list(f["next"]), "fix": f["fix"],
                        "auto": f["fix"] != "manual", "checks": [{"id": c, "status": bad[c]["status"], "summary": bad[c]["summary"]} for c in hit]})
    return out
