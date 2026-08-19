import time

from monte_neo.utils.parallel import ParallelExecutor


def square(x):
    return x * x

def slow_square(x):
    time.sleep(0.1)
    return x * x

def test_parallel_executor_threads():
    with ParallelExecutor(n_workers=2, use_processes=False) as executor:
        results = executor.map(square, [1, 2, 3, 4])
        assert results == [1, 4, 9, 16]

def test_parallel_executor_processes():
    # Only test simple case to avoid pickling issues in tests
    with ParallelExecutor(n_workers=2, use_processes=True) as executor:
        results = executor.map(square, [1, 2, 3])
        assert results == [1, 4, 9]

def test_parallel_executor_single_worker():
    executor = ParallelExecutor(n_workers=1)
    results = executor.map(square, [5])
    assert results == [25]

def test_parallel_executor_empty():
    executor = ParallelExecutor(n_workers=2)
    assert executor.map(square, []) == []

def test_parallel_executor_context_manager():
    executor = ParallelExecutor(n_workers=2)
    with executor:
        assert executor._pool is not None
    assert executor._pool is None
