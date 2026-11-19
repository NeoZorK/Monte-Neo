"""``verify_options``: a ``strategy-verdict/1`` certificate for a table of option trades."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from monte_neo._version import __version__
from monte_neo.options import checks as ck
from monte_neo.options.load import load_trades
from monte_neo.verify.schema import DISCLAIMER, VERDICT_SCHEMA_ID, aggregate_verdict, to_jsonable
from monte_neo.verify.verdict import certificate_id

SCOPE_NOTE = (
    "Trade-table checks only: fills against the quoted spread, the date of each volatility, a Black-Scholes stress of the open book, "
    "assignment and pin warnings, a simplified margin and dividends. A historical option chain is not read: the surface as of each "
    "date, tradable strikes and open interest are not assessed."
)
ACTIONS = {
    "bid_ask_fill": "Fill at the touch (buy at the ask, sell at the bid) or at a measured fraction of the spread, then re-run.",
    "iv_asof": "Use only the volatility observed on or before the decision time (as-of join), then re-run.",
    "tail_stress": "Cut the short-option size or add long wings so the -20 % / +20 % with volatility x2 stress loses a small share of equity.",
    "early_exercise_pin": "Close or roll short options before the ex-dividend date and before expiry when they are near the strike.",
    "margin_simplified": "Reduce the short size or hold more capital: the peak margin must fit the account with room to spare.",
    "dividends": "Add ex_div_date and dividend columns so early assignment and dividend drag are priced.",
}


def _rounded(df: pd.DataFrame) -> pd.DataFrame:
    """Numeric columns rounded to 10 places; dates and text untouched (``DataFrame.round`` warns about them and leaves them as they are)."""
    return df.apply(lambda c: c.round(10) if pd.api.types.is_numeric_dtype(c) and not pd.api.types.is_bool_dtype(c) else c)


def verify_options(
    source: str | Path | pd.DataFrame, *, equity: float | None = None, rate: float = 0.0, dividend_yield: float = 0.0, profile: bool = True,
) -> dict[str, Any]:
    """Verify option trades (columns in :mod:`monte_neo.options.load`). Missing optional columns give ``skip`` rows, never a pass.

    ``equity`` sizes the stress loss and margin; ``rate`` and ``dividend_yield`` are the stress model's inputs.
    """
    if equity is not None and float(equity) <= 0:
        raise ValueError("equity must be positive")
    df = load_trades(source)
    rows = [
        ck.bid_ask_fill(df), ck.iv_asof(df), ck.tail_stress(df, equity, rate, dividend_yield), ck.assignment_pin(df),
        ck.margin_simplified(df, equity), ck.dividends(df), ck.chain_scope(df),
    ]
    verdict = aggregate_verdict(rows)
    skipped = [c["id"] for c in rows if c["status"] == "skip"]
    if verdict == "PASS" and skipped:
        verdict = "NEEDS_MORE_EVIDENCE"  # a check that could not run never counts as passed
    pnl = ck.pnl_reported(df)
    repro = {
        "engine": "monte-neo", "engine_version": __version__, "n_trials": 1,
        "data_sha256": hashlib.sha256(_rounded(df).astype(str).to_csv().encode()).hexdigest(),
        "settings": {"kind": "options", "equity": equity, "rate": rate, "dividend_yield": dividend_yield},
    }
    problems = [c for c in rows if c["status"] in ("fail", "warn")]
    block = None
    if profile:
        from monte_neo.profiles import profile_block

        block = profile_block("options", rows)
    return to_jsonable({
        "schema": VERDICT_SCHEMA_ID, "verdict": verdict, "certificate_id": certificate_id(repro, verdict),
        "reasons": [f"{c['id']}: {c['summary']}" for c in problems] + [f"{c['id']}: {c['summary']}" for c in rows if c["status"] == "skip"],
        "checks": rows,
        "metrics": {"trades": int(len(df)), "closed_trades": int(pnl.notna().sum()), "pnl_reported": float(pnl.sum(skipna=True))},
        "next_actions": [ACTIONS[c["id"]] for c in rows if c["id"] in ACTIONS and c["status"] in ("fail", "warn")],
        "reproducibility": repro, "scope": SCOPE_NOTE, **({"profile": block} if block else {}),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "disclaimer": DISCLAIMER,
    })
