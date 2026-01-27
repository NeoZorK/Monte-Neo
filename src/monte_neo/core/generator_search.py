from __future__ import annotations

import time
from typing import TYPE_CHECKING

from monte_neo.core.config import GeneratorResult
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine
from monte_neo.monte_carlo.workers import init_worker_data
from monte_neo.utils.logger import get_logger
from monte_neo.utils.parallel import ParallelExecutor

if TYPE_CHECKING:
    import pandas as pd

    from monte_neo.core.generator import IndicatorGenerator

logger = get_logger(__name__)


def run_search(generator: IndicatorGenerator, data: pd.DataFrame) -> GeneratorResult:
    """Run the search process."""
    start_time = time.time()
    best_indicator = None
    best_mc_rate = 0.0
    best_mc_details = {}
    iterations_tried = 0
    final_metrics = {}

    mc_cache: dict[str, float] = {}
    fallback_indicator = None
    fallback_metrics = {}
    best_performance_score = -float('inf')

    # Initialize persistent executor
    if generator.config.use_sequential_mc:
        generator.executor = ParallelExecutor(
            n_workers=1,
            use_processes=False,
            initializer=init_worker_data,
            initargs=(data,)
        )
    else:
        generator.executor = ParallelExecutor(
            initializer=init_worker_data,
            initargs=(data,)
        )
    generator.executor.__enter__()

    logger.info(f"Starting indicator generation (max {generator.config.max_iterations} iterations)")

    # Optimization: Use larger batch size to reduce IPC and parallel overhead
    batch_size = max(500, generator.config.population_size * 5)
    total_iterations = generator.config.max_iterations

    # Pre-generate MC scenarios
    mc_scenarios = _pre_generate_scenarios(generator, data, total_iterations)

    try:
        if generator._progress_callback:
            generator._progress_callback(0, total_iterations, "Starting search...")

        for batch_start in range(0, total_iterations, batch_size):
            actual_batch_size = min(batch_size, total_iterations - batch_start)
            batch_indicators = [generator._generate_random_indicator() for _ in range(actual_batch_size)]

            # GPU Backtest
            try:
                gpu_results = generator.gpu_engine.backtest_batch(
                    data,
                    batch_indicators,
                    executor=generator.executor,
                    use_shared_data=True,
                    use_sl_tp=generator.config.use_sl_tp,
                    sl_pct=generator.config.stop_loss_pct,
                    tp_pct=generator.config.take_profit_pct,
                    force_parallel=True  # Force parallel for large batches
                )
            except Exception as e:
                logger.warning(f"Backtest failed: {e}. Skipping batch.")
                gpu_results = []

            # Process results
            for i, result in enumerate(gpu_results):
                iterations_tried += 1
                indicator = batch_indicators[i]
                metrics = result["metrics"]

                # Fallback logic
                perf_score = (metrics.get("total_return", 0) * metrics.get("profit_factor", 1)) / (metrics.get("max_drawdown", 0) + 0.01)
                if perf_score > best_performance_score:
                    best_performance_score = perf_score
                    fallback_indicator = indicator
                    fallback_metrics = metrics

                if not generator._meets_basic_targets(metrics):
                    continue

                if metrics.get("trade_count", 0) < generator.config.min_trades:
                    continue

                # MC Validation
                try:
                    ind_id = indicator.get_id()
                    if ind_id in mc_cache:
                        mc_pass_rate = mc_cache[ind_id]
                    else:
                        mc_result = generator._run_mc_validation(data, indicator, scenarios=mc_scenarios)
                        mc_pass_rate = mc_result.pass_rate
                        mc_cache[ind_id] = mc_pass_rate

                        if mc_pass_rate > best_mc_rate:
                            best_mc_details = {
                                "step_results": [
                                    {"method": r.method_name, "passed": r.passed, "rate": r.pass_rate, "advice": r.advice}
                                    for r in mc_result.step_results
                                ]
                            }

                    if mc_pass_rate > 0.0:
                        generator._candidates.append((indicator, mc_pass_rate))

                    if mc_pass_rate > best_mc_rate:
                        best_mc_rate = mc_pass_rate
                        best_indicator = indicator
                        logger.info(f"New best: {indicator.name} MC rate={mc_pass_rate:.2%}")

                except Exception as e:
                    logger.warning(f"Error validating indicator: {e}")
                    continue

            # Progress callback
            _update_progress(generator, start_time, batch_start, actual_batch_size, total_iterations, best_mc_rate)

            # Early stopping
            if generator.config.early_stopping and best_mc_rate >= 0.95:
                logger.info(f"Early stopping: found solution at iteration {batch_start + actual_batch_size}")
                break

            # Check for shutdown requested
            if generator.executor and getattr(generator.executor, "_shutdown_requested", False):
                logger.info("Shutdown requested. Stopping search.")
                break

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt caught in generator. Cleaning up...")
        if generator._progress_callback:
            generator._progress_callback(iterations_tried, total_iterations, "Interrupted by user")
        if generator.executor:
            generator.executor.__exit__(None, None, None)
            generator.executor = None
        # Return what we found so far instead of crashing
        return _create_result(generator, best_indicator, fallback_indicator, best_mc_rate, best_mc_details, final_metrics, fallback_metrics, iterations_tried, start_time, data)

    # Evolution Phase
    best_indicator, best_mc_rate, best_mc_details = _run_evolution_phase(
        generator, data, best_indicator, best_mc_rate, best_mc_details
    )

    elapsed = time.time() - start_time
    if generator._progress_callback:
        generator._progress_callback(total_iterations, total_iterations, f"Best MC rate: {best_mc_rate:.1%} [Done]")

    if generator.executor:
        generator.executor.__exit__(None, None, None)
        generator.executor = None

    return _create_result(
        generator, best_indicator, fallback_indicator, best_mc_rate,
        best_mc_details, final_metrics, fallback_metrics, iterations_tried, start_time, data
    )


