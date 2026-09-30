"""pandas accessor: ``df.monte_neo.verify(...)`` on a price table.

Import this module once (``import monte_neo.verify.accessor``) to register the accessor.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


@pd.api.extensions.register_dataframe_accessor("monte_neo")
class MonteNeoAccessor:
    """Verify a strategy against the OHLCV table this accessor is attached to."""

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def verify(self, signals: Any = None, *, strategy: Any = None, **kwargs: Any) -> dict[str, Any]:
        """``verify_strategy`` with this table as the data: positions per bar, or a strategy file/function."""
        from monte_neo.verify.verdict import verify_strategy

        if callable(strategy):
            return verify_strategy(self._df, signal_fn=strategy, **kwargs)
        return verify_strategy(self._df, signals=signals, strategy=strategy, **kwargs)


__all__ = ["MonteNeoAccessor"]
