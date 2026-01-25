"""Parallel processing utilities."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Any

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class ParallelExecutor:
    """Parallel execution helper."""

    def __init__(
        self,
        n_workers: int | None = None,
        use_processes: bool = True,
    ) -> None:
        """Initialize executor.

        Args:
            n_workers: Number of workers (None = CPU count).
            use_processes: Use processes (True) or threads (False).
        """
        self.n_workers = n_workers or os.cpu_count() or 4
        self.use_processes = use_processes

    def map(
        self,
        func: Callable,
        items: Iterable,
        show_progress: bool = False,
    ) -> list[Any]:
        """Map function over items in parallel.

        Args:
            func: Function to apply.
            items: Items to process.
            show_progress: Show progress (requires tqdm).

        Returns:
            List of results.
        """
        items = list(items)

        if len(items) == 0:
            return []

        if len(items) == 1 or self.n_workers == 1:
            return [func(item) for item in items]

        executor_cls = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        results = []

        executor = executor_cls(max_workers=self.n_workers)
        try:
            futures = {executor.submit(func, item): i for i, item in enumerate(items)}

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    results.append((idx, result))
                except Exception as e:
                    logger.error(f"Error processing item {idx}: {e}", exc_info=True)
                    results.append((idx, None))
        except KeyboardInterrupt:
            logger.warning("Parallel execution interrupted. Shutting down workers...")
            # Kill workers immediately
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        finally:
            # Clean up properly if not already done
            executor.shutdown(wait=False)

        # Sort by original order
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

    def starmap(
        self,
        func: Callable,
        args_list: Iterable[tuple],
    ) -> list[Any]:
        """Starmap function over argument tuples.

        Args:
            func: Function to apply.
            args_list: List of argument tuples.

        Returns:
            List of results.
        """

        def wrapper(args: Any) -> Any:
            return func(*args)

        return self.map(wrapper, args_list)

    def map_reduce(
        self,
        map_func: Callable,
        reduce_func: Callable,
        items: Iterable,
        initial: Any = None,
    ) -> Any:
        """Map-reduce pattern.

        Args:
            map_func: Function to apply to each item.
            reduce_func: Function to combine results.
            items: Items to process.
            initial: Initial value for reduction.

        Returns:
            Reduced result.
        """
        mapped = self.map(map_func, items)

        result = initial
        for item in mapped:
            if item is not None:
                if result is None:
                    result = item
                else:
                    result = reduce_func(result, item)

        return result
