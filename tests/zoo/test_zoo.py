"""Hypothesis zoo: leaks must be caught by the dynamic probes, honest twins must not be accused.

``ZOO_LEVEL=lite`` (default) runs the direct form of every mechanism; ``full`` runs all six disguises.
Cases the verifier is known to miss live in ``known_gaps.json``: a new miss fails the run, and so does a gap that closed.
"""

from __future__ import annotations

import os

import pytest
from zoo_run import cases, known_gaps, outcome_ok, run_case

LEVEL = os.environ.get("ZOO_LEVEL", "lite")
GAPS = known_gaps()


@pytest.mark.parametrize("case", cases(LEVEL), ids=lambda c: c[0])
def test_case(case: tuple) -> None:
    case_id, _, disguise, leaks, row = case
    result = run_case(row, disguise)
    ok = outcome_ok(leaks, result)
    if case_id in GAPS:
        assert not ok, f"{case_id} is now handled correctly: remove it from known_gaps.json ({GAPS[case_id]})"
    else:
        what = "was not caught by the truncation or perturbation probe" if leaks else f"was accused: {result['accused']}"
        assert ok, f"{case_id} {what}"
