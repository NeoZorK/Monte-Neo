"""A10: universes (many symbols in one long table): cross-sectional leaks and their honest twins."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_strategy

SYMBOLS = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")


def universe(n: int = 400) -> pd.DataFrame:
    frames = []
    for k, sym in enumerate(SYMBOLS):
        d = synthetic_ohlcv(n, seed=60 + k)
        d["timestamp"] = pd.date_range("2023-01-01", periods=n, freq="D")
        d["symbol"] = sym
        frames.append(d)
    return pd.concat(frames).sort_values(["timestamp", "symbol"]).reset_index(drop=True)


DF = universe()
G = "df.groupby('symbol')"
X = "df.groupby('timestamp')"


def _rank(expr: str) -> str:
    return f"({expr}).groupby(df['timestamp']).rank(pct=True).sub(0.5).fillna(0.0)"


# (id, expression of the weight, leaks)
CASES = [
    ("future_return_rank", _rank(f"{G}['close'].pct_change(-5)"), True),
    ("whole_sample_mean_scaling", _rank(f"df['close'] / {G}['close'].transform('mean')"), True),
    ("whole_sample_volume_rank", _rank(f"{G}['volume'].transform('sum')"), True),
    ("last_price_weights", _rank(f"{G}['close'].transform('last')"), True),
    ("rank_over_the_whole_panel", "df['close'].pct_change().rank(pct=True).sub(0.5).fillna(0.0)", True),
    ("centred_window_per_symbol", _rank(f"{G}['close'].transform(lambda s: s.rolling(7, center=True).mean())"), True),
    ("next_bar_return_sign", f"np.sign({G}['close'].pct_change(-1)).fillna(0.0) * 0.5", True),
    ("full_sample_volatility_weights", f"(1.0 / {G}['close'].transform(lambda s: s.pct_change().std())).pipe(lambda w: w / w.max()) - 0.5", True),
    ("momentum_rank", _rank(f"{G}['close'].pct_change(10)"), False),
    ("lagged_momentum_rank", _rank(f"{G}['close'].pct_change(10).groupby(df['symbol']).shift(1)"), False),
    ("expanding_mean_scaling", _rank(f"df['close'] / {G}['close'].transform(lambda s: s.expanding().mean())"), False),
    ("rolling_volatility_weights", "-" + _rank(f"{G}['close'].transform(lambda s: s.pct_change().rolling(20).std())"), False),
    ("demeaned_cross_section", f"({G}['close'].pct_change(5) - {X}['close'].transform(lambda s: 0)).fillna(0.0).pipe(lambda x: x - x.groupby(df['timestamp']).transform('mean')).clip(-0.5, 0.5)", False),
    ("equal_weight_long_only", "pd.Series(1.0 / 6, index=df.index)", False),
]


def _fn(expr: str):  # noqa: ANN202
    src = f"import numpy as np\nimport pandas as pd\n\n\ndef signal(df):\n    return {expr}\n"
    scope: dict = {}
    exec(compile(src, "<universe>", "exec"), scope)  # noqa: S102 - a literal table of expressions in this file
    return scope["signal"], src


def _oracle_causal(fn) -> bool:  # noqa: ANN001
    """Weights on the dates up to ``cut`` are the same when the later dates are removed."""
    full = pd.Series(np.asarray(fn(DF.copy()), dtype=float), index=DF.index)
    stamps = np.sort(DF["timestamp"].unique())
    for cut in stamps[[80, 150, 230, 310, 380]]:
        head = DF[DF["timestamp"] <= cut].reset_index(drop=True)
        got = np.asarray(fn(head.copy()), dtype=float)
        if not np.allclose(np.nan_to_num(got), np.nan_to_num(full.loc[DF["timestamp"] <= cut].to_numpy()), atol=1e-12):
            return False
    return True


@pytest.mark.parametrize("case", CASES, ids=lambda c: c[0])
def test_universe_case(case: tuple) -> None:
    case_id, expr, leaks = case
    fn, src = _fn(expr)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert _oracle_causal(fn) == (not leaks), f"{case_id}: label disagrees with the oracle"
        report = verify_strategy(DF, signal_fn=fn, source=src, positions="weight")
    status = {c["id"]: c["status"] for c in report["checks"]}
    dynamic = status.get("lookahead_truncation") == "fail" or status.get("lookahead_perturbation") == "fail"
    if leaks:
        assert dynamic, f"{case_id} leaks but was not caught: {status}"
    else:
        accused = [k for k in ("lookahead_truncation", "lookahead_perturbation", "external_data", "lookahead_static_lint", "determinism") if status.get(k) == "fail"]
        assert not accused, f"{case_id} is honest but was accused: {accused}"


def test_a_universe_of_survivors_only_is_warned_about() -> None:
    fn, src = _fn(CASES[8][1])
    report = verify_strategy(DF, signal_fn=fn, source=src, positions="weight")
    row = next(c for c in report["checks"] if c["id"] == "survivorship")
    assert row["status"] == "warn"  # every symbol trades until the last bar: delisted names may be missing


def test_a_symbol_that_stops_trading_removes_the_survivorship_warning() -> None:
    cut = DF[~((DF["symbol"] == "FFF") & (DF["timestamp"] > "2023-09-01"))].reset_index(drop=True)
    fn, src = _fn(CASES[8][1])
    row = next(c for c in verify_strategy(cut, signal_fn=fn, source=src, positions="weight")["checks"] if c["id"] == "survivorship")
    assert row["status"] == "pass" and "stop trading" in row["summary"]


def test_symbol_case_duplicates_and_repeated_rows_are_integrity_failures() -> None:
    dup = pd.concat([DF, DF.iloc[:5]]).sort_values(["timestamp", "symbol"]).reset_index(drop=True)
    fn, src = _fn(CASES[8][1])
    report = verify_strategy(dup, signal_fn=fn, source=src, positions="weight")
    assert report["verdict"] == "REJECT" and report["checks"][0]["id"] == "data_integrity" and report["checks"][0]["status"] == "fail"
