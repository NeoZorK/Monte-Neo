"""Lint rules for repainting signals, and the cases where a future-looking call is harmless."""

from __future__ import annotations

import pytest

from monte_neo.verify.fixes import suggest_fixes
from monte_neo.verify.lint import lint_source


def _rules(src: str) -> dict[str, str]:
    return {f["rule"]: f["severity"] for f in lint_source(src)["findings"]}


@pytest.mark.parametrize(
    "body,rule",
    [
        ("d = df['close'].resample('D').last()\n    return d", "htf_without_shift"),
        ("return security(df, lookahead='on')", "lookahead_on"),
        ("from scipy.signal import find_peaks\n    return find_peaks(df['close'])[0]", "unconfirmed_pivot"),
        ("return zigzag(df['close'])", "repaint_zigzag"),
    ],
)
def test_repaint_rules_are_warnings(body: str, rule: str) -> None:
    src = f"def zigzag(c):\n    return c\n\n\ndef signal(df):\n    {body}\n"
    assert _rules(src).get(rule) == "warn"


def test_a_shifted_higher_timeframe_series_is_not_flagged() -> None:
    assert "htf_without_shift" not in _rules("def signal(df):\n    return df['close'].resample('D').last().shift(1)\n")


def test_a_future_value_that_nothing_reads_is_a_warning_not_a_failure() -> None:
    src = "def signal(df):\n    label = df['close'].shift(-1)\n    return df['close'].rolling(5).mean()\n"
    assert _rules(src)["negative_shift"] == "warn"
    used = "def signal(df):\n    label = df['close'].shift(-1)\n    return label\n"
    assert _rules(used)["negative_shift"] == "fail"


def test_a_private_helper_nobody_calls_is_not_a_failure_but_a_called_one_is() -> None:
    dead = "def _label(df):\n    return df['close'].shift(-1)\n\n\ndef signal(df):\n    return df['close']\n"
    assert _rules(dead)["negative_shift"] == "warn"
    live = "def _label(df):\n    return df['close'].shift(-1)\n\n\ndef signal(df):\n    return _label(df)\n"
    assert _rules(live)["negative_shift"] == "fail"
    named = "def label(df):\n    return df['close'].shift(-1)\n"
    assert _rules(named)["negative_shift"] == "fail"  # a public function may be the strategy itself


def test_only_one_future_value_rules_are_softened() -> None:
    src = "import numpy as np\nfrom sklearn.model_selection import KFold\n\n\ndef signal(df):\n    cv = KFold(5, shuffle=True)\n    return np.zeros(len(df))\n"
    assert _rules(src).get("kfold_split") == "fail"


@pytest.mark.parametrize("size,origin,flagged", [(9, 4, False), (9, 3, True), (8, 3, False), (8, 2, True), (9, 0, True)])
def test_uniform_filter_with_a_trailing_origin_is_causal(size: int, origin: int, flagged: bool) -> None:
    src = f"import scipy.ndimage as nd\n\n\ndef signal(df):\n    return nd.uniform_filter1d(df['close'].to_numpy(), {size}, origin={origin})\n"
    assert ("centered_filter" in _rules(src)) is flagged


def test_the_fixer_shifts_a_higher_timeframe_aggregate_once_and_switches_lookahead_off() -> None:
    out = suggest_fixes("def signal(df):\n    return df['close'].resample('D').last()\n")
    assert [c["rule"] for c in out["changes"]] == ["htf_without_shift"] and ".shift(1)" in out["patched"]
    assert suggest_fixes("def signal(df):\n    return df['close'].resample('D').last().shift(2)\n")["changes"] == []
    fixed = suggest_fixes("def signal(df):\n    return security(df, lookahead='on')\n")
    assert fixed["changes"][0]["rule"] == "lookahead_on" and "lookahead='off'" in fixed["patched"]
