"""Known-error benchmark: every generated mistake is flagged, honest controls are not rejected, noise is not accepted."""

from __future__ import annotations

import pytest

from monte_neo.bench.known_errors import CASES, FLAG_CHECKS, ar_market, render_markdown, run_case, run_known_errors

SEEDS = 1


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case_behaves_as_expected(case) -> None:  # noqa: ANN001
    for seed in range(SEEDS):
        r = run_case(case, seed)
        assert r["ok"], f"{case.id} seed {seed}: verdict {r['verdict']}, flagged by {r['flagged_by']}"
        if case.id in FLAG_CHECKS:
            assert r["flagged_by"]


def test_report_rates_and_markdown() -> None:
    only = tuple(c for c in CASES if c.id in ("next_bar_leak", "momentum_ar", "noise_strategy"))
    rep = run_known_errors(1, only)
    assert rep["cases"]["next_bar_leak"]["miss_rate"] == 0.0
    assert rep["cases"]["momentum_ar"]["false_reject_rate"] == 0.0
    assert rep["cases"]["noise_strategy"]["false_accept_rate"] == 0.0
    md = render_markdown(rep)
    assert "| next_bar_leak | error |" in md and "1 seeds" in md


def test_generators_are_reproducible_and_valid() -> None:
    a, b = ar_market(200, 0.1, 5), ar_market(200, 0.1, 5)
    assert a.equals(b) and (a["high"] >= a[["open", "close"]].max(axis=1)).all() and (a["low"] <= a[["open", "close"]].min(axis=1)).all()
    split = ar_market(200, 0.0, 5, split_at=100)
    assert split["close"].iloc[100] / split["close"].iloc[99] < 0.6  # the 2:1 split shows as a jump
    assert [c.kind for c in CASES].count("error") == 6 and {"honest", "noise"} <= {c.kind for c in CASES}
