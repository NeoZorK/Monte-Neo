"""Track-record metrics computed only from the journal (no number is typed by hand)."""

from __future__ import annotations

import math
from typing import Any

from monte_neo.deploy import account

ANN = 365  # crypto trades every day


def sharpe(r: list[float]) -> float | None:
    if len(r) < 2:
        return None
    m = sum(r) / len(r)
    sd = math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))
    return m / sd * math.sqrt(ANN) if sd > 0 else None


def max_drawdown(navs: list[float]) -> float:
    peak, dd = -math.inf, 0.0
    for v in navs:
        peak = max(peak, v)
        dd = min(dd, v / peak - 1.0)
    return dd


def worst_week(navs: list[float]) -> float | None:
    if len(navs) < 8:
        return None
    return min(navs[i] / navs[i - 7] - 1.0 for i in range(7, len(navs)))


def var_es(r: list[float], q: float = 0.95) -> dict[str, float | None]:
    """Historical one-day value at risk and expected shortfall (losses as negative returns)."""
    if len(r) < 20:
        return {"var": None, "es": None}
    s = sorted(r)
    k = max(1, int(math.floor((1 - q) * len(s))))
    return {"var": s[k - 1], "es": sum(s[:k]) / k}


def tracking_error(a: list[float], b: list[float]) -> float | None:
    """Annualised standard deviation of the daily difference of two return series (aligned at the end)."""
    n = min(len(a), len(b))
    if n < 2:
        return None
    d = [x - y for x, y in zip(a[-n:], b[-n:], strict=True)]
    m = sum(d) / n
    return math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1) * ANN)


def costs_x2_returns(entries: list[dict[str, Any]]) -> list[float]:
    """Paper daily returns with every paper fill's costs (fee and slippage) paid a second time.

    A day's fills happen after that day's mark, so their extra cost enters from the next mark on.
    """
    extra: dict[str, float] = {}
    for e in entries:
        if e["kind"] == "paper_fill":
            b = e["body"]
            extra[b["day"]] = extra.get(b["day"], 0.0) + b["fee_usdt"] + abs(b["price"] - b["mainnet_price"]) * b["qty"]
    navs, cum = [], 0.0
    for m in account.replay(entries, "paper")["marks"]:
        navs.append(m["nav"] - cum)
        cum += extra.get(m["day"], 0.0)
    return [b / a - 1.0 for a, b in zip(navs, navs[1:], strict=False) if a]


def summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    paper, test = account.replay(entries, "paper"), account.replay(entries, "testnet")
    pn = [m["nav"] for m in paper["marks"]]
    has_fills = any(e["kind"] == "fill" for e in entries)
    tn = [m["nav"] for m in test["marks"]] if has_fills else []
    pr = account.daily_returns(paper["marks"])
    tr = account.daily_returns(test["marks"]) if tn else []
    r2 = costs_x2_returns(entries)
    certs = [e["body"] for e in entries if e["kind"] == "certify"]
    es = var_es(pr)
    start = next((e["body"] for e in entries if e["kind"] == "start"), {})
    n_trials = int(((start.get("eligibility") or {}).get("certificate") or start.get("certificate") or {}).get("n_trials") or 1)
    from monte_neo.deploy.sequential import evaluate as _sequential

    seq = _sequential(r2, n_trials=n_trials, target_sharpe=float(start.get("target_sharpe", 0.5)))
    return {
        "days": len(pn), "weeks": len(pn) / 7.0, "paper_nav": pn[-1] if pn else None,
        "paper_return": (pn[-1] / pn[0] - 1.0) if len(pn) > 1 else None,
        "sharpe": sharpe(pr), "sharpe_costs_x2": sharpe(r2), "max_drawdown": max_drawdown(pn) if pn else None,
        "worst_week": worst_week(pn), "one_day_var_95": es["var"], "one_day_es_95": es["es"],
        "testnet_nav": tn[-1] if tn else None, "tracking_error": tracking_error(pr, tr) if tr else None,
        "paper_fees": paper["fees"], "testnet_fees": test["fees"] if tn else None,
        "killed": any(e["kind"] == "kill" for e in entries),
        "forward_verdict": certs[-1].get("verdict") if certs else None,
        "sequential": seq,
    }
