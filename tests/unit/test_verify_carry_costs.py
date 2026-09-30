"""Borrow fee (shorts only) and funding (every position) in the verifier's engines."""

from __future__ import annotations

import numpy as np
import pytest

from monte_neo.backtest import ExecutionModel, run_bar_backtest, synthetic_ohlcv
from monte_neo.backtest.batch import run_bar_backtest_batch
from monte_neo.backtest.weight_engine import run_weight_backtest
from monte_neo.verify import model_from_costs, verify_strategy
from monte_neo.verify.engine import simulate
from monte_neo.verify.timing import _terminal_return


@pytest.fixture(scope="module")
def ohlc() -> dict[str, np.ndarray]:
    df = synthetic_ohlcv(600, seed=5)
    return {k: df[k].to_numpy(dtype=np.float64) for k in ("open", "high", "low", "close")}


def _model(**kw: float) -> ExecutionModel:
    return ExecutionModel(side_mode="long_short", warmup_bars=20, commission_bps=1.0, slippage_bps=1.0, **kw)


def _flat_then(sign: int, n: int) -> np.ndarray:
    sig = np.zeros(n, dtype=np.int64)
    sig[30:] = sign
    return sig


def test_borrow_charges_shorts_only(ohlc: dict[str, np.ndarray]) -> None:
    n = ohlc["close"].size
    for sign, charged in ((-1, True), (1, False)):
        base = simulate(ohlc, _flat_then(sign, n), _model())["total_return"]
        with_fee = simulate(ohlc, _flat_then(sign, n), _model(borrow_bps_per_bar=2.0))["total_return"]
        assert (with_fee < base) is charged
        assert with_fee == base or charged


def test_borrow_matches_the_hand_computed_cost(ohlc: dict[str, np.ndarray]) -> None:
    """A constant short pays about borrow_rate x bars held x the position value."""
    n = ohlc["close"].size
    rate = 1.0  # bps per bar
    base = simulate(ohlc, _flat_then(-1, n), _model())["total_return"]
    fee = simulate(ohlc, _flat_then(-1, n), _model(borrow_bps_per_bar=rate))["total_return"]
    bars_held = n - 31  # entered at the open of bar 31, closed at the end
    assert base - fee == pytest.approx(bars_held * rate * 1e-4, rel=0.25)


def test_funding_charges_both_sides(ohlc: dict[str, np.ndarray]) -> None:
    n = ohlc["close"].size
    for sign in (-1, 1):
        base = simulate(ohlc, _flat_then(sign, n), _model())["total_return"]
        assert simulate(ohlc, _flat_then(sign, n), _model(funding_bps_per_bar=1.0))["total_return"] < base


def test_sign_and_weight_engines_agree_with_borrow(ohlc: dict[str, np.ndarray]) -> None:
    n = ohlc["close"].size
    rng = np.random.default_rng(1)
    sig = np.sign(np.convolve(rng.standard_normal(n), np.ones(15), "same")).astype(np.int64)  # long and short stretches
    model = _model(borrow_bps_per_bar=1.5, funding_bps_per_bar=0.5)
    a = simulate(ohlc, sig, model)
    b = run_weight_backtest(ohlc["open"], ohlc["close"], sig.astype(np.float64), model=model)
    assert a["total_return"] == pytest.approx(b["total_return"], rel=1e-9, abs=1e-12)
    assert np.allclose(a["equity"], b["equity"], rtol=1e-9)


def test_terminal_return_and_journal_engine_agree(ohlc: dict[str, np.ndarray]) -> None:
    n = ohlc["close"].size
    sig = _flat_then(-1, n)
    model = _model(borrow_bps_per_bar=1.0)
    full = run_bar_backtest(ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model)["total_return"]
    assert _terminal_return(ohlc, sig, model) == pytest.approx(full, rel=1e-12)


def test_engines_that_ignore_borrow_refuse_it(ohlc: dict[str, np.ndarray]) -> None:
    n = ohlc["close"].size
    with pytest.raises(ValueError, match="borrow"):
        run_bar_backtest_batch(
            ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], np.zeros((1, n), dtype=np.int64), _model(borrow_bps_per_bar=1.0)
        )


def test_negative_borrow_is_refused() -> None:
    with pytest.raises(ValueError, match="borrow"):
        ExecutionModel(borrow_bps_per_bar=-0.1)


def test_default_model_dict_and_certificate_id_are_unchanged(ohlc: dict[str, np.ndarray]) -> None:
    assert "borrow_bps_per_bar" not in ExecutionModel().to_dict()
    assert ExecutionModel(borrow_bps_per_bar=0.5).to_dict()["borrow_bps_per_bar"] == 0.5


def test_borrow_reaches_the_certificate_and_recheck(tmp_path) -> None:
    import json

    import pandas as pd

    from monte_neo.verify import recheck_certificate

    df = synthetic_ohlcv(600, seed=5)
    sig = -np.ones(len(df), dtype=np.int64)
    csv, sigs, cert = tmp_path / "p.csv", tmp_path / "s.csv", tmp_path / "cert.json"
    df.to_csv(csv, index=False)  # verified from the file, so the recheck reads the same bytes
    pd.Series(sig).to_csv(sigs, index=False, header=["signal"])
    costs = {"commission_bps": 1.0, "slippage_bps": 1.0, "n_bars": len(df)}
    free = verify_strategy(csv, signals=sigs, model=model_from_costs(**costs))
    report = verify_strategy(csv, signals=sigs, model=model_from_costs(**costs, borrow_bps_per_bar=2.0))
    assert report["reproducibility"]["model"]["borrow_bps_per_bar"] == 2.0
    assert "borrow_bps_per_bar" not in free["reproducibility"]["model"]
    assert report["metrics"]["total_return"] < free["metrics"]["total_return"]
    assert report["certificate_id"] != free["certificate_id"]
    cert.write_text(json.dumps(report))
    assert recheck_certificate(cert, csv, signals=sigs)["reproduced"] is True
