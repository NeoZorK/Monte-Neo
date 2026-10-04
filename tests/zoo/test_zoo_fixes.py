"""Suggested fixes against the leak zoo: every patch must make the strategy causal (judged by the independent oracle)."""

from __future__ import annotations

import pytest
from mechanisms import HONEST, LEAKS
from zoo_lib import build, compile_signal, dataset

from monte_neo.verify.fixes import suggest_fixes

DF = dataset()
# The rewrite fixes one pattern but another leak in the same strategy remains (a fit or a transform over the whole table).
PARTIAL = {"sc_hilbert", "ml_lstsq_in_sample", "ml_target_encoding"}
# Honest code that the syntactic fixer rewrites anyway: a negative shift whose result never reaches the signal.
REWRITTEN_ANYWAY = {"hl_label_unused", "hl_label_shifted_back"}


def _pre(row: tuple) -> tuple:
    return tuple(row[4]) if len(row) > 4 else ()


def _fixed(row: tuple) -> dict:
    return suggest_fixes(build(row[2], row[3], "direct", _pre(row)))


@pytest.mark.parametrize("row", LEAKS, ids=lambda r: r[0])
def test_a_patch_never_leaves_a_leak_and_always_runs(row: tuple) -> None:
    result = _fixed(row)
    if not result["changes"]:
        pytest.skip("no rewrite for this mechanism")
    fn = compile_signal(result["patched"])
    assert fn(DF.copy()) is not None
    from zoo_lib import oracle_source

    causal = oracle_source(result["patched"], DF)
    if row[0] in PARTIAL:
        assert not causal, f"{row[0]} is now fully fixed: remove it from PARTIAL"
    else:
        assert causal, f"{row[0]}: the patch is still not causal\n{result['diff']}"


def test_the_fixer_covers_a_third_of_the_leak_mechanisms() -> None:
    patched = [row[0] for row in LEAKS if _fixed(row)["changes"]]
    assert len(patched) >= len(LEAKS) // 3, f"only {len(patched)} of {len(LEAKS)} mechanisms are rewritten"


@pytest.mark.parametrize("row", HONEST, ids=lambda r: r[0])
def test_honest_code_is_left_alone(row: tuple) -> None:
    result = _fixed(row)
    if row[0] in REWRITTEN_ANYWAY:
        assert result["changes"], f"{row[0]} is no longer rewritten: remove it from REWRITTEN_ANYWAY"
    else:
        assert not result["changes"], f"{row[0]} is causal but was rewritten: {result['changes']}"


def test_each_rewrite_reports_what_it_did() -> None:
    result = suggest_fixes('import pandas as pd\ndef signal(df):\n    x = df["close"].shift(-3) - df["close"].rolling(5, center=True).mean()\n    return (x - x.mean()).fillna(0)\n')
    rules = {c["rule"] for c in result["changes"]}
    assert rules == {"negative_shift", "centered_window", "whole_sample_statistic"}
    assert "shift(3)" in result["patched"] and "center" not in result["patched"] and "expanding().mean()" in result["patched"]
    assert result["diff"].startswith("--- strategy.py") and result["remaining"] == []


def test_untouched_and_unparsable_sources() -> None:
    clean = "def signal(df):\n    return df['close'].rolling(5).mean()\n"
    assert suggest_fixes(clean)["patched"] == clean and suggest_fixes(clean)["changes"] == []
    assert "syntax error" in suggest_fixes("def (:")["error"]
