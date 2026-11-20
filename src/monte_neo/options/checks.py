"""The options checks. Each returns one check row; missing input gives ``skip`` with the reason ("not assessed")."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.options import bs
from monte_neo.verify.checks import check

SCENARIOS = ((-0.20, 2.0), (0.20, 2.0))  # (underlying move, volatility multiplier): the two tails of a stress


def _skip(cid: str, why: str) -> dict[str, Any]:
    return check(cid, "economics", "skip", f"not assessed: {why}", {"not_assessed": True})


def _has(df: pd.DataFrame, *cols: str) -> bool:
    return all(c in df.columns and df[c].notna().any() for c in cols)


def pnl_reported(df: pd.DataFrame) -> pd.Series:
    """Dollar P&L of trades that have an exit price, as reported (fills as given)."""
    if "exit_price" not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df["qty"] * df["multiplier"] * (df["exit_price"] - df["fill_price"])


def pnl_at_touch(df: pd.DataFrame) -> pd.Series:
    """The same trades filled at the touch: buys at the ask, sells at the bid; an exit without a quote pays the entry half-spread."""
    ask, bid = df["ask"], df["bid"]
    entry = np.where(df["qty"] > 0, ask, bid)
    half = (ask - bid) / 2.0
    xb = df["exit_bid"] if "exit_bid" in df.columns else pd.Series(np.nan, index=df.index)
    xa = df["exit_ask"] if "exit_ask" in df.columns else pd.Series(np.nan, index=df.index)
    exit_ = np.where(df["qty"] > 0, xb.fillna(df["exit_price"] - half), xa.fillna(df["exit_price"] + half))
    return df["qty"] * df["multiplier"] * (exit_ - entry)


def bid_ask_fill(df: pd.DataFrame) -> dict[str, Any]:
    """Fantasy fill: fills at the mid (or better) of a quoted spread, and the P&L when the same trades fill at the touch."""
    if not _has(df, "bid", "ask"):
        return _skip("bid_ask_fill", "no bid/ask in the table, so fills cannot be compared with the spread")
    q = df.dropna(subset=["bid", "ask"])
    if (q["ask"] < q["bid"]).any():
        return check("bid_ask_fill", "integrity", "fail", "some quotes have ask below bid", {"rows": int((q["ask"] < q["bid"]).sum())})
    mid, half = (q["bid"] + q["ask"]) / 2.0, (q["ask"] - q["bid"]) / 2.0
    worse = np.where(q["qty"] > 0, q["fill_price"] - mid, mid - q["fill_price"])  # > 0: paid more than the mid
    mid_share = float(np.mean(worse <= 0.05 * half.clip(lower=1e-12)))
    better = float(np.mean(np.where(q["qty"] > 0, q["fill_price"] < mid - 1e-9, q["fill_price"] > mid + 1e-9)))
    spread_pct = float((half * 2 / mid.clip(lower=1e-12)).median())
    details: dict[str, Any] = {"trades": int(len(q)), "share_at_or_better_than_mid": round(mid_share, 3), "share_better_than_mid": round(better, 3), "median_spread_pct_of_mid": round(spread_pct, 4)}
    pr = pnl_reported(q)
    done = pr.notna()
    if done.any():
        pt = pnl_at_touch(q)
        details |= {"pnl_reported": round(float(pr[done].sum()), 2), "pnl_at_touch": round(float(pt[done].sum()), 2)}
        if pr[done].sum() > 0 >= pt[done].sum():
            return check("bid_ask_fill", "economics", "fail", "the profit exists only because fills are at the mid or better: at the touch it is zero or negative", details)
    if better > 0.2:
        return check("bid_ask_fill", "economics", "fail", f"{better:.0%} of fills are better than the mid of the quote: not obtainable", details)
    if mid_share > 0.5:
        return check("bid_ask_fill", "economics", "warn", f"{mid_share:.0%} of fills are at the mid: a passive fill is not certain on a wide spread", details)
    return check("bid_ask_fill", "economics", "pass", f"fills are at or beyond the mid in most cases (median spread {spread_pct:.1%} of mid)", details)


def iv_asof(df: pd.DataFrame) -> dict[str, Any]:
    """Volatility from the future: an IV observed after the decision date used to price or choose the trade."""
    if not _has(df, "iv_used"):
        return _skip("iv_asof", "no iv_used column")
    if "iv_asof" not in df.columns or df["iv_asof"].isna().all():
        return _skip("iv_asof", "no iv_asof date: the date of the volatility observation is unknown")
    d = df.dropna(subset=["iv_used", "iv_asof"])
    late = d[d["iv_asof"] > d["date"]]
    details = {"rows": int(len(d)), "from_the_future": int(len(late)), "max_days_ahead": int((late["iv_asof"] - late["date"]).dt.days.max()) if len(late) else 0}
    if len(late):
        return check("iv_asof", "lookahead", "fail", f"{len(late)} of {len(d)} trades use a volatility observed after the decision", details)
    return check("iv_asof", "lookahead", "pass", "every volatility was observed on or before the decision date", details)


def _snapshots(df: pd.DataFrame) -> list[pd.DataFrame]:
    """Open positions at each distinct entry date (a trade is open from its date until exit_date, or its expiry)."""
    end = df["exit_date"].fillna(df["expiry"]) if "exit_date" in df.columns else df["expiry"]
    out = []
    for t in sorted(df["date"].unique()):
        open_ = df[(df["date"] <= t) & (end > t)].copy()
        if len(open_):
            open_["t_now"] = t
            out.append(open_)
    return out


def tail_stress(df: pd.DataFrame, equity: float | None, r: float = 0.0, q: float = 0.0) -> dict[str, Any]:
    """Reprice the open book at its worst moment with the underlying -20 % / +20 % and volatility doubled; also net gamma."""
    need = ("underlying_price", "iv_used")
    if not _has(df, *need):
        return _skip("tail_stress", "needs underlying_price and iv_used to reprice the book")
    d = df.dropna(subset=list(need)).copy()
    worst, worst_gamma, when = 0.0, 0.0, None
    for snap in _snapshots(d):
        t = ((snap["expiry"] - snap["t_now"]).dt.days.to_numpy() / 365.0).clip(min=0.0)
        s0 = snap.groupby("symbol")["underlying_price"].transform("last").to_numpy()  # latest price known at that date
        k, vol, call = snap["strike"].to_numpy(), snap["iv_used"].to_numpy(), (snap["right"] == "C").to_numpy()
        size = (snap["qty"] * snap["multiplier"]).to_numpy()
        base = bs.price(s0, k, t, vol, call, r, q)
        g = float(np.sum(size * bs.gamma(s0, k, t, vol, r, q) * s0 * s0 * 0.01))  # dollar gamma per 1 % move
        if g < worst_gamma:
            worst_gamma = g
        for move, vm in SCENARIOS:
            loss = float(np.sum(size * (bs.price(s0 * (1 + move), k, t, vol * vm, call, r, q) - base)))
            if loss < worst:
                worst, when = loss, pd.Timestamp(snap["t_now"].iloc[0]).date().isoformat()
    realised = float(pnl_reported(df).sum(skipna=True))
    details: dict[str, Any] = {"worst_stress_pnl": round(worst, 2), "worst_at": when, "net_dollar_gamma_per_1pct": round(worst_gamma, 2), "scenarios": "underlying -20% and +20% with volatility x2", "realised_pnl": round(realised, 2)}
    if equity:
        share = -worst / float(equity)
        details["stress_loss_share_of_equity"] = round(share, 3)
        if share > 0.5:
            return check("tail_stress", "economics", "fail", f"a -20%/+20% move with volatility doubled loses {share:.0%} of equity: the book sells a tail", details)
        if share > 0.2:
            return check("tail_stress", "economics", "warn", f"the stress scenario loses {share:.0%} of equity", details)
        return check("tail_stress", "economics", "pass", f"the stress scenario loses {share:.0%} of equity", details)
    details["equity"] = "not given: pass --equity to compare the stress loss with the account"
    if worst < 0 and realised > 0 and -worst > 5 * realised:
        return check("tail_stress", "economics", "warn", "the stress loss is more than 5x the whole realised profit (no equity given to size it)", details)
    return check("tail_stress", "economics", "pass", "no outsized stress loss relative to the realised profit (equity not given)", details)


def assignment_pin(df: pd.DataFrame) -> dict[str, Any]:
    """Early exercise and pin risk warnings for short American options. A warning only: it needs live quotes to be exact."""
    short = df[(df["qty"] < 0)]
    if short.empty:
        return check("early_exercise_pin", "economics", "pass", "no short options: no assignment risk", {})
    notes: list[str] = []
    american = short[short["style"].astype(str).str.lower() == "american"]
    if "dividend" in df.columns and "ex_div_date" in df.columns:
        calls = american[(american["right"] == "C") & american["ex_div_date"].notna() & (american["ex_div_date"] <= american["expiry"]) & (american["ex_div_date"] >= american["date"])]
        if len(calls):
            notes.append(f"{len(calls)} short American call(s) are open over an ex-dividend date: early assignment is likely when the call is in the money and its time value is below the dividend")
    if "underlying_at_expiry" in df.columns:
        near = short[(short["underlying_at_expiry"].notna()) & ((short["underlying_at_expiry"] - short["strike"]).abs() / short["strike"] < 0.005)]
        if len(near):
            notes.append(f"{len(near)} short option(s) expired within 0.5% of the strike: pin risk (assignment unknown until after the close)")
    else:
        notes.append("underlying_at_expiry is not given: pin risk is not assessed")
    deep = american[(american["right"] == "P") & american["underlying_price"].notna() & (american["underlying_price"] < 0.8 * american["strike"])] if "underlying_price" in american.columns else american.iloc[0:0]
    if len(deep):
        notes.append(f"{len(deep)} short American put(s) were deep in the money at entry: early exercise is rational")
    warn = [n for n in notes if "not assessed" not in n]
    details = {"short_trades": int(len(short)), "notes": notes}
    if warn:
        return check("early_exercise_pin", "economics", "warn", "; ".join(warn), details)
    if "underlying_at_expiry" not in df.columns:
        return check("early_exercise_pin", "economics", "skip",
                     "not assessed: underlying_at_expiry is not given, so pin risk of the short options is unknown",
                     {**details, "not_assessed": True})
    return check("early_exercise_pin", "economics", "info", "no assignment or pin warning" + ("; " + notes[0] if notes else ""), details)


def margin_simplified(df: pd.DataFrame, equity: float | None) -> dict[str, Any]:
    """Peak margin of the short options, simplified Reg-T style: max(20% of S - OTM amount, 10% of S or K) + premium, per contract."""
    if not _has(df, "underlying_price"):
        return _skip("margin_simplified", "needs underlying_price")
    peak, when = 0.0, None
    for snap in _snapshots(df.dropna(subset=["underlying_price"])):
        sh = snap[snap["qty"] < 0]
        if sh.empty:
            continue
        s0 = sh.groupby("symbol")["underlying_price"].transform("last")
        otm = np.where(sh["right"] == "C", (sh["strike"] - s0).clip(lower=0), (s0 - sh["strike"]).clip(lower=0))
        floor = np.where(sh["right"] == "C", 0.10 * s0, 0.10 * sh["strike"])
        per = np.maximum(0.20 * s0 - otm, floor) + sh["fill_price"]
        total = float((per * (-sh["qty"]) * sh["multiplier"]).sum())
        if total > peak:
            peak, when = total, pd.Timestamp(snap["t_now"].iloc[0]).date().isoformat()
    details: dict[str, Any] = {"peak_margin": round(peak, 2), "peak_at": when, "model": "simplified Reg-T style, naked options only; real broker and portfolio margin differ"}
    if not equity:
        return check("margin_simplified", "economics", "info", f"peak margin about {peak:,.0f} (equity not given, so no ratio)", details)
    ratio = peak / float(equity)
    details["peak_margin_share_of_equity"] = round(ratio, 3)
    if ratio > 1.0:
        return check("margin_simplified", "economics", "fail", f"the short options need {ratio:.0%} of equity as margin: the book could not be held", details)
    if ratio > 0.7:
        return check("margin_simplified", "economics", "warn", f"the short options use {ratio:.0%} of equity as margin: little room for a move", details)
    return check("margin_simplified", "economics", "pass", f"peak margin {ratio:.0%} of equity", details)


def dividends(df: pd.DataFrame) -> dict[str, Any]:
    """Short calls held over an ex-dividend date without a dividend input."""
    calls = df[(df["qty"] < 0) & (df["right"] == "C")]
    if calls.empty:
        return check("dividends", "economics", "pass", "no short calls: dividends do not change the result", {})
    if "ex_div_date" not in df.columns or df["ex_div_date"].isna().all():
        return _skip("dividends", "no ex_div_date column: dividends and early assignment before them are unknown")
    over = calls[calls["ex_div_date"].notna() & (calls["ex_div_date"] >= calls["date"]) & (calls["ex_div_date"] <= calls["expiry"])]
    if len(over) and ("dividend" not in df.columns or over["dividend"].isna().any()):
        return check("dividends", "economics", "warn", f"{len(over)} short call(s) span an ex-dividend date and the dividend amount is missing", {"rows": int(len(over))})
    return check("dividends", "economics", "pass", f"{len(over)} short call(s) span an ex-dividend date; amounts are given", {"rows": int(len(over))})


def chain_scope(df: pd.DataFrame) -> dict[str, Any]:
    """Always present: what the table cannot show."""
    return check("options_chain", "economics", "info", "not assessed: no historical option chain was supplied, so the volatility surface as of each date, strikes that could not be traded, and open interest are not verified",
                 {"not_assessed": True, "columns": sorted(df.columns)})
