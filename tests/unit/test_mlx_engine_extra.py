import importlib
import sys
import unittest
from unittest.mock import MagicMock, patch

import mlx.core as mx
import numpy as np
import pandas as pd

# First import to ensure it's in sys.modules
import monte_neo.core.mlx_engine
from monte_neo.core.mlx_engine import MLXBacktestEngine


class TestMLXEngineExtra(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            "open": np.random.rand(10),
            "high": np.random.rand(10),
            "low": np.random.rand(10),
            "close": np.random.rand(10),
            "volume": np.random.rand(10)
        })
        self.indicator = MagicMock()
        self.indicator.generate_signals_fast.return_value = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 0])
        
    @patch("monte_neo.core.mlx_engine.MetricsCalculator")
    @patch("monte_neo.core.mlx_engine.normalize_signal_array")
    def test_backtest_batch_sl_tp(self, mock_normalize, mock_metrics):
        # Test backtest_batch with use_sl_tp=True
        mock_normalize.return_value = np.array([1]*10)
        mock_metrics.calculate_batch_fast.return_value = np.zeros((1, 4))
        
        engine = MLXBacktestEngine()
        results = engine.backtest_batch(self.data, [self.indicator], use_sl_tp=True)
        
        self.assertEqual(len(results), 1)
        self.assertIn("metrics", results[0])
        mock_metrics.calculate_batch_fast.assert_called_once()

    @patch("monte_neo.core.mlx_engine.run_scenarios_backtest")
    def test_backtest_scenarios(self, mock_run):
        engine = MLXBacktestEngine()
        engine.backtest_scenarios(self.indicator, [self.data])
        mock_run.assert_called_once()

    @patch("monte_neo.core.mlx_engine.run_lazy_backtest")
    def test_backtest_lazy_scenarios(self, mock_run):
        engine = MLXBacktestEngine()
        executor = MagicMock()
        engine.backtest_lazy_scenarios(self.indicator, n_scenarios=5, executor=executor)
        mock_run.assert_called_once()

    @patch("monte_neo.core.mlx_engine.GpuAccelerationEngine")
    def test_run_full_simulation_no_sl_tp(self, mock_gpu_engine_cls):
        # Test run_full_simulation when use_sl_tp is False
        mock_gpu_engine = MagicMock()
        mock_gpu_engine.run_simulation.return_value = [{"metrics": {}}]
        mock_gpu_engine_cls.return_value = mock_gpu_engine
        
        engine = MLXBacktestEngine()
        engine.native_bridge = None # Force fallback to pure_gpu_engine
        results, timing = engine.run_full_simulation(self.data, self.indicator, n_scenarios=1, use_sl_tp=False)
        
        self.assertEqual(len(results), 1)
        mock_gpu_engine.run_simulation.assert_called_once()

    @patch("monte_neo.core.mlx_engine.load_cache")
    @patch("monte_neo.core.mlx_engine.save_cache")
    @patch("monte_neo.core.mlx_engine.MetalBacktestBridge")
    @patch("monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE", True)
    def test_select_best_driver_cached(self, mock_bridge, mock_save, mock_load):
        # Test _select_best_driver with cached result
        mock_load.return_value = "objc"
        
        # We need to manually call _select_best_driver since __init__ might not call it if not "auto"
        engine = MLXBacktestEngine(metal_driver="cpp")
        driver = engine._select_best_driver()
        self.assertEqual(driver, "objc")
        mock_load.assert_called_with("best_metal_driver.json")

    @patch("monte_neo.core.mlx_engine.MetalBacktestBridge")
    @patch("monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE", True)
    def test_init_bridge_fail(self, mock_bridge_cls):
        # Test bridge initialization failure
        mock_bridge = MagicMock()
        mock_bridge.init.return_value = False
        mock_bridge_cls.return_value = mock_bridge
        
        engine = MLXBacktestEngine(metal_driver="cpp")
        self.assertIsNone(engine.native_bridge)

    @patch("monte_neo.core.mlx_engine.Candle")
    @patch("monte_neo.core.mlx_engine.GpuAccelerationEngine")
    def test_run_full_simulation_fallback(self, mock_gpu_engine_cls, mock_candle):
        # Test fallback from native bridge to MLX on exception
        engine = MLXBacktestEngine(metal_driver="cpp")
        mock_bridge = MagicMock()
        mock_bridge.run_backtest.side_effect = Exception("Native failed")
        engine.native_bridge = mock_bridge
        
        self.indicator.get_metal_params.return_value = [1.0]
        
        # It should fall back to pure_gpu_engine since use_sl_tp=False
        mock_gpu_engine = MagicMock()
        mock_gpu_engine.run_simulation.return_value = [{"metrics": {}}]
        engine.pure_gpu_engine = mock_gpu_engine
        
        results, timing = engine.run_full_simulation(self.data, self.indicator, n_scenarios=1, use_sl_tp=False)
        self.assertEqual(len(results), 1)
        mock_gpu_engine.run_simulation.assert_called_once()

    @patch("monte_neo.core.mlx_engine.load_cache")
    @patch("monte_neo.core.mlx_engine.save_cache")
    @patch("monte_neo.core.mlx_engine.MetalBacktestBridge")
    @patch("monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE", True)
    @patch("monte_neo.core.mlx_engine.time.perf_counter")
    def test_select_best_driver_benchmark(self, mock_perf, mock_bridge_cls, mock_save, mock_load):
        # Test _select_best_driver with benchmark
        mock_load.return_value = None
        mock_perf.side_effect = [0, 1, 0, 0.5, 0, 2, 0, 3, 0, 4] # Mock times
        
        mock_bridge = MagicMock()
        mock_bridge.init.return_value = True
        mock_bridge_cls.return_value = mock_bridge
        
        engine = MLXBacktestEngine(metal_driver="auto")
        # Since objc had 0.5s duration (min), it should be selected
        self.assertEqual(engine.metal_driver, "objc")
        mock_save.assert_called_with("best_metal_driver.json", "objc")

    @patch("monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE", False)
    def test_select_best_driver_no_extension(self):
        with patch("monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE", False):
            engine = MLXBacktestEngine(metal_driver="auto")
            self.assertEqual(engine.metal_driver, "cpp")

    @patch("monte_neo.core.acceleration.tensor_ops.TensorOps")
    @patch("monte_neo.core.acceleration.tensor_ops.to_tensor")
    @patch("monte_neo.core.mlx_engine.MetricsCalculator")
    def test_run_full_simulation_noise(self, mock_metrics, mock_to_tensor, mock_tensor_ops):
        # Test noise method in run_full_simulation
        mock_to_tensor.return_value = {"close": mx.array([1.0, 1.1])}
        mock_tensor_ops.generate_noise_scenarios.return_value = mx.array([[1.0, 1.1]])
        
        mock_strategy = MagicMock()
        mock_strategy.generate_signals.return_value = mx.array([[1, 1]])
        self.indicator.to_mlx_representation.return_value = mock_strategy
        
        mock_metrics.calculate_batch_multi_price_fast.return_value = np.zeros((1, 4))
        
        engine = MLXBacktestEngine()
        results, timing = engine.run_full_simulation(self.data, self.indicator, n_scenarios=1, method="noise", use_sl_tp=True)
        
        mock_tensor_ops.generate_noise_scenarios.assert_called_once()
        self.assertEqual(len(results), 1)

    @patch("monte_neo.core.mlx_engine.subprocess.run")
    @patch("monte_neo.core.mlx_engine.os.path.exists")
    def test_compilation_logic_fail(self, mock_exists, mock_run):
        # Test the path where extension is missing and compilation fails
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        
        with patch.dict(sys.modules, {"monte_neo.core.acceleration.cpp_metal.metal_engine": None}):
            with patch("monte_neo.core.mlx_engine.os.path.dirname", return_value="/tmp"):
                importlib.reload(monte_neo.core.mlx_engine)
                self.assertFalse(monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE)

    @patch("monte_neo.core.mlx_engine.subprocess.run")
    @patch("monte_neo.core.mlx_engine.os.path.exists")
    def test_compilation_logic_no_script(self, mock_exists, mock_run):
        # Test the path where compilation script is missing
        mock_exists.return_value = False
        
        with patch.dict(sys.modules, {"monte_neo.core.acceleration.cpp_metal.metal_engine": None}):
            importlib.reload(monte_neo.core.mlx_engine)
            self.assertFalse(monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE)

    @patch("monte_neo.core.mlx_engine.subprocess.run")
    @patch("monte_neo.core.mlx_engine.os.path.exists")
    def test_compilation_logic_exception(self, mock_exists, mock_run):
        # Test the path where compilation script raises exception
        mock_exists.side_effect = Exception("OS Error")
        
        with patch.dict(sys.modules, {"monte_neo.core.acceleration.cpp_metal.metal_engine": None}):
            importlib.reload(monte_neo.core.mlx_engine)
            self.assertFalse(monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE)

    @patch("monte_neo.core.mlx_engine.subprocess.run")
    @patch("monte_neo.core.mlx_engine.os.path.exists")
    def test_compilation_logic_success(self, mock_exists, mock_run):
        # Test the path where extension is missing but compilation succeeds
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock the successful import that happens inside the try block after compilation
        mock_metal = MagicMock()
        with patch.dict(sys.modules, {"monte_neo.core.acceleration.cpp_metal.metal_engine": mock_metal}):
            with patch("monte_neo.core.mlx_engine.os.path.dirname", return_value="/tmp"):
                importlib.reload(monte_neo.core.mlx_engine)
                self.assertTrue(monte_neo.core.mlx_engine.METAL_EXTENSION_AVAILABLE)
