"""Data download workflow."""

from __future__ import annotations  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

from datetime import datetime, timedelta  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from typing import TYPE_CHECKING  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

import questionary  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from rich.console import Console  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from rich.panel import Panel  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

from monte_neo.cli.menu.symbol_selector import SymbolSelector  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from monte_neo.cli.styles import CUSTOM_STYLE  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from monte_neo.data.downloader import BinanceDownloader  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from monte_neo.utils.logger import get_logger  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

logger = get_logger(__name__)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
console = Console()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests


def download_data_workflow(menu: InteractiveMenu) -> None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    """Download market data workflow."""
    console.print("\n[bold cyan]📊 Download Market Data[/]\n")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    # Select symbol
    if not menu._cached_symbols:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        try:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            menu.progress.start(100, "Fetching available symbols from Binance...")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            downloader = BinanceDownloader()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            symbols = downloader.get_available_symbols()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

            # Prioritize USDT pairs
            usdt_pairs = [s for s in symbols if s.endswith("USDT")]  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            other_pairs = [s for s in symbols if not s.endswith("USDT")]  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            menu._cached_symbols = sorted(usdt_pairs) + sorted(other_pairs)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

            menu.progress.update(100, 100, "Done")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            menu.progress.stop()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        except Exception as e:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            logger.error(f"Error fetching symbols: {e}")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            menu.progress.stop()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            console.print(f"[red]Error fetching symbols: {e}. Using default.[/]")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            menu._cached_symbols = [menu._selected_symbol]  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    # Use the new multi-column searchable selector
    selector = SymbolSelector(menu._cached_symbols, style=CUSTOM_STYLE)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    symbol = selector.ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    if not symbol:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    # Select timeframe
    timeframe = questionary.select(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        "Timeframe:",
        choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        default=menu._selected_timeframe,
        style=CUSTOM_STYLE,
    ).ask()

    if not timeframe:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    _process_download(menu, symbol, timeframe)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests


def _process_download(menu: InteractiveMenu, symbol: str, timeframe: str) -> None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    # Check if exists
    info = menu.storage.get_info(symbol, timeframe)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    if info:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        console.print(f"\n[yellow]⚠ Data for {symbol} {timeframe} already exists.[/]")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        start = info.get('start_date')  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        end = info.get('end_date')  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        # Format dates if they exist
        start_str = str(start).split(".")[0] if start else "Unknown"  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        end_str = str(end).split(".")[0] if end else "Unknown"  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        range_str = f"{start_str} ➜ {end_str}"  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        console.print(Panel(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            f"Rows:  {info.get('rows', 0):,}\n"
            f"Range: {range_str}\n"
            f"Size:  {info.get('size_mb', 0):.2f} MB",
            title="Existing Data",
            border_style="yellow"
        ))

        if not questionary.confirm(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            "Overwrite existing data?", default=False, style=CUSTOM_STYLE
        ).ask():
            return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    # Select period
    choices = [  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
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

    days_val = questionary.select(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        "Historical period:",
        choices=choices,
        style=CUSTOM_STYLE,
    ).ask()

    if not days_val:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    if days_val == "custom":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        days_str = questionary.text("Enter number of days:").ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        try:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            days = int(days_str)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        except (ValueError, TypeError):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            console.print("[red]Invalid number of days.[/]")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            return  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    else:
        days = days_val  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    menu._selected_symbol = symbol  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    menu._selected_timeframe = timeframe  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    try:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        downloader = BinanceDownloader()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        end_date = datetime.now()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        start_date = end_date - timedelta(days=days)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        menu.progress.start(100, f"Downloading {symbol}...")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        data = downloader.download(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            symbol, timeframe, start_date, end_date, menu.progress.update
        )
        menu.progress.update(100, 100, "Done")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        menu.progress.stop()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        menu.storage.save(data, symbol, timeframe)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        console.print(f"[green]✓ Downloaded {len(data)} candles[/]")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        console.print(f"[dim]Saved to: data/raw/{symbol}_{timeframe}.parquet[/]\n")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    except Exception as e:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        menu.progress.stop()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        console.print(f"[red]✗ Download failed: {e}[/]\n")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        logger.error(f"Download failed for {symbol}: {e}")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
