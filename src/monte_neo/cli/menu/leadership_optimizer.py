"""Smart optimizer for Leadership Pipeline."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from rich.table import Table
from rich.panel import Panel

from monte_neo.data.downloader import BinanceDownloader
from monte_neo.utils.console import console
from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

logger = get_logger(__name__)

class SmartPipelineOptimizer:
    """Intelligent search orchestrator for the Global Leadership Pipeline."""
    
    def __init__(self, menu: InteractiveMenu, log_callback: callable = None):
        self.menu = menu
        self.log_callback = log_callback
        self.iteration = 0
        self.best_score_ever = 0.0
        self.best_formula_ever = None
        self.last_failure_reason = "Initial search"
        self.adjustments_made = []
        self.last_mc_results = {}
        self.available_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
        self.current_tf_index = self.available_timeframes.index(menu._selected_timeframe) \
            if menu._selected_timeframe in self.available_timeframes else 4

    def _log(self, msg: str):
        """Internal helper to log to callback or console."""
        if self.log_callback:
            self.log_callback(msg)
        else:
            console.print(msg)

    def brainstorm_and_adjust(self, validation_res: Any, gate_results: dict) -> str:
        """Analyzes failures and adjusts evolution parameters and timeframe for the next run."""
        self.iteration += 1
        self.adjustments_made = []
        
        score = gate_results.get("final_score", 0.0)
        if score > self.best_score_ever:
            self.best_score_ever = score

        warnings = validation_res.warnings if hasattr(validation_res, 'warnings') else []
        
        # 1. Overfitting Analysis
        oos_ratio_fail = any("OOS/IS ratio" in w for w in warnings)
        oos_targets_fail = any("OOS metrics don't meet targets" in w for w in warnings)
        
        if oos_ratio_fail or oos_targets_fail:
            self.last_failure_reason = "Overfitting detected (Strategy is too specific to history)"
            self.menu._mutation_rate = max(0.1, self.menu._mutation_rate - 0.05)
            self.menu._crossover_rate = min(0.9, self.menu._crossover_rate + 0.05)
            self.adjustments_made.append(f"Reduced mutation rate to {self.menu._mutation_rate:.2f}")
            self.adjustments_made.append(f"Increased crossover rate to {self.menu._crossover_rate:.2f}")
            
            if self.current_tf_index < len(self.available_timeframes) - 1:
                self.current_tf_index += 1
                new_tf = self.available_timeframes[self.current_tf_index]
                self.menu._selected_timeframe = new_tf
                self.adjustments_made.append(f"Brain switched to higher timeframe: {new_tf}")
        
        # 2. Insufficient Activity Analysis
        low_trades_fail = any("Insufficient" in w and "trades" in w for w in warnings)
        if low_trades_fail:
            self.last_failure_reason = "Strategy is too selective (Not enough trades)"
            self.menu._pop_size = min(200, self.menu._pop_size + 20)
            self.adjustments_made.append(f"Increased population size to {self.menu._pop_size}")
            
            if self.current_tf_index > 0:
                self.current_tf_index -= 1
                new_tf = self.available_timeframes[self.current_tf_index]
                self.menu._selected_timeframe = new_tf
                self.adjustments_made.append(f"Brain switched to lower timeframe: {new_tf}")

        # 3. Quality Analysis
        if score < 50 and not (oos_ratio_fail or low_trades_fail):
            self.last_failure_reason = "Low overall quality/fitness"
            self.menu._generations = min(100, self.menu._generations + 10)
            self.menu._pop_size = min(200, self.menu._pop_size + 10)
            self.adjustments_made.append(f"Increased evolution depth (Gens: {self.menu._generations})")

        if not self.adjustments_made:
            self.last_failure_reason = "General rejection from Production Gate"
            self.menu._generations = min(100, self.menu._generations + 5)
            self.adjustments_made.append("Slightly increased evolution depth")

        return self.last_failure_reason

    def ensure_data(self, symbol: str, timeframe: str):
        """Checks for local data and downloads if missing and auto-download is enabled."""
        try:
            data = self.menu.storage.load(symbol, timeframe=timeframe)
            if data is not None and not data.empty:
                return data
        except FileNotFoundError:
            pass

        if not self.menu.config.auto_download_data:
            return None

        self._log(f"[yellow]Data for {symbol} {timeframe} missing. Auto-downloading from Binance...[/]")
        try:
            downloader = BinanceDownloader()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            
            # Hide the global progress bar as it messes with Live output
            # self.menu.progress.start(100, f"Downloading {symbol} {timeframe}...")
            data = downloader.download(
                symbol, timeframe, start_date, end_date # , self.menu.progress.update
            )
            # self.menu.progress.update(100, 100, "Done")
            # self.menu.progress.stop()
            
            if data is not None and not data.empty:
                self.menu.storage.save(data, symbol, timeframe)
                self._log(f"[green]✓ Successfully downloaded and saved {len(data)} candles.[/]")
                return data
        except Exception as e:
            # self.menu.progress.stop()
            self._log(f"[red]✗ Auto-download failed: {e}[/]")
            logger.error(f"Auto-download failed for {symbol} {timeframe}: {e}")
        
        return None

    def print_report(self):
        """Prints a brainstorm report to the console."""
        report = Table.grid(padding=(0, 1))
        report.add_column(style="bold cyan")
        report.add_column()
        report.add_row("Iteration:", f"#{self.iteration}")
        report.add_row("Last Fail:", f"[yellow]{self.last_failure_reason}[/]")
        report.add_row("Best Score:", f"[green]{self.best_score_ever:.2f}/100[/]")
        adj_str = ", ".join(self.adjustments_made) if self.adjustments_made else "None"
        report.add_row("Adjustments:", f"[dim]{adj_str}[/]")
        console.print(Panel(report, title="[bold magenta]🧠 Smart Search Brainstorm[/]", border_style="magenta"))
