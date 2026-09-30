"""Verify a backtest that was run in another framework, from what it recorded.

A framework's own result (a vectorbt portfolio, a Freqtrade trade list, Lean order events, Zipline
transactions, a list of fills) is turned into positions per bar of the price table. The verifier
then treats them as ``--signals``: it re-simulates them with its own costs and runs the economic and
statistical checks. Without strategy code the look-ahead probes and the lint cannot run, so the
certificate says so; give the strategy code as well when you have it.

Timing follows the verifier: the position at bar ``t`` is decided at the close of ``t`` and filled
at the open of ``t + 1``. A trade that the framework opened at the open of bar ``t`` therefore
enters the array at ``t - 1``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.ingest import load_ohlcv

FILL_COLUMNS = ("timestamp", "quantity")


@dataclass
class Adapted:
    """A price table and the positions a framework held on it."""

    ohlcv: pd.DataFrame
    positions: np.ndarray
    mode: str = "auto"

    def verify(self, **kwargs: Any) -> dict[str, Any]:
        """Run :func:`monte_neo.verify.verify_strategy` on the adapted backtest."""
        from monte_neo.verify.verdict import verify_strategy

        return verify_strategy(self.ohlcv, signals=self.positions, positions=self.mode, **kwargs)


def _timestamps(ohlcv: pd.DataFrame) -> pd.DatetimeIndex:
    if "timestamp" not in ohlcv.columns:
        raise ValueError("the price table needs a timestamp column (or a DatetimeIndex) to place trades on bars")
    return _naive(pd.DatetimeIndex(pd.to_datetime(ohlcv["timestamp"], utc=True)))


def _naive(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """UTC wall time without a zone, so tz-aware and naive inputs compare."""
    return index.tz_convert("UTC").tz_localize(None) if index.tz is not None else index


def _times(values: Any) -> pd.DatetimeIndex:
    return _naive(pd.DatetimeIndex(pd.to_datetime(pd.Series(values), utc=True)))


def _prices_with_ohlc(close: pd.Series, **parts: Any) -> pd.DataFrame:
    """OHLC table from a close series; missing open/high/low fall back to the close."""
    frame = pd.DataFrame({"timestamp": close.index, "close": close.to_numpy(dtype=np.float64)})
    for name in ("open", "high", "low"):
        part = parts.get(name)
        frame[name] = np.asarray(part, dtype=np.float64) if part is not None else frame["close"]
    return load_ohlcv(frame[["timestamp", "open", "high", "low", "close"]])


def positions_from_fills(ohlcv: pd.DataFrame, fills: pd.DataFrame | list[dict[str, Any]]) -> np.ndarray:
    """Direction held after each bar from signed fill quantities (buys positive, sells negative).

    ``fills`` has ``timestamp`` and ``quantity``. The position is the running sum of the quantities
    filled up to and including each bar; its sign is returned (+1 long, 0 flat, -1 short).
    """
    table = pd.DataFrame(fills)
    missing = [c for c in FILL_COLUMNS if c not in table.columns]
    if missing:
        raise ValueError(f"fills need columns {list(FILL_COLUMNS)}, missing {missing}")
    bars = _timestamps(ohlcv)
    if table.empty:
        return np.zeros(len(bars))
    when = _times(table["timestamp"]).to_numpy()
    qty = pd.to_numeric(table["quantity"], errors="raise").to_numpy(dtype=np.float64)
    # A fill stamped at a bar's open belongs to the decision at the previous close: index - 1.
    where = np.maximum(np.searchsorted(bars.to_numpy(), when, side="left") - 1, 0)
    delta = np.zeros(len(bars))
    np.add.at(delta, where, qty)
    held = np.cumsum(delta)
    held[np.abs(held) < 1e-9 * max(1.0, float(np.abs(qty).max()))] = 0.0  # rounding noise is flat
    return np.sign(held)


def positions_from_trades(
    ohlcv: pd.DataFrame,
    trades: pd.DataFrame | list[dict[str, Any]],
    *,
    open_col: str = "open_time",
    close_col: str = "close_time",
    side_col: str = "side",
    size_col: str | None = None,
) -> np.ndarray:
    """Position per bar from closed trades (entry time, exit time, side, optional size).

    ``side`` is ``+1`` / ``-1`` or ``"long"`` / ``"short"`` / ``"buy"`` / ``"sell"``. Trades that
    overlap add up; the result is clipped to ``[-1, 1]``. A trade holds from the open of the bar it
    was entered on to the open of the bar it was left on (see the module note on timing).
    """
    table = pd.DataFrame(trades)
    for col in (open_col, close_col, side_col):
        if col not in table.columns:
            raise ValueError(f"trades need a {col!r} column")
    bars = _timestamps(ohlcv).to_numpy()
    out = np.zeros(len(bars))
    opens = _times(table[open_col]).to_numpy()
    closes = _times(table[close_col]).to_numpy()
    sizes = pd.to_numeric(table[size_col]).to_numpy(dtype=np.float64) if size_col else np.ones(len(table))
    for t_open, t_close, side, size in zip(opens, closes, table[side_col], sizes, strict=True):
        direction = _direction(side)
        start = int(np.searchsorted(bars, t_open, side="left")) - 1
        stop = int(np.searchsorted(bars, t_close, side="left")) - 1
        out[max(start, 0) : max(stop, 0)] += direction * size
    return np.clip(out, -1.0, 1.0)


def _direction(side: Any) -> float:
    if isinstance(side, str):
        text = side.strip().lower()
        if text in ("long", "buy", "b", "1", "+1"):
            return 1.0
        if text in ("short", "sell", "s", "-1"):
            return -1.0
        raise ValueError(f"unknown trade side {side!r}")
    value = float(side)
    if value == 0.0 or not np.isfinite(value):
        raise ValueError(f"unknown trade side {side!r}")
    return 1.0 if value > 0 else -1.0


def from_vectorbt(pf: Any) -> Adapted:
    """A vectorbt ``Portfolio`` (one column) → price table and the weight of equity held per bar.

    Uses ``pf.close`` for prices (``pf.open`` / ``pf.high`` / ``pf.low`` when the portfolio has
    them) and ``pf.assets()`` x price / ``pf.value()`` for the weights. Pass one column of a wide
    portfolio: ``from_vectorbt(pf["BTC"])``.
    """
    close = pf.close
    if isinstance(close, pd.DataFrame):
        if close.shape[1] != 1:
            raise ValueError("pass one column of the portfolio, for example from_vectorbt(pf['BTC'])")
        close = close.iloc[:, 0]
    assets = pf.assets()
    value = pf.value()
    assets = assets.iloc[:, 0] if isinstance(assets, pd.DataFrame) else assets
    value = value.iloc[:, 0] if isinstance(value, pd.DataFrame) else value
    weights = (assets * close / value).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    parts = {}
    for name in ("open", "high", "low"):
        series = getattr(pf, name, None)
        if series is not None:
            parts[name] = series.iloc[:, 0] if isinstance(series, pd.DataFrame) else series
    return Adapted(_prices_with_ohlc(close, **parts), np.clip(weights.to_numpy(dtype=np.float64), -1.0, 1.0), "weight")


def from_freqtrade(trades: pd.DataFrame | list[dict[str, Any]], ohlcv: pd.DataFrame | str) -> Adapted:
    """Freqtrade backtest trades (``open_date``, ``close_date``, ``is_short``) → positions on ``ohlcv``.

    Use the trade list of one pair (``results['strategy'][name]['trades']`` filtered by ``pair``, or
    the exported ``backtest-result`` file). ``ohlcv`` is that pair's candles at the strategy's timeframe.
    """
    table = pd.DataFrame(trades)
    for col in ("open_date", "close_date"):
        if col not in table.columns:
            raise ValueError(f"Freqtrade trades need an {col!r} column")
    side = table["is_short"].map(lambda v: -1 if bool(v) else 1) if "is_short" in table.columns else pd.Series(1, index=table.index)
    frame = pd.DataFrame({"open_time": table["open_date"], "close_time": table["close_date"], "side": side})
    prices = load_ohlcv(ohlcv)
    return Adapted(prices, positions_from_trades(prices, frame), "sign")


def from_lean(order_events: pd.DataFrame | list[dict[str, Any]], ohlcv: pd.DataFrame | str) -> Adapted:
    """QuantConnect Lean order events → positions on ``ohlcv``.

    Filled events are read from ``time`` (or ``timestamp``) and ``fillQuantity`` (or ``quantity``);
    buys are positive, sells negative. Events that are not fills are ignored.
    """
    table = pd.DataFrame(order_events)
    if "status" in table.columns:
        table = table[table["status"].astype(str).str.lower().isin(["filled", "partiallyfilled", "2", "3"])]
    time_col = next((c for c in ("time", "timestamp") if c in table.columns), None)
    qty_col = next((c for c in ("fillQuantity", "quantity", "fill_quantity") if c in table.columns), None)
    if time_col is None or qty_col is None:
        raise ValueError("Lean order events need a time column and a fillQuantity column")
    fills = pd.DataFrame({"timestamp": table[time_col].to_numpy(), "quantity": table[qty_col].to_numpy()})
    prices = load_ohlcv(ohlcv)
    return Adapted(prices, positions_from_fills(prices, fills), "sign")


def from_zipline(transactions: pd.DataFrame | list[dict[str, Any]], ohlcv: pd.DataFrame | str) -> Adapted:
    """Zipline transactions (``dt``, ``amount``) → positions on ``ohlcv``.

    ``perf.transactions`` from a zipline run is a column of lists of dicts; flatten it first with
    ``[t for day in perf.transactions for t in day]`` and pass the resulting list.
    """
    table = pd.DataFrame(transactions)
    if table.empty:
        fills = pd.DataFrame({"timestamp": [], "quantity": []})
    else:
        if "dt" not in table.columns or "amount" not in table.columns:
            raise ValueError("Zipline transactions need 'dt' and 'amount'")
        fills = pd.DataFrame({"timestamp": table["dt"].to_numpy(), "quantity": table["amount"].to_numpy()})
    prices = load_ohlcv(ohlcv)
    return Adapted(prices, positions_from_fills(prices, fills), "sign")


def from_fills(fills: pd.DataFrame | list[dict[str, Any]], ohlcv: pd.DataFrame | str) -> Adapted:
    """Any framework: signed fills (``timestamp``, ``quantity``) → positions on ``ohlcv``.

    The escape hatch for Backtrader (collect ``order.executed.dt`` and ``order.executed.size`` in
    ``notify_order``), Nautilus (order-filled events) and hand-written engines.
    """
    prices = load_ohlcv(ohlcv)
    return Adapted(prices, positions_from_fills(prices, fills), "sign")


__all__ = [
    "Adapted",
    "from_fills",
    "from_freqtrade",
    "from_lean",
    "from_vectorbt",
    "from_zipline",
    "positions_from_fills",
    "positions_from_trades",
]