def _create_result(
    generator: IndicatorGenerator,
    best_indicator,
    fallback_indicator,
    best_mc_rate: float,
    best_mc_details: dict,
    final_metrics: dict,
    fallback_metrics: dict,
    iterations_tried: int,
    start_time: float,
    data: pd.DataFrame
) -> GeneratorResult:
    """Helper to create GeneratorResult."""
    if not best_indicator and fallback_indicator:
        best_indicator = fallback_indicator
        final_metrics = fallback_metrics

    if best_indicator and not final_metrics:
        signals = best_indicator.generate_signals(data)
        final_metrics = generator.metrics_calc.calculate_all(
            data, signals, use_sl_tp=generator.config.use_sl_tp,
            sl_pct=generator.config.stop_loss_pct, tp_pct=generator.config.take_profit_pct
        )

    elapsed = time.time() - start_time
    
    return GeneratorResult(
        success=best_mc_rate >= generator.config.mc_pass_threshold,
        indicator=best_indicator,
        parameters=best_indicator.get_parameters() if best_indicator else {},
        final_metrics=final_metrics,
        mc_pass_rate=best_mc_rate,
        mc_details=best_mc_details,
        iterations_tried=iterations_tried,
        elapsed_time=elapsed,
        candidates_found=len(generator._candidates),
    )


def _pre_generate_scenarios(generator: IndicatorGenerator, data: pd.DataFrame, total_iterations: int) -> list[pd.DataFrame] | None:
    if not generator.config.use_mc_block_bootstrap:
        try:
            temp_mc_config = MCConfig(
                iterations=generator.config.mc_iterations,
                use_shuffling=generator.config.use_mc_shuffling,
                use_noise=generator.config.use_mc_noise,
                use_sensitivity=generator.config.use_mc_sensitivity,
                use_walk_forward=generator.config.use_mc_walk_forward,
                use_block_bootstrap=False,
            )
            if generator._progress_callback:
                generator._progress_callback(0, total_iterations, "Generating shared MC scenarios...")

            temp_engine = MonteCarloEngine(temp_mc_config)
            return temp_engine.scenario_builder.generate(data)
        except Exception as e:
            logger.warning(f"Failed to pre-generate scenarios: {e}. Will generate per candidate.")
    return None


def _update_progress(generator: IndicatorGenerator, start_time: float, batch_start: int, batch_size: int, total: int, best_rate: float):
    if generator._progress_callback:
        current_iter = min(batch_start + batch_size, total)
        elapsed = time.time() - start_time
        ops_sec = current_iter / elapsed if elapsed > 0 else 0.0
        status = f"Best MC rate: {best_rate:.1%} | Speed: {ops_sec:.1f} op/s"
        generator._progress_callback(current_iter, total, status)


def _run_evolution_phase(generator: IndicatorGenerator, data: pd.DataFrame, best_ind, best_rate, best_details):
    if "dynamic" in generator.config.indicator_types and len(generator._candidates) >= 2:
        logger.info(f"Starting evolutionary optimization on {len(generator._candidates)} candidates...")
        try:
            dynamic_candidates = [c[0] for c in generator._candidates if isinstance(c[0], DynamicIndicator)]
            if len(dynamic_candidates) >= 2:
                evolved_best = generator._run_evolution(data, initial_population=dynamic_candidates)
                if evolved_best:
                    mc_result = generator._run_mc_validation(data, evolved_best)
                    mc_rate = mc_result.pass_rate

                    if mc_rate > 0:
                        generator._candidates.append((evolved_best, mc_rate))

                    if mc_rate > best_rate:
                        best_rate = mc_rate
                        best_ind = evolved_best
                        best_details = {
                            "step_results": [
                                {"method": r.method_name, "passed": r.passed, "rate": r.pass_rate, "advice": r.advice}
                                for r in mc_result.step_results
                            ]
                        }
                        logger.info(f"Evolution found better indicator: {evolved_best.name} MC rate={mc_rate:.2%}")
        except Exception as e:
            logger.error(f"Evolutionary optimization failed: {e}")
    return best_ind, best_rate, best_details
