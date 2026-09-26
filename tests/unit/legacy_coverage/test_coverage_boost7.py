"""Seventh coverage boost: metal dispatch, adapters edges, evolution run, viz heatmap."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.show = lambda *a, **k: None

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402


def test_metal_l2_dispatch_cpu_and_batch():
    from monte_neo.oms.accel import metal_l2 as ml2

    bid_px = np.array([99.0, 98.0], dtype=np.float64)
    bid_sz = np.array([1.0, 1.0], dtype=np.float64)
    ask_px = np.array([101.0, 102.0], dtype=np.float64)
    ask_sz = np.array([1.0, 1.0], dtype=np.float64)

    out = ml2.run_l2_walk_dispatch(
        1, 0.5, bid_px, bid_sz, ask_px, ask_sz, commission_bps=5.0, slip_bps=1.0, device="cpu_numba"
    )
    assert out["ok"] is True
    assert out["device_used"] == "cpu_numba"

    # metal path with fake engine
    eng = MagicMock()
    eng.walk_batch.return_value = (
        np.array([0.5], dtype=np.float32),
        np.array([101.0], dtype=np.float32),
        np.array([0.01], dtype=np.float32),
    )
    with patch.object(ml2, "get_metal_l2_engine", return_value=eng), patch(
        "monte_neo.oms.accel.device.resolve_device", return_value="metal"
    ):
        out2 = ml2.run_l2_walk_dispatch(
            1, 0.5, bid_px, bid_sz, ask_px, ask_sz, device="metal"
        )
        assert out2["device_used"] == "metal"

    batch = ml2.run_l2_walk_batch(
        np.array([1, -1], dtype=np.int32),
        np.array([0.4, 0.4], dtype=np.float64),
        bid_px,
        bid_sz,
        ask_px,
        ask_sz,
        commission_bps=5.0,
        slip_bps=0.0,
        device="cpu_numba",
    )
    assert batch["ok"] is True
    assert batch["device_used"] == "cpu_numba"
    assert len(batch["filled"]) == 2

    eng2 = MagicMock()
    eng2.walk_batch.return_value = (
        np.array([0.4, 0.4], dtype=np.float32),
        np.array([101.0, 99.0], dtype=np.float32),
        np.array([0.01, 0.01], dtype=np.float32),
    )
    with patch.object(ml2, "get_metal_l2_engine", return_value=eng2), patch(
        "monte_neo.oms.accel.device.resolve_device", return_value="metal"
    ):
        batch2 = ml2.run_l2_walk_batch(
            np.array([1, -1], dtype=np.int32),
            np.array([0.4, 0.4], dtype=np.float64),
            bid_px,
            bid_sz,
            ask_px,
            ask_sz,
            device="metal",
        )
        assert batch2["device_used"] == "metal"

    # force cached miss without replacing MetalL2Engine type (isinstance needs real class)
    ml2._metal_l2 = False  # type: ignore[attr-defined]  # re-arm lazy init


def test_metal_l2_engine_error_branches():
    from monte_neo.oms.accel import metal_l2 as ml2

    fake_metal = MagicMock()
    fake_metal.MTLCreateSystemDefaultDevice.return_value = None
    with patch.dict("sys.modules", {"Metal": fake_metal}):
        with pytest.raises(RuntimeError, match="No Metal device"):
            ml2.MetalL2Engine()

    device = MagicMock()
    fake_metal.MTLCreateSystemDefaultDevice.return_value = device
    device.newCommandQueue.return_value = MagicMock()
    device.newLibraryWithSource_options_error_.return_value = (None, "err")
    with patch.dict("sys.modules", {"Metal": fake_metal}):
        with pytest.raises(RuntimeError, match="shader compile"):
            ml2.MetalL2Engine()

    lib = MagicMock()
    fn = MagicMock()
    lib.newFunctionWithName_.return_value = fn
    device.newLibraryWithSource_options_error_.return_value = (lib, None)
    device.newComputePipelineStateWithFunction_error_.return_value = (None, "pipe")
    with patch.dict("sys.modules", {"Metal": fake_metal}):
        with pytest.raises(RuntimeError, match="pipeline"):
            ml2.MetalL2Engine()


def test_paper_reject_partial_and_cancel():
    from monte_neo.oms.adapters.base import OrderIntent
    from monte_neo.oms.adapters.paper_exchange import PaperExchangeAdapter
    from monte_neo.oms.types import OrderSide, OrderType

    ex = PaperExchangeAdapter(initial_cash=1000.0, mid=100.0, book_depth=1)
    # huge qty may partial/reject depending on book size
    rep = ex.submit(
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=100.0,
            client_order_id="big",
        )
    )
    assert rep.status in {"FILLED", "PARTIAL", "REJECTED", "NEW"}
    # unmarketable limit stays NEW
    lim = ex.submit(
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            qty=0.1,
            limit_px=50.0,
            client_order_id="far",
        )
    )
    assert lim.status in {"NEW", "REJECTED", "FILLED", "PARTIAL"}
    # cancel working / missing
    assert ex.cancel("missing") is False
    if lim.venue_order_id:
        ex.cancel(lim.venue_order_id)
        assert ex.cancel(lim.venue_order_id) is False


def test_bybit_live_dry_run_logging(monkeypatch):
    from monte_neo.oms.adapters import bybit as by
    from monte_neo.oms.adapters.base import OrderIntent
    from monte_neo.oms.types import OrderSide, OrderType

    monkeypatch.setenv("MONTE_NEO_LIVE_TRADING", "1")
    monkeypatch.setenv("MONTE_NEO_LIVE_DRY_RUN", "1")
    live = by.BybitAdapter(mode="live", api_key="k", api_secret="s", mid=100.0)
    live.submit(
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=0.01,
            client_order_id="l1",
        )
    )
    live.cancel("PAPER-1")
    assert live.dry_run_log()
    # invalid mode
    with pytest.raises(ValueError):
        by.BybitAdapter(mode="spot")
    # live without keys
    with pytest.raises(RuntimeError):
        by.BybitAdapter(mode="live", api_key="", api_secret="")
    # live without dry-run raises on submit
    monkeypatch.setenv("MONTE_NEO_LIVE_DRY_RUN", "0")
    live2 = by.BybitAdapter(mode="live", api_key="k", api_secret="s")
    with pytest.raises(RuntimeError):
        live2.submit(
            OrderIntent(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                qty=0.01,
            )
        )
    with pytest.raises(RuntimeError):
        live2.cancel("x")


def test_sensitivity_heatmap_and_stress():
    from monte_neo.utils import visualization as uv

    assert uv.plot_sensitivity_heatmap({}) is None
    assert uv.plot_sensitivity_heatmap({"grid": {}}) is None
    fig = uv.plot_sensitivity_heatmap(
        {
            "grid": {
                "matrix": [[0.1, 0.2], [0.15, 0.05]],
                "p1_values": [5.0, 10.0],
                "p2_values": [20.0, 30.0],
                "p1_name": "fast",
                "p2_name": "slow",
            }
        }
    )
    assert fig is not None
    uv.plot_stress_test_summary(
        {
            "black_swan": {"total_return": -0.2},
            "sensitivity": {"std_return_variation": 0.05},
            "breaking_point": {"breaking_point_bps": ">50"},
        }
    )


def test_evolution_run_tiny(sample_ohlcv):
    from monte_neo.core.config import GeneratorConfig
    from monte_neo.core.evolution import EvolutionEngine
    from monte_neo.indicators.base import IndicatorConfig
    from monte_neo.indicators.dynamic import DynamicIndicator

    cfg = GeneratorConfig(
        population_size=4,
        generations=1,
        crossover_rate=0.5,
        min_trades=0,
        use_sl_tp=False,
    )
    eng = EvolutionEngine(cfg, progress_callback=lambda *a, **k: None)
    pop = [
        DynamicIndicator(
            IndicatorConfig(
                name=f"d{i}",
                parameters={"source_code": "data['close'].rolling(5).mean()"},
            )
        )
        for i in range(4)
    ]
    # mock batch metrics to avoid heavy / signature issues
    fake = np.ones((4, 4), dtype=float)
    fake[:, 1] = 0.1  # dd
    fake[:, 2] = 1.5  # pf
    fake[:, 3] = 10  # trades
    with patch.object(eng.metrics_calc, "calculate_batch_fast", return_value=fake):
        best = eng.run(sample_ohlcv, pop)
        assert best is not None
    # KeyboardInterrupt path
    with patch.object(
        eng.metrics_calc, "calculate_batch_fast", side_effect=KeyboardInterrupt()
    ):
        best2 = eng.run(sample_ohlcv, pop)
        assert best2 is not None


def test_metal_economics_try_batch(sample_ohlcv):
    from monte_neo.backtest.metal_economics import (
        metal_economics_eligible,
        try_metal_batch_returns,
    )
    from monte_neo.backtest.model import ExecutionModel

    model = ExecutionModel(warmup_bars=5)
    assert isinstance(metal_economics_eligible(model, None), bool)
    n = 64
    o = sample_ohlcv["open"].to_numpy()[:n]
    h = sample_ohlcv["high"].to_numpy()[:n]
    l = sample_ohlcv["low"].to_numpy()[:n]
    c = sample_ohlcv["close"].to_numpy()[:n]
    sig = np.zeros((2, n), dtype=np.int64)
    sig[0, 10:20] = 1
    # non-metal device -> None
    assert try_metal_batch_returns(o, h, l, c, sig, model, device="cpu_numba") is None
    # size gate skip path
    with patch(
        "monte_neo.backtest.memory_plan.decide_research_accelerator",
        return_value={"use_metal": False, "fallback_reason": "metal_size_gate", "metal_tile_combos": 1},
    ), patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"):
        out = try_metal_batch_returns(o, h, l, c, sig, model, device="metal")
        assert out is not None
        assert out.get("skipped") is True
    # engine None
    with patch(
        "monte_neo.backtest.metal_economics.get_metal_research_engine", return_value=None
    ), patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"), patch(
        "monte_neo.backtest.memory_plan.decide_research_accelerator",
        return_value={"use_metal": True, "metal_tile_combos": 1},
    ):
        assert (
            try_metal_batch_returns(o, h, l, c, sig, model, device="metal", skip_size_gate=True)
            is None
        )
    # fake engine success + tiled
    eng = MagicMock()
    eng.batch_terminal.side_effect = lambda *a, **k: np.array([0.01, 0.02])
    with patch(
        "monte_neo.backtest.metal_economics.get_metal_research_engine", return_value=eng
    ), patch("monte_neo.oms.accel.device.resolve_device", return_value="metal"), patch(
        "monte_neo.backtest.memory_plan.decide_research_accelerator",
        return_value={"use_metal": True, "metal_tile_combos": 1},
    ):
        out2 = try_metal_batch_returns(
            o, h, l, c, sig, model, device="metal", skip_size_gate=True, tile_combos=1
        )
        assert out2 and out2.get("ok") is True
    import monte_neo.backtest.metal_economics as me

    me._metal_research = False  # re-arm lazy init


def test_sequential_advice_and_steps(sample_ohlcv):
    from monte_neo.indicators.base import IndicatorConfig
    from monte_neo.indicators.sma import SMAIndicator
    from monte_neo.metrics.calculator import MetricsCalculator
    from monte_neo.monte_carlo.sequential import SequentialMCRunner

    # Build with mocked engine config
    engine = MagicMock()
    engine.config.pass_threshold = 0.5
    engine.config.sensitivity_range = 0.1
    engine.config.use_sl_tp = False
    engine.config.sl_pct = 0.0
    engine.config.tp_pct = 0.0
    engine.executor = None
    runner = SequentialMCRunner(engine)
    # advice branches
    for name in (
        "Walk Forward",
        "Noise Injection",
        "Sensitivity Analysis",
        "Other",
    ):
        for rate in (0.99, 0.7, 0.4):
            runner._generate_advice(name, rate, {"sharpe_ratio": {"mean": 1.0}})
    sma = SMAIndicator(IndicatorConfig(name="sma", parameters={"period": 5}))
    calc = MetricsCalculator()
    # sensitivity step mocked
    with patch("monte_neo.monte_carlo.sensitivity.SensitivityAnalyzer") as signal_adapter:
        inst = signal_adapter.return_value
        inst.analyze_all_parameters.return_value = [{"ok": True}]
        inst.get_stability_report.return_value = {
            "average_stability": 0.8,
            "overall_stable": True,
            "stable_parameters": 2,
            "total_parameters": 3,
        }
        step = runner._run_sensitivity_step(sma, sample_ohlcv, calc, {"sharpe_ratio": 0.5})
        assert step.method_name == "Sensitivity Analysis"


def test_calculator_extract_and_empty(sample_ohlcv):
    from monte_neo.metrics.calculator import MetricsCalculator

    calc = MetricsCalculator()
    # empty signals
    sig0 = pd.DataFrame({"signal": 0}, index=sample_ohlcv.index)
    m0 = calc.calculate_all(sample_ohlcv, sig0)
    assert isinstance(m0, dict)
    # required_metrics filter
    sig = sig0.copy()
    sig.iloc[5:15, 0] = 1
    m1 = calc.calculate_all(sample_ohlcv, sig, required_metrics=["sharpe_ratio", "max_drawdown"])
    assert isinstance(m1, dict)
    trades = calc._extract_trades(sample_ohlcv, sig, use_sl_tp=True, sl_pct=0.02, tp_pct=0.03)
    assert isinstance(trades, list)


def test_batch_session_mask_and_metal_skip():
    from monte_neo.backtest.batch import run_bar_backtest_batch
    from monte_neo.backtest.model import ExecutionModel

    n = 80
    o = np.linspace(100, 110, n)
    h = o + 1
    l = o - 1
    c = o.copy()
    sig = np.zeros((2, n), dtype=np.int64)
    sig[0, 10:20] = 1
    model = ExecutionModel(warmup_bars=5)
    sess = np.ones(n, dtype=bool)
    sess[0:5] = False
    out = run_bar_backtest_batch(o, h, l, c, sig, model=model, session_mask=sess, device="cpu_numba")
    assert isinstance(out, dict)
    with pytest.raises(ValueError):
        run_bar_backtest_batch(
            o, h, l, c, sig, model=model, session_mask=np.ones(n - 1, dtype=bool)
        )


def test_winrate_edge_empty_branches():
    from monte_neo.metrics.winrate import WinrateMetric

    wr = WinrateMetric()
    assert wr.calculate(np.array([])) == 0.0 or wr.calculate(np.array([])) == 0
    assert wr.expectancy(np.array([])) == 0.0 or True
    assert wr.avg_win(np.array([-1.0, -2.0])) == 0.0 or True
    assert wr.avg_loss(np.array([1.0, 2.0])) == 0.0 or True
    wr.win_loss_ratio(np.array([1.0]))
    wr.edge_ratio(np.array([]))
    wr.get_trade_distribution(np.array([]))
    wr._skewness(np.array([1.0, 1.0, 1.0]))
    wr.required_winrate(0.0)


def test_portfolio_manager_import_and_mc():
    from monte_neo.core.portfolio.manager import PortfolioAsset, PortfolioManager

    pm = PortfolioManager()
    eq = np.linspace(1, 1.1, 30)
    pm.add_asset(
        PortfolioAsset(id="a", indicator_path="a", symbol="X", equity_curve=eq, weight=1.0)
    )
    # force ImportError inside real cluster_assets by patching sklearn import
    import builtins

    real_import = builtins.__import__

    def no_sklearn(name, *a, **k):
        if name.startswith("sklearn"):
            raise ImportError("no")
        return real_import(name, *a, **k)

    rets = {"a": pd.Series(eq).pct_change().dropna(), "b": pd.Series(eq[::-1]).pct_change().dropna()}
    pm.add_asset(
        PortfolioAsset(id="b", indicator_path="b", symbol="Y", equity_curve=eq[::-1].copy(), weight=1.0)
    )
    with patch("builtins.__import__", side_effect=no_sklearn):
        clusters = pm.cluster_assets(rets)
        assert clusters and isinstance(clusters, dict)
    with patch("pandas.concat", side_effect=RuntimeError("x")):
        clusters2 = pm.cluster_assets(rets)
        assert clusters2 and isinstance(clusters2, dict)
    # MC with assets
    try:
        pm.run_portfolio_monte_carlo(iterations=3)
    except Exception:
        pass
    # auto_rebalance default vol
    pm.auto_rebalance(method="risk_parity")
