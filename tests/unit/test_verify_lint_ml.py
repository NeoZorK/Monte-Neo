"""Lint rules for the machine-learning mistakes agents make on time series: shuffled splits and k-fold without time order."""

from __future__ import annotations

import pytest

from monte_neo.verify.lint import lint_source


def _rules(source: str) -> dict[str, str]:
    return {f["rule"]: f["severity"] for f in lint_source(source)["findings"]}


@pytest.mark.parametrize(
    ("call", "rule", "severity"),
    [
        ("train_test_split(X, y, test_size=0.3)", "shuffled_split", "warn"),  # shuffles by default
        ("train_test_split(X, y, shuffle=True)", "shuffled_split", "fail"),
        ("model_selection.train_test_split(X, y)", "shuffled_split", "warn"),
        ("KFold(n_splits=5, shuffle=True)", "kfold_split", "fail"),
        ("KFold(5)", "kfold_split", "warn"),
        ("StratifiedKFold(n_splits=4)", "kfold_split", "warn"),
        ("GroupKFold(3)", "kfold_split", "warn"),
        ("ShuffleSplit(n_splits=3)", "kfold_split", "fail"),
        ("sklearn.model_selection.RepeatedKFold()", "kfold_split", "warn"),
    ],
)
def test_split_mistakes_are_flagged(call: str, rule: str, severity: str) -> None:
    source = f"import numpy as np\n\ndef signal(df):\n    splitter = {call}\n    return np.zeros(len(df))\n"
    assert _rules(source) == {rule: severity}


@pytest.mark.parametrize(
    "call",
    ["train_test_split(X, y, shuffle=False)", "TimeSeriesSplit(n_splits=5, gap=10)", "KFoldish(3)", "walk_forward_split(X)"],
)
def test_time_aware_splits_are_not_flagged(call: str) -> None:
    source = f"def signal(df):\n    splitter = {call}\n    return df\n"
    assert _rules(source) == {}


def test_finding_reports_line_and_snippet() -> None:
    result = lint_source("def signal(df):\n    a, b = train_test_split(df)\n    return a\n")
    finding = result["findings"][0]
    assert finding["line"] == 2 and "train_test_split" in finding["snippet"] and "training sees the future" in finding["message"]
    assert result["status"] == "warn"
    assert lint_source("def signal(df):\n    return KFold(3, shuffle=True)\n")["status"] == "fail"
