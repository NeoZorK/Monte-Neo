import unittest
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from monte_neo.monte_carlo.workers import (
    SHARED_DATA,
    SHARED_SCENARIOS,
    _generate_signals_wrapper,
    init_worker,
    init_worker_data,
    run_block_bootstrap_scenario,
    run_indicator_batch,
    run_scenario_batch,
    run_single_scenario,
)


class TestMonteCarloWorkers(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1100, 1200]
        })
        self.indicator = MagicMock()
        self.indicator.generate_signals_fast.return_value = [1, 1, 1]
        
        self.metrics_calc = MagicMock()
        self.metrics_calc.calculate_all.return_value = {"return": 0.1, "max_drawdown": 0.05}
        self.target_metrics = {"return": 0.05, "max_drawdown": 0.1}

    def tearDown(self):
        # Reset globals
        import monte_neo.monte_carlo.workers as workers
        workers.SHARED_DATA = None
        workers.SHARED_SCENARIOS = None

    def test_init_worker_data(self):
        init_worker_data(self.df)
        pd.testing.assert_frame_equal(SHARED_DATA, self.df)

    def test_init_worker(self):
        scenarios = [self.df]
        init_worker(scenarios)
        self.assertEqual(SHARED_SCENARIOS, scenarios)

    def test_generate_signals_wrapper_with_df(self):
        args = (self.indicator, self.df)
        result = _generate_signals_wrapper(args)
        np.testing.assert_array_equal(result, np.array([1, 1, 1], dtype=np.float32))
        self.indicator.generate_signals_fast.assert_called_with(self.df)

    def test_generate_signals_wrapper_with_shared_data(self):
        init_worker_data(self.df)
        args = (self.indicator, None)
        result = _generate_signals_wrapper(args)
        np.testing.assert_array_equal(result, np.array([1, 1, 1], dtype=np.float32))

    def test_generate_signals_wrapper_no_data(self):
        args = (self.indicator, None)
        result = _generate_signals_wrapper(args)
        self.assertEqual(len(result), 0)

    def test_run_indicator_batch(self):
        args = ([self.indicator], self.df)
        results = run_indicator_batch(args)
        self.assertEqual(len(results), 1)
        np.testing.assert_array_equal(results[0], np.array([1, 1, 1], dtype=np.float32))

    def test_run_indicator_batch_shared(self):
        init_worker_data(self.df)
        args = ([self.indicator], None)
        results = run_indicator_batch(args)
        self.assertEqual(len(results), 1)

    def test_run_indicator_batch_error(self):
        self.indicator.generate_signals_fast.side_effect = Exception("Test")
        args = ([self.indicator], self.df)
        results = run_indicator_batch(args)
        self.assertEqual(len(results), 1)
        np.testing.assert_array_equal(results[0], np.zeros(len(self.df), dtype=np.float32))

    def test_run_scenario_batch_explicit(self):
        scenarios = [self.df]
        results = run_scenario_batch(scenarios, self.indicator, self.metrics_calc, self.target_metrics)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][0]) # passed
        self.assertEqual(results[0][1], {"return": 0.1, "max_drawdown": 0.05})

    def test_run_scenario_batch_shared(self):
        init_worker([self.df])
        results = run_scenario_batch(None, self.indicator, self.metrics_calc, self.target_metrics, indices=[0])
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][0])

    def test_run_scenario_batch_empty(self):
        results = run_scenario_batch(None, self.indicator, self.metrics_calc, self.target_metrics)
        self.assertEqual(results, [])

    def test_run_scenario_batch_failure_check(self):
        # Test targets failure
        self.metrics_calc.calculate_all.return_value = {"return": 0.01, "max_drawdown": 0.05}
        results = run_scenario_batch([self.df], self.indicator, self.metrics_calc, self.target_metrics)
        self.assertFalse(results[0][0]) # return < 0.05

        self.metrics_calc.calculate_all.return_value = {"return": 0.1, "max_drawdown": 0.2}
        results = run_scenario_batch([self.df], self.indicator, self.metrics_calc, self.target_metrics)
        self.assertFalse(results[0][0]) # mdd > 0.1

    def test_run_scenario_batch_exception(self):
        self.indicator.generate_signals_fast.side_effect = Exception("Test")
        results = run_scenario_batch([self.df], self.indicator, self.metrics_calc, self.target_metrics)
        self.assertEqual(results, [(False, {})])

    def test_run_single_scenario(self):
        passed, metrics = run_single_scenario(self.df, self.indicator, self.metrics_calc, self.target_metrics)
        self.assertTrue(passed)
        self.assertEqual(metrics, {"return": 0.1, "max_drawdown": 0.05})

    def test_run_block_bootstrap_scenario(self):
        init_worker_data(self.df)
        self.indicator.generate_signals_fast.side_effect = lambda df: [1] * len(df)
        result = run_block_bootstrap_scenario(self.indicator, seed=42, block_size=2)
        self.assertIsNotNone(result)
        signal_arr, returns, ohlc = result
        self.assertEqual(len(signal_arr), 2)
        self.assertEqual(len(returns), 1)
        self.assertEqual(ohlc.shape, (2, 4))

    def test_run_block_bootstrap_no_data(self):
        result = run_block_bootstrap_scenario(self.indicator, seed=42)
        self.assertIsNone(result)

    def test_run_indicator_batch_no_shared(self):
        args = ([self.indicator], None)
        # SHARED_DATA is None here
        results = run_indicator_batch(args)
        self.assertEqual(results, [])

    def test_generate_lazy_scenario_wrapper(self):
        init_worker_data(self.df)
        self.indicator.generate_signals_fast.side_effect = lambda df: [1] * len(df)
        from monte_neo.monte_carlo.workers import _generate_lazy_scenario_wrapper
        args = (self.indicator, 42, 2)
        result = _generate_lazy_scenario_wrapper(args)
        self.assertIsNotNone(result)

    def test_run_scenario_batch_compile_error(self):
        self.indicator._compile_if_needed.side_effect = Exception("Compile error")
        scenarios = [self.df]
        results = run_scenario_batch(scenarios, self.indicator, self.metrics_calc, self.target_metrics)
        self.assertEqual(len(results), 1)

    def test_run_scenario_batch_missing_metric(self):
        # metric name not in metrics
        self.metrics_calc.calculate_all.return_value = {"other_metric": 0.1}
        results = run_scenario_batch([self.df], self.indicator, self.metrics_calc, self.target_metrics)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][0]) # passed because no targets were checked

    def test_run_single_scenario_missing_metric(self):
        self.metrics_calc.calculate_all.return_value = {"other_metric": 0.1}
        passed, metrics = run_single_scenario(self.df, self.indicator, self.metrics_calc, self.target_metrics)
        self.assertTrue(passed)

    def test_run_single_scenario_fail_mdd(self):
        self.metrics_calc.calculate_all.return_value = {"return": 0.1, "max_drawdown": 0.2}
        passed, metrics = run_single_scenario(self.df, self.indicator, self.metrics_calc, self.target_metrics)
        self.assertFalse(passed)

    def test_run_single_scenario_fail_return(self):
        self.metrics_calc.calculate_all.return_value = {"return": 0.01, "max_drawdown": 0.05}
        passed, metrics = run_single_scenario(self.df, self.indicator, self.metrics_calc, self.target_metrics)
        self.assertFalse(passed)

    def test_run_block_bootstrap_scenario_default_block(self):
        init_worker_data(self.df)
        self.indicator.generate_signals_fast.side_effect = lambda df: [1] * len(df)
        result = run_block_bootstrap_scenario(self.indicator, seed=42, block_size=None)
        self.assertIsNotNone(result)

    def test_run_block_bootstrap_scenario_exception(self):
        init_worker_data(self.df)
        self.indicator.generate_signals_fast.side_effect = Exception("Test")
        result = run_block_bootstrap_scenario(self.indicator, seed=42)
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
