"""Polars look-ahead forms (issue 124) and cross-sectional axis=1 operations (issue 125)."""

from __future__ import annotations

import pytest

from monte_neo.verify.lint import lint_source


def _rules(body: str) -> dict[str, str]:
    src = "def signal(df):\n    " + body + "\n"
    return {f["rule"]: f["severity"] for f in lint_source(src)["findings"]}


@pytest.mark.parametrize(
    "body,rule",
    [
        ("return df.with_columns(pl.col('c').fill_null(strategy='backward'))", "backward_fill"),
        ("return df.join_asof(o, on='t', strategy='forward')", "forward_asof"),
        ("return df.join_asof(o, on='t', strategy='nearest')", "forward_asof"),
        ("return pl.col('c').cum_max(reverse=True)", "reversed_cumulative"),
        ("return pl.col('c').cum_min(reverse=True)", "reversed_cumulative"),
        ("return pl.col('c').cum_sum(reverse=True)", "reversed_cumulative"),
        ("return pl.col('c').cum_prod(reverse=True)", "reversed_cumulative"),
    ],
)
def test_polars_future_forms_fail(body: str, rule: str) -> None:
    assert _rules(body).get(rule) == "fail"


@pytest.mark.parametrize(
    "body",
    [
        "return pl.col('c').fill_null(strategy='forward')",
        "return pl.col('c').fill_null(0)",
        "return pl.col('c').fill_null(strategy='mean')",
        "return df.join_asof(o, on='t', strategy='backward')",
        "return df.join_asof(o, on='t')",
        "return pl.col('c').cum_max()",
        "return pl.col('c').cum_sum(reverse=False)",
        "return df.merge_asof(o, direction='backward')",
        "return df['c'].fillna(method='ffill')",
    ],
)
def test_polars_clean_forms_stay_silent(body: str) -> None:
    assert not {"backward_fill", "forward_asof", "reversed_cumulative"} & set(_rules(body))


def test_pandas_forms_still_fail() -> None:
    assert _rules("return df['c'].fillna(method='bfill')").get("backward_fill") == "fail"
    assert _rules("return pd.merge_asof(a, b, on='t', direction='forward')").get("forward_asof") == "fail"
    assert _rules("return pd.merge_asof(a, b, on='t', strategy='forward')").get("forward_asof") is None


@pytest.mark.parametrize(
    "body",
    [
        "return df.rank(axis=1, pct=True)",
        "return df.rank(axis='columns')",
        "return np.nanmean(arr, axis=1)",
        "return np.nanmean(arr, 1)",
        "return np.mean(arr, axis='columns')",
        "return df.std(axis=1)",
        "return df.mean(1)",
        "return np.percentile(arr, 50, 1)",
        "return df.quantile(0.5, axis=1)",
        "return df.argsort(axis=1)",
    ],
)
def test_cross_sectional_axis_is_not_flagged(body: str) -> None:
    found = set(_rules(body))
    assert not {"full_sample_rank", "full_sample_stat"} & found


@pytest.mark.parametrize(
    "body,rule",
    [
        ("return df['c'].rank(axis=0)", "full_sample_rank"),
        ("return df['c'].rank()", "full_sample_rank"),
        ("return np.nanmean(arr, axis=0)", "full_sample_stat"),
        ("return np.nanmean(arr, 0)", "full_sample_stat"),
        ("return np.nanmean(arr, axis=None)", "full_sample_stat"),
        ("return np.nanmean(arr)", "full_sample_stat"),
        ("return np.mean(arr, axis=-1)", "full_sample_stat"),
        ("return df['c'].std(axis=0)", "full_sample_stat"),
        ("return df['c'].std()", "full_sample_stat"),
        ("return np.percentile(arr, 50, axis=0)", "full_sample_stat"),
    ],
)
def test_other_axes_still_warn(body: str, rule: str) -> None:
    assert rule in _rules(body)


def test_axis_one_over_a_gather_from_the_whole_sample_still_warns() -> None:
    assert "full_sample_stat" in _rules("return nxt[near].mean(axis=1)")
    assert "full_sample_stat" not in _rules("return nxt[:, :5].mean(axis=1)")
