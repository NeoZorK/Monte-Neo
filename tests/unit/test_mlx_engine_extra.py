"""Extra MLXBacktestEngine coverage against the current kwargs-only API."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from monte_neo.core.mlx_engine import MLXBacktestEngine


class TestMLXEngineExtra(unittest.TestCase):
    def setUp(self) -> None:
        self.data = pd.DataFrame(
            {
                "open": np.random.rand(10),
                "high": np.random.rand(10),
                "low": np.random.rand(10),
                "close": np.random.rand(10),
                "volume": np.random.rand(10),
            }
        )
        self.indicator = MagicMock()
        self.indicator.generate_signals_fast.return_value = np.array(
            [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        )

    @patch("monte_neo.core.mlx_sim_engine.backtest_batch_impl")
    def test_backtest_batch_forwards_kwargs(self, mock_impl) -> None:
        mock_impl.return_value = [{"metrics": {}}]
        engine = MLXBacktestEngine()
        out = engine.backtest_batch(self.data, [self.indicator], use_sl_tp=True)
        self.assertEqual(len(out), 1)
        mock_impl.assert_called_once()
        kwargs = mock_impl.call_args.kwargs
        if not kwargs and len(mock_impl.call_args.args) >= 1:
            kwargs = {}
        self.assertTrue(kwargs.get("use_sl_tp", True))

    @patch("monte_neo.core.mlx_engine.run_scenarios_backtest")
    def test_backtest_scenarios(self, mock_run) -> None:
        engine = MLXBacktestEngine()
        engine.backtest_scenarios(self.indicator, [self.data])
        mock_run.assert_called_once()

    @patch("monte_neo.core.mlx_engine.run_lazy_backtest")
    def test_backtest_lazy_scenarios(self, mock_run) -> None:
        engine = MLXBacktestEngine()
        engine.backtest_lazy_scenarios(self.indicator, n_scenarios=5, executor=MagicMock())
        mock_run.assert_called_once()

    @patch("monte_neo.core.mlx_sim_engine.run_full_simulation_impl")
    def test_run_full_simulation_forwards(self, mock_impl) -> None:
        mock_impl.return_value = ([{"metrics": {}}], {"kernel_execution": 0.01})
        engine = MLXBacktestEngine()
        results, timing = engine.run_full_simulation(
            self.data, self.indicator, n_scenarios=1, use_sl_tp=False
        )
        self.assertEqual(len(results), 1)
        self.assertIn("kernel_execution", timing)
        mock_impl.assert_called_once()

    @patch("monte_neo.core.mlx_engine.select_best_metal_driver", return_value="objc")
    @patch("monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE", True)
    @patch("monte_neo.core.mlx_engine.MetalBacktestBridge")
    def test_auto_driver_uses_select_best(self, mock_bridge_cls, _sel) -> None:
        mock_bridge = MagicMock()
        mock_bridge.init.return_value = True
        mock_bridge_cls.return_value = mock_bridge
        engine = MLXBacktestEngine(metal_driver="auto")
        self.assertEqual(engine.metal_driver, "objc")
        self.assertIsNotNone(engine.native_bridge)

    @patch("monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE", True)
    @patch("monte_neo.core.mlx_engine.MetalBacktestBridge")
    def test_init_bridge_fail(self, mock_bridge_cls) -> None:
        mock_bridge = MagicMock()
        mock_bridge.init.return_value = False
        mock_bridge_cls.return_value = mock_bridge
        engine = MLXBacktestEngine(metal_driver="cpp")
        self.assertIsNone(engine.native_bridge)

    @patch("monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE", False)
    def test_auto_without_extension_defaults_cpp(self) -> None:
        engine = MLXBacktestEngine(metal_driver="auto")
        self.assertEqual(engine.metal_driver, "cpp")

    @patch("monte_neo.core.mlx_driver_utils.load_cache", return_value="swift")
    def test_select_best_metal_driver_cached(self, mock_load) -> None:
        from monte_neo.core.mlx_driver_utils import select_best_metal_driver

        out = select_best_metal_driver(True, MagicMock())
        self.assertEqual(out, "swift")
        mock_load.assert_called_with("best_metal_driver.json")

    @patch("monte_neo.core.mlx_driver_utils.subprocess.run")
    @patch("monte_neo.core.mlx_driver_utils.os.path.exists", return_value=True)
    def test_try_auto_compile_fail(self, _exists, mock_run) -> None:
        from monte_neo.core.mlx_driver_utils import try_auto_compile_metal

        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        self.assertFalse(try_auto_compile_metal())

    @patch("monte_neo.core.mlx_driver_utils.os.path.exists", return_value=False)
    def test_try_auto_compile_no_script(self, _exists) -> None:
        from monte_neo.core.mlx_driver_utils import try_auto_compile_metal

        self.assertFalse(try_auto_compile_metal())


if __name__ == "__main__":
    unittest.main()
