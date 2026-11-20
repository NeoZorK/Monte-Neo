"""ARL depth on the alpha zoo: no false promotions (a trap is not ranked above the twin it imitates, depth never skips a level)."""

from __future__ import annotations

import warnings

import pytest
from alpha_cases import GENERATORS, declare_universe, run_case

ARL_PAIRS = ("residual_alpha", "hidden_short_volatility", "signal_placebo")
_CACHE: dict[tuple[str, bool], dict] = {}


def _readiness(key: str, trap: bool) -> dict:
    if (key, trap) not in _CACHE:
        case = declare_universe(GENERATORS[key](0, trap))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _CACHE[(key, trap)] = run_case(case, seed=0)["readiness"]
    return _CACHE[(key, trap)]


@pytest.mark.parametrize("trap", [True, False], ids=["trap", "twin"])
@pytest.mark.parametrize("key", list(GENERATORS))
def test_depth_is_honest_on_every_case(key: str, trap: bool) -> None:
    r = _readiness(key, trap)
    assert r["rules_version"] == "arl-rules/2" and r["provisional"] is True and r["headline"].startswith(f"ARL {r['level']}, depth {r['depth']}/4")
    for lv in r["levels"]:
        assert lv["counts"] or lv["depth"] == 0
        assert 0 <= lv["depth"] <= 4
        # the alpha path has no sealed holdout, no live fills and no fresh fetch: those criteria are not assessed, never passed
        by = {c["id"]: c["state"] for c in lv["depth_criteria"]}
        assert by["D4"] != "met", (key, lv["level"])
    assert r["level"] <= 8, "the alpha path cannot reach ARL 9 without live fills"


@pytest.mark.parametrize("key", ARL_PAIRS)
def test_trap_is_not_promoted_above_its_twin(key: str) -> None:
    trap, twin = _readiness(key, True), _readiness(key, False)
    assert trap["level"] < twin["level"]
    must_fail = next(lv for lv in trap["levels"] if lv["state"] == "failed")
    assert must_fail["depth"] == 0  # the level the trap must fail shows no depth
    assert (trap["level"], trap["depth"]) < (twin["level"], 5)
