"""Family G: data and research process."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from monte_neo.alpha._core import leg_weights, quantile_index
from monte_neo.alpha.panel import Panel
from monte_neo.alpha.process import NEXT_ACTIONS, load_membership, run_process

N, M = 800, 8


def _panel(close: np.ndarray, scores: np.ndarray, start: str = "2018-01-01") -> Panel:
    dates = pd.bdate_range(start, periods=close.shape[0])
    return Panel(dates, [f"S{i}" for i in range(close.shape[1])], close, scores)


def _weights(p: Panel) -> np.ndarray:
    valid = np.isfinite(p.scores) & np.isfinite(p.close)
    return leg_weights(quantile_index(p.scores, valid, 3), 3)


def _random(seed: int = 0) -> Panel:
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.01, (N, M)), axis=0)
    return _panel(close, rng.normal(size=(N, M)))


def _rows(p: Panel, **kw):
    return {r["id"]: r for r in run_process(p, _weights(p), **kw)}


def test_membership_violation_fails_with_counts() -> None:
    p = _random()
    w = _weights(p)
    mem = pd.DataFrame({"symbol": p.symbols, "start": [None] * M, "end": [None] * M})
    mem.loc[0, "end"] = str(p.dates[100].date())
    rows = {r["id"]: r for r in run_process(p, w, membership=mem)}
    row = rows["universe_lookahead"]
    assert row["status"] == "fail"
    assert row["details"]["violating_symbols"] == ["S0"]
    assert row["details"]["violating_bars"] > 0
    assert row["details"]["violating_positions"] == row["details"]["violating_bars"]


def test_membership_respected_passes() -> None:
    p = _random()
    mem = pd.DataFrame({"symbol": p.symbols, "start": ["2000-01-01"] * M, "end": [""] * M})
    assert _rows(p, membership=mem)["universe_lookahead"]["status"] == "pass"


def test_survivor_universe_warns_and_churn_does_not() -> None:
    p = _random()
    assert _rows(p)["universe_lookahead"]["status"] == "warn"
    p.close[:200, 1] = np.nan
    assert _rows(p)["universe_lookahead"]["status"] == "info"


def test_groups_without_dates_warn() -> None:
    p = _random()
    g = pd.DataFrame({"symbol": p.symbols, "sector": ["a", "b"] * 4})
    assert _rows(p, groups=g)["classification_lookahead"]["status"] == "warn"
    g["as_of"] = "2018-01-01"
    assert _rows(p, groups=g)["classification_lookahead"]["status"] == "info"
    assert _rows(p)["classification_lookahead"]["status"] == "skip"


def _two_exchange(lag: int) -> tuple[Panel, dict[str, str]]:
    rng = np.random.default_rng(3)
    n = 1200
    ny = rng.normal(0, 0.01, (n, 4))
    tk = np.zeros((n, 4))
    tk[1:] = 0.8 * ny[:-1] + rng.normal(0, 0.003, (n - 1, 4))
    rets = np.hstack([ny, tk])
    close = 100 * np.cumprod(1 + rets, axis=0)
    scores = np.full((n, 8), np.nan)
    scores[:, 4:] = np.roll(ny, lag, axis=0)
    scores[:lag, 4:] = np.nan if lag else scores[:lag, 4:]
    p = _panel(close, scores)
    ex = {s: "XNYS" for s in p.symbols[:4]} | {s: "XTKS" for s in p.symbols[4:]}
    return p, ex


def test_cross_market_same_date_fails_and_lagged_passes() -> None:
    p, ex = _two_exchange(0)
    row = _rows(p, exchanges=ex)["cross_market_close_alignment"]
    assert row["status"] in ("warn", "fail")
    assert row["details"]["max_close_gap_hours"] > 4
    p2, ex2 = _two_exchange(1)
    assert _rows(p2, exchanges=ex2)["cross_market_close_alignment"]["status"] == "pass"


def test_cross_market_single_exchange_and_none_skip() -> None:
    p, _ = _two_exchange(0)
    assert _rows(p, exchanges={s: "XNYS" for s in p.symbols})["cross_market_close_alignment"]["status"] == "skip"
    assert _rows(p)["cross_market_close_alignment"]["status"] == "skip"


def test_dst_changes_new_york_close() -> None:
    p, ex = _two_exchange(0)
    hours = _rows(p, exchanges=ex)["cross_market_close_alignment"]["details"]["close_hours_utc"]["XNYS"]
    assert hours == [21.0, 20.0]


def _decay_panel(post_drift: float) -> Panel:
    rng = np.random.default_rng(5)
    n = 1000
    rets = rng.normal(0, 0.01, (n, M))
    scores = rng.normal(size=(n, M))
    drift = np.where(np.arange(n) < 500, 0.01, post_drift)
    rets[1:] += scores[:-1] * drift[1:, None] * 0.5
    return _panel(100 * np.cumprod(1 + rets, axis=0), scores)


def test_post_discovery_decay_detected() -> None:
    p = _decay_panel(0.0)
    row = _rows(p, discovery_date=str(p.dates[500].date()))["post_discovery_decay"]
    assert row["status"] == "warn"
    assert row["details"]["decay"] > 0.5
    p2 = _decay_panel(0.01)
    assert _rows(p2, discovery_date=str(p2.dates[500].date()))["post_discovery_decay"]["status"] == "info"


def test_post_discovery_skips() -> None:
    p = _random()
    assert _rows(p)["post_discovery_decay"]["status"] == "skip"
    late = str(p.dates[-10].date())
    assert _rows(p, discovery_date=late)["post_discovery_decay"]["status"] == "skip"


def test_hygiene_scoring() -> None:
    p = _random()
    full = dict(registered=True, registered_before_first_run=True, ledger_variants=5, holdout_used=True)
    row = _rows(p, hygiene=full)["research_hygiene"]
    assert row["status"] == "info" and row["details"]["score"] == 4
    row = _rows(p, hygiene=dict(registered=True, registered_before_first_run=False, ledger_variants=None, holdout_used=None))["research_hygiene"]
    assert row["status"] == "warn" and row["details"]["score"] == 1
    assert "holdout_used" in row["details"]["missing"]
    assert _rows(p)["research_hygiene"]["status"] == "skip"


def test_load_membership_open_end(tmp_path: Path) -> None:
    f = tmp_path / "m.csv"
    f.write_text("symbol,start,end\nAAA,2019-01-01,2020-06-30\nBBB,2018-01-01,\n")
    m = load_membership(f)
    assert m["symbol"].tolist() == ["AAA", "BBB"]
    assert m["end"].iloc[0] == pd.Timestamp("2020-06-30")
    assert pd.isna(m["end"].iloc[1])


def test_next_actions_cover_ids() -> None:
    assert set(NEXT_ACTIONS) == {"universe_lookahead", "classification_lookahead", "cross_market_close_alignment", "post_discovery_decay", "research_hygiene"}
