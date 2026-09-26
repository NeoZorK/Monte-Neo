"""Load OHLCV, signals and strategy callables for the verifier.

Signals are target positions per bar: ``+1`` long, ``0`` flat, ``-1`` short.
Any numeric input is reduced to its sign; NaN means flat.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.export_signals import normalize_positions

OHLC_COLS = ("open", "high", "low", "close")
SignalFn = Callable[[pd.DataFrame], Any]


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix in (".csv", ".txt"):
        return pd.read_csv(path)
    raise ValueError(f"unsupported table format: {path.suffix} (use .csv or .parquet)")


def load_ohlcv(source: pd.DataFrame | str | Path) -> pd.DataFrame:
    """Return a DataFrame with lower-case float ``open/high/low/close`` columns.

    A ``timestamp`` / ``time`` / ``date`` column (or DatetimeIndex) is kept as
    ``timestamp`` when present; it is only used to infer bars per year.
    """
    df = source.copy() if isinstance(source, pd.DataFrame) else _read_table(Path(source))
    df.columns = [str(c).strip().lower() for c in df.columns]
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


def normalize_signals(signals: Any, n_bars: int | None = None) -> np.ndarray:
    """Reduce any numeric signal to int64 positions in ``{-1, 0, 1}``."""
    if isinstance(signals, pd.DataFrame):
        col = "signal" if "signal" in signals.columns else signals.columns[-1]
        signals = signals[col]
    out = normalize_positions(signals)
    if n_bars is not None and out.size != int(n_bars):
        raise ValueError(f"signal length {out.size} != bar count {int(n_bars)}")
    return out


def load_signals(source: Any, n_bars: int | None = None) -> np.ndarray:
    """Load signals from an array-like or a ``.csv`` / ``.parquet`` / ``.npy`` file."""
    if isinstance(source, str | Path):
        path = Path(source)
        data: Any = np.load(path) if path.suffix.lower() == ".npy" else _read_table(path)
        return normalize_signals(data, n_bars)
    return normalize_signals(source, n_bars)


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
    source = path.read_text(encoding="utf-8")
    mod_name = f"_monte_neo_strategy_{abs(hash(path.resolve()))}"
    spec_obj = importlib.util.spec_from_file_location(mod_name, path)
    if spec_obj is None or spec_obj.loader is None:  # pragma: no cover - importlib edge
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec_obj)
    sys.modules[mod_name] = module
    try:
        spec_obj.loader.exec_module(module)
    finally:
        sys.modules.pop(mod_name, None)
    fn = getattr(module, func_name, None)
    if not callable(fn):
        raise AttributeError(f"{path} has no callable '{func_name}(df)'")
    return fn, source


def call_signal_fn(fn: SignalFn, df: pd.DataFrame) -> np.ndarray:
    """Run ``fn`` on a private copy of ``df`` and normalize its output."""
    return normalize_signals(fn(df.copy()), len(df))


__all__ = [
    "OHLC_COLS",
    "SignalFn",
    "call_signal_fn",
    "load_ohlcv",
    "load_signal_fn",
    "load_signals",
    "normalize_signals",
]
