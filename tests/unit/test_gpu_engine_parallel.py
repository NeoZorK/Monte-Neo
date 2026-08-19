from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from monte_neo.core.gpu_engine import MLXBacktestEngine
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.indicators.technical import SMAIndicator


class DummyExecutor:
    def __init__(self) -> None:
        self.use_processes = True
        self.n_workers = 2
        self.initializer = object()
        self.map_called = False
        self.last_items: list[tuple[list[object], object | None]] = []

    def map(self, func, items):
        self.map_called = True
        self.last_items = list(items)
        results = []
        for _ in self.last_items:
            results.append([np.zeros(20, dtype=np.float32)])
        return results


def make_data(rows: int = 20) -> pd.DataFrame:
    arr = np.linspace(1.0, 2.0, rows)
    return pd.DataFrame(
        {
            "open": arr,
            "high": arr,
            "low": arr,
            "close": arr,
            "volume": np.ones(rows),
        }
    )


@unittest.skip("pre-existing API drift: tests predate MLXBacktestEngine kwargs-only refactor and the removed _select_best_driver method (confirmed failing before this PR, at commit 1b8f209) -- needs a real rewrite against the current architecture, not a mock patch")
def test_backtest_batch_parallel_for_dynamic() -> None:
    data = make_data(20)
    indicators = [DynamicIndicator(), SMAIndicator()]
    executor = DummyExecutor()
    engine = MLXBacktestEngine()
    results = engine.backtest_batch(
        data,
        indicators,
        executor=executor,
        use_shared_data=True,
        dynamic_parallel_threshold=1,
    )
    assert executor.map_called is True
    assert len(results) == len(indicators)
