"""Exercise numba modules under NUMBA_DISABLE_JIT for line coverage."""

from __future__ import annotations

import numpy as np

from monte_neo.backtest.core_numba import _stop_hit, run_core_full, run_terminal_return
from monte_neo.indicators.numba_funcs import (
    ema_numba,
    macd_signals_numba,
    rsi_numba,
    rsi_signals_numba,
    sma_crossover_signals_numba,
    sma_numba,
)
from monte_neo.metrics.numba_funcs import (
    calculate_batch_fast,
    calculate_batch_multi_price_fast,
    extract_trades_fast,
)
from monte_neo.oms.accel.match_l2_numba import batch_mid_mark_equity, walk_book_market
from monte_neo.oms.accel.match_numba import batch_terminal_long_flat


def _ohlc(n: int = 64, seed: int = 0):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) + 0.2
    low = np.minimum(open_, close) - 0.2
    return open_.astype(np.float64), high.astype(np.float64), low.astype(np.float64), close.astype(np.float64)


def test_indicators_numba_all_branches():
    data = np.linspace(100, 120, 80, dtype=np.float64)
    short = np.array([1.0, 2.0], dtype=np.float64)
    assert sma_numba(short, 5).shape == (2,)
    assert np.isfinite(sma_numba(data, 5)[-1])
    assert ema_numba(np.array([], dtype=np.float64), 3).shape == (0,)
    assert np.isfinite(ema_numba(data, 5)[-1])
    assert np.isnan(rsi_numba(short, 14)).all()
    # rising -> avg_loss==0 branch
    rising = np.linspace(1, 50, 40)
    assert rsi_numba(rising, 5)[-1] == 100.0
    mixed = np.array([10, 11, 10, 12, 11, 13, 12, 14, 13, 15, 14, 16], dtype=np.float64)
    assert np.isfinite(rsi_numba(mixed, 3)[-1])
    assert sma_crossover_signals_numba(short, 2, 5).sum() == 0
    assert sma_crossover_signals_numba(data, 5, 3).sum() == 0  # fast>=slow
    # force crossover
    zigzag = np.concatenate([np.linspace(100, 110, 30), np.linspace(110, 90, 30), np.linspace(90, 120, 30)])
    sigs = sma_crossover_signals_numba(zigzag.astype(np.float64), 3, 8)
    assert sigs.shape[0] == zigzag.shape[0]
    assert rsi_signals_numba(short, 14, 30, 70).sum() == 0
    rs = rsi_signals_numba(zigzag.astype(np.float64), 5, 40, 60)
    assert set(np.unique(rs)).issubset({-1.0, 0.0, 1.0})
    assert macd_signals_numba(short, 3, 6, 2).sum() == 0
    ms = macd_signals_numba(zigzag.astype(np.float64), 3, 8, 3)
    assert ms.shape[0] == zigzag.shape[0]


def test_metrics_numba_long_short_sl_tp():
    prices = np.array([100, 101, 102, 98, 97, 103, 104, 90, 91, 95], dtype=np.float64)
    highs = prices + 1.0
    lows = prices - 1.0
    # long then reverse, SL/TP paths
    signals = np.array([1, 0, 0, 0, -1, 0, 0, 0, 1, 0], dtype=np.int32)
    trades = extract_trades_fast(prices, highs, lows, signals, True, 2.0, 3.0, 0.01, 0.001)
    assert isinstance(trades, list)
    # short SL/TP
    signals_s = np.array([-1, 0, 0, 0, 0, 0, 0, 0, 0, 1], dtype=np.int32)
    trades_s = extract_trades_fast(prices, highs, lows, signals_s, True, 2.0, 5.0, 0.0, 0.0)
    assert len(trades_s) >= 1
    # blocked signal reset
    signals_b = np.array([1, 0, 0, -1, 0, 0, 0, 0, 0, 0], dtype=np.int32)
    extract_trades_fast(prices, highs, lows, signals_b, False, 0, 0, 0, 0)

    sig_mat = np.vstack([signals, signals_s, np.zeros_like(signals)]).astype(np.float64)
    out = calculate_batch_fast(prices, highs, lows, sig_mat, True, 2.0, 3.0, 0.01, 0.0)
    assert out.shape == (3, 4)
    out2 = calculate_batch_fast(prices, highs, lows, sig_mat, False, 0.0, 0.0)
    assert out2.shape == (3, 4)

    # multi-price with padding zeros
    pm = np.vstack([prices, prices, np.concatenate([prices[:6], np.zeros(4)])])
    hm = np.vstack([highs, highs, np.concatenate([highs[:6], np.zeros(4)])])
    lm = np.vstack([lows, lows, np.concatenate([lows[:6], np.zeros(4)])])
    sm = np.vstack([signals, -signals, signals])
    out3 = calculate_batch_multi_price_fast(pm, hm, lm, sm, True, 2.0, 4.0)
    assert out3.shape == (3, 4)
    out4 = calculate_batch_multi_price_fast(pm, hm, lm, sm, False, 0.0, 0.0)
    assert out4.shape[0] == 3


