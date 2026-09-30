"""What the verifier tests on: one instrument, or a universe of instruments.

A universe is a long table with a ``symbol`` column (``ticker``, ``asset`` and
``instrument`` are accepted too) and a ``timestamp`` column. Its rows are sorted by
timestamp, then symbol, and that sorted table is what ``signal(df)`` receives: one
value per row, the target weight of that symbol on that bar. At each timestamp the
gross weight is capped at 1 (weights are scaled down proportionally), so ``+1`` on
ten symbols means ten equal longs of 10% each.

The adapters give the verifier one interface: data checks, reading the signal,
positions for the engine, look-ahead probes, the passive benchmark and the data hash.
For one instrument they call exactly the functions the verifier always used.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.backtest.weight_engine import normalize_weights
from monte_neo.verify import checks as rows
from monte_neo.verify.executor import FULL, Head, evaluate
from monte_neo.verify.ingest import (
    OHLC_COLS,
    SignalFn,
    _read_table,
    load_signal_values,
    signal_values,
    to_positions,
)
from monte_neo.verify.lookahead import (
    MAX_REPORTED,
    _checkpoints,
    _status,
    implausible_accuracy,
    probe_determinism,
    probe_perturbation,
    probe_truncation,
    run_positions,
)

SYMBOL_ALIASES = ("symbol", "ticker", "asset", "instrument")


def _values_from(fn: SignalFn | None, signals: Any, frame: pd.DataFrame) -> np.ndarray:
    return evaluate(fn, frame, [FULL])[0] if fn is not None else load_signal_values(signals)


class SingleMarket:
    """One instrument: the table as loaded, positions per bar."""

    kind = "single"
    benchmark_description = "long every bar after warm-up, same costs"

    def __init__(self, df: pd.DataFrame) -> None:
        self.frame = df
        self.n_bars = len(df)
        self.ohlc = {k: df[k].to_numpy(dtype=np.float64) for k in OHLC_COLS}
        self.timestamps = df.get("timestamp")
        self.volume = df["volume"].to_numpy() if "volume" in df.columns else None
        self.symbols: list[str] | None = None
        self.capacity_volume = self.volume  # (bars,) volume for the capacity estimate

    def integrity(self) -> dict[str, Any]:
        return rows.data_integrity(self.ohlc, self.timestamps)

    def read_values(self, fn: SignalFn | None, signals: Any) -> np.ndarray:
        values = _values_from(fn, signals, self.frame)
        if values.size != self.n_bars:
            raise ValueError(f"signal length {values.size} != bar count {self.n_bars}")
        return values

    def positions(self, values: np.ndarray, mode: str, model: ExecutionModel) -> tuple[np.ndarray, np.ndarray]:
        """(positions for the engine, positions it actually trades)."""
        sig = to_positions(values, mode)
        traded = sig if model.side_mode == "long_short" else np.maximum(sig, 0)
        return sig, traded

    def probes(self, fn: SignalFn, full: np.ndarray, mode: str, n_checks: int) -> tuple[dict[str, Any], ...]:
        return (
            probe_determinism(fn, self.frame, full=full, positions=mode),
            probe_truncation(fn, self.frame, n_checks=n_checks, full=full, positions=mode),
            probe_perturbation(fn, self.frame, n_checks=max(2, n_checks // 4), full=full, positions=mode),
        )

    def accuracy(self, traded: np.ndarray) -> dict[str, Any]:
        return implausible_accuracy(self.ohlc["open"], self.ohlc["close"], traded)

    def benchmark_positions(self) -> np.ndarray:
        return np.ones(self.n_bars, dtype=np.int64)

    def market_close(self) -> np.ndarray:
        return self.ohlc["close"]

    def universe_checks(self) -> list[dict[str, Any]]:
        return []

    def data_bytes(self) -> bytes:
        return np.ascontiguousarray(self.frame[list(OHLC_COLS)].to_numpy(dtype=np.float64)).tobytes()

    def describe(self, traded: np.ndarray) -> dict[str, Any]:
        return {}


class UniverseMarket:
    """Many instruments in one long table: weights per (timestamp, symbol) row."""

    kind = "universe"
    benchmark_description = "equal weight in every symbol with a price, same costs"

    def __init__(self, df: pd.DataFrame) -> None:
        if "timestamp" not in df.columns:
            raise ValueError("a universe (symbol column) needs a timestamp column")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        if parsed.isna().any():
            raise ValueError(f"{int(parsed.isna().sum())} timestamps could not be parsed")
        missing = df["symbol"].isna()
        if missing.any():
            raise ValueError(f"{int(missing.sum())} rows have no symbol")
        # Integer codes (hash-based, names sorted) instead of sorting 10^5-10^6 strings.
        codes, names = pd.factorize(df["symbol"].astype(str), sort=True)
        stamps = parsed.to_numpy(dtype="datetime64[ns]").astype(np.int64)
        order = np.lexsort((codes, stamps))
        frame = df.iloc[order].reset_index(drop=True)
        frame.attrs = dict(df.attrs)
        self.frame = frame
        self._stamps = stamps[order]
        times, self.t_idx = np.unique(self._stamps, return_inverse=True)
        self.s_idx = codes[order].astype(np.int64)
        self.symbols = [str(s) for s in names]
        self.timestamps = pd.DatetimeIndex(times.astype("datetime64[ns]")).tz_localize("UTC")
        self.n_bars = len(times)
        shape = (self.n_bars, len(self.symbols))
        self.row_ohlc = {k: frame[k].to_numpy(dtype=np.float64) for k in OHLC_COLS}
        self.ohlc = {}
        for k in OHLC_COLS:
            m = np.full(shape, np.nan)
            m[self.t_idx, self.s_idx] = self.row_ohlc[k]
            self.ohlc[k] = m
        keys = self.t_idx.astype(np.int64) * len(self.symbols) + self.s_idx
        self.duplicates = int(keys.size - np.unique(keys).size)
        self.volume = frame["volume"].to_numpy() if "volume" in frame.columns else None
        self.capacity_volume = None  # (bars, symbols) volume for the capacity estimate
        if self.volume is not None:
            vm = np.full(shape, np.nan)
            vm[self.t_idx, self.s_idx] = pd.to_numeric(frame["volume"], errors="coerce").to_numpy(dtype=np.float64)
            self.capacity_volume = vm
        # Rows of each symbol in time order (the table is sorted by time, so a stable sort keeps it).
        self._by_symbol = np.argsort(self.s_idx, kind="stable")
        self._symbol_bounds = np.searchsorted(self.s_idx[self._by_symbol], np.arange(len(self.symbols) + 1))

    # -- data -----------------------------------------------------------------
    def integrity(self) -> dict[str, Any]:
        return rows.data_integrity(self.row_ohlc, None, duplicates=self.duplicates)

    def read_values(self, fn: SignalFn | None, signals: Any) -> np.ndarray:
        if fn is None and isinstance(signals, str | Path) and Path(signals).suffix.lower() in (".csv", ".txt", ".parquet"):
            return self._aligned(_read_table(Path(signals)))
        if fn is None and isinstance(signals, pd.DataFrame) and {"symbol", "timestamp"} <= set(signals.columns):
            return self._aligned(signals)
        values = _values_from(fn, signals, self.frame)
        if values.size != len(self.frame):
            raise ValueError(f"signal length {values.size} != row count {len(self.frame)} (one value per timestamp and symbol)")
        return values

    def _aligned(self, table: pd.DataFrame) -> np.ndarray:
        """A signals table keyed by (timestamp, symbol), matched to the sorted rows."""
        table = table.rename(columns=lambda c: str(c).strip().lower())
        table = table.rename(columns={a: "symbol" for a in SYMBOL_ALIASES[1:] if a in table.columns})
        if not {"symbol", "timestamp"} <= set(table.columns):
            values = signal_values(table)
            if values.size != len(self.frame):
                raise ValueError(f"signal length {values.size} != row count {len(self.frame)} (one value per timestamp and symbol)")
            return values
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            stamps = pd.to_datetime(table["timestamp"], utc=True, errors="coerce").to_numpy(dtype="datetime64[ns]")
        keyed = pd.Series(signal_values(table.drop(columns=["symbol", "timestamp"])),
                          index=pd.MultiIndex.from_arrays([stamps.astype(np.int64), table["symbol"].astype(str).to_numpy()]))
        if keyed.index.has_duplicates:
            raise ValueError("signals table has duplicate (timestamp, symbol) rows")
        want = pd.MultiIndex.from_arrays([self._stamps, self.frame["symbol"].astype(str).to_numpy()])
        return keyed.reindex(want).to_numpy(dtype=np.float64)  # missing rows: NaN = flat

    # -- positions ------------------------------------------------------------
    def matrix(self, row_values: np.ndarray) -> np.ndarray:
        m = np.zeros((self.n_bars, len(self.symbols)))
        m[self.t_idx, self.s_idx] = row_values
        return m

    def positions(self, values: np.ndarray, mode: str, model: ExecutionModel) -> tuple[np.ndarray, np.ndarray]:
        weights, self.scaled_bars = normalize_weights(
            self.matrix(to_positions(values, mode).astype(np.float64)), long_short=model.side_mode == "long_short"
        )
        return weights, weights

    # -- probes ---------------------------------------------------------------
    def _rows_until(self, t: int) -> int:
        return int(np.searchsorted(self.t_idx, t, side="right"))

    def probes(self, fn: SignalFn, full: np.ndarray, mode: str, n_checks: int) -> tuple[dict[str, Any], ...]:
        return (
            probe_determinism(fn, self.frame, full=full, positions=mode),
            self._truncation(fn, full, mode, n_checks),
            self._perturbation(fn, full, mode, max(2, n_checks // 4)),
        )

    def _checkpoints(self, full: np.ndarray, n_checks: int) -> np.ndarray:
        even = _checkpoints(self.n_bars, n_checks, None)
        changed = np.flatnonzero(np.any(np.diff(self.matrix(full.astype(np.float64)), axis=0) != 0, axis=1)) + 1
        lo = max(2, self.n_bars // 10)
        changed = changed[(changed >= lo) & (changed <= self.n_bars - 2)]
        if changed.size:
            picks = np.linspace(0, changed.size - 1, num=min(n_checks, changed.size)).astype(np.int64)
            even = np.union1d(even, changed[picks])
        return even

    def _mismatch(self, t: int, got: np.ndarray, full: np.ndarray) -> dict[str, Any] | None:
        diff = np.flatnonzero(got != full[: got.size])
        if not diff.size:
            return None
        row = int(diff[0])
        return {
            "checkpoint": int(t), "bar": int(self.t_idx[row]), "symbol": self.symbols[int(self.s_idx[row])],
            "full": full[row].item(), "truncated": got[row].item(), "changed_rows": int(diff.size),
        }

    def _truncation(self, fn: SignalFn, full: np.ndarray, mode: str, n_checks: int) -> dict[str, Any]:
        """Cut the table after timestamp t (all symbols at once); earlier weights must not change."""
        points = self._checkpoints(full, n_checks)
        heads = run_positions(fn, self.frame, [Head(self._rows_until(int(t))) for t in points], mode)
        found = []
        for t, head in zip(points, heads, strict=True):
            m = self._mismatch(int(t), head, full)
            if m:
                found.append(m)
        return {
            "status": _status(found, int(points.size)), "checkpoints": int(points.size),
            "mismatch_count": len(found), "mismatches": found[:MAX_REPORTED],
            "first_mismatch_bar": min(m["bar"] for m in found) if found else None,
        }

    def _mirrored(self, t: int) -> pd.DataFrame:
        """Every symbol's prices after timestamp t follow its mirrored log returns."""
        out = self.frame.copy()
        close = out["close"].to_numpy(dtype=np.float64)
        factor = np.ones(close.size)
        for s in range(len(self.symbols)):
            idx = self._by_symbol[self._symbol_bounds[s] : self._symbol_bounds[s + 1]]
            k = int(np.searchsorted(self.t_idx[idx], t, side="right"))
            if 0 < k < idx.size:
                after = idx[k:]
                factor[after] = (close[idx[k - 1]] / close[after]) ** 2  # exp(-2 * (log c - log anchor))
        for col in OHLC_COLS:
            out[col] = out[col].to_numpy(dtype=np.float64) * factor
        return out

    def _perturbation(self, fn: SignalFn, full: np.ndarray, mode: str, n_checks: int) -> dict[str, Any]:
        points = _checkpoints(self.n_bars, n_checks, None)
        alts = run_positions(fn, self.frame, [self._mirrored(int(t)) for t in points], mode)
        found = []
        for t, alt in zip(points, alts, strict=True):
            k = self._rows_until(int(t))
            m = self._mismatch(int(t), alt[:k], full)
            if m:
                found.append(m)
        return {
            "status": _status(found, int(points.size)), "checkpoints": int(points.size),
            "mismatch_count": len(found), "mismatches": found[:MAX_REPORTED],
        }

    def accuracy(self, traded: np.ndarray) -> dict[str, Any]:
        return implausible_accuracy(self.ohlc["open"], self.ohlc["close"], traded)

    # -- benchmark and market -------------------------------------------------
    def benchmark_positions(self) -> np.ndarray:
        valid = np.isfinite(self.ohlc["close"])
        count = valid.sum(axis=1, keepdims=True)
        return np.where(valid, 1.0 / np.maximum(count, 1), 0.0)

    def market_close(self) -> np.ndarray:
        c = self.ohlc["close"]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            step = np.nanmean(c[1:] / c[:-1] - 1.0, axis=1)
        return np.concatenate([[1.0], np.cumprod(1.0 + np.nan_to_num(step))])

    def universe_checks(self) -> list[dict[str, Any]]:
        valid = np.isfinite(self.ohlc["close"])
        first = np.argmax(valid, axis=0)
        last = self.n_bars - 1 - np.argmax(valid[::-1], axis=0)
        return [rows.survivorship_row(self.symbols, first, last, self.n_bars)]

    def data_bytes(self) -> bytes:
        prices = np.ascontiguousarray(self.frame[list(OHLC_COLS)].to_numpy(dtype=np.float64)).tobytes()
        names = "\n".join(self.symbols).encode("utf-8")
        return prices + names + np.ascontiguousarray(self.s_idx).tobytes() + np.ascontiguousarray(self._stamps).tobytes()

    def describe(self, traded: np.ndarray) -> dict[str, Any]:
        return {
            "symbols": len(self.symbols),
            "rows": len(self.frame),
            "gross_scaled_bars": int(getattr(self, "scaled_bars", 0)),
            "mean_gross_exposure": float(np.mean(np.abs(traded).sum(axis=1))),
        }


def bar_count(df: pd.DataFrame) -> int:
    """Bars in time: rows for one instrument, distinct timestamps for a universe."""
    return int(df["timestamp"].nunique()) if "symbol" in df.columns and "timestamp" in df.columns else len(df)


def market_for(df: pd.DataFrame) -> SingleMarket | UniverseMarket:
    """The adapter for a loaded table: a universe when it has a symbol column."""
    return UniverseMarket(df) if "symbol" in df.columns else SingleMarket(df)


__all__ = ["SYMBOL_ALIASES", "SingleMarket", "UniverseMarket", "bar_count", "market_for"]
