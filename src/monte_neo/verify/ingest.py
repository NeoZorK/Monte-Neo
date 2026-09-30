"""Load OHLCV, signals and strategy callables for the verifier.

Signals are target positions per bar. Two readings exist:

* ``sign``: ``+1`` long, ``0`` flat, ``-1`` short; any number is reduced to its sign.
* ``weight``: a fraction of equity in ``[-1, 1]`` (``0.5`` = long half the equity);
  values outside are clipped.

``auto`` (the verifier's default) picks ``weight`` when every value lies in
``[-1, 1]`` and at least one is fractional, else ``sign``. NaN means flat.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.limits import check_size, read_source, table_limit_bytes

OHLC_COLS = ("open", "high", "low", "close")
SignalFn = Callable[[pd.DataFrame], Any]


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix not in (".parquet", ".csv", ".txt"):
        raise ValueError(f"unsupported table format: {path.suffix} (use .csv or .parquet)")
    check_size(path, table_limit_bytes(), "table")
    if suffix == ".parquet":
        try:
            return pd.read_parquet(path)
        except ImportError as exc:
            raise ImportError("reading .parquet needs pyarrow: pip install 'monte-neo[parquet]' (or use .csv)") from exc
    table = pd.read_csv(path)
    if table.shape[1] == 1:
        # One column that holds the whole header: a semicolon, tab or pipe separated file (common exports).
        head = str(table.columns[0])
        for sep in (";", "\t", "|"):
            if sep in head:
                return pd.read_csv(path, sep=sep)
    return table


def _read_signal_table(path: Path) -> pd.DataFrame:
    """A signals table; a CSV without a header row (its first line is a number) keeps its first value."""
    table = _read_table(path)
    if path.suffix.lower() != ".parquet" and len(table.columns) and all(_is_number(c) for c in table.columns):
        return pd.read_csv(path, header=None)
    return table


def _is_number(text: Any) -> bool:
    try:
        float(str(text))
    except ValueError:
        return False
    return True


def load_ohlcv(source: pd.DataFrame | str | Path) -> pd.DataFrame:
    """Return a DataFrame with lower-case float ``open/high/low/close`` columns.

    A ``timestamp`` / ``time`` / ``date`` column (or DatetimeIndex) is kept as
    ``timestamp`` when present; it sets bars per year and must run oldest-first.
    A ``symbol`` (or ``ticker`` / ``asset`` / ``instrument``) column makes the table
    a universe: one row per timestamp and symbol.
    """
    df = source.copy() if isinstance(source, pd.DataFrame) else _read_table(Path(source))
    if not isinstance(source, pd.DataFrame):
        # Lets the outside-data watch recognise this file under any name or suffix.
        df.attrs["source_path"] = str(Path(source).resolve())
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "symbol" not in df.columns:
        # A universe: one row per (timestamp, symbol).
        for alias in ("ticker", "asset", "instrument"):
            if alias in df.columns:
                df = df.rename(columns={alias: "symbol"})
                break
    missing = [c for c in OHLC_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"OHLCV is missing columns: {missing}")
    if "timestamp" not in df.columns:
        for alt in ("time", "date", "datetime", "open_time"):
            if alt in df.columns:
                df = df.rename(columns={alt: "timestamp"})
                break
        else:
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.assign(timestamp=df.index)
    for col in OHLC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(np.float64)
    return df.reset_index(drop=True)


POSITION_MODES = ("auto", "sign", "weight")


def signal_values(signals: Any) -> np.ndarray:
    """Raw float values of a signal (array, Series, list or DataFrame with a ``signal`` column)."""
    if signals is None:
        raise ValueError("signal() returned None: return one position per row of df (array or Series)")
    if isinstance(signals, pd.DataFrame):
        col = "signal" if "signal" in signals.columns else signals.columns[-1]
        signals = signals[col]
    if np.ndim(signals) == 0:
        raise ValueError(f"signal() returned a single value ({signals!r}): return one position per row of df")
    try:
        return np.asarray(signals, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"positions must be numbers (+1 / 0 / -1 or weights in [-1, 1]): {exc}") from exc


def resolve_positions(values: np.ndarray, positions: str = "auto") -> str:
    """``sign`` or ``weight`` for ``values`` under the requested mode."""
    if positions not in POSITION_MODES:
        raise ValueError(f"positions must be one of {POSITION_MODES}, got {positions!r}")
    if positions != "auto":
        return positions
    finite = values[np.isfinite(values)]
    if finite.size and np.all(np.abs(finite) <= 1.0) and np.any(finite != np.round(finite)):
        return "weight"
    return "sign"


def to_positions(values: np.ndarray, positions: str) -> np.ndarray:
    """int64 signs in ``{-1, 0, 1}`` (``sign``) or float64 weights clipped to ``[-1, 1]`` (``weight``)."""
    if positions == "weight":
        return np.clip(np.nan_to_num(values, nan=0.0, posinf=1.0, neginf=-1.0), -1.0, 1.0)
    if positions != "sign":
        raise ValueError(f"positions must be 'sign' or 'weight' here, got {positions!r}")
    from monte_neo.backtest.export_signals import normalize_positions  # keeps this module light for workers

    return normalize_positions(values)


def normalize_signals(signals: Any, n_bars: int | None = None, positions: str = "sign") -> np.ndarray:
    """Positions from any numeric signal: signs (default) or weights; ``auto`` decides from the values."""
    values = signal_values(signals)
    if n_bars is not None and values.size != int(n_bars):
        raise ValueError(f"signal length {values.size} != bar count {int(n_bars)}")
    return to_positions(values, resolve_positions(values, positions))


def load_signal_values(source: Any) -> np.ndarray:
    """Raw signal values from an array-like or a ``.csv`` / ``.parquet`` / ``.npy`` file."""
    if isinstance(source, str | Path):
        path = Path(source)
        data: Any = np.load(check_size(path, table_limit_bytes(), "table"), allow_pickle=False) if path.suffix.lower() == ".npy" else _read_signal_table(path)
        return signal_values(data)
    return signal_values(source)


def load_signals(source: Any, n_bars: int | None = None, positions: str = "sign") -> np.ndarray:
    """Load positions from an array-like or a ``.csv`` / ``.parquet`` / ``.npy`` file."""
    return normalize_signals(load_signal_values(source), n_bars, positions)


def load_signal_fn(spec: str | Path) -> tuple[SignalFn, str]:
    """Import ``path/to/file.py[:func]`` (default ``signal``); return (fn, source).

    Runs the module with the caller's permissions — only verify code you trust
    as much as code you would run yourself.
    """
    text = str(spec)
    func_name = "signal"
    path_str = text
    if ":" in text and not Path(text).exists():
        path_str, func_name = text.rsplit(":", 1)
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"strategy file not found: {path}")
    source = read_source(path)
    mod_name = f"_monte_neo_strategy_{abs(hash(path.resolve()))}"
    spec_obj = importlib.util.spec_from_file_location(mod_name, path)
    if spec_obj is None or spec_obj.loader is None:  # pragma: no cover - importlib edge
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec_obj)
    sys.modules[mod_name] = module
    # Modules next to the strategy file (helpers, packages) must import, as when the file is run
    # as a script. The directory goes to the END of the path: it can never shadow the standard
    # library or an installed package such as numpy.
    folder = str(path.resolve().parent)
    if folder not in sys.path:
        sys.path.append(folder)
    try:
        spec_obj.loader.exec_module(module)
    finally:
        sys.modules.pop(mod_name, None)
    fn = getattr(module, func_name, None)
    if not callable(fn):
        raise AttributeError(f"{path} has no callable '{func_name}(df)'")
    return fn, source


def call_signal_fn(fn: SignalFn, df: pd.DataFrame, positions: str = "sign") -> np.ndarray:
    """Run ``fn`` on a private copy of ``df`` and normalize its output."""
    return normalize_signals(fn(df.copy()), len(df), positions)


__all__ = [
    "OHLC_COLS",
    "POSITION_MODES",
    "SignalFn",
    "call_signal_fn",
    "load_ohlcv",
    "load_signal_fn",
    "load_signal_values",
    "load_signals",
    "normalize_signals",
    "resolve_positions",
    "signal_values",
    "to_positions",
]
