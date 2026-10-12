"""Families B, C, F and I on a scores panel, judged on the score's long-short portfolio returns.

* B (attribution): is the return a known factor? Factors are built from the same universe unless a factor file is given.
* C (book): what does the portfolio add to an existing book? Needs a book file.
* F (multiple testing): does it survive the number of variants tried?
* I (risk): neutrality, concentration, leverage, named crises, tail risk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.alpha.attribution import NEXT_ACTIONS as B_ACTIONS
from monte_neo.alpha.attribution import run_attribution
from monte_neo.alpha.book import NEXT_ACTIONS as C_ACTIONS
from monte_neo.alpha.book import run_book
from monte_neo.alpha.factors import build_factors, load_factors
from monte_neo.alpha.implementability_common import gross_series, simple_returns
from monte_neo.alpha.implementability_run import portfolio_weights
from monte_neo.alpha.multiple_testing import NEXT_ACTIONS as F_ACTIONS
from monte_neo.alpha.multiple_testing import run_multiple_testing
from monte_neo.alpha.panel import Panel
from monte_neo.alpha.process import NEXT_ACTIONS as G_ACTIONS
from monte_neo.alpha.process import run_process
from monte_neo.alpha.risk import NEXT_ACTIONS as I_ACTIONS
from monte_neo.alpha.risk import run_risk
from monte_neo.alpha.robustness import NEXT_ACTIONS as E_ACTIONS
from monte_neo.alpha.robustness import run_robustness
from monte_neo.verify.checks import check
from monte_neo.verify.ingest import _read_table

NEXT_ACTIONS: dict[str, str] = {
    **B_ACTIONS, **C_ACTIONS, **E_ACTIONS, **F_ACTIONS, **G_ACTIONS, **I_ACTIONS,
    "signal_orthogonality": "The new score mostly repeats signals you already run: residualise it on them and test what is left, "
                            "or drop it.",
}
TIME_COLUMNS = ("date", "timestamp", "time", "datetime")


def read_book(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    """Book returns (a date column and one column per strategy, as decimals) indexed by naive dates."""
    table = source.copy() if isinstance(source, pd.DataFrame) else _read_table(Path(source))
    table.columns = [str(c).strip().lower() for c in table.columns]
    col = next((c for c in TIME_COLUMNS if c in table.columns), table.columns[0])
    stamps = pd.to_datetime(table.pop(col), utc=True).dt.tz_localize(None)
    out = table.apply(pd.to_numeric, errors="coerce")
    out.index = pd.DatetimeIndex(stamps)
    if out.empty or out.shape[1] == 0:
        raise ValueError("the book file needs a date column and at least one return column")
    return out.sort_index()


def portfolio_returns(panel: Panel, quantiles: int) -> tuple[np.ndarray, np.ndarray]:
    """Returns of the score's long-short portfolio (weights decided at t-1 earn bar t) and its weights."""
    w = portfolio_weights(panel, quantiles)
    return gross_series(w, simple_returns(panel.close)), w


def run_families(
    panel: Panel,
    *,
    quantiles: int,
    factors: str | Path | None = None,
    book: str | Path | pd.DataFrame | None = None,
    n_trials: int = 1,
    declared_neutral: bool = True,
    seed: int = 0,
    process: dict[str, Any] | None = None,
    groups: dict[str, str] | None = None,
    existing: str | Path | pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Run families B, C, E, F, G and I on the portfolio returns of the score.

    Args:
        panel: The aligned panel.
        quantiles: Quantile buckets of the long-short portfolio.
        factors: Optional factor file (date + factor returns); default: factors built from the universe.
        book: Optional book returns (date + one column per strategy) for family C; skipped without it.
        n_trials: Variants tried before this one (family F).
        declared_neutral: The portfolio is meant to be market neutral (true for top-minus-bottom).
        seed: Seed for bootstraps and simulations.
        process: Inputs of family G: ``membership``, ``groups`` (with ``as_of``), ``exchanges``, ``discovery_date``,
            ``hygiene`` (see :func:`monte_neo.alpha.process.run_process`).
        groups: ``symbol -> sector or country`` for the robustness split by group.
        existing: Scores of signals the fund already runs (timestamp, symbol, one column per signal): is the new one new?

    Returns:
        Check rows.
    """
    r, w = portfolio_returns(panel, quantiles)
    ppy = panel.periods_per_year
    dates = panel.dates
    built = build_factors(panel.close, panel.volume, dates)
    table = load_factors(factors, dates) if factors else built
    aligned = pd.Series(r, index=dates).reindex(table.index)
    rows = run_attribution(aligned.to_numpy(), table, ppy)
    if book is None:
        rows.append(check("book_correlation", "statistics", "skip", "no book given (--book): the value to an existing book was not assessed", {}))
    else:
        rows += run_book(pd.Series(r, index=dates), read_book(book), ppy, seed=seed)
    if existing is not None:
        from monte_neo.alpha.orthogonality import load_existing_scores, signal_orthogonality

        rows.append(signal_orthogonality(panel, load_existing_scores(existing, panel)))
    rows += run_multiple_testing(r, ppy, int(n_trials), timestamps=dates, seed=seed)
    market = built["market"].reindex(dates).fillna(0.0).to_numpy() if "market" in built else np.zeros_like(r)
    rows += run_risk(r, market, dates, ppy, weights=w, declared_neutral=declared_neutral)
    rows += run_robustness(panel, quantiles=quantiles, seed=seed, groups=groups, cost_bps=0.0)  # costs are family D's job
    rows += run_process(panel, w, **(process or {}))
    return rows


__all__ = ["NEXT_ACTIONS", "portfolio_returns", "read_book", "run_families"]
