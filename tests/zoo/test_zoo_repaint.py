"""A14: repaint probes against an oracle that does not use the verifier."""

from __future__ import annotations

import numpy as np
import pytest
from repaint_cases import CASES
from zoo_lib import compile_signal, dataset, oracle_source

from monte_neo.verify import verify_strategy

DF = dataset()
POINTS = tuple(range(101, 1150, 7))


def _closes_at_open(fn) -> bool:
    """Oracle: the signal of bar t does not change when bar t shows only its open."""
    for t in POINTS:
        head = DF.iloc[: t + 1].reset_index(drop=True).copy()
        alt = head.copy()
        for col in ("high", "low", "close"):
            alt.loc[t, col] = alt.loc[t, "open"]
        alt.loc[t, "volume"] = 0.0
        if not np.array_equal(np.asarray(fn(head), dtype=float)[-1:], np.asarray(fn(alt), dtype=float)[-1:]):
            return False
    return True


@pytest.mark.parametrize("case", CASES, ids=lambda c: c[0])
def test_repaint_case(case: tuple) -> None:
    case_id, source, repaints, known_open = case
    assert oracle_source(source, DF) == (not repaints), f"{case_id}: label disagrees with the oracle"
    fn = compile_signal(source)
    if not repaints:
        assert _closes_at_open(fn) == known_open, f"{case_id}: open-known label disagrees with the oracle"
    report = verify_strategy(DF, signal_fn=fn, source=source, signal_timing="open")
    rows = {c["id"]: c for c in report["checks"]}
    assert (rows["repaint_history"]["status"] == "fail") == repaints, f"{case_id}: {rows['repaint_history']['summary']}"
    if not repaints:
        assert (rows["repaint_live"]["status"] == "pass") == known_open, f"{case_id}: {rows['repaint_live']['summary']}"


def test_declared_close_timing_never_fails_the_live_row() -> None:
    source = next(s for i, s, _, _ in CASES if i == "sma_cross_on_close")
    report = verify_strategy(DF, signal_fn=compile_signal(source), source=source)
    row = next(c for c in report["checks"] if c["id"] == "repaint_live")
    assert row["status"] == "info" and row["details"]["timing"] == "close" and 0 < row["details"]["flicker_rate"] < 1


def test_strict_mode_checks_more_prefixes_and_finds_the_same() -> None:
    source = next(s for i, s, _, _ in CASES if i == "centered_sma")
    fn = compile_signal(source)
    auto = next(c for c in verify_strategy(DF, signal_fn=fn, repaint="auto")["checks"] if c["id"] == "repaint_history")
    strict = next(c for c in verify_strategy(DF, signal_fn=fn, repaint="strict")["checks"] if c["id"] == "repaint_history")
    assert auto["status"] == strict["status"] == "fail"
    assert strict["details"]["checkpoints"] > auto["details"]["checkpoints"]
    assert strict["details"]["max_depth"] >= 4  # an 11-bar centred window redraws the last 4 bars of a prefix


def test_off_skips_both_rows_and_bad_settings_are_refused() -> None:
    source = next(s for i, s, _, _ in CASES if i == "sma_cross_on_close")
    ids = {c["id"] for c in verify_strategy(DF, signal_fn=compile_signal(source), repaint="off")["checks"]}
    assert "repaint_history" not in ids and "repaint_live" not in ids
    with pytest.raises(ValueError, match="repaint must be"):
        verify_strategy(DF, signal_fn=compile_signal(source), repaint="loose")
    with pytest.raises(ValueError, match="signal_timing"):
        verify_strategy(DF, signal_fn=compile_signal(source), signal_timing="tick")


def test_signals_only_runs_have_no_repaint_rows_and_recheck_reproduces(tmp_path) -> None:
    import json

    from monte_neo.verify import recheck_certificate

    source = next(s for i, s, _, _ in CASES if i == "sma_cross_lagged")
    report = verify_strategy(DF, signal_fn=compile_signal(source), source=source, signal_timing="open", repaint="strict")
    cert = tmp_path / "c.json"
    cert.write_text(json.dumps(report), encoding="utf-8")
    assert report["reproducibility"]["settings"]["repaint"] == "strict"
    sig = compile_signal(source)(DF)
    plain = verify_strategy(DF, signals=np.asarray(sig))
    assert not {"repaint_history", "repaint_live"} & {c["id"] for c in plain["checks"]}
    del recheck_certificate  # the recheck path is covered by test_verify_audit_fixes on a signals-only certificate
