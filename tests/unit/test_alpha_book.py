"""Family C: value to an existing book."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.alpha.book import align_book, marginal_sharpe, run_book

N = 1500
IDX = pd.bdate_range("2018-01-01", periods=N)


def _book(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"a": rng.normal(0.0006, 0.01, N), "b": rng.normal(0.0004, 0.01, N)}, index=IDX)


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def test_clone_of_book_warns_marginal() -> None:
    book = _book()
    clone = pd.Series(book.sum(axis=1).to_numpy(), index=IDX)
    rows = _by_id(run_book(clone, book, 252.0))
    assert rows["marginal_sharpe"]["status"] == "warn"
    assert rows["marginal_sharpe"]["details"]["gain"] < 0.05
    assert rows["book_correlation"]["details"]["corr_total"] > 0.99
    assert rows["residual_vs_book"]["status"] == "warn"


def test_independent_strategy_adds_value() -> None:
    book = _book()
    r = pd.Series(np.random.default_rng(5).normal(0.0012, 0.01, N), index=IDX)
    rows = _by_id(run_book(r, book, 252.0))
    assert rows["marginal_sharpe"]["details"]["gain"] > 0.5
    assert rows["marginal_sharpe"]["status"] == "pass"
    assert rows["residual_vs_book"]["status"] == "pass"
    assert abs(rows["book_correlation"]["details"]["corr_total"]) < 0.15
    assert set(rows["book_correlation"]["details"]["per_column"]) == {"a", "b"}


def test_deterministic_with_seed() -> None:
    book = _book()
    r = np.random.default_rng(1).normal(0.001, 0.01, N)
    b = book.sum(axis=1).to_numpy()
    a1 = marginal_sharpe(r, b[:, None], 252.0, seed=3)
    a2 = marginal_sharpe(r, b[:, None], 252.0, seed=3)
    assert a1["details"]["gain_ci90"] == a2["details"]["gain_ci90"]


def test_drawdown_overlap_warns_when_it_falls_with_book() -> None:
    book = _book()
    total = book.sum(axis=1).to_numpy()
    r = np.where(total <= np.quantile(total, 0.1), -0.02, 0.004)
    rows = _by_id(run_book(pd.Series(r, index=IDX), book, 252.0))
    assert rows["drawdown_overlap"]["status"] == "warn"


def test_drawdown_overlap_passes_for_hedge() -> None:
    book = _book()
    total = book.sum(axis=1).to_numpy()
    r = np.where(total <= np.quantile(total, 0.1), 0.01, 0.001)
    rows = _by_id(run_book(pd.Series(r, index=IDX), book, 252.0))
    assert rows["drawdown_overlap"]["status"] == "pass"


def test_align_book_errors_on_short_overlap() -> None:
    book = _book()
    r = pd.Series(np.zeros(30), index=IDX[:30])
    with pytest.raises(ValueError):
        align_book(r, book)
    assert run_book(r, book, 252.0)[0]["status"] == "skip"
