"""Interactive menu module.

Arrow-key navigable menu system like cline/claude code CLI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from monte_neo.cli.progress import ProgressTracker
from monte_neo.cli.styles import CUSTOM_STYLE
from monte_neo.core.generator import GeneratorConfig, GeneratorResult, IndicatorGenerator
from monte_neo.data.downloader import BinanceDownloader
from monte_neo.data.storage import ParquetStorage
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

        # Evolutionary Settings
        self._pop_size: int = 50
        self._generations: int = 20
        self._mutation_rate: float = 0.3
        self._crossover_rate: float = 0.7

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

        return (
            questionary.select(
                "Select an option:",
                choices=choices,
                style=CUSTOM_STYLE,
                use_shortcuts=True,
            ).ask()
            or "exit"
        )

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

        try:
            from datetime import datetime, timedelta

            downloader = BinanceDownloader()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            self.progress.start(100, f"Downloading {symbol}...")
            data = downloader.download(
                symbol, timeframe, start_date, end_date, self.progress.update
            )
            self.progress.stop()
            self.storage.save(data, symbol, timeframe)

            console.print(f"[green]✓ Downloaded {len(data)} candles[/]")
            console.print(f"[dim]Saved to: data/raw/{symbol}_{timeframe}.parquet[/]\n")

        except Exception as e:
            console.print(f"[red]✗ Download failed: {e}[/]\n")

    def _set_metrics(self) -> None:
        """Set target metrics workflow."""
        console.print("\n[bold cyan]🎯 Set Target Metrics[/]\n")

        metrics_choices = [
            {
                "name": "📈 Profit Factor (> 2.0)",
                "value": "profit_factor",
                "checked": True,
            },
            {
                "name": "📊 Sharpe Ratio (> 1.0)",
                "value": "sharpe_ratio",
                "checked": True,
            },
            {
                "name": "📉 Max Drawdown (< 20%)",
                "value": "max_drawdown",
                "checked": True,
            },
            {"name": "🎯 Winrate (> 45%)", "value": "winrate", "checked": False},
            {
                "name": "💹 Sortino Ratio (> 1.5)",
                "value": "sortino_ratio",
                "checked": False,
            },
            {
                "name": "🔄 Recovery Factor (> 2.0)",
                "value": "recovery_factor",
                "checked": False,
            },
            {
                "name": "📆 Calmar Ratio (> 0.5)",
                "value": "calmar_ratio",
                "checked": False,
            },
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
                {
                    "name": "📏 Sensitivity Analysis (±10%)",
                    "value": "sensitivity",
                    "checked": True,
                },
                {
                    "name": "📅 Walk-Forward Analysis",
                    "value": "walk_forward",
                    "checked": True,
                },
                {
                    "name": "📦 Block Bootstrap",
                    "value": "block_bootstrap",
                    "checked": False,
                },
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

        # Select indicator types
        indicator_types = questionary.checkbox(
            "Select indicator types to search:",
            choices=[
                {
                    "name": "SMA (Simple Moving Average)",
                    "value": "sma",
                    "checked": True,
                },
                {
                    "name": "RSI (Relative Strength Index)",
                    "value": "rsi",
                    "checked": True,
                },
                {
                    "name": "MACD (Moving Average Convergence Divergence)",
                    "value": "macd",
                    "checked": True,
                },
                {
                    "name": "🧬 Dynamic (Genetic Programming)",
                    "value": "dynamic",
                    "checked": True,
                },
            ],
            style=CUSTOM_STYLE,
        ).ask()

        if not indicator_types:
            indicator_types = ["dynamic"]  # Fallback

        if not iterations:
            return

        # Confirm
        console.print(f"  Data: {symbol} {timeframe}")
        console.print(f"  Iterations: {iterations:,}")
        console.print(f"  Types: {', '.join(indicator_types)}")
        console.print(f"  Target metrics: {len(self._target_metrics)}")
        console.print(f"  MC methods: {len(self._mc_methods)}")

        if not questionary.confirm("Start generation?", style=CUSTOM_STYLE).ask():
            return

        # Load data and run
        data = self.storage.load(symbol, timeframe)
        self._last_data = data  # Store for plotting later

        config = GeneratorConfig(
            max_iterations=iterations,
            target_metrics=self._target_metrics,
            indicator_types=indicator_types,
            population_size=self._pop_size,
            generations=self._generations,
            mutation_rate=self._mutation_rate,
            crossover_rate=self._crossover_rate,
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
        import time

        time.sleep(0.1)  # Let the 100% state render
        self.progress.stop()

        # Show results
        self._show_generation_result(result)

        # Save result
        if result.indicator:
            self._save_result(result)

    def _save_result(self, result: GeneratorResult) -> None:
        """Save generation result to file."""
        import json
        import time

        results_dir = self.config.data_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        # Create filename
        timestamp = int(time.time())
        name = result.indicator.name if result.indicator else "unknown"
        filename = f"result_{timestamp}_{name}.json"
        file_path = results_dir / filename

        # Prepare data
        data = {
            "timestamp": timestamp,
            "type": name,
            "metrics": result.final_metrics,
            "config": result.parameters,
            "mc_pass_rate": result.mc_pass_rate,
            "iterations_tried": result.iterations_tried,
            "elapsed_time": result.elapsed_time,
            "candidates_found": result.candidates_found,
        }

        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)
            console.print(f"[dim]Result saved to: results/{filename}[/]")
        except Exception as e:
            console.print(f"[red]Error saving result: {e}[/]")

    def _show_generation_result(self, result) -> None:
        """Display generation results."""
        console.print()

        if result.success:
            console.print("[bold green]✓ Indicator generated successfully![/]\n")
        else:
            console.print(
                "[bold yellow]⚠ Indicator found but with lower confidence[/]\n"
            )

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

        # Display Formula/Configuration
        console.print(f"[bold cyan]Indicator Configuration[/]")
        params = result.parameters
        if "source_code" in params:
            # Format source code nicely
            code = params['source_code']
            # Highlight key parts
            console.print(Panel(code, title="Formula", border_style="blue"))
        else:
            # Standard params
            param_str = "\n".join([f"{k}: {v}" for k, v in params.items()])
            console.print(Panel(param_str, title=f"{result.indicator.name if result.indicator else 'Indicator'} Parameters", border_style="blue"))
        console.print()

        if result.candidates_found == 0:
            console.print(
                "[yellow]💡 Tip: No indicators met your target metrics.[/]\n"
                "[dim]Try the following:\n"
                "1. Relax target metrics (e.g., lower Profit Factor or Sharpe Ratio)\n"
                "2. Increase number of iterations\n"
                "3. Use a longer timeframe (e.g. 4h, 1d) which is often less noisy[/]\n"
            )

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
            from monte_neo.visualization.charts import ChartGenerator

            # Generate signals for the best indicator
            best_ind = result.indicator if result.indicator else None
            
            if best_ind and hasattr(self, "_last_data"):
                signals = best_ind.generate_signals(self._last_data)
                
                chart_gen = ChartGenerator()
                chart_gen.plot_with_signals(
                    self._last_data, 
                    signals, 
                    title=f"Best Indicator: {best_ind.name}"
                )
            else:
                console.print("[red]⚠ No data or indicator available for plotting[/]")

        console.print()

    def _view_results(self) -> None:
        """View saved results."""
        import os
        import json
        
        results_dir = self.config.data_dir / "results"
        if not results_dir.exists():
            console.print("[yellow]⚠ No results directory found.[/]\n")
            return
            
        files = list(results_dir.glob("*.json"))
        if not files:
            console.print("[yellow]⚠ No saved results found.[/]\n")
            return
            
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        choices = [f.stem for f in files] + ["🔙 Back"]
        
        selected = questionary.select(
            "Select result to view:",
            choices=choices,
            style=CUSTOM_STYLE,
        ).ask()
        
        if not selected or selected == "🔙 Back":
            return
            
        # Load and display result
        file_path = results_dir / f"{selected}.json"
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                
            console.print(f"\n[bold cyan]📄 Results for {selected}[/]")
            
            # Metrics table
            if "metrics" in data:
                table = Table(title="Metrics")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                for k, v in data["metrics"].items():
                    val = f"{v:.4f}" if isinstance(v, float) else str(v)
                    table.add_row(k, val)
                console.print(table)
                
            # Config info
            if "config" in data:
                console.print("\n[bold]Configuration:[/]")
                console.print(f"Type: {data.get('type', 'Unknown')}")
                
                config = data['config']
                if "source_code" in config:
                    console.print(Panel(config['source_code'], title="Formula", border_style="blue"))
                else:
                    param_str = "\n".join([f"{k}: {v}" for k, v in config.items()])
                    console.print(Panel(param_str, title="Parameters", border_style="blue"))
                
        except Exception as e:
            console.print(f"[red]Error loading result: {e}[/]")
        
        console.print()

    def _settings(self) -> None:
        """Settings menu for evolutionary parameters."""
        console.print("\n[bold cyan]⚙️  Evolutionary Settings[/]\n")

        choices = [
            {"name": f"👥 Population Size ({self._pop_size})", "value": "pop_size"},
            {"name": f"🔄 Generations ({self._generations})", "value": "generations"},
            {
                "name": f"🧪 Mutation Rate ({self._mutation_rate:.2f})",
                "value": "mutation",
            },
            {
                "name": f"🧬 Crossover Rate ({self._crossover_rate:.2f})",
                "value": "crossover",
            },
            {"name": "🔙 Back", "value": "back"},
        ]

        choice = questionary.select(
            "Select setting to modify:",
            choices=choices,
            style=CUSTOM_STYLE,
        ).ask()

        if choice == "pop_size":
            val = questionary.text(
                "Population Size:", default=str(self._pop_size)
            ).ask()
            if val:
                self._pop_size = int(val)
        elif choice == "generations":
            val = questionary.text("Generations:", default=str(self._generations)).ask()
            if val:
                self._generations = int(val)
        elif choice == "mutation":
            val = questionary.text(
                "Mutation Rate (0.0-1.0):", default=str(self._mutation_rate)
            ).ask()
            if val:
                self._mutation_rate = float(val)
        elif choice == "crossover":
            val = questionary.text(
                "Crossover Rate (0.0-1.0):", default=str(self._crossover_rate)
            ).ask()
            if val:
                self._crossover_rate = float(val)

        if choice != "back":
            console.print("[green]✓ Settings updated[/]\n")
            self._settings()  # Recurse
