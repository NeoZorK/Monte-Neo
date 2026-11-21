"""The worst-scenario card of a strategy, written for hedged and market-neutral books ("hedged" never means "risk-free").

A market-neutral book has a small day-to-day volatility, so its Sharpe ratio and drawdown can look safe while the losses
that matter come from events its history may not hold. The card puts both on one page:

1. **Measured** (from the net returns): worst day, worst week (5 bars), worst month (21 bars), maximum drawdown and its
   length in bars, expected shortfall (mean of the worst 1 % of bars), share of losing months.
2. **Hedge behaviour** (when the two legs' returns are given): the correlation of the legs on all bars and on the 10 %
   of bars when the long leg fell most, and the worst month of the long leg ALONE: what the book loses if the hedge
   stops working (leg decoupling).
3. **Stated shocks** (assumptions, not measurements; each with its formula):
   * ``short_squeeze``: the short leg jumps ``squeeze_jump`` (default +50 %) in one bar while the long leg is flat:
     loss = short weight x jump.
   * ``spread_break``: the spread moves three times its worst observed one-bar move against the book.
   * ``funding_spike``: the book pays ``funding_spike_bps_day`` (default 30 bps a day, a stressed crypto level) on the
     short side for 30 days.
   * ``venue_failure``: the venue holding ``venue_share`` of the capital fails and returns nothing: loss = venue_share.
     This is the loss a hedge does not protect against.

The headline is the largest market loss among the measured and stated rows; the venue failure is shown beside it,
separately, because it is a counterparty loss of a different kind (it can take everything the venue holds). Nothing here forecasts; it states what happened
and what the stated shocks would cost. Not investment advice.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

SCHEMA_ID = "worst-case-card/1"
DEFAULTS = {"squeeze_jump": 0.5, "funding_spike_bps_day": 30.0, "funding_days": 30, "venue_share": 1.0, "short_weight": 0.5}


def _worst_window(r: pd.Series, n: int) -> float:
    if len(r) < n:
        return float("nan")
    comp = np.log1p(r.clip(lower=-0.999999)).rolling(n).sum()
    return float(np.expm1(comp.min()))


def _drawdown(r: pd.Series) -> tuple[float, int]:
    nav = (1 + r).cumprod()
    peak = nav.cummax()
    dd = nav / peak - 1.0
    longest, cur = 0, 0
    for under in (dd < 0).to_numpy():
        cur = cur + 1 if under else 0
        longest = max(longest, cur)
    return float(dd.min()), int(longest)


def measured(r: pd.Series) -> dict[str, Any]:
    r = r.dropna().astype(float)
    k = max(1, int(math.ceil(0.01 * len(r))))
    mdd, length = _drawdown(r)
    months = r.groupby(pd.Grouper(freq="ME")).apply(lambda x: (1 + x).prod() - 1) if isinstance(r.index, pd.DatetimeIndex) else None
    return {"bars": len(r), "worst_bar": float(r.min()), "worst_5": _worst_window(r, 5), "worst_21": _worst_window(r, 21),
            "max_drawdown": mdd, "longest_drawdown_bars": length, "expected_shortfall_1pct": float(r.nsmallest(k).mean()),
            "losing_month_share": None if months is None or not len(months) else float((months < 0).mean())}


def hedge(long_leg: pd.Series, short_leg: pd.Series) -> dict[str, Any]:
    """Legs as the returns of the instruments (the short leg is the instrument sold, not its negative)."""
    df = pd.concat([long_leg, short_leg], axis=1, keys=["long", "short"]).dropna()
    if len(df) < 30:
        return {"error": "fewer than 30 common bars of the two legs"}
    cut = df["long"].quantile(0.10)
    stress = df[df["long"] <= cut]
    spread = df["long"] - df["short"]
    return {"corr_all": float(df["long"].corr(df["short"])),
            "corr_stress": float(stress["long"].corr(stress["short"])) if len(stress) >= 10 else None,
            "long_alone_worst_21": _worst_window(df["long"], 21), "worst_spread_bar": float(spread.min()),
            "bars": len(df)}


def card(returns: pd.Series, legs: tuple[pd.Series, pd.Series] | None = None, **assumptions: float) -> dict[str, Any]:
    a = {**DEFAULTS, **assumptions}
    m = measured(returns)
    h = hedge(*legs) if legs is not None else None
    w = float(a["short_weight"])
    shocks = {
        "short_squeeze": {"loss": -w * a["squeeze_jump"], "formula": f"short weight {w:g} x jump {a['squeeze_jump']:.0%}"},
        "funding_spike": {"loss": -w * a["funding_spike_bps_day"] / 1e4 * a["funding_days"],
                          "formula": f"short weight {w:g} x {a['funding_spike_bps_day']:g} bps/day x {int(a['funding_days'])} days"},
        "venue_failure": {"loss": -float(a["venue_share"]),
                          "formula": f"capital at the failed venue {a['venue_share']:.0%}: a hedge does not protect it"},
    }
    if h and "error" not in h:
        shocks["spread_break"] = {"loss": 3.0 * w * h["worst_spread_bar"], "formula": f"3 x worst one-bar spread move {h['worst_spread_bar']:.2%} x weight {w:g}"}
        shocks["hedge_stops_working"] = {"loss": w * h["long_alone_worst_21"], "formula": f"long leg alone, worst month {h['long_alone_worst_21']:.2%} x weight {w:g}"}
    rows = [("measured: max drawdown", m["max_drawdown"]), ("measured: worst month", m["worst_21"]),
            *((f"stated: {k}", v["loss"]) for k, v in shocks.items() if k != "venue_failure")]
    rows = [(n, v) for n, v in rows if v is not None and not (isinstance(v, float) and math.isnan(v))]
    name, loss = min(rows, key=lambda t: t[1])
    return {"schema": SCHEMA_ID, "measured": m, "hedge": h, "shocks": shocks, "assumptions": a,
            "headline": {"scenario": name, "loss": loss}, "counterparty": shocks["venue_failure"],
            "note": "Hedged is not risk-free: the stated shocks are assumptions with their formulas, not forecasts. Not investment advice."}


def markdown(c: dict[str, Any], title: str = "Worst scenario") -> str:
    m, h = c["measured"], c["hedge"]

    def pct(x: Any) -> str:
        return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2%}"

    lines = [f"## {title}", "", f"**Largest market loss on this card: {pct(c['headline']['loss'])}** ({c['headline']['scenario']}).",
             f"Counterparty: if the venue fails, the loss can reach {pct(-c['counterparty']['loss'])} of capital, hedged or not.", "",
             "Measured on the net returns:", "", "| | |", "|---|---|",
             f"| worst bar | {pct(m['worst_bar'])} |", f"| worst 5 bars | {pct(m['worst_5'])} |", f"| worst 21 bars | {pct(m['worst_21'])} |",
             f"| maximum drawdown | {pct(m['max_drawdown'])} ({m['longest_drawdown_bars']} bars under water at most) |",
             f"| expected shortfall, worst 1 % of bars | {pct(m['expected_shortfall_1pct'])} |",
             f"| losing months | {pct(m['losing_month_share'])} |", ""]
    if h and "error" not in h:
        cs = "n/a" if h["corr_stress"] is None else f"{h['corr_stress']:.2f}"
        lines += ["Hedge:", "", f"- correlation of the legs: {h['corr_all']:.2f} on all bars, {cs} on the 10 % worst bars of the long leg",
                  f"- the long leg alone, worst month: {pct(h['long_alone_worst_21'])}", ""]
    lines += ["Stated shocks (assumptions, not forecasts):", "", "| scenario | loss | formula |", "|---|---|---|"]
    lines += [f"| {k} | {pct(v['loss'])} | {v['formula']} |" for k, v in c["shocks"].items()]
    lines += ["", c["note"], ""]
    return "\n".join(lines)
