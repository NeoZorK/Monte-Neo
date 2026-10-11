"""Reference alpha 1: diversified time-series trend following with volatility targeting (version 1).

A simple, low-return, robust strategy. It is here to show what an honest, boring strategy looks like when an
independent verifier tests it, not to make money. The parameters below were fixed in advance and never optimised.

Rules
-----
1. Signal per symbol: the mean of ``sign(close_t / close_(t-L) - 1)`` for L in 63, 126 and 252 bars. It is
   +1 when all three lookbacks are up, -1 when all are down, and in between otherwise. It uses closes up to bar t only.
2. Size per symbol: ``signal * (TARGET_VOL / sqrt(n_symbols)) / sigma_t``, where ``sigma_t`` is the EWMA volatility
   (span 60) of daily returns, annualised with 252. With roughly uncorrelated symbols the portfolio aims near
   ``TARGET_VOL`` (10 %). Each ``|weight|`` is capped at ``2 / n_symbols``.
3. Rebalance monthly in four weekly tranches: four sleeves rebalance every 21 bars at offsets 0, 5, 10 and 15;
   the final weight is the average of the sleeves. A sleeve keeps its old weight while the new target is within
   a no-trade band of 10 % of the target (a flat sleeve always opens).
4. Gross cap: this file does not scale to gross 1. The Monte-Neo engine scales every timestamp with
   gross > 1 down proportionally. With the cap of ``2 / n_symbols`` per symbol, the gross can reach 2 when
   all symbols trend together; the engine then halves it, so the realised risk is lower than the 10 % target in
   such periods and the strategy never uses leverage.

The fill convention: a weight computed from the close of bar t is traded at the open of bar t + 1, so the
rules are causal (the verifier's truncation probe confirms it).

Literature: Moskowitz, Ooi and Pedersen, "Time Series Momentum" (2012); Hurst, Ooi and Pedersen,
"A Century of Evidence on Trend-Following Investing" (2017).

DISCLAIMER (full text; the same text is the module constant ``DISCLAIMER``):

Not investment advice. Monte-Neo is a research and verification tool. Its reports, examples and reference
strategies illustrate a method; they are not a recommendation, an offer or a call to buy, sell or trade any
instrument, and not a promise of profit. Simulated and past results do not predict future returns. Trading can
lose money, including more than the initial capital when leverage is used. Decisions and their consequences
are yours; consult a licensed adviser if you need advice.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.disclaimer import FULL as DISCLAIMER

__all__ = ["DISCLAIMER", "signal"]

LOOKBACKS: tuple[int, ...] = (63, 126, 252)  # bars; fixed in advance, never re-tuned on performance
TARGET_VOL = 0.10  # annual volatility the whole portfolio aims at (split by sqrt(n_symbols) per asset)
VOL_SPAN = 60  # EWMA span (bars) of the volatility estimate
TRADING_DAYS = 252  # annualisation of daily volatility
REBALANCE_EVERY = 21  # bars between rebalances of one sleeve (about one month)
SLEEVE_OFFSETS: tuple[int, ...] = (0, 5, 10, 15)  # four weekly tranches
NO_TRADE_BAND = 0.10  # a sleeve keeps its weight while |target - held| <= band * |target|
CAP_GROSS_PER_SYMBOL = 2.0  # |weight| <= CAP_GROSS_PER_SYMBOL / n_symbols


def _target_weights(close: np.ndarray) -> np.ndarray:
    """Vol-targeted trend weights per bar and symbol, before rebalancing rules.

    Args:
        close: Close prices, shape (bars, symbols); NaN where a symbol has no price.

    Returns:
        Array of the same shape; NaN where the signal or volatility is not yet defined.
    """
    n_bars, n_sym = close.shape
    frame = pd.DataFrame(close)
    votes = np.zeros((n_bars, n_sym))
    for lb in LOOKBACKS:
        past = frame.pct_change(lb, fill_method=None).to_numpy()
        votes += np.where(np.isnan(past), np.nan, np.sign(past))
    signal = votes / len(LOOKBACKS)
    rets = frame.pct_change(fill_method=None)
    sigma = np.sqrt((rets**2).ewm(span=VOL_SPAN, min_periods=VOL_SPAN).mean().to_numpy() * TRADING_DAYS)
    per_asset = TARGET_VOL / np.sqrt(n_sym)
    with np.errstate(divide="ignore", invalid="ignore"):
        w = signal * per_asset / sigma
    cap = CAP_GROSS_PER_SYMBOL / n_sym
    return np.clip(w, -cap, cap)


def _sleeve(target: np.ndarray, offset: int) -> np.ndarray:
    """One sleeve: rebalances every REBALANCE_EVERY bars from ``offset`` with a no-trade band."""
    n_bars, n_sym = target.shape
    out = np.zeros((n_bars, n_sym))
    held = np.zeros(n_sym)
    for t in range(n_bars):
        if t >= offset and (t - offset) % REBALANCE_EVERY == 0:
            tgt = target[t]
            ok = np.isfinite(tgt)
            new = np.where(ok, tgt, 0.0)
            keep = ok & (held != 0) & (np.abs(new - held) <= NO_TRADE_BAND * np.abs(new)) & (np.sign(new) == np.sign(held))
            held = np.where(keep, held, new)
        out[t] = held
    return out


def signal(df: pd.DataFrame) -> np.ndarray:
    """Target weight per row of a long universe table (timestamp, symbol, open, high, low, close).

    Args:
        df: Universe rows sorted by timestamp then symbol.

    Returns:
        One target weight per row, in the order of ``df``. Zero during the warm-up (about one year).
    """
    symbols = df["symbol"].astype(str).to_numpy()
    stamps = pd.to_datetime(df["timestamp"], utc=True).to_numpy()
    close = (
        pd.DataFrame({"t": stamps, "s": symbols, "c": df["close"].to_numpy(dtype=float)})
        .pivot_table(index="t", columns="s", values="c", aggfunc="last")
        .sort_index()
    )
    target = _target_weights(close.to_numpy())
    book = sum(_sleeve(target, k) for k in SLEEVE_OFFSETS) / len(SLEEVE_OFFSETS)
    weights = pd.DataFrame(book, index=close.index, columns=close.columns)
    long = weights.stack()
    key = pd.MultiIndex.from_arrays([stamps, symbols])
    return long.reindex(key).fillna(0.0).to_numpy(dtype=float)
