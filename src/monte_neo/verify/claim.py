"""Check what was claimed against what the backtest reproduces.

An agent (or a person) reports "Sharpe 2.1, return +85%, drawdown 12%". ``--claim claim.json``
compares those numbers with the verified ones. A claim that is *better* than the verified result
by more than a tolerance is an overclaim and fails the ``claim_consistency`` check (verdict
``NEEDS_MORE_EVIDENCE``: the strategy may be fine, its report cannot be trusted). A claim that
is equal or more modest is fine.

Claim file, all keys optional (fractions, or strings such as ``"85%"``)::

    {"sharpe": 2.1, "total_return": 0.85, "max_drawdown": 0.12, "n_trades": 300,
     "win_rate": 0.62, "profit_factor": 1.9}
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from monte_neo.verify.checks import check
from monte_neo.verify.limits import MAX_GRID_BYTES, loads_strict, read_text_limited

ALIASES = {
    "sharpe": ("sharpe", "sharpe_ratio", "annualized_sharpe"),
    "total_return": ("total_return", "return", "net_return"),
    "max_drawdown": ("max_drawdown", "drawdown", "max_dd"),
    "n_trades": ("n_trades", "trades", "closed_trades"),
    "win_rate": ("win_rate", "hit_rate"),
    "profit_factor": ("profit_factor",),
}
LABELS = {
    "sharpe": "Sharpe",
    "total_return": "total return",
    "max_drawdown": "max drawdown",
    "n_trades": "closed trades",
    "win_rate": "win rate",
    "profit_factor": "profit factor",
}
_FRACTIONS = ("total_return", "max_drawdown", "win_rate")
_PERCENT_KEYS = ("max_drawdown", "win_rate")  # a value above 1 is read as a percentage


def _number(key: str, raw: Any) -> float:
    if isinstance(raw, bool):
        raise ValueError(f"claim {key!r} must be a number, got {raw!r}")
    if isinstance(raw, str):
        text = raw.strip()
        percent = text.endswith("%")
        try:
            value = float(text.rstrip("%").replace(",", ""))
        except ValueError:
            raise ValueError(f"claim {key!r} must be a number, got {raw!r}") from None
        value = value / 100.0 if percent else value
    elif isinstance(raw, int | float):
        value = float(raw)
    else:
        raise ValueError(f"claim {key!r} must be a number, got {raw!r}")
    if not math.isfinite(value):
        raise ValueError(f"claim {key!r} must be finite, got {raw!r}")
    if key in _PERCENT_KEYS and not (isinstance(raw, str) and raw.strip().endswith("%")) and abs(value) > 1.0:
        value /= 100.0
    return abs(value) if key == "max_drawdown" else value


def parse_claim(spec: dict[str, Any] | str | Path) -> dict[str, float]:
    """Normalized claim from a dict, JSON text or a JSON file; unknown keys are refused."""
    if isinstance(spec, dict):
        raw = spec
    else:
        text = str(spec).strip()
        raw = loads_strict(text if text[:1] in ("{", "[") else read_text_limited(text, MAX_GRID_BYTES, "claim"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("a claim must be a non-empty JSON object, e.g. {\"sharpe\": 2.1, \"total_return\": 0.85}")
    by_alias = {alias: key for key, names in ALIASES.items() for alias in names}
    out: dict[str, float] = {}
    for name, value in raw.items():
        key = by_alias.get(str(name).strip().lower())
        if key is None:
            raise ValueError(f"unknown claim key {name!r}; use one of {', '.join(ALIASES)}")
        if key in out:
            raise ValueError(f"claim key {key!r} given twice")
        out[key] = _number(key, value)
    return out


def _judge(key: str, claimed: float, verified: float | None) -> tuple[str, str]:
    """(status, note) for one metric: ``overclaimed``, ``matches``, ``conservative`` or ``not verifiable``."""
    if verified is None or not math.isfinite(verified):
        return "not verifiable", "no verified value for this strategy type"
    if key == "sharpe":
        margin = max(0.3, 0.10 * abs(verified))
    elif key == "total_return":
        margin = max(0.02, 0.10 * abs(verified))
    elif key == "max_drawdown":
        margin = max(0.02, 0.10 * verified)
    elif key == "n_trades":
        margin = max(2.0, 0.05 * verified)
    elif key == "win_rate":
        margin = 0.03
    else:
        margin = 0.1 + 0.10 * abs(verified)
    # A smaller drawdown is the flattering direction; for every other metric a larger number is.
    gain = (verified - claimed) if key == "max_drawdown" else (claimed - verified)
    if gain > margin:
        return "overclaimed", "better than the backtest reproduces"
    if -gain > margin:
        return "conservative", "more modest than the backtest"
    return "matches", "within tolerance"


def _fmt(key: str, value: float) -> str:
    if key in _FRACTIONS:
        return f"{value:+.1%}" if key == "total_return" else f"{value:.1%}"
    return f"{value:,.0f}" if key == "n_trades" else f"{value:.2f}"


def claim_row(claim: dict[str, float], verified: dict[str, float | None]) -> dict[str, Any]:
    """``claim_consistency``: fail on an overclaim."""
    rows = {}
    for key, claimed in claim.items():
        status, note = _judge(key, claimed, verified.get(key))
        rows[key] = {"claimed": claimed, "verified": verified.get(key), "status": status, "note": note}
    over = [k for k, v in rows.items() if v["status"] == "overclaimed"]
    details = {"metrics": rows}
    if over:
        parts = "; ".join(f"{LABELS[k]} claimed {_fmt(k, rows[k]['claimed'])}, verified {_fmt(k, rows[k]['verified'])}" for k in over)
        return check("claim_consistency", "claim", "fail", f"claim overstated: {parts}", details)
    checked = [k for k, v in rows.items() if v["status"] != "not verifiable"]
    if not checked:
        return check("claim_consistency", "claim", "skip", "nothing in the claim can be verified for this strategy", details)
    parts = ", ".join(f"{LABELS[k]} {_fmt(k, rows[k]['claimed'])} vs {_fmt(k, rows[k]['verified'])}" for k in checked)
    return check("claim_consistency", "claim", "pass", f"claim matches the backtest: {parts}", details)


__all__ = ["ALIASES", "claim_row", "parse_claim"]
