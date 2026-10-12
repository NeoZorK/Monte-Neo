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


@pytest.mark.parametrize(
    "line",
    [
        "m = LogisticRegression().fit(X[train], y[train])",
        "m = model.fit(X[:t], y[:t])",
        "model.fit(features.iloc[lo:hi], labels.iloc[lo:hi])",
    ],
)
def test_a_fit_on_a_chosen_slice_is_not_warned(line: str) -> None:
    assert lint_source(f"def signal(df):\n    {line}\n    return 0\n")["status"] == "pass"


@pytest.mark.parametrize("line", ["m = LogisticRegression().fit(X, y)", "km = KMeans(2).fit(vol)", "scaler.fit(prices)"])
def test_a_fit_on_a_whole_array_still_warns(line: str) -> None:
    result = lint_source(f"def signal(df):\n    {line}\n    return 0\n")
    assert result["status"] == "warn" and result["findings"][0]["rule"] == "full_sample_fit"


def _wrap(body: str) -> str:
    return "import numpy as np\n\ndef signal(df):\n" + "".join(f"    {line}\n" for line in body.splitlines()) + "    return np.zeros(len(df))\n"


@pytest.mark.parametrize(
    "body",
    [
        "X = df[['a', 'b']].to_numpy()\nZ = StandardScaler().fit_transform(X)",
        "scaler = MinMaxScaler()\nscaler.fit(X)",
        "pca = PCA(n_components=3)\nZ = pca.fit_transform(X)",
        "sel = SelectKBest(f_regression, k=5).fit(X, y)",
        "s = preprocessing.RobustScaler()\ns.fit(df[cols])",
    ],
)
def test_full_sample_transform_flagged(body: str) -> None:
    assert _rules(_wrap(body)).get("full_sample_transform") == "warn"


@pytest.mark.parametrize(
    "body",
    [
        "scaler = StandardScaler()\nscaler.fit(X[:split])",
        "scaler = StandardScaler()\nscaler.fit(df.iloc[:split])",
        "Z = StandardScaler().fit_transform(X_train)",
        "model = Ridge()\nmodel.fit(Xs, ys)",
    ],
)
def test_full_sample_transform_not_flagged(body: str) -> None:
    assert "full_sample_transform" not in _rules(_wrap(body))


@pytest.mark.parametrize(
    "body",
    [
        "df['enc'] = df.groupby('sector')['fwd_ret'].transform('mean')",
        "df['enc'] = df['sector'].map(df.groupby('sector')['target'].mean())",
        "df['enc'] = df.groupby('k')['future_move'].transform('mean')",
    ],
)
def test_target_encoding_full_flagged(body: str) -> None:
    assert _rules(_wrap(body)).get("target_encoding_full") == "warn"


@pytest.mark.parametrize(
    "body",
    [
        "df['m'] = df.groupby('sector')['volume'].transform('mean')",
        "means = df.groupby('sector')['target'].mean()",
        "df['enc'] = df.groupby('k')['fwd_ret'].transform('std')",
    ],
)
def test_target_encoding_full_not_flagged(body: str) -> None:
    assert "target_encoding_full" not in _rules(_wrap(body))
