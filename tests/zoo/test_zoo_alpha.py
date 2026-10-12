"""A15: alpha traps and their honest twins.

Each trap must be caught by the named check and each twin must not be falsely accused by that check.
``ZOO_LEVEL=lite`` (default, CI) runs one seed per case and needs every expectation to hold; ``full`` (nightly) runs 20 seeds per
case and needs the share of seeds where the expectation holds to reach ``FULL_FLOOR`` (the checks that rest on a p-value cannot
reach 100 % on a pure-noise trap by design, see docs/guides/alpha-calibration.md).
"""

from __future__ import annotations

import os
import warnings

import pytest
from alpha_cases import GENERATORS, met, run_case

LEVEL = os.environ.get("ZOO_LEVEL", "lite")
SEEDS = range(20) if LEVEL == "full" else range(1)
FULL_FLOOR = 0.80
# (generator, trap) pairs the verifier is known to get wrong at lite seed 0: none today. A new miss fails; a closed gap fails too.
GAPS: dict[tuple[str, bool], str] = {}
# generators whose trap must end at a lower Alpha Readiness Level than its twin, with the level the trap must not exceed
ARL_PAIRS = ("residual_alpha", "hidden_short_volatility", "signal_placebo")

_CACHE: dict[tuple[str, bool, int], tuple] = {}


def _run(key: str, trap: bool, seed: int) -> tuple[dict[str, bool], int]:
    """Expectation results and readiness level of one generated case (cached: the ARL test reuses the run)."""
    if (key, trap, seed) not in _CACHE:
        case = GENERATORS[key](seed, trap)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            report = run_case(case, seed=seed)
        _CACHE[(key, trap, seed)] = (met(case, report), int(report["readiness"]["level"]))
    return _CACHE[(key, trap, seed)]


@pytest.mark.parametrize("trap", [True, False], ids=["trap", "twin"])
@pytest.mark.parametrize("key", list(GENERATORS))
def test_case(key: str, trap: bool) -> None:
    results = [_run(key, trap, s)[0] for s in SEEDS]
    hits = [all(r.values()) for r in results]
    rate = sum(hits) / len(hits)
    what = "trap was not caught" if trap else "twin was falsely accused"
    if (key, trap) in GAPS:
        assert rate < 1.0, f"{key} is now handled correctly: remove it from GAPS ({GAPS[(key, trap)]})"
        return
    need = 1.0 if LEVEL != "full" else FULL_FLOOR
    failing = [(s, r) for s, r, h in zip(SEEDS, results, hits, strict=True) if not h]
    assert rate >= need, f"{key} {what} on {len(failing)} of {len(hits)} seeds (need {need:.0%}): {failing[:3]}"


@pytest.mark.parametrize("key", ARL_PAIRS)
def test_readiness_orders_twin_above_trap(key: str) -> None:
    """The twin with the real edge reaches a higher Alpha Readiness Level than its trap (on the lite seed, or on most seeds in full)."""
    better = [_run(key, False, s)[1] > _run(key, True, s)[1] for s in SEEDS]
    need = 1.0 if LEVEL != "full" else FULL_FLOOR
    assert sum(better) / len(better) >= need, f"{key}: the twin out-ranked its trap on {sum(better)} of {len(better)} seeds"
