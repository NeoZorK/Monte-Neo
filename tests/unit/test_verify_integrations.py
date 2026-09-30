"""Framework adapters, notebook display, pandas accessor, badge and the pre-commit lint entry."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli.verify_cmd import main as verify_main
from monte_neo.verify import Certificate, badge_payload, show, verify_strategy
from monte_neo.verify.adapters import (
    from_fills,
    from_freqtrade,
    from_lean,
    from_vectorbt,
    from_zipline,
    positions_from_fills,
    positions_from_trades,
)


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    df = synthetic_ohlcv(400, seed=3)
    return df.assign(timestamp=pd.date_range("2024-01-01", periods=len(df), freq="h"))


def _t(prices: pd.DataFrame, i: int) -> pd.Timestamp:
    return pd.Timestamp(prices["timestamp"].iloc[i])


def test_trade_holds_from_entry_open_to_exit_open(prices: pd.DataFrame) -> None:
    trades = pd.DataFrame({"open_time": [_t(prices, 10)], "close_time": [_t(prices, 20)], "side": ["long"]})
    pos = positions_from_trades(prices, trades)
    assert pos[:9].sum() == 0
    assert (pos[9:19] == 1).all()  # decided one bar before the entry bar opens
    assert pos[19:].sum() == 0


def test_short_and_overlap_are_clipped(prices: pd.DataFrame) -> None:
    trades = pd.DataFrame(
        {"open_time": [_t(prices, 10), _t(prices, 12)], "close_time": [_t(prices, 20)] * 2, "side": [1, 1]},
    )
    assert positions_from_trades(prices, trades).max() == 1.0
    short = pd.DataFrame({"open_time": [_t(prices, 5)], "close_time": [_t(prices, 8)], "side": ["short"]})
    assert (positions_from_trades(prices, short)[4:7] == -1).all()


def test_unknown_side_and_missing_columns_raise(prices: pd.DataFrame) -> None:
    bad = pd.DataFrame({"open_time": [_t(prices, 1)], "close_time": [_t(prices, 3)], "side": ["sideways"]})
    with pytest.raises(ValueError, match="side"):
        positions_from_trades(prices, bad)
    with pytest.raises(ValueError, match="close_time"):
        positions_from_trades(prices, pd.DataFrame({"open_time": [1], "side": [1]}))


def test_fills_accumulate_and_flatten(prices: pd.DataFrame) -> None:
    fills = [
        {"timestamp": _t(prices, 10), "quantity": 2.0},
        {"timestamp": _t(prices, 30), "quantity": -2.0},
        {"timestamp": _t(prices, 50), "quantity": -1.0},
    ]
    pos = positions_from_fills(prices, fills)
    assert (pos[9:29] == 1).all() and (pos[29:49] == 0).all() and (pos[49:] == -1).all()


def test_timezone_aware_fills_match_naive_prices(prices: pd.DataFrame) -> None:
    fills = [{"timestamp": _t(prices, 10).tz_localize("UTC"), "quantity": 1.0}]
    assert positions_from_fills(prices, fills)[9:].min() == 1


def test_empty_fills_are_flat(prices: pd.DataFrame) -> None:
    assert not positions_from_fills(prices, pd.DataFrame({"timestamp": [], "quantity": []})).any()


def test_freqtrade_lean_zipline_and_fills_agree(prices: pd.DataFrame) -> None:
    a, b = _t(prices, 40), _t(prices, 90)
    ft = from_freqtrade(pd.DataFrame({"open_date": [a], "close_date": [b], "is_short": [False]}), prices)
    lean = from_lean([{"time": a, "fillQuantity": 5, "status": "Filled"}, {"time": b, "fillQuantity": -5, "status": "Filled"},
                      {"time": a, "fillQuantity": 99, "status": "Submitted"}], prices)
    zl = from_zipline([{"dt": a, "amount": 3}, {"dt": b, "amount": -3}], prices)
    raw = from_fills(pd.DataFrame({"timestamp": [a, b], "quantity": [1, -1]}), prices)
    for adapted in (ft, lean, zl, raw):
        assert (adapted.positions[39:89] == 1).all()
        assert adapted.positions[89:].sum() == 0


def test_lean_needs_fill_columns(prices: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="fillQuantity"):
        from_lean([{"time": _t(prices, 1)}], prices)


class _Frame:
    """The parts of a vectorbt portfolio the adapter reads."""

    def __init__(self, df: pd.DataFrame) -> None:
        idx = pd.DatetimeIndex(df["timestamp"])
        self.close = pd.Series(df["close"].to_numpy(), index=idx)
        self._assets = pd.Series(np.where((np.arange(len(df)) > 50) & (np.arange(len(df)) < 200), 10.0, 0.0), index=idx)
        self.open = pd.Series(df["open"].to_numpy(), index=idx)
        self.high = pd.Series(df["high"].to_numpy(), index=idx)
        self.low = None

    def assets(self) -> pd.Series:
        return self._assets

    def value(self) -> pd.Series:
        return pd.Series(1000.0 * 10, index=self.close.index)


def test_vectorbt_weights_and_verify(prices: pd.DataFrame) -> None:
    adapted = from_vectorbt(_Frame(prices))
    assert adapted.mode == "weight"
    assert adapted.positions.min() >= 0.0 and adapted.positions.max() <= 1.0
    assert {"open", "high", "low", "close", "timestamp"} <= set(adapted.ohlcv.columns)
    report = adapted.verify()
    assert report["schema"] == "strategy-verdict/1"
    assert isinstance(report, Certificate)


def test_vectorbt_wide_portfolio_is_refused(prices: pd.DataFrame) -> None:
    pf = _Frame(prices)
    pf.close = pd.concat([pf.close, pf.close], axis=1)
    with pytest.raises(ValueError, match="one column"):
        from_vectorbt(pf)


def test_certificate_is_a_dict_that_renders_in_a_notebook(prices: pd.DataFrame) -> None:
    report = verify_strategy(prices, signals=np.sign(np.sin(np.arange(len(prices)) / 20.0)))
    assert isinstance(report, dict) and json.loads(json.dumps(report))["verdict"] == report["verdict"]
    page = report._repr_html_()
    assert page.startswith("<iframe sandbox srcdoc=") and "Monte-Neo" in page
    assert show(dict(report)) is not report and isinstance(show(dict(report)), Certificate)
    assert show(report) is report


def test_accessor_verifies_signals_and_functions(prices: pd.DataFrame) -> None:
    import monte_neo.verify.accessor  # noqa: F401

    sig = np.sign(np.sin(np.arange(len(prices)) / 20.0))
    by_signals = prices.monte_neo.verify(sig)
    by_function = prices.monte_neo.verify(strategy=lambda df: np.sign(np.sin(np.arange(len(df)) / 20.0)))
    assert by_signals["schema"] == by_function["schema"] == "strategy-verdict/1"


@pytest.mark.parametrize(
    ("verdict", "color"),
    [("PASS", "brightgreen"), ("PASS_WITH_WARNINGS", "yellow"), ("NEEDS_MORE_EVIDENCE", "orange"), ("REJECT", "red")],
)
def test_badge_payload(verdict: str, color: str) -> None:
    badge = badge_payload({"verdict": verdict, "certificate_id": "0123456789abcdef"})
    assert badge["schemaVersion"] == 1 and badge["color"] == color and badge["message"].endswith("01234567")
    assert badge["label"] == "Monte-Neo"


def test_badge_for_unknown_verdict_is_grey() -> None:
    assert badge_payload({})["color"] == "lightgrey"


def test_cli_writes_the_badge(tmp_path, prices: pd.DataFrame) -> None:
    csv, sig, badge = tmp_path / "p.csv", tmp_path / "s.csv", tmp_path / "badge.json"
    prices.to_csv(csv, index=False)
    pd.Series(np.sign(np.sin(np.arange(len(prices)) / 20.0))).to_csv(sig, index=False, header=["signal"])
    code = verify_main(["--ohlcv", str(csv), "--signals", str(sig), "--badge", str(badge), "--format", "json"])
    assert code in (0, 1, 2)
    assert json.loads(badge.read_text())["schemaVersion"] == 1


def test_cli_lint_only_for_pre_commit(tmp_path) -> None:
    bad, good, broken = tmp_path / "bad.py", tmp_path / "good.py", tmp_path / "broken.py"
    bad.write_text("def signal(df):\n    return df['close'].shift(-1) > df['close']\n")
    good.write_text("def signal(df):\n    return df['close'].shift(1) < df['close']\n")
    broken.write_text("def signal(:\n")
    assert verify_main(["--lint", str(good)]) == 0
    assert verify_main(["--lint", str(good), str(bad)]) == 1
    assert verify_main(["--lint", str(broken)]) == 0  # a syntax error is the compiler's job, not a look-ahead finding
    assert verify_main(["--lint", str(tmp_path / "missing.py")]) == 3
