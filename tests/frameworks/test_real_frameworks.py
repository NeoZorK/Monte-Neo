"""Adapters against real frameworks: the verifier must read the same positions the framework held."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify import (
    from_backtesting_py,
    from_backtrader,
    from_bt,
    from_fills,
    from_nautilus,
    from_vectorbt,
    from_zipline,
)


def mismatches(positions: np.ndarray, held_after_decision: np.ndarray) -> int:
    """Bars where the adapter's position differs from what the framework held after that bar's decision."""
    n = min(len(positions), len(held_after_decision))
    return int(np.sum(np.sign(positions[:n]) != np.sign(held_after_decision[:n])))


VERDICTS = {"PASS", "PASS_WITH_WARNINGS", "NEEDS_MORE_EVIDENCE", "REJECT"}


def _held_by_bar(recorded: list[float], total: int) -> np.ndarray:
    """``recorded[i]`` is the position seen at the start of bar ``total - len + i``; the position decided at
    bar ``t`` is the one seen at the start of bar ``t + 1``. Returns it aligned to decision bars (last bar flat)."""
    seen = np.zeros(total)
    seen[total - len(recorded) :] = recorded
    decided = np.zeros(total)
    decided[:-1] = seen[1:]
    return decided


def test_backtrader(prices: pd.DataFrame) -> None:
    bt = pytest.importorskip("backtrader")

    class Cross(bt.Strategy):
        def __init__(self) -> None:
            self.fast, self.slow = bt.ind.SMA(period=20), bt.ind.SMA(period=80)
            self.held: list[float] = []

        def next(self) -> None:
            self.held.append(self.position.size)
            if self.fast[0] > self.slow[0] and not self.position:
                self.buy(size=1)
            elif self.fast[0] < self.slow[0] and self.position:
                self.close()

    feed = bt.feeds.PandasData(dataname=prices.set_index("timestamp"), openinterest=None)
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(1e12)
    cerebro.adddata(feed)
    cerebro.addstrategy(Cross)
    cerebro.addanalyzer(bt.analyzers.Transactions, _name="tx")
    strat = cerebro.run()[0]
    adapted = from_backtrader(strat.analyzers.tx.get_analysis(), prices)
    truth = _held_by_bar(strat.held, len(prices))
    assert mismatches(adapted.positions[:-1], truth[:-1]) == 0
    assert adapted.positions.any() and adapted.verify()["verdict"] in VERDICTS


def test_backtrader_that_never_trades(prices: pd.DataFrame) -> None:
    pytest.importorskip("backtrader")
    adapted = from_backtrader({}, prices)
    assert not adapted.positions.any() and adapted.verify()["verdict"] in VERDICTS


def test_backtesting_py(prices: pd.DataFrame) -> None:
    pytest.importorskip("backtesting")
    from backtesting import Backtest, Strategy
    from backtesting.lib import crossover

    held: list[float] = []

    def sma(values: object, n: int) -> pd.Series:
        return pd.Series(values).rolling(n).mean()

    class Cross(Strategy):
        def init(self) -> None:
            self.fast = self.I(sma, self.data.Close, 20)
            self.slow = self.I(sma, self.data.Close, 80)

        def next(self) -> None:
            held.append(self.position.size)
            if crossover(self.fast, self.slow):
                self.buy(size=1)
            elif crossover(self.slow, self.fast) and self.position:
                self.position.close()

    data = prices.set_index("timestamp").rename(columns=str.capitalize)[["Open", "High", "Low", "Close", "Volume"]]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stats = Backtest(data, Cross, cash=1e12, commission=0, finalize_trades=True).run()
    adapted = from_backtesting_py(stats, prices)
    truth = _held_by_bar(held, len(prices))
    assert mismatches(adapted.positions[:-2], truth[:-2]) == 0  # the trade closed by finalize_trades ends on the last bar
    assert adapted.positions.any() and adapted.verify()["verdict"] in VERDICTS


def test_bt(prices: pd.DataFrame) -> None:
    bt = pytest.importorskip("bt")
    px = prices.set_index("timestamp")[["close"]].rename(columns={"close": "X"})
    target = (px.rolling(20).mean() > px.rolling(80).mean()).astype(float)
    strategy = bt.Strategy("cross", [bt.algos.SelectAll(), bt.algos.WeighTarget(target), bt.algos.Rebalance()])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = bt.run(bt.Backtest(strategy, px))
    weights = result.get_security_weights()["X"]
    adapted = from_bt(result, prices)
    assert adapted.mode == "weight"
    assert np.allclose(adapted.positions, weights.reindex(pd.DatetimeIndex(prices["timestamp"])).fillna(0.0).to_numpy())
    assert adapted.positions.any() and adapted.verify()["verdict"] in VERDICTS
    with pytest.raises(ValueError):
        from_bt(result, prices, security="nope")


def test_vectorbt(prices: pd.DataFrame) -> None:
    vbt = pytest.importorskip("vectorbt")
    close = pd.Series(prices["close"].to_numpy(), index=pd.DatetimeIndex(prices["timestamp"]), name="X")
    fast, slow = close.rolling(20).mean(), close.rolling(80).mean()
    entries, exits = (fast > slow) & (fast.shift() <= slow.shift()), (fast < slow) & (fast.shift() >= slow.shift())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=1e12, size=1.0, freq="1D")
    adapted = from_vectorbt(pf)
    assert adapted.positions.any() and adapted.verify()["verdict"] in VERDICTS


def _run_nautilus(prices: pd.DataFrame):  # noqa: ANN202
    from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
    from nautilus_trader.indicators import SimpleMovingAverage
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.data import BarType
    from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
    from nautilus_trader.model.identifiers import TraderId, Venue
    from nautilus_trader.model.objects import Money, Quantity
    from nautilus_trader.persistence.wranglers import BarDataWrangler
    from nautilus_trader.test_kit.providers import TestInstrumentProvider
    from nautilus_trader.trading.strategy import Strategy, StrategyConfig

    instrument = TestInstrumentProvider.equity(symbol="AAA", venue="XNAS")
    bar_type = BarType.from_str(f"{instrument.id}-1-DAY-LAST-EXTERNAL")
    held: list[float] = []

    class Cfg(StrategyConfig, frozen=True):
        pass

    class Cross(Strategy):
        def __init__(self) -> None:
            super().__init__(Cfg())
            self.fast, self.slow = SimpleMovingAverage(20), SimpleMovingAverage(80)

        def on_start(self) -> None:
            self.register_indicator_for_bars(bar_type, self.fast)
            self.register_indicator_for_bars(bar_type, self.slow)
            self.subscribe_bars(bar_type)

        def on_bar(self, bar: object) -> None:
            net = float(self.portfolio.net_position(instrument.id))
            held.append(net)
            if not (self.fast.initialized and self.slow.initialized):
                return
            if self.fast.value > self.slow.value and net == 0:
                self.submit_order(self.order_factory.market(instrument.id, OrderSide.BUY, Quantity.from_int(1)))
            elif self.fast.value < self.slow.value and net > 0:
                self.submit_order(self.order_factory.market(instrument.id, OrderSide.SELL, Quantity.from_int(1)))

    frame = pd.DataFrame(
        {k: np.array(prices[k].to_numpy(), dtype=np.float64) for k in ("open", "high", "low", "close", "volume")},
        index=pd.date_range("2020-01-01", periods=len(prices), freq="D", tz="UTC"),
    ).copy(deep=True)
    engine = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId("T-001")))
    engine.add_venue(
        venue=Venue("XNAS"), oms_type=OmsType.NETTING, account_type=AccountType.CASH,
        base_currency=USD, starting_balances=[Money(1_000_000_000_000, USD)],
    )
    engine.add_instrument(instrument)
    engine.add_data(BarDataWrangler(bar_type, instrument).process(frame))
    engine.add_strategy(Cross())
    engine.run()
    return engine, held


def test_nautilus(prices: pd.DataFrame) -> None:
    pytest.importorskip("nautilus_trader")
    try:
        engine, held = _run_nautilus(prices)
    except ValueError as exc:  # the Nautilus data wrangler needs pandas < 3
        pytest.skip(f"Nautilus could not load the bars: {exc}")
    truth = _held_by_bar(held, len(prices))
    adapted = from_nautilus(engine, prices)
    assert mismatches(adapted.positions[:-1], truth[:-1]) == 0
    # Reading the same fills as open fills puts every position one bar too early: the verifier would see the future.
    report = engine.trader.generate_order_fills_report()
    early = from_nautilus(report, prices, fill_at="open")
    assert mismatches(early.positions[:-1], truth[:-1]) > 0
    assert adapted.positions.any() and adapted.verify()["verdict"] in VERDICTS
    engine.dispose()


def test_from_fills_close_fills_are_read_at_their_own_bar() -> None:
    prices = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=6, freq="D"),
            "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0,
        }
    )
    fills = [{"timestamp": "2024-01-03", "quantity": 1.0}, {"timestamp": "2024-01-05", "quantity": -1.0}]
    assert list(from_fills(fills, prices, fill_at="open").positions) == [0, 1, 1, 0, 0, 0]
    assert list(from_fills(fills, prices, fill_at="close").positions) == [0, 0, 1, 1, 0, 0]
    with pytest.raises(ValueError):
        from_fills(fills, prices, fill_at="middle")
    assert not from_fills([], prices).positions.any()


def test_zipline(prices: pd.DataFrame, tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("zipline")
    monkeypatch.setenv("ZIPLINE_ROOT", str(tmp_path))
    from zipline import run_algorithm
    from zipline.api import order_target, symbol
    from zipline.data.bundles import ingest, register
    from zipline.utils.calendar_utils import get_calendar

    calendar = get_calendar("XNYS")
    sessions = calendar.sessions_in_range(pd.Timestamp("2020-01-02"), pd.Timestamp("2026-12-31"))[: len(prices)]
    table = prices.copy()
    table["timestamp"] = sessions.tz_localize(None)
    bars = table.set_index("timestamp")[["open", "high", "low", "close", "volume"]]

    def ingest_fn(environ, asset_db_writer, minute_bar_writer, daily_bar_writer, adjustment_writer, calendar, start_session, end_session, cache, show_progress, output_dir):  # noqa: ANN001, E501
        daily_bar_writer.write([(0, bars)], show_progress=False)
        asset_db_writer.write(
            pd.DataFrame(
                {
                    "start_date": [bars.index[0]], "end_date": [bars.index[-1]],
                    "auto_close_date": [bars.index[-1] + pd.Timedelta(days=1)], "symbol": ["AAA"], "exchange": ["NYSE"],
                }
            )
        )
        adjustment_writer.write()

    register("synthetic", ingest_fn, calendar_name="XNYS")
    ingest("synthetic", show_progress=False)
    closes: list[float] = []
    held: list[float] = []

    def initialize(context) -> None:  # noqa: ANN001
        context.asset = symbol("AAA")

    def handle_data(context, data) -> None:  # noqa: ANN001
        closes.append(float(data.current(context.asset, "close")))
        held.append(context.portfolio.positions[context.asset].amount if context.asset in context.portfolio.positions else 0)
        if len(closes) < 80:
            return
        recent = np.array(closes[-80:])
        order_target(context.asset, 1 if recent[-20:].mean() > recent.mean() else 0)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        perf = run_algorithm(
            start=sessions[0], end=sessions[-1], initialize=initialize, handle_data=handle_data,
            capital_base=1e12, bundle="synthetic", trading_calendar=calendar, data_frequency="daily",
        )
    transactions = [t for day in perf["transactions"] for t in day]
    adapted = from_zipline(transactions, table)
    truth = _held_by_bar(held, len(table))
    assert mismatches(adapted.positions[:-1], truth[:-1]) == 0
    assert adapted.positions.any() and adapted.verify()["verdict"] in VERDICTS
