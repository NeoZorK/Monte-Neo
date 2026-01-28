import unittest
from unittest.mock import MagicMock, patch

import mlx.core as mx
import numpy as np
import pandas as pd

from monte_neo.core.acceleration.engine import GpuAccelerationEngine
from monte_neo.core.acceleration.indicators import MLXSMA, MLXCrossStrategy


class TestGpuAccelerationEngine(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1100, 1200]
        })
        self.strategy_dict = {"type": "sma_crossover", "period": 2}
        self.engine = GpuAccelerationEngine(batch_size=10)

    def test_init_defaults(self):
        engine = GpuAccelerationEngine()
        self.assertEqual(engine.batch_size, 50000)
        self.assertEqual(engine.precision, "float32")
        self.assertEqual(engine.metal_driver, "cpp")
        self.assertEqual(engine.initial_capital, 100000.0)
        self.assertEqual(engine.leverage, 1.0)
        self.assertIsNone(engine.float8_encoder)
        self.assertIsNone(engine.metal_engine)

    @patch("monte_neo.core.native.metal_engine.MetalFloat8Engine")
    def test_init_float8_e4m3_success(self, mock_metal):
        engine = GpuAccelerationEngine(precision="float8_e4m3")
        self.assertIsNotNone(engine.metal_engine)
        self.assertIsNone(engine.float8_encoder)

    @patch("monte_neo.core.native.metal_engine.MetalFloat8Engine", side_effect=ImportError)
    def test_init_float8_e4m3_fallback(self, mock_metal):
        engine = GpuAccelerationEngine(precision="float8_e4m3")
        self.assertIsNone(engine.metal_engine)
        self.assertIsNotNone(engine.float8_encoder)
        self.assertEqual(engine.float8_encoder.format_type, "e4m3")

    def test_reconstruct_strategy(self):
        # Case 1: Dict
        strat = self.engine._reconstruct_strategy(self.strategy_dict)
        self.assertIsInstance(strat, MLXCrossStrategy)
        self.assertIsInstance(strat.indicator, MLXSMA)
        self.assertEqual(strat.indicator.period, 2)

        # Case 2: Already a strategy
        original_strat = MLXCrossStrategy(MLXSMA(5))
        reconstructed = self.engine._reconstruct_strategy(original_strat)
        self.assertEqual(reconstructed, original_strat)

        # Case 3: Unknown dict type
        unknown_strat = {"type": "unknown"}
        reconstructed = self.engine._reconstruct_strategy(unknown_strat)
        self.assertEqual(reconstructed, unknown_strat)

    @patch("monte_neo.core.acceleration.engine.to_tensor")
    @patch("monte_neo.core.acceleration.engine.generate_shuffle_scenarios")
    def test_run_simulation_unknown_method(self, mock_shuffle, mock_to_tensor):
        mock_to_tensor.return_value = {"close": mx.array([100.5, 101.5, 102.5])}
        mock_shuffle.return_value = mx.array([[100.0, 101.0, 102.0]])
        
        mock_strat = MagicMock()
        mock_strat.generate_signals.return_value = mx.array([[1, 1, 1]])

        # Passing an unknown method should fallback to shuffling
        results = self.engine.run_simulation(self.data, mock_strat, n_scenarios=1, method="unknown")
        self.assertEqual(len(results), 1)
        mock_shuffle.assert_called_once()

    @patch("monte_neo.core.acceleration.engine.to_tensor")
    @patch("monte_neo.core.acceleration.engine.generate_shuffle_scenarios")
    def test_run_simulation_shuffling(self, mock_shuffle, mock_to_tensor):
        # Setup
        mock_to_tensor.return_value = {"close": mx.array([100.5, 101.5, 102.5])}
        # 2 scenarios, 3 time steps
        mock_shuffle.return_value = mx.array([
            [100.0, 101.0, 102.0],
            [100.0, 99.0, 98.0]
        ])
        
        mock_strat = MagicMock()
        # Signals must be (N, T) -> (2, 3)
        mock_strat.generate_signals.return_value = mx.array([
            [1, 1, 1],
            [1, 1, 1]
        ])

        results = self.engine.run_simulation(self.data, mock_strat, n_scenarios=2, method="shuffling")

        self.assertEqual(len(results), 2)
        self.assertIn("total_return", results[0])
        self.assertIn("final_balance", results[0])
        self.assertIn("max_drawdown", results[0])
        self.assertIn("profit_factor", results[0])
        
        mock_shuffle.assert_called_once()
        mock_strat.generate_signals.assert_called_once()

    @patch("monte_neo.core.acceleration.engine.to_tensor")
    @patch("monte_neo.core.acceleration.engine.generate_noise_scenarios")
    def test_run_simulation_noise(self, mock_noise, mock_to_tensor):
        mock_to_tensor.return_value = {"close": mx.array([100.5, 101.5, 102.5])}
        mock_noise.return_value = mx.array([[100.0, 101.0, 102.0]])
        
        mock_strat = MagicMock()
        mock_strat.generate_signals.return_value = mx.array([[1, 1, 1]])

        results = self.engine.run_simulation(self.data, mock_strat, n_scenarios=1, method="noise")
        self.assertEqual(len(results), 1)
        mock_noise.assert_called_once()

    @patch("monte_neo.core.acceleration.engine.to_tensor")
    @patch("monte_neo.core.acceleration.engine.generate_shuffle_scenarios")
    def test_run_simulation_batching(self, mock_shuffle, mock_to_tensor):
        # Test that it loops correctly when n_scenarios > batch_size
        self.engine.batch_size = 1
        mock_to_tensor.return_value = {"close": mx.array([100.0, 101.0])}
        mock_shuffle.return_value = mx.array([[100.0, 101.0]])
        
        mock_strat = MagicMock()
        mock_strat.generate_signals.return_value = mx.array([[1, 1]])

        results = self.engine.run_simulation(self.data, mock_strat, n_scenarios=2)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(mock_shuffle.call_count, 2)

    @patch("monte_neo.core.acceleration.engine.to_tensor")
    def test_run_simulation_float8_e4m3_metal(self, mock_to_tensor):
        with patch("monte_neo.core.native.metal_engine.MetalFloat8Engine") as mock_metal_class:
            mock_metal = mock_metal_class.return_value
            engine = GpuAccelerationEngine(precision="float8_e4m3")
            
            mock_to_tensor.return_value = {"close": mx.array([100.0, 101.0])}
            mock_metal.encode_float32_to_e4m3.return_value = b"encoded"
            mock_metal.generate_scenarios_e4m3.return_value = b"scenarios"
            mock_metal.decode_e4m3_to_float32.return_value = np.array([[100.0, 101.0]], dtype=np.float32)
            
            mock_strat = MagicMock()
            mock_strat.generate_signals.return_value = mx.array([[1, 1]])
            
            results = engine.run_simulation(self.data, mock_strat, n_scenarios=1)
            
            self.assertEqual(len(results), 1)
            mock_metal.encode_float32_to_e4m3.assert_called_once()
            mock_metal.generate_scenarios_e4m3.assert_called_once()
            mock_metal.decode_e4m3_to_float32.assert_called_once()

    @patch("monte_neo.core.acceleration.engine.to_tensor")
    @patch("monte_neo.core.acceleration.engine.generate_shuffle_scenarios")
    def test_run_simulation_float8_e5m2_fallback(self, mock_shuffle, mock_to_tensor):
        with patch("monte_neo.core.native.metal_engine.MetalFloat8Engine") as mock_metal_class:
            # We want it to be initialized but for e5m2 it should fallback to MLX as per code comments
            engine = GpuAccelerationEngine(precision="float8_e5m2")
            
            mock_to_tensor.return_value = {"close": mx.array([100.0, 101.0])}
            mock_shuffle.return_value = mx.array([[100.0, 101.0]])
            
            mock_strat = MagicMock()
            mock_strat.generate_signals.return_value = mx.array([[1, 1]])
            
            results = engine.run_simulation(self.data, mock_strat, n_scenarios=1)
            
            self.assertEqual(len(results), 1)
            mock_shuffle.assert_called_once()

    @patch("monte_neo.core.acceleration.engine.to_tensor")
    @patch("monte_neo.core.acceleration.engine.generate_shuffle_scenarios")
    def test_run_benchmark_simulation(self, mock_shuffle, mock_to_tensor):
        mock_to_tensor.return_value = {"close": mx.array([100.0, 101.0])}
        mock_shuffle.return_value = mx.array([[100.0, 101.0]])
        
        # Test with 2 scenarios and batch size 1 to check looping
        self.engine.batch_size = 1
        result = self.engine.run_benchmark_simulation(self.data, n_scenarios=2)
        
        self.assertIn("elapsed", result)
        self.assertIn("ops_per_sec", result)
        self.assertEqual(result["scenarios_processed"], 2)
        self.assertEqual(mock_shuffle.call_count, 2)

if __name__ == "__main__":
    unittest.main()
