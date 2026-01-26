"""Main CLI application.

Entry point for the Monte-Neo CLI.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from rich.console import Console

from monte_neo._version import __version__
from monte_neo.cli.menu import InteractiveMenu
from monte_neo.cli.styles import print_banner, print_error
from monte_neo.utils.config import load_config
from monte_neo.utils.logger import get_logger, setup_logging

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
console = Console()


class MonteNeoCLI:
    """Main CLI application class."""

    def __init__(self) -> None:
        """Initialize CLI."""
        self.config = load_config()
        self.menu = InteractiveMenu(self.config)

    def run(self, interactive: bool = True) -> int:
        """Run the CLI application.

        Args:
            interactive: Run in interactive mode.

        Returns:
            Exit code.
        """
        print_banner()

        if interactive:
            return self.menu.run()
        else:
            console.print("[yellow]Non-interactive mode not yet implemented[/]")
            return 1

    def run_headless(
        self,
        config_file: str,
    ) -> int:
        """Run in headless mode with config file.

        Args:
            config_file: Path to YAML config.

        Returns:
            Exit code.
        """
        from monte_neo.cli.headless import run_headless_generation

        return run_headless_generation(config_file)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="monte-neo",
        description="Monte Carlo Indicator Generator Framework",
    )

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        default=True,
        help="Run in interactive mode (default)",
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to YAML config file (for headless mode)",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode with config file",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )

    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"monte-neo {__version__}",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(args.log_level)

    try:
        app = MonteNeoCLI()

        if args.headless and args.config:
            return app.run_headless(args.config)
        else:
            return app.run(interactive=args.interactive)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/]")
        sys.exit(0)

    except Exception as e:
        print_error(f"Error: {e}")
        logger.exception("Unhandled exception")
        return 1


if __name__ == "__main__":
    sys.exit(main())
