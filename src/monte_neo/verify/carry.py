"""Delta-neutral carry (spot long, perpetual short) as a strategy in the full verifier, funding paid as explicit P&L.

The return-series path (``verify --returns``) cannot run signal-level checks, so a carry strategy stayed at a low ARL
by construction. Here the hedged position becomes an instrument of its own: per bar it earns

``spot return - perpetual return + funding``  (the short perpetual receives what the long pays)

and this series is the ``close`` of a synthetic table (``open`` is the previous close, so a signal on bar ``t`` fills on the
next bar exactly like any other strategy). ``signal(df)`` still sees ``spot_close``, ``perp_close``, ``basis`` and
``funding_rate`` and returns 1 (hold the hedged pair) or 0 (flat), so the look-ahead, truncation, perturbation,
cost and significance checks of ``verify_strategy`` all apply to the entry rule. Entering or leaving costs both legs: the
model charges the sum of the two per-leg costs.

Funding of a bar is the rate settled **over** that bar: a signal may use it only on later bars, and the truncation probe
catches a rule that reads the funding it is about to earn.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.carry_market import entries, few_decisions_row, margin_rows
from monte_neo.verify.checks import check
from monte_neo.verify.ingest import load_signal_fn

MIN_BARS = 60
PROBE_NOISE = 0.03
FUNDING_SHARE_WARN = 0.5


def quote_volume(df: pd.DataFrame) -> np.ndarray | None:
    """Traded value per bar a hedged pair can use: the smaller of its two legs, **in quote currency** (``volume`` is read as quote value of the thinner leg)."""
    cols = [c for c in ("spot_quote_volume", "perp_quote_volume", "volume") if c in df.columns]
    if not cols:
        return None
    return np.fmin.reduce([pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float) for c in cols])


def _one(df: pd.DataFrame, spread_bars: int = 1) -> pd.DataFrame:
    num = df[["spot_close", "perp_close", "funding_rate"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(num.to_numpy()).all():
        raise ValueError("spot_close, perp_close and funding must be finite numbers with no empty cells")
    if (num[["spot_close", "perp_close"]] <= 0).any().any():
        raise ValueError("prices must be positive")
    if len(df) < MIN_BARS:
        raise ValueError(f"only {len(df)} bars; at least {MIN_BARS} are needed")
    stamps = pd.to_datetime(df["timestamp"], errors="coerce")
    if stamps.isna().any() or not stamps.is_monotonic_increasing or stamps.duplicated().any():
        raise ValueError("timestamps must be valid, increasing and unique")
    spot, perp, f = (num[c].to_numpy() for c in ("spot_close", "perp_close", "funding_rate"))
    basis_pnl = np.zeros(len(df))
    basis_pnl[1:] = spot[1:] / spot[:-1] - perp[1:] / perp[:-1]
    ret = basis_pnl + f  # the funding settled over bar t goes to the short perpetual
    ret[0] = 0.0
    if (ret <= -1.0).any():
        raise ValueError("a bar loses 100% or more of the hedged position: check the prices and the funding units")
    close = 100.0 * np.cumprod(1.0 + ret)
    open_ = np.concatenate([[100.0], close[:-1]])
    out = pd.DataFrame({"timestamp": stamps.to_numpy(), "open": open_, "high": np.maximum(open_, close), "low": np.minimum(open_, close), "close": close,
                        "spot_close": spot, "perp_close": perp, "basis": perp / spot - 1.0, "funding_rate": f, "basis_pnl": basis_pnl})
    for c in ("perp_high", "in_universe", "spot_quote_volume", "perp_quote_volume"):
        if c in df.columns:
            out[c] = pd.to_numeric(df[c], errors="coerce").to_numpy() if c != "in_universe" else df[c].astype(bool).to_numpy()
    q = quote_volume(df)
    if q is not None:
        k = max(1, int(spread_bars))
        spread = pd.Series(q).iloc[::-1].rolling(k, min_periods=1).sum().iloc[::-1].to_numpy() if k > 1 else q  # the bars an order may be spread over
        out["volume"] = spread / close  # the engine reads traded value as volume x close; the close here is the hedged index, so divide it out
    return out


def membership_from_rule(raw: pd.DataFrame, rule: dict[str, Any]) -> pd.Series:
    """Ex-ante membership recomputed by the verifier: ``top_n`` coins by ``on`` (a quote-volume column) over the ``lookback_bars`` bars
    *before* each rebalance bar, rebalanced every ``rebalance_every`` bars. A bar belongs to the set chosen at the last rebalance bar.

    Raises:
        ValueError: A missing rule key, a non-positive number, or no such volume column.
    """
    need = ("top_n", "lookback_bars", "rebalance_every")
    if any(k not in rule for k in need) or any(int(rule[k]) < 1 for k in need):
        raise ValueError("universe_rule needs top_n, lookback_bars and rebalance_every (positive integers) and optionally on (a quote-volume column)")
    col = rule.get("on", "perp_quote_volume")
    if col not in raw.columns or "symbol" not in raw.columns:
        raise ValueError(f"universe_rule needs a symbol column and a {col} column in the table")
    n, look, every = int(rule["top_n"]), int(rule["lookback_bars"]), int(rule["rebalance_every"])
    wide = raw.assign(timestamp=pd.to_datetime(raw["timestamp"])).pivot(index="timestamp", columns="symbol", values=col).sort_index()
    member = np.zeros(wide.shape, dtype=bool)
    for t0 in range(look, wide.shape[0], every):
        win = wide.iloc[t0 - look:t0]  # strictly earlier bars
        score = win.mean().where(win.notna().sum() >= max(1, look // 2))
        top = score.dropna().sort_values(ascending=False, kind="stable").index[:n]
        member[t0:t0 + every, [wide.columns.get_loc(c) for c in top]] = True
    flags = pd.DataFrame(member, index=wide.index, columns=wide.columns).stack()
    keys = pd.MultiIndex.from_arrays([pd.to_datetime(raw["timestamp"]), raw["symbol"]])
    return pd.Series(flags.reindex(keys).fillna(False).to_numpy(dtype=bool), index=raw.index)


def carry_table(source: str | Path | pd.DataFrame, *, universe_rule: dict[str, Any] | None = None, capacity_spread_bars: int = 1) -> pd.DataFrame:
    """Build the verifier table from ``timestamp, spot_close, perp_close`` and ``funding_rate`` (fraction a long pays per bar) or ``funding_bps``.

    A ``symbol`` column makes a basket: each coin becomes its own hedged instrument and the table is a universe (one row per
    timestamp and coin; ``signal(df)`` returns one weight per row). Optional ``spot_quote_volume`` / ``perp_quote_volume`` (traded value per
    bar in quote currency; ``volume`` is read as the quote value of the thinner leg) feed the capacity estimate: the capital a fill can use is
    the smaller of the two legs times the participation share, over ``capacity_spread_bars`` bars. ``perp_high`` (the bar's highest
    perpetual price) lets the margin check test liquidation inside the bar. ``universe_rule`` adds ``in_universe`` (see :func:`membership_from_rule`).

    Raises:
        ValueError: Missing or non-finite columns, non-positive prices, too few bars, or a hedged return of -100% or worse.
    """
    df = source.copy() if isinstance(source, pd.DataFrame) else (pd.read_parquet(source) if str(source).lower().endswith((".parquet", ".pq")) else pd.read_csv(source))
    df.columns = [str(c).strip() for c in df.columns]
    for need in ("timestamp", "spot_close", "perp_close"):
        if need not in df.columns:
            raise ValueError(f"missing column {need}; the carry table needs timestamp, spot_close, perp_close and funding_rate (or funding_bps)")
    if "funding_rate" not in df.columns:
        if "funding_bps" not in df.columns:
            raise ValueError("missing funding: add funding_rate (fraction a long pays per bar) or funding_bps")
        df["funding_rate"] = pd.to_numeric(df["funding_bps"], errors="coerce") / 1e4
    if universe_rule is not None:
        df["in_universe"] = membership_from_rule(df, universe_rule)
    if "symbol" not in df.columns:
        return _one(df, capacity_spread_bars)
    parts = []
    for sym, g in df.groupby("symbol", sort=True):
        one = _one(g.reset_index(drop=True), capacity_spread_bars)
        one.insert(1, "symbol", str(sym))
        parts.append(one)
    return pd.concat(parts, ignore_index=True).sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)


def decomposition_row(table: pd.DataFrame, weights: np.ndarray | None) -> dict[str, Any]:
    """Check row ``carry_decomposition``: where the P&L of the held hedged pairs comes from, funding or the basis moving."""
    from monte_neo.verify.market import market_for

    f, b, _ = market_for(table).parts()  # type: ignore[union-attr]
    w = np.ones_like(f) if weights is None else np.abs(np.nan_to_num(np.asarray(weights, dtype=float))).reshape(f.shape)
    prev = np.vstack([np.zeros((1, f.shape[1])), w[:-1]])  # position held over bar t was decided at t-1
    funding = float(np.nansum(prev * np.nan_to_num(f)))
    basis = float(np.nansum(prev * np.nan_to_num(b)))
    total = funding + basis
    bars = int(np.sum(prev.sum(axis=1) > 0))
    n = f.shape[0]
    if bars == 0:
        return check("carry_decomposition", "economics", "skip", "the strategy never held the hedged pair", {"held_bars": 0})
    share = funding / total if total > 0 else None
    details = {"funding_pnl": funding, "basis_pnl": basis, "total_pnl": total, "funding_share": share, "held_bars": bars,
               "held_share": bars / n, "bars_paying_funding": int(np.sum((prev > 0) & (f < 0)))}
    if total <= 0 or funding <= 0:
        status, why = "warn", "the hedged pair did not earn from funding"
    elif share is not None and share < FUNDING_SHARE_WARN:
        status, why = "warn", f"only {share:.0%} of the profit is funding; the rest is the basis moving, which is a bet and not carry"
    else:
        status, why = "pass", "the profit is funding, as carry should be"
    return check("carry_decomposition", "economics", status,
                 f"funding {funding:+.2%}, basis {basis:+.2%} over {bars} held bars: {why}", details)


def carry_future_probe(fn: Any, raw: pd.DataFrame, n_checks: int = 6, seed: int = 0) -> dict[str, Any]:
    """Row ``carry_future_probe``: does the signal at bar ``t`` change when the future of the prices and of funding changes?

    From several bars ``t`` the spot and perpetual prices after ``t`` are scaled by random noise and the funding after ``t`` is
    replaced by its negative plus noise; the table is rebuilt (so ``basis`` and the hedged index follow) and the signal up to ``t``
    must not move. A rule that reads the funding it is about to earn, or the next basis, fails here. Deterministic.
    """
    cols = ["timestamp", "spot_close", "perp_close", "funding_rate"] + [c for c in ("symbol", "volume", "in_universe", "perp_high", "spot_quote_volume", "perp_quote_volume") if c in raw.columns]
    base = raw[cols].copy()
    table = carry_table(base)
    stamps = np.sort(pd.to_datetime(table["timestamp"]).unique())
    if len(stamps) < 120:
        return check("carry_future_probe", "lookahead", "skip", "fewer than 120 bars: too short to probe the future", {})
    ref = np.asarray(fn(table.copy()), dtype=float).reshape(-1)
    rng = np.random.default_rng(seed)
    cuts = np.unique(np.linspace(len(stamps) * 0.25, len(stamps) * 0.9, n_checks).astype(int))
    moved = []
    for ci in cuts:
        cut = stamps[ci]
        fut = pd.to_datetime(base["timestamp"]) > cut
        pert = base.copy()
        k = int(fut.sum())
        for c in ("spot_close", "perp_close"):
            pert.loc[fut, c] = pert.loc[fut, c].to_numpy() * np.exp(rng.normal(0, PROBE_NOISE, k))
        pert.loc[fut, "funding_rate"] = -pert.loc[fut, "funding_rate"].to_numpy() + rng.normal(0, 3e-4, k)
        tab2 = carry_table(pert)
        out = np.asarray(fn(tab2.copy()), dtype=float).reshape(-1)
        before = (pd.to_datetime(table["timestamp"]) <= cut).to_numpy()
        if out.shape != ref.shape or not np.allclose(np.nan_to_num(out[before]), np.nan_to_num(ref[before])):
            moved.append(str(pd.Timestamp(cut)))
    details = {"checked": int(cuts.size), "cuts_where_the_past_moved": moved}
    if moved:
        return check("carry_future_probe", "lookahead", "fail",
                     f"the signal changed before {moved[0]} when only later prices or funding changed in {len(moved)} of {cuts.size} probes: it reads the future (a next funding rate or a next basis move)", details)
    return check("carry_future_probe", "lookahead", "pass", f"the signal did not move in {cuts.size} probes that changed only later prices and funding", details)


def attribution_rows(rets: np.ndarray, market: Any, warmup: int, ppy: float, reference_symbol: str | None, weights: np.ndarray) -> list[dict[str, Any]]:
    """Rows ``residual_alpha`` and ``hidden_short_volatility`` for the carry returns, against the underlying (and the equal-weight spot of a basket).

    The hidden-short-volatility row also reports what carry is exposed to by nature: the funding paid on held bars when funding is negative
    and the worst basis bar; it warns when negative funding takes back most of what funding earned.
    """
    from monte_neo.alpha.attribution import check_residual_alpha
    from monte_neo.alpha.attribution_tail import check_hidden_short_vol

    ew = np.asarray(market.reference_returns(warmup), dtype=float)
    cols = {"market": ew}
    if hasattr(market, "symbols") and reference_symbol is not None:
        if reference_symbol not in market.symbols:
            raise ValueError(f"reference_symbol {reference_symbol!r} is not a coin of the basket: {', '.join(map(str, market.symbols[:10]))}")
        j = list(market.symbols).index(reference_symbol)
        spot = market._m["spot_close"][warmup:, j]
        cols = {"market": spot[1:] / spot[:-1] - 1.0, "ew_spot": ew}
    n = min(rets.size, *(v.size for v in cols.values()))
    f = pd.DataFrame({k: v[-n:] for k, v in cols.items()})
    r = np.asarray(rets[-n:], dtype=float)
    ok = np.isfinite(r) & f.notna().all(axis=1).to_numpy()
    r, f = r[ok], f[ok].reset_index(drop=True)
    alpha, tail = check_residual_alpha(r, f, ppy), check_hidden_short_vol(r, f)
    fund, basis, _ = market.parts()
    wprev = np.vstack([np.zeros((1, fund.shape[1])), np.abs(np.nan_to_num(np.asarray(weights, dtype=float)).reshape(fund.shape))[:-1]])
    earned = float(np.sum(wprev * np.clip(np.nan_to_num(fund), 0, None)))
    paid = float(np.sum(wprev * np.clip(np.nan_to_num(fund), None, 0)))
    held_basis = np.where(wprev > 0, np.nan_to_num(basis), np.nan)
    worst = float(np.nanmin(held_basis)) if np.isfinite(held_basis).any() else 0.0
    share = -paid / earned if earned > 0 else None
    tail["details"] = {**tail.get("details", {}), "funding_earned": earned, "funding_paid_when_negative": -paid, "negative_funding_share_of_earned": share, "worst_basis_bar_while_held": worst}
    if share is not None and share >= 0.5 and tail["status"] == "pass":
        tail = check("hidden_short_volatility", "statistics", "warn", f"negative funding takes back {share:.0%} of the funding earned: the carry sells insurance against funding turning", tail["details"])
    return [alpha, tail]


def verify_carry(
    carry: str | Path | pd.DataFrame, *, strategy: str | Path | None = None, signal_fn: Any = None, source: str | None = None,
    spot_cost_bps: float = 10.0, perp_cost_bps: float = 5.0, capital_cost_apr: float = 0.0, perp_leverage: float = 3.0,
    maintenance_margin: float = 0.005, margin_policy: dict[str, float] | None = None, universe_rule: dict[str, Any] | None = None,
    reference_symbol: str | None = None, capacity_spread_bars: int = 1, extra_checks: list[dict[str, Any]] | None = None, **verify_kwargs: Any,
) -> dict[str, Any]:
    """Verify a delta-neutral carry rule (or a basket of coins) with the full verifier; funding is explicit P&L.

    Carry rules differ from the generic ones (see :mod:`monte_neo.verify.carry_market`): accuracy is measured on the basis, the
    sample is the effective number of independent accrual periods, the beta reference is the underlying, and the certificate adds
    ``carry_decomposition``, ``carry_future_probe``, ``carry_margin`` (and ``carry_margin_no_topup`` with a policy), ``few_decisions``,
    ``residual_alpha`` and ``hidden_short_volatility`` against the underlying, and for a basket with ``universe_rule`` ``universe_rule``.

    Args:
        carry: Table for :func:`carry_table`.
        strategy: File with ``signal(df)`` returning 1 (hold the pair) or 0 (flat) per bar (per row for a basket); or pass ``signal_fn``.
        spot_cost_bps: All-in cost of one spot fill (fee and spread), in bps.
        perp_cost_bps: All-in cost of one perpetual fill, in bps. Entry and exit pay both.
        capital_cost_apr: Yearly cost of the capital tied up while the pair is held (for example 0.05); charged per held bar.
        perp_leverage: Leverage of the short perpetual for the margin check; the spot leg is not collateral.
        maintenance_margin: Maintenance margin of the perpetual, as a fraction of its notional.
        margin_policy: Declared collateral policy ``{"trigger": share of notional, "delay_bars": n, "cost_bps": c}``: top up to ``1/leverage``
            when equity falls below ``trigger`` of the notional; the transfer arrives ``delay_bars`` later. Without it nothing is ever added.
        universe_rule: ``{"top_n", "lookback_bars", "rebalance_every", "on"}``: ex-ante composition the verifier recomputes (basket only).
        reference_symbol: The coin used as the market (for example ``BTC``); default the equal-weight spot of the basket.
        capacity_spread_bars: Bars an order may be spread over for the capacity estimate (1 = the fill bar only).
        verify_kwargs: Passed to ``verify_strategy`` (``n_trials``, ``claim``, ...).

    Raises:
        ValueError: A bad table, negative costs, or no strategy.
    """
    from monte_neo.verify.engine import simulate
    from monte_neo.verify.ingest import resolve_positions
    from monte_neo.verify.market import market_for
    from monte_neo.verify.stats import bar_returns, infer_periods_per_year
    from monte_neo.verify.verdict import verify_strategy

    if min(spot_cost_bps, perp_cost_bps, capital_cost_apr) < 0:
        raise ValueError("costs must be non-negative")
    raw = carry.copy() if isinstance(carry, pd.DataFrame) else (pd.read_parquet(carry) if str(carry).lower().endswith((".parquet", ".pq")) else pd.read_csv(carry))
    if "funding_rate" not in raw.columns and "funding_bps" in raw.columns:
        raw["funding_rate"] = pd.to_numeric(raw["funding_bps"], errors="coerce") / 1e4
    if universe_rule is not None:
        raw["in_universe"] = membership_from_rule(raw, universe_rule)
    table = carry_table(raw, capacity_spread_bars=capacity_spread_bars)
    if strategy is not None:
        signal_fn, text = load_signal_fn(strategy)
        source = source if source is not None else text
    if signal_fn is None:
        raise ValueError("verify_carry needs strategy= or signal_fn=")
    market = market_for(table)
    stamps = pd.to_datetime(table["timestamp"]).drop_duplicates()
    ppy = float(verify_kwargs.get("periods_per_year") or infer_periods_per_year(stamps))
    model = verify_kwargs.pop("model", None) or ExecutionModel(
        side_mode="long_flat", commission_bps=spot_cost_bps + perp_cost_bps, slippage_bps=0.0, warmup_bars=max(0, min(60, market.n_bars // 10)),
        funding_bps_per_bar=capital_cost_apr * 1e4 / ppy)
    values = np.asarray(signal_fn(table.copy()), dtype=float).reshape(-1)
    if values.size != len(table):
        raise ValueError(f"signal length {values.size} != row count {len(table)}")
    clipped = np.clip(np.nan_to_num(values), 0.0, 1.0)
    mode = resolve_positions(clipped, verify_kwargs.get("positions", "auto"))
    sig, weights = market.positions(clipped, mode, model)
    rets = bar_returns(simulate(market.ohlc, sig, model)["equity"], start=model.warmup_bars)
    years = max((stamps.iloc[-1] - stamps.iloc[0]).total_seconds() / (365.25 * 86400), 1e-9)
    funding, _, perp = market.parts()  # type: ignore[union-attr]
    rows = [decomposition_row(table, weights), carry_future_probe(signal_fn, raw), *margin_rows(weights, perp, perp_leverage, maintenance_margin,
            perp_high=market.perp_high(), funding=funding, policy=margin_policy),  # type: ignore[union-attr]
            few_decisions_row(entries(weights), years), *attribution_rows(rets, market, model.warmup_bars, ppy, reference_symbol, weights), *(extra_checks or [])]
    if universe_rule is not None:
        rows.append(universe_rule_row(market, weights, universe_rule))
    return verify_strategy(table, signal_fn=signal_fn, source=source, model=model, extra_checks=rows,
                           extra={"carry": {"spot_cost_bps": spot_cost_bps, "perp_cost_bps": perp_cost_bps, "capital_cost_apr": capital_cost_apr,
                                            "perp_leverage": perp_leverage, "margin_policy": margin_policy, "universe_rule": universe_rule,
                                            "legs": ["spot long", "perpetual short"], "basket": "symbol" in table.columns}},
                           **verify_kwargs)


def universe_rule_row(market: Any, weights: np.ndarray, rule: dict[str, Any]) -> dict[str, Any]:
    """Row ``universe_rule``: positions are only taken in coins the ex-ante rule had selected on that date."""
    member = getattr(market, "member_matrix", lambda: None)()
    if member is None:
        return check("universe_rule", "integrity", "skip", "the table has no composition rule (a basket with universe_rule=... is needed)", {})
    w = np.abs(np.nan_to_num(np.asarray(weights, dtype=float)))
    outside = (w > 0) & ~(np.nan_to_num(member) > 0)
    held = int(np.sum(w > 0))
    details = {"rule": rule, "held_cells": held, "held_outside_rule": int(outside.sum()), "member_share": float(np.mean(np.nan_to_num(member) > 0))}
    if outside.any():
        t, j = (int(x[0]) for x in np.nonzero(outside))
        return check("universe_rule", "integrity", "fail", f"{int(outside.sum())} of {held} positions are in coins the ex-ante rule had not selected on that date "
                     f"(first: {market.symbols[j]} at bar {t}): the composition used information the rule does not have", details)
    return check("universe_rule", "integrity", "pass", f"all {held} positions are in coins the verifier's recomputed ex-ante rule had selected", details)


__all__ = ["attribution_rows", "carry_future_probe", "carry_table", "decomposition_row", "membership_from_rule", "quote_volume", "universe_rule_row", "verify_carry"]
