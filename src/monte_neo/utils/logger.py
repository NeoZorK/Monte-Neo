"""Logging utilities."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
) -> None:
    """Setup application logging.

    Args:
        level: Log level string.
        log_file: Optional log file path.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    try:
        from rich.logging import RichHandler
        from monte_neo.utils.console import console as shared_console
        console_handler = RichHandler(
            console=shared_console,
            rich_tracebacks=True,
            show_time=True,
            show_path=False,
        )
    except ImportError:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
    
    console_handler.setLevel(log_level)

    # Root logger
    root_logger = logging.getLogger("monte_neo")
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
        
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module.

    Args:
        name: Module name (typically __name__).

    Returns:
        Logger instance.
    """
    if name.startswith("monte_neo"):
        return logging.getLogger(name)
    return logging.getLogger(f"monte_neo.{name}")
