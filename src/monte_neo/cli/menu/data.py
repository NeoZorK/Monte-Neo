"""Data download workflow."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import questionary
from rich.console import Console
from rich.panel import Panel

from monte_neo.cli.menu.symbol_selector import SymbolSelector
from monte_neo.cli.styles import CUSTOM_STYLE
from monte_neo.data.downloader import BinanceDownloader
from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

logger = get_logger(__name__)
console = Console()


def download_data_workflow(menu: InteractiveMenu) -> None:
    """Download market data workflow."""
    console.print("\n[bold cyan]📊 Download Market Data[/]\n")

    # Select symbol
    if not menu._cached_symbols:
        try:
            menu.progress.start(100, "Fetching available symbols from Binance...")
            downloader = BinanceDownloader()
            symbols = downloader.get_available_symbols()
            
            # Prioritize USDT pairs
            usdt_pairs = [s for s in symbols if s.endswith("USDT")]
            other_pairs = [s for s in symbols if not s.endswith("USDT")]
            menu._cached_symbols = sorted(usdt_pairs) + sorted(other_pairs)
            
            menu.progress.update(100, 100, "Done")
            menu.progress.stop()
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            menu.progress.stop()
            console.print(f"[red]Error fetching symbols: {e}. Using default.[/]")
            menu._cached_symbols = [menu._selected_symbol]

    # Use the new multi-column searchable selector
    selector = SymbolSelector(menu._cached_symbols, style=CUSTOM_STYLE)
    symbol = selector.ask()

    if not symbol:
        return

    # Select timeframe
    timeframe = questionary.select(
        "Timeframe:",
        choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        default=menu._selected_timeframe,
        style=CUSTOM_STYLE,
    ).ask()

    if not timeframe:
        return

    _process_download(menu, symbol, timeframe)


def _process_download(menu: InteractiveMenu, symbol: str, timeframe: str) -> None:
    # Check if exists
    info = menu.storage.get_info(symbol, timeframe)
    if info:
        console.print(f"\n[yellow]⚠ Data for {symbol} {timeframe} already exists.[/]")
        
        start = info.get('start_date')
        end = info.get('end_date')
        
        # Format dates if they exist
        start_str = str(start).split(".")[0] if start else "Unknown"
        end_str = str(end).split(".")[0] if end else "Unknown"
        range_str = f"{start_str} ➜ {end_str}"
        
        console.print(Panel(
            f"Rows:  {info.get('rows', 0):,}\n"
            f"Range: {range_str}\n"
            f"Size:  {info.get('size_mb', 0):.2f} MB",
            title="Existing Data",
            border_style="yellow"
        ))

        if not questionary.confirm(
            "Overwrite existing data?", default=False, style=CUSTOM_STYLE
        ).ask():
            return

    # Select period
    choices = [
        {"name": "30 days", "value": 30},
        {"name": "90 days", "value": 90},
        {"name": "180 days", "value": 180},
        {"name": "365 days (1 year)", "value": 365},
        {"name": "730 days (2 years)", "value": 730},
        {"name": "1095 days (3 years)", "value": 1095},
        {"name": "1825 days (5 years)", "value": 1825},
        {"name": "3650 days (10 years)", "value": 3650},
        {"name": "Custom days...", "value": "custom"},
    ]
    
    days_val = questionary.select(
        "Historical period:",
        choices=choices,
        style=CUSTOM_STYLE,
    ).ask()

    if not days_val:
        return

    if days_val == "custom":
        days_str = questionary.text("Enter number of days:").ask()
        try:
            days = int(days_str)
        except (ValueError, TypeError):
            console.print("[red]Invalid number of days.[/]")
            return
    else:
        days = days_val

    menu._selected_symbol = symbol
    menu._selected_timeframe = timeframe

    try:
        downloader = BinanceDownloader()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        menu.progress.start(100, f"Downloading {symbol}...")
        data = downloader.download(
            symbol, timeframe, start_date, end_date, menu.progress.update
        )
        menu.progress.update(100, 100, "Done")
        menu.progress.stop()
        
        menu.storage.save(data, symbol, timeframe)

        console.print(f"[green]✓ Downloaded {len(data)} candles[/]")
        console.print(f"[dim]Saved to: data/raw/{symbol}_{timeframe}.parquet[/]\n")

    except Exception as e:
        menu.progress.stop()
        console.print(f"[red]✗ Download failed: {e}[/]\n")
        logger.error(f"Download failed for {symbol}: {e}")
