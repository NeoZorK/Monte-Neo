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
        initializer: Callable | None = None,
        initargs: tuple = (),
    ) -> None:
        """Initialize executor.

        Args:
            n_workers: Number of workers (None = CPU count).
            use_processes: Use processes (True) or threads (False).
            initializer: Function to initialize each worker.
            initargs: Arguments for initializer.
        """
        self.n_workers = n_workers or os.cpu_count() or 4
        self.use_processes = use_processes
        self.initializer = initializer
        self.initargs = initargs
        self._pool: ProcessPoolExecutor | ThreadPoolExecutor | None = None

    def __enter__(self) -> ParallelExecutor:
        """Context manager entry."""
        if self._pool is None:
            executor_cls = (
                ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
            )
            kwargs: dict[str, Any] = {"max_workers": self.n_workers}
            if self.initializer:
                kwargs["initializer"] = self.initializer
                kwargs["initargs"] = self.initargs

            self._pool = executor_cls(**kwargs)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        if self._pool:
            self._shutdown_requested = True
            # Cancel all pending futures if possible
            if hasattr(self._pool, "_pending_work_items"): # ProcessPoolExecutor internal
                try:
                    for future in list(self._pool._pending_work_items.values()):
                        future.cancel()
                except Exception:
                    pass
            
            # Use wait=False to avoid hanging on exit
            # cancel_futures=True is supported in Python 3.9+
            try:
                self._pool.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                # Fallback for older Python versions
                self._pool.shutdown(wait=False)
            
            self._pool = None

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

        # Reduce overhead for small batches or single worker
        if len(items) == 1 or self.n_workers == 1:
            return [func(item) for item in items]

        executor_cls = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        results = []

        executor = self._pool
        is_temp_pool = False
        if executor is None:
            executor = executor_cls(max_workers=self.n_workers)
            is_temp_pool = True

        try:
            # Submit tasks and store futures
            futures_map = {executor.submit(func, item): i for i, item in enumerate(items)}
            pending = set(futures_map.keys())

            while pending:
                if getattr(self, "_shutdown_requested", False):
                    # Cancel all remaining if shutdown requested
                    for f in pending:
                        f.cancel()
                    break

                # Wait for some futures to complete with a small timeout to allow checking _shutdown_requested
                done, pending = as_completed_with_timeout(pending, timeout=0.1)
                
                for future in done:
                    idx = futures_map[future]
                    try:
                        result = future.result()
                        results.append((idx, result))
                    except Exception as e:
                        # Only log if not a cancellation/shutdown error
                        if not getattr(self, "_shutdown_requested", False):
                            logger.error(f"Error processing item {idx}: {e}")
                        results.append((idx, None))

        except (KeyboardInterrupt, SystemExit):
            self._shutdown_requested = True
            # Kill workers immediately
            if executor:
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except (TypeError, Exception):
                    executor.shutdown(wait=False)
            raise
        finally:
            # Clean up properly if it was a temp pool
            if is_temp_pool and executor:
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except (TypeError, Exception):
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


def as_completed_with_timeout(fs, timeout=None):
    """Wait for some futures to complete with a timeout."""
    from concurrent.futures import FIRST_COMPLETED, wait

    done_set = wait(fs, timeout=timeout, return_when=FIRST_COMPLETED).done
    return done_set, fs - done_set
