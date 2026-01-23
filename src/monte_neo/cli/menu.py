"""Interactive menu module.

Arrow-key navigable menu system like cline/claude code CLI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from monte_neo.cli.progress import ProgressTracker
from monte_neo.cli.styles import CUSTOM_STYLE
from monte_neo.data.downloader import BinanceDownloader
from monte_neo.data.storage import ParquetStorage
from monte_neo.core.generator import IndicatorGenerator, GeneratorConfig
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    from monte_neo.utils.config import Config

logger = get_logger(__name__)
console = Console()


class InteractiveMenu:
    """Interactive CLI menu with arrow navigation."""

    def __init__(self, config: Config) -> None:
        """Initialize menu.

        Args:
            config: Application configuration.
        """
        self.config = config
        self.storage = ParquetStorage(config.data_dir)
        self.progress = ProgressTracker()
        
        # State
        self._target_metrics: dict = {}
        self._selected_symbol: str = config.default_symbol
        self._selected_timeframe: str = config.default_timeframe
        self._mc_methods: list[str] = []

    def run(self) -> int:
        """Run the interactive menu loop.

        Returns:
            Exit code.
        """
        while True:
            choice = self._show_main_menu()
            
            if choice == "exit":
                console.print("[green]Goodbye![/]")
                return 0
            
            self._handle_choice(choice)

    def _show_main_menu(self) -> str:
        """Show main menu and get selection."""
        choices = [
            {"name": "📊 Download Market Data", "value": "download"},
            {"name": "🎯 Set Target Metrics", "value": "metrics"},
            {"name": "🔧 Configure Monte Carlo Methods", "value": "mc_config"},
            {"name": "🚀 Generate Indicator", "value": "generate"},
            {"name": "📈 View Results", "value": "results"},
            {"name": "⚙️  Settings", "value": "settings"},
            {"name": "❌ Exit", "value": "exit"},
        ]
        
        return questionary.select(
            "Select an option:",
            choices=choices,
            style=CUSTOM_STYLE,
            use_shortcuts=True,
        ).ask() or "exit"

    def _handle_choice(self, choice: str) -> None:
        """Handle menu selection."""
        handlers = {
            "download": self._download_data,
            "metrics": self._set_metrics,
            "mc_config": self._configure_mc,
            "generate": self._generate_indicator,
            "results": self._view_results,
            "settings": self._settings,
        }
        
        handler = handlers.get(choice)
        if handler:
            handler()

    def _download_data(self) -> None:
        """Download market data workflow."""
        console.print("\n[bold cyan]📊 Download Market Data[/]\n")
        
        # Select symbol
        symbol = questionary.text(
            "Symbol (e.g., BTCUSDT):",
            default=self._selected_symbol,
            style=CUSTOM_STYLE,
        ).ask()
        
        if not symbol:
            return
        
        # Select timeframe
        timeframe = questionary.select(
            "Timeframe:",
            choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
            default=self._selected_timeframe,
            style=CUSTOM_STYLE,
        ).ask()
        
        # Select period
        days = questionary.select(
            "Historical period:",
            choices=[
                {"name": "30 days", "value": 30},
                {"name": "90 days", "value": 90},
                {"name": "180 days", "value": 180},
                {"name": "365 days (1 year)", "value": 365},
                {"name": "730 days (2 years)", "value": 730},
            ],
            style=CUSTOM_STYLE,
        ).ask()
        
        if not all([symbol, timeframe, days]):
            return
        
        self._selected_symbol = symbol
        self._selected_timeframe = timeframe
        
        # Download with progress
        console.print(f"\n[yellow]Downloading {symbol} {timeframe}...[/]")
        
        try:
            from datetime import datetime, timedelta
            
            downloader = BinanceDownloader()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            data = downloader.download(symbol, timeframe, start_date, end_date)
            self.storage.save(data, symbol, timeframe)
            
            console.print(f"[green]✓ Downloaded {len(data)} candles[/]")
            console.print(f"[dim]Saved to: data/raw/{symbol}_{timeframe}.parquet[/]\n")
            
        except Exception as e:
            console.print(f"[red]✗ Download failed: {e}[/]\n")

    def _set_metrics(self) -> None:
        """Set target metrics workflow."""
        console.print("\n[bold cyan]🎯 Set Target Metrics[/]\n")
        
        metrics_choices = [
            {"name": "📈 Profit Factor (> 2.0)", "value": "profit_factor", "checked": True},
            {"name": "📊 Sharpe Ratio (> 1.0)", "value": "sharpe_ratio", "checked": True},
            {"name": "📉 Max Drawdown (< 20%)", "value": "max_drawdown", "checked": True},
            {"name": "🎯 Winrate (> 45%)", "value": "winrate", "checked": False},
            {"name": "💹 Sortino Ratio (> 1.5)", "value": "sortino_ratio", "checked": False},
            {"name": "🔄 Recovery Factor (> 2.0)", "value": "recovery_factor", "checked": False},
            {"name": "📆 Calmar Ratio (> 0.5)", "value": "calmar_ratio", "checked": False},
        ]
        
        selected = questionary.checkbox(
            "Select metrics to target:",
            choices=metrics_choices,
            style=CUSTOM_STYLE,
        ).ask()
        
        if not selected:
            return
        
        # Get values for selected metrics
        self._target_metrics = {}
        defaults = {
            "profit_factor": 2.0,
            "sharpe_ratio": 1.0,
            "max_drawdown": 0.20,
            "winrate": 0.45,
            "sortino_ratio": 1.5,
            "recovery_factor": 2.0,
            "calmar_ratio": 0.5,
        }
        
        for metric in selected:
            value = questionary.text(
                f"{metric}:",
                default=str(defaults.get(metric, 1.0)),
                style=CUSTOM_STYLE,
            ).ask()
            
            if value:
                self._target_metrics[metric] = float(value)
        
        # Show summary
        console.print("\n[green]✓ Target metrics set:[/]")
        for k, v in self._target_metrics.items():
            console.print(f"  • {k}: {v}")
        console.print()

    def _configure_mc(self) -> None:
        """Configure Monte Carlo methods."""
        console.print("\n[bold cyan]🔧 Configure Monte Carlo Methods[/]\n")
        
        methods = questionary.checkbox(
            "Select MC methods:",
            choices=[
                {"name": "🔀 Return Shuffling", "value": "shuffling", "checked": True},
                {"name": "🎲 Noise Injection", "value": "noise", "checked": True},
                {"name": "📏 Sensitivity Analysis (±10%)", "value": "sensitivity", "checked": True},
                {"name": "📅 Walk-Forward Analysis", "value": "walk_forward", "checked": True},
                {"name": "📦 Block Bootstrap", "value": "block_bootstrap", "checked": False},
            ],
            style=CUSTOM_STYLE,
        ).ask()
        
        self._mc_methods = methods or []
        
        console.print(f"\n[green]✓ Selected {len(self._mc_methods)} methods[/]\n")

    def _generate_indicator(self) -> None:
        """Generate indicator workflow."""
        console.print("\n[bold cyan]🚀 Generate Indicator[/]\n")
        
        # Check prerequisites
        if not self._target_metrics:
            console.print("[yellow]⚠ Please set target metrics first[/]\n")
            return
        
        # Get data
        files = self.storage.list_files()
        if not files:
            console.print("[yellow]⚠ No data available. Download data first.[/]\n")
            return
        
        # Select data
        file_choices = [f"{f['symbol']}_{f['timeframe']}" for f in files]
        selected = questionary.select(
            "Select data:",
            choices=file_choices,
            style=CUSTOM_STYLE,
        ).ask()
        
        if not selected:
            return
        
        symbol, timeframe = selected.split("_")
        
        # Get iterations
        iterations = questionary.select(
            "Number of iterations:",
            choices=[
                {"name": "1,000 (fast test)", "value": 1000},
                {"name": "10,000 (standard)", "value": 10000},
                {"name": "50,000 (thorough)", "value": 50000},
                {"name": "100,000 (maximum)", "value": 100000},
            ],
            style=CUSTOM_STYLE,
        ).ask()
        
        if not iterations:
            return
        
        # Confirm
        console.print(f"\n[bold]Configuration:[/]")
        console.print(f"  Data: {symbol} {timeframe}")
        console.print(f"  Iterations: {iterations:,}")
        console.print(f"  Target metrics: {len(self._target_metrics)}")
        console.print(f"  MC methods: {len(self._mc_methods)}")
        
        if not questionary.confirm("Start generation?", style=CUSTOM_STYLE).ask():
            return
        
        # Load data and run
        data = self.storage.load(symbol, timeframe)
        
        config = GeneratorConfig(
            max_iterations=iterations,
            target_metrics=self._target_metrics,
            use_mc_shuffling="shuffling" in self._mc_methods,
            use_mc_noise="noise" in self._mc_methods,
            use_mc_sensitivity="sensitivity" in self._mc_methods,
            use_mc_walk_forward="walk_forward" in self._mc_methods,
        )
        
        generator = IndicatorGenerator(config)
        
        # Progress tracking
        self.progress.start(iterations, "Generating indicator...")
        generator.set_progress_callback(self.progress.update)
        
        result = generator.generate(data)
        self.progress.stop()
        
        # Show results
        self._show_generation_result(result)

    def _show_generation_result(self, result) -> None:
        """Display generation results."""
        console.print()
        
        if result.success:
            console.print("[bold green]✓ Indicator generated successfully![/]\n")
        else:
            console.print("[bold yellow]⚠ Indicator found but with lower confidence[/]\n")
        
        # Stats table
        table = Table(title="Generation Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Time", f"{result.elapsed_time:.1f}s")
        table.add_row("Iterations", f"{result.iterations_tried:,}")
        table.add_row("MC Pass Rate", f"{result.mc_pass_rate:.1%}")
        table.add_row("Candidates Found", str(result.candidates_found))
        
        console.print(table)
        console.print()
        
        # Metrics
        if result.final_metrics:
            table = Table(title="Final Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            for k, v in result.final_metrics.items():
                if isinstance(v, float):
                    table.add_row(k, f"{v:.4f}")
                else:
                    table.add_row(k, str(v))
            
            console.print(table)
        
        # Ask to visualize
        if questionary.confirm("Show chart?", style=CUSTOM_STYLE).ask():
            console.print("[yellow]Chart visualization coming soon...[/]")
        
        console.print()

    def _view_results(self) -> None:
        """View saved results."""
        console.print("\n[yellow]Results viewer coming soon...[/]\n")

    def _settings(self) -> None:
        """Settings menu."""
        console.print("\n[yellow]Settings coming soon...[/]\n")
