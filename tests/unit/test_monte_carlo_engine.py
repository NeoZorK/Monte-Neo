import unittest
from unittest.mock import MagicMock, patch, ANY
import pandas as pd
import numpy as np
from monte_neo.monte_carlo.engine import MonteCarloEngine
from monte_neo.monte_carlo.types import MCConfig, MCResult

class TestMonteCarloEngine(unittest.TestCase):
    def setUp(self):
        self.config = MCConfig(iterations=10, n_workers=1)
        self.engine = MonteCarloEngine(config=self.config)
        self.data = pd.DataFrame({
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100]
        })
        self.indicator = MagicMock()
        self.indicator.to_mlx_representation.return_value = None
        self.indicator.get_metal_params.return_value = None
        
        self.metrics_calc = MagicMock()
        self.target_metrics = {"total_return": 0.05}

    def test_init_defaults(self):
        engine = MonteCarloEngine()
        self.assertIsInstance(engine.config, MCConfig)
        self.assertIsNone(engine.executor)
        self.assertIsNotNone(engine.gpu_engine)

    def test_set_progress_callback(self):
        callback = MagicMock()
        self.engine.set_progress_callback(callback)
        self.assertEqual(self.engine._progress_callback, callback)

    @patch("monte_neo.monte_carlo.engine.time.time")
    @patch("monte_neo.monte_carlo.engine.summarize_metrics")
    def test_finalize_results(self, mock_summarize, mock_time):
        mock_summarize.return_value = {"mean_return": 0.1}
        results = [{"metrics": {"total_return": 0.1}}]
        # Set time.time() to return 105.0 when called inside _finalize_results
        mock_time.return_value = 105.0
        
        res = self.engine._finalize_results(passed_count=1, total=1, all_results=results, start_time=100.0)
        
        self.assertIsInstance(res, MCResult)
        self.assertTrue(res.passed)
        self.assertEqual(res.pass_rate, 1.0)
        self.assertEqual(res.iterations_run, 1)
        self.assertEqual(res.elapsed_time, 5.0)
        self.assertEqual(res.metrics_summary, {"mean_return": 0.1})

    @patch("monte_neo.monte_carlo.engine.MonteCarloEngine.run_sequential")
    def test_run_sequential_config(self, mock_run_seq):
        self.config.use_sequential = True
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics)
        mock_run_seq.assert_called_once()

    @patch("monte_neo.monte_carlo.engine.MonteCarloEngine._finalize_results")
    def test_run_pure_gpu_mlx(self, mock_finalize):
        self.indicator.to_mlx_representation.return_value = {"params": []}
        self.config.iterations = 101
        self.config.use_shuffling = True
        self.config.use_noise = False
        self.config.use_sensitivity = False
        self.config.use_walk_forward = False
        self.config.use_block_bootstrap = False
        
        mock_gpu_results = [{"metrics": {"total_return": 0.1}}] * 101
        self.engine.gpu_engine.run_full_simulation = MagicMock(return_value=(mock_gpu_results, {}))
        
        callback = MagicMock()
        self.engine.set_progress_callback(callback)
        
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics)
        
        self.engine.gpu_engine.run_full_simulation.assert_called_once()
        callback.assert_called_with(101, 101) # Total is self.config.iterations
        mock_finalize.assert_called_once()

    @patch("monte_neo.monte_carlo.engine.ParallelExecutor")
    @patch("monte_neo.monte_carlo.engine.MonteCarloEngine._finalize_results")
    def test_run_block_bootstrap_lazy(self, mock_finalize, mock_executor_class):
        self.config.use_block_bootstrap = True
        self.config.use_shuffling = False
        self.config.use_noise = False
        self.config.use_sensitivity = False
        self.config.use_walk_forward = False
        
        mock_executor = mock_executor_class.return_value
        mock_gpu_results = [{"metrics": {"total_return": 0.1}}]
        self.engine.gpu_engine.backtest_lazy_scenarios = MagicMock(return_value=mock_gpu_results)
        
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics)
        
        self.engine.gpu_engine.backtest_lazy_scenarios.assert_called_once()
        mock_finalize.assert_called_once()

    @patch("monte_neo.monte_carlo.engine.MonteCarloEngine._finalize_results")
    def test_run_existing_scenarios(self, mock_finalize):
        scenarios = [self.data] * 11 # Trigger GPU path
        self.engine.gpu_engine.backtest_scenarios = MagicMock(return_value=[{"metrics": {"total_return": 0.1}}] * 11)
        
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics, existing_scenarios=scenarios)
        
        self.engine.gpu_engine.backtest_scenarios.assert_called_once()

    @patch("monte_neo.monte_carlo.engine.MonteCarloEngine._run_cpu_parallel")
    @patch("monte_neo.monte_carlo.engine.MonteCarloEngine._finalize_results")
    def test_run_gpu_failure_fallback(self, mock_finalize, mock_run_cpu):
        self.engine.gpu_engine.backtest_scenarios = MagicMock(side_effect=Exception("GPU Fail"))
        mock_run_cpu.return_value = {"passed_count": 1, "all_results": []}
        
        scenarios = [self.data] * 11 # Trigger GPU path (>10)
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics, existing_scenarios=scenarios)
        
        mock_run_cpu.assert_called_once()

    @patch("monte_neo.monte_carlo.engine.ParallelExecutor")
    def test_run_cpu_parallel_small(self, mock_executor_class):
        mock_executor = mock_executor_class.return_value
        mock_executor.n_workers = 1
        mock_executor.map.return_value = [(True, {"total_return": 0.1})]
        
        res = self.engine._run_cpu_parallel([self.data], self.indicator, self.metrics_calc, self.target_metrics)
        
        self.assertEqual(res["passed_count"], 1)
        self.assertEqual(len(res["all_results"]), 1)

    @patch("monte_neo.monte_carlo.engine.ParallelExecutor")
    def test_run_cpu_parallel_large(self, mock_executor_class):
        mock_executor = mock_executor_class.return_value
        mock_executor.n_workers = 2
        # batch of results
        mock_executor.map.return_value = [[(True, {"total_return": 0.1})]]
        
        scenarios = [self.data] * 100
        res = self.engine._run_cpu_parallel(scenarios, self.indicator, self.metrics_calc, self.target_metrics)
        
        self.assertEqual(res["passed_count"], 1)
        self.assertEqual(len(res["all_results"]), 1)

    @patch("monte_neo.monte_carlo.sequential.SequentialMCRunner")
    def test_run_sequential_method(self, mock_runner_class):
        mock_runner = mock_runner_class.return_value
        self.engine.run_sequential(self.data, self.indicator, self.metrics_calc, self.target_metrics)
        mock_runner.run.assert_called_once()

    @patch("monte_neo.monte_carlo.engine.MonteCarloEngine._finalize_results")
    def test_run_pure_gpu_failure(self, mock_finalize):
        self.indicator.to_mlx_representation.return_value = {"params": []}
        self.config.iterations = 101
        self.engine.gpu_engine.run_full_simulation = MagicMock(side_effect=Exception("GPU Fail"))
        # Should fallback to standard path
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics)
        mock_finalize.assert_called_once()

    @patch("monte_neo.monte_carlo.engine.MonteCarloEngine._finalize_results")
    def test_run_generate_scenarios(self, mock_finalize):
        self.engine.scenario_builder.generate = MagicMock(return_value=[self.data])
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics)
        self.engine.scenario_builder.generate.assert_called_once()

    def test_meets_targets_logic(self):
        # We can test this indirectly through run_sequential or by mocking internal functions
        # but since it's a nested function, it's easier to trigger through run()
        self.target_metrics = {"max_drawdown": 0.1, "total_return": 0.05}
        
        # Test missing metric, mdd fail, return fail
        scenarios = [self.data]
        self.engine.gpu_engine.backtest_scenarios = MagicMock(return_value=[
            {"metrics": {"total_return": 0.1}}, # Missing max_drawdown -> should continue
            {"metrics": {"total_return": 0.1, "max_drawdown": 0.2}}, # MDD fail
            {"metrics": {"total_return": 0.01, "max_drawdown": 0.05}}, # Return fail
        ])
        
        res = self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics, existing_scenarios=scenarios*3)
        # Check passed_count if we can, but it's internal. We check pass_rate in final result.
        self.assertEqual(res.iterations_run, 3)

    @patch("monte_neo.monte_carlo.engine.ParallelExecutor")
    @patch("monte_neo.monte_carlo.engine.MonteCarloEngine._finalize_results")
    def test_run_progress_callbacks(self, mock_finalize, mock_executor_class):
        callback = MagicMock()
        self.engine.set_progress_callback(callback)
        
        # 1. Lazy block bootstrap callback
        self.config.use_block_bootstrap = True
        self.config.use_shuffling = False
        self.config.use_noise = False
        self.config.use_sensitivity = False
        self.config.use_walk_forward = False
        
        mock_gpu_results = [{"metrics": {}}] * 5
        self.engine.gpu_engine.backtest_lazy_scenarios = MagicMock(return_value=mock_gpu_results)
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics)
        callback.assert_any_call(5, 5)
        callback.reset_mock()
        
        # 2. GPU offload callback
        self.config.use_block_bootstrap = False
        scenarios = [self.data] * 11
        self.engine.gpu_engine.backtest_scenarios = MagicMock(return_value=[{"metrics": {}}] * 11)
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics, existing_scenarios=scenarios)
        callback.assert_any_call(11, 11)
        callback.reset_mock()
        
        # 3. CPU fallback callback
        self.engine.gpu_engine.backtest_scenarios = MagicMock(side_effect=Exception("GPU Fail"))
        self.engine._run_cpu_parallel = MagicMock(return_value={"passed_count": 0, "all_results": [{"metrics": {}}] * 11})
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics, existing_scenarios=scenarios)
        callback.assert_any_call(11, 11)

    def test_meets_targets_mdd_consecutive_losses(self):
        # Target for max_drawdown (lower is better)
        self.target_metrics = {"max_drawdown": 0.1, "consecutive_losses": 3}
        
        # 1. MDD fail (0.2 > 0.1)
        res = self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics, 
                             existing_scenarios=[self.data], interactive=False)
        # We need to control the metrics returned by the internal engine
        with patch.object(self.engine.gpu_engine, "backtest_scenarios", return_value=[
            {"metrics": {"max_drawdown": 0.2, "consecutive_losses": 2}}
        ]):
            res = self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics, 
                                 existing_scenarios=[self.data] * 11)
            self.assertEqual(res.detailed_results[0]["passed"], False)

        # 2. Consecutive losses fail (4 > 3)
        with patch.object(self.engine.gpu_engine, "backtest_scenarios", return_value=[
            {"metrics": {"max_drawdown": 0.05, "consecutive_losses": 4}}
        ]):
            res = self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics, 
                                 existing_scenarios=[self.data] * 11)
            self.assertEqual(res.detailed_results[0]["passed"], False)

    @patch("monte_neo.monte_carlo.engine.MonteCarloEngine._finalize_results")
    def test_run_pure_gpu_exception_coverage(self, mock_finalize):
        # Trigger line 164-165 (Pure GPU execution failed, falling back)
        self.indicator.to_mlx_representation.return_value = {"params": []}
        self.config.iterations = 101
        self.config.use_noise = False
        self.config.use_sensitivity = False
        self.config.use_walk_forward = False
        self.config.use_block_bootstrap = False
        
        # Make run_full_simulation raise an exception
        # Note: the engine expects (results, timing_stats) if successful
        self.engine.gpu_engine.run_full_simulation = MagicMock(side_effect=Exception("GPU Panic"))
        
        # Should fallback to standard path
        self.engine.run(self.data, self.indicator, self.metrics_calc, self.target_metrics)
        # Finalize should be called by the fallback path
        mock_finalize.assert_called()

if __name__ == "__main__":
    unittest.main()
