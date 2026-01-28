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

    def run_export(self, json_path: str) -> int:
        """Export an indicator to C++."""
        import json

        from monte_neo.core.optimization.production_exporter import ProductionExporter
        
        try:
            with open(json_path) as f:
                data = json.load(f)
            
            # Mock indicator for export
            from monte_neo.indicators.dynamic import DynamicIndicator
            indicator = DynamicIndicator()
            indicator.set_parameter("source_code", data.get("formula", ""))
            
            exporter = ProductionExporter()
            export_path = exporter.export(indicator, data.get("validation", {}))
            
            console.print(f"[green]Successfully exported to: {export_path}[/]")
            return 0
        except Exception as e:
            console.print(f"[red]Export failed: {e}[/]")
            return 1

    def run_evolve(self, symbol: str) -> int:
        """Run AI-driven evolution for a symbol."""
        from monte_neo.core.evolution_ai import AIEvolutionEngine
        from monte_neo.data.storage import ParquetStorage
        from monte_neo.utils.config import Config
        
        try:
            console.print(f"[bold cyan]Starting AI Evolution for {symbol}...[/]")
            config = Config()
            storage = ParquetStorage(config.data_dir)
            data = storage.load(symbol, timeframe=config.default_timeframe)
            
            if data is None or data.empty:
                console.print(f"[red]No data found for {symbol}[/]")
                return 1
                
            engine = AIEvolutionEngine()
            best_indicator = engine.evolve(data, {"profit_factor": 1.5, "sharpe_ratio": 1.0}, generations=5)
            
            console.print("[green]Evolution complete! Best formula:[/]")
            console.print(f"[bold white]{best_indicator.get_formula()}[/]")
            return 0
        except Exception as e:
            console.print(f"[red]Evolution failed: {e}[/]")
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
        "--export",
        type=str,
        help="Path to indicator JSON to export to C++",
    )

    parser.add_argument(
        "--evolve",
        type=str,
        help="Symbol to run AI evolution for (e.g. BTCUSDT)",
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

        if args.export:
            return app.run_export(args.export)
        elif args.evolve:
            return app.run_evolve(args.evolve)
        elif args.headless and args.config:
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
