"""Fixed discovery / validation / sealed-holdout split by date (or bar number), written down before the first run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

MIN_DISCOVERY, MIN_VALIDATION, MIN_HOLDOUT = 60, 100, 30


def _stamps(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["timestamp"]) if "timestamp" in df.columns else pd.Series(np.arange(len(df)), index=df.index)


def _coerce(value: Any, like: pd.Series) -> Any:
    """A cut as a Timestamp in the time zone of the data, or an int bar number when the data has no timestamps."""
    if not pd.api.types.is_datetime64_any_dtype(like):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise ValueError("data without a timestamp column is split by bar number: give integers")
        return int(value)
    ts = pd.Timestamp(value)
    tz = like.dt.tz
    if tz is not None:
        ts = ts.tz_localize(tz) if ts.tzinfo is None else ts.tz_convert(tz)
    elif ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


@dataclass(frozen=True)
class Splits:
    """``discovery < discovery_end <= validation < validation_end <= holdout`` (cuts are part of the project record)."""

    discovery_end: str
    validation_end: str

    @classmethod
    def build(cls, df: pd.DataFrame, discovery_end: Any, validation_end: Any) -> Splits:
        """Check the cuts against the data and keep them as text.

        Raises:
            ValueError: The cuts are not increasing, or a part has too few bars.
        """
        stamps = _stamps(df)
        d, v = _coerce(discovery_end, stamps), _coerce(validation_end, stamps)
        if not d < v:
            raise ValueError("discovery_end must be before validation_end")
        sp = cls(str(d), str(v))
        counts = sp.bar_counts(df)
        for name, need in (("discovery", MIN_DISCOVERY), ("validation", MIN_VALIDATION), ("holdout", MIN_HOLDOUT)):
            if counts[name] < need:
                raise ValueError(f"the {name} part has {counts[name]} bars, at least {need} are needed")
        return sp

    def _cuts(self, df: pd.DataFrame) -> tuple[Any, Any]:
        stamps = _stamps(df)
        return _coerce(self.discovery_end if stamps.dtype.kind != "i" else int(self.discovery_end), stamps), \
            _coerce(self.validation_end if stamps.dtype.kind != "i" else int(self.validation_end), stamps)

    def masks(self, df: pd.DataFrame) -> dict[str, np.ndarray]:
        stamps = _stamps(df)
        d, v = self._cuts(df)
        return {"discovery": np.asarray(stamps < d), "validation": np.asarray((stamps >= d) & (stamps < v)), "holdout": np.asarray(stamps >= v)}

    def bar_counts(self, df: pd.DataFrame) -> dict[str, int]:
        """Distinct time steps per part (rows for one instrument, timestamps for a universe)."""
        stamps = _stamps(df)
        return {k: int(stamps[m].nunique()) for k, m in self.masks(df).items()}

    def upto(self, df: pd.DataFrame, stage: str) -> pd.DataFrame:
        """All rows up to the end of ``stage`` (``discovery`` or ``validation``); never the holdout."""
        if stage not in ("discovery", "validation"):
            raise ValueError("only discovery and validation can be read this way")
        m = self.masks(df)
        keep = m["discovery"] if stage == "discovery" else (m["discovery"] | m["validation"])
        return df[keep].reset_index(drop=True)

    def holdout_cut(self, df: pd.DataFrame) -> Any:
        return self._cuts(df)[1]

    def as_dict(self) -> dict[str, str]:
        return {"discovery_end": self.discovery_end, "validation_end": self.validation_end}


__all__ = ["MIN_DISCOVERY", "MIN_HOLDOUT", "MIN_VALIDATION", "Splits"]
