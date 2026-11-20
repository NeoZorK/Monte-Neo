"""Read the options trade table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED = ("date", "expiry", "right", "strike", "qty", "fill_price")
DATES = ("date", "expiry", "exit_date", "iv_asof", "ex_div_date")
NUMBERS = ("strike", "qty", "fill_price", "bid", "ask", "underlying_price", "iv_used", "exit_price", "exit_bid", "exit_ask",
           "multiplier", "dividend", "underlying_at_expiry")


def load_trades(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    """A clean trade table: dates parsed, numbers numeric, ``right`` as C/P, ``multiplier`` defaulting to 100.

    Raises ``ValueError`` for a missing required column, an unreadable value, a zero quantity or a bad right.
    """
    df = source.copy() if isinstance(source, pd.DataFrame) else (pd.read_parquet(source) if str(source).endswith(".parquet") else pd.read_csv(source))
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"the options table lacks required column(s): {', '.join(missing)}")
    for c in DATES:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    if df[["date", "expiry"]].isna().any().any():
        raise ValueError("date and expiry must be valid dates in every row")
    for c in NUMBERS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if df[["strike", "qty", "fill_price"]].isna().any().any():
        raise ValueError("strike, qty and fill_price must be numbers in every row")
    df["right"] = df["right"].astype(str).str.strip().str.upper().str[0]
    if not df["right"].isin(["C", "P"]).all():
        raise ValueError("right must be C or P (call or put)")
    if (df["qty"] == 0).any():
        raise ValueError("qty must not be zero (positive = bought, negative = sold)")
    if "multiplier" not in df.columns:
        df["multiplier"] = 100.0
    df["multiplier"] = df["multiplier"].fillna(100.0)
    if "style" not in df.columns:
        df["style"] = "american"
    if "symbol" not in df.columns:
        df["symbol"] = "UNDERLYING"
    return df.sort_values("date", kind="stable").reset_index(drop=True)