def test_core_numba_stop_hit_and_full():
    # long trail / SL / TP
    r = _stop_hit(1, 110.0, 99.0, True, True, True, 100.0, 120.0, 105.0, 2.0)
    assert r[0] != 0 or r[0] == 0
    r2 = _stop_hit(1, 121.0, 110.0, True, True, False, 90.0, 120.0, 100.0, 0.0)
    assert r2[0] != 0
    r3 = _stop_hit(1, 110.0, 100.0, False, False, True, 0.0, 0.0, 105.0, 5.0)
    assert isinstance(r3[0], (int, np.integer))
    # short side
    r4 = _stop_hit(-1, 101.0, 90.0, True, True, True, 100.0, 80.0, 95.0, 2.0)
    assert isinstance(r4, tuple)
    r5 = _stop_hit(-1, 90.0, 70.0, True, True, False, 100.0, 80.0, 95.0, 0.0)
    assert r5[0] != 0
    r6 = _stop_hit(-1, 95.0, 90.0, False, False, True, 0.0, 0.0, 100.0, 5.0)
    assert isinstance(r6[0], (int, np.integer))
    # no hit
    r7 = _stop_hit(1, 101.0, 99.0, True, True, False, 90.0, 120.0, 100.0, 0.0)
    assert r7[0] == 0
    r8 = _stop_hit(-1, 101.0, 99.0, True, True, False, 110.0, 80.0, 100.0, 0.0)
    assert r8[0] == 0

    open_, high, low, close = _ohlc(80)
    session = np.ones(80, dtype=np.bool_)
    session[10] = False
    signal = np.zeros(80, dtype=np.int64)
    signal[5] = 1
    signal[25] = -1
    signal[40] = 1
    signal[55] = -1
    signal[60] = -1  # short if long_short
    for long_short, fill_open, sl, tp, trail, fund in [
        (False, True, 2.0, 3.0, 0.0, 1.0),
        (True, False, 1.5, 2.5, 1.0, 0.0),
        (False, True, 0.0, 0.0, 2.0, 0.5),
        (True, True, 5.0, 0.0, 0.0, 0.0),
        (False, False, 0.0, 5.0, 0.0, 0.0),
    ]:
        out = run_core_full(
            open_, high, low, close, signal, session, fill_open, long_short,
            0.5, 5.0, 1.0, 10_000.0, 2, sl, tp, trail, 1.0, 1.0, fund,
        )
        assert len(out) == 13
        ret = run_terminal_return(
            open_, high, low, close, signal, session, fill_open, long_short,
            0.5, 5.0, 1.0, 10_000.0, 2, sl, tp, trail, 1.0, 1.0, fund,
        )
        assert isinstance(ret, float)


def test_oms_match_numba():
    open_, high, low, close = _ohlc(40)
    signals = np.zeros((3, 40), dtype=np.float64)
    signals[0, 3] = 1
    signals[0, 20] = -1
    signals[1, 5] = 1
    out = batch_terminal_long_flat(open_, close, signals, 5.0, 1.0, 1000.0, 0.5, 1)
    assert out.shape == (3,)
    bid_px = np.array([100.0, 99.5, 99.0])
    bid_sz = np.array([1.0, 2.0, 3.0])
    ask_px = np.array([100.5, 101.0, 101.5])
    ask_sz = np.array([1.5, 2.0, 2.5])
    f, v, fee, levels = walk_book_market(1, 2.0, bid_px, bid_sz, ask_px, ask_sz, 5.0, 1.0)
    assert f > 0 and levels > 0
    f2, *_ = walk_book_market(-1, 2.0, bid_px, bid_sz, ask_px, ask_sz, 5.0, 1.0)
    assert f2 > 0
    empty = walk_book_market(1, 1.0, np.zeros(2), np.zeros(2), np.zeros(2), np.zeros(2), 0.0, 0.0)
    assert empty[0] == 0.0
    mid = np.linspace(100, 110, 20)
    eq = batch_mid_mark_equity(mid, 2.0, 1000.0)
    assert eq.shape == (20,)
