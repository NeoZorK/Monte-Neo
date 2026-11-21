"""Is a strategy new to a catalog? Correlation with every existing strategy and what it adds to them together.

Novel (``novel = True``) when all hold:
* its absolute correlation with every catalog strategy is below ``max_corr`` (default 0.3);
* ``marginal_sharpe`` passes: adding it to the catalog's equal-risk book lifts the Sharpe ratio beyond the bootstrap noise
  (ARL level 8, "it adds to your book", the same check);
* the correlation in the book's worst 10 % of days is below ``max_corr`` too (it does not fall with the others in a crash).

Used to decide whether a contributed strategy is a different source of return, not the same idea with new parameters.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from monte_neo.alpha.book import run_book

MAX_CORR = 0.3


def novelty(returns: pd.Series, catalog: pd.DataFrame, periods_per_year: float = 252.0, max_corr: float = MAX_CORR, seed: int = 0) -> dict[str, Any]:
    if catalog.shape[1] == 0:
        raise ValueError("the catalog book has no strategy columns")
    rows = run_book(returns, catalog, periods_per_year, seed)
    by = {r["id"]: r for r in rows}
    corr = by.get("book_correlation", {}).get("details", {})
    per = {k: v for k, v in (corr.get("per_column") or {}).items() if v == v}
    worst = max(per.items(), key=lambda kv: abs(kv[1]), default=(None, None))
    tail = corr.get("tail_corr")
    reasons = []
    if worst[1] is not None and abs(worst[1]) >= max_corr:
        reasons.append(f"correlation {worst[1]:+.2f} with {worst[0]} (limit {max_corr})")
    if by.get("marginal_sharpe", {}).get("status") != "pass":
        reasons.append("it does not lift the catalog book's Sharpe beyond noise (marginal_sharpe)")
    if tail is not None and tail == tail and abs(tail) >= max_corr:
        reasons.append(f"correlation {tail:+.2f} in the book's worst days")
    if "book_correlation" in by and by["book_correlation"]["status"] == "skip":
        reasons = [by["book_correlation"]["summary"]]
    return {"schema": "catalog-novelty/1", "novel": not reasons, "why_not": reasons, "max_abs_corr": worst[1], "closest": worst[0],
            "tail_corr": tail, "checks": rows}
