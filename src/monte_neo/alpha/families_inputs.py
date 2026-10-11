"""Read the optional inputs of families E and G (membership, groups, exchanges) from files or objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from monte_neo.verify.ingest import _read_table


def _table(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    table = source.copy() if isinstance(source, pd.DataFrame) else _read_table(Path(source))
    table.columns = [str(c).strip().lower() for c in table.columns]
    if "symbol" not in table.columns:
        raise ValueError("the table needs a symbol column")
    table["symbol"] = table["symbol"].astype(str)
    return table


def process_inputs(
    membership: Any = None, groups: Any = None, exchanges: Any = None, discovery_date: str | None = None
) -> tuple[dict[str, Any], dict[str, str] | None]:
    """Keyword arguments for :func:`monte_neo.alpha.process.run_process` and the ``symbol -> group`` map for robustness."""
    process: dict[str, Any] = {"discovery_date": discovery_date}
    group_map = None
    if membership is not None:
        process["membership"] = membership
    if groups is not None:
        table = _table(groups)
        if "group" not in table.columns:
            raise ValueError("the groups table needs symbol and group columns (and optionally as_of)")
        process["groups"] = table
        group_map = dict(zip(table["symbol"], table["group"].astype(str), strict=False))
    if exchanges is not None:
        if isinstance(exchanges, dict):
            process["exchanges"] = {str(k): str(v) for k, v in exchanges.items()}
        else:
            table = _table(exchanges)
            if "exchange" not in table.columns:
                raise ValueError("the exchanges table needs symbol and exchange columns")
            process["exchanges"] = dict(zip(table["symbol"], table["exchange"].astype(str), strict=False))
    return process, group_map


__all__ = ["process_inputs"]
