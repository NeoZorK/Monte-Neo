"""Main interactive menu logic."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import questionary
from rich.console import Console

from monte_neo.cli.progress import ProgressTracker
from monte_neo.cli.styles import CUSTOM_STYLE
from monte_neo.data.storage import ParquetStorage
from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    from monte_neo.utils.config import Config

logger = get_logger(__name__)
console = Console()


class InteractiveMenu:
    """Interactive CLI menu with arrow navigation."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.storage = ParquetStorage(config.data_dir)
        self.progress = ProgressTracker()

        # State
        self._target_metrics: dict = {
            "profit_factor": 2.0,
            "sharpe_ratio": 1.0,
            "max_drawdown": 0.20
        }
        self._selected_symbol: str = config.default_symbol
        self._selected_timeframe: str = config.default_timeframe
        self._mc_methods: list[str] = ["shuffling", "noise", "sensitivity", "walk_forward", "block_bootstrap"]
        self._pop_size, self._generations = 50, 20
        self._mutation_rate, self._crossover_rate = 0.3, 0.7
        self._cached_symbols: list[str] = []

        # Risk Management Settings
        self._stop_loss_pct: float = 1.0
        self._take_profit_pct: float = 2.0
        self._use_sl_tp: bool = True

        # Validation Settings
        self._mc_pass_threshold: float = 0.80

        # Hardware Settings
        self._use_gpu: bool = config.use_gpu
        self._gpu_precision: str = config.gpu_precision
        self._metal_driver: str = config.metal_driver

        self._last_data: pd.DataFrame | None = None

    def run(self) -> int:
        """Run the interactive menu loop."""
        while True:
            try:
                choice = self._show_main_menu()
                if choice == "exit":
                    console.print("[green]Goodbye![/]")
                    return 0
                self._handle_choice(choice)
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled by user. Returning to menu...[/]")
            except Exception as e:
                console.print(f"\n[red]An error occurred: {e}[/]")
                logger.exception("Error in menu loop")

    def _show_main_menu(self) -> str:
        choices = [
            {"name": "📊 Download Market Data", "value": "download"},
            {"name": "🎯 Set Target Metrics", "value": "metrics"},
            {"name": "🎲 Configure Monte Carlo Methods", "value": "mc_config"},
            {"name": "🚀 Generate Indicator", "value": "generate"},
            {"name": "🔄 Sequential Generate Indicator", "value": "generate_sequential"},
            {"name": "🧪 Test Custom Formula", "value": "test_custom"},
            {"name": "💼 Smart Portfolio", "value": "portfolio"},
            {"name": "📈 View Results", "value": "results"},
            {"name": "⚙️  Settings", "value": "settings"},
            {"name": "🔧 Hardware Configuration", "value": "hardware"},
            {"name": "❌ Exit", "value": "exit"},
        ]
        return questionary.select(
            "Select an option:", choices=choices, style=CUSTOM_STYLE, use_shortcuts=True
        ).ask() or "exit"

    def _handle_choice(self, choice: str) -> None:
        from monte_neo.cli.menu.data import download_data_workflow
        from monte_neo.cli.menu.generator import generate_indicator_workflow
        from monte_neo.cli.menu.hardware import hardware_workflow
        from monte_neo.cli.menu.mc_config import configure_mc_workflow
        from monte_neo.cli.menu.metrics import set_metrics_workflow
        from monte_neo.cli.menu.results import view_results_workflow
        from monte_neo.cli.menu.settings import settings_workflow

        if choice == "generate":
            generate_indicator_workflow(self, sequential=False)
            return
        elif choice == "generate_sequential":
            generate_indicator_workflow(self, sequential=True)
            return
        elif choice == "test_custom":
            from monte_neo.cli.menu.custom_test import test_custom_indicator_workflow
            test_custom_indicator_workflow(self)
            return
        elif choice == "portfolio":
            from monte_neo.cli.menu.portfolio import portfolio_workflow
            portfolio_workflow(self)
            return

        handlers = {
            "download": download_data_workflow,
            "metrics": set_metrics_workflow,
            "mc_config": configure_mc_workflow,
            "results": view_results_workflow,
            "settings": settings_workflow,
            "hardware": hardware_workflow,
        }
        handler = handlers.get(choice)
        if handler:
            handler(self)
            self._sync_to_config()
            self._save_config()

    def _sync_to_config(self) -> None:
        """Sync internal state to config object."""
        self.config.default_symbol = self._selected_symbol
        self.config.default_timeframe = self._selected_timeframe
        self.config.target_profit_factor = self._target_metrics["profit_factor"]
        self.config.target_sharpe_ratio = self._target_metrics["sharpe_ratio"]
        self.config.target_max_drawdown = self._target_metrics["max_drawdown"]
        self.config.use_gpu = self._use_gpu
        self.config.gpu_precision = self._gpu_precision
        self.config.metal_driver = self._metal_driver

    def _save_config(self) -> None:
        """Save config to default path."""
        from monte_neo.utils.config import save_config
        config_path = Path("config.yaml")
        save_config(self.config, config_path)
