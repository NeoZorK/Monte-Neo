"""Unit tests for utility modules."""

from monte_neo.utils.config import Config, load_config
from monte_neo.utils.logger import get_logger, setup_logging
from monte_neo.utils.parallel import ParallelExecutor


def test_config_loading():
    config = load_config()
    assert isinstance(config, Config)
    assert hasattr(config, "default_symbol")


def test_parallel_executor():
    # Test thread pool
    executor = ParallelExecutor(n_workers=2, use_processes=False)
    results = executor.map(lambda x: x * x, [1, 2, 3, 4])
    assert results == [1, 4, 9, 16]

    # Test starmap
    results = executor.starmap(lambda x, y: x + y, [(1, 1), (2, 2)])
    assert results == [2, 4]


def test_logger_setup(tmp_path):
    log_file = tmp_path / "test.log"
    setup_logging(level="DEBUG", log_file=log_file)
    logger = get_logger("test_module")
    logger.debug("Debug message")

    assert log_file.exists()
    content = log_file.read_text()
    assert "DEBUG" in content
    assert "test_module" in content
