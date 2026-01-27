"""Portfolio management menu workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING
import questionary
from rich.console import Console
from rich.table import Table

from monte_neo.cli.styles import CUSTOM_STYLE
from monte_neo.core.portfolio import PortfolioManager

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()

def portfolio_workflow(menu: InteractiveMenu) -> None:
    """Portfolio management sub-menu."""
    # Initialize manager if not exists (in a real app, we'd load it from config/storage)
    if not hasattr(menu, "_portfolio_manager"):
        menu._portfolio_manager = PortfolioManager()

    while True:
        choices = [
            {"name": "📋 View Portfolio Summary", "value": "summary"},
            {"name": "➕ Add Indicator to Portfolio", "value": "add_asset"},
            {"name": "📊 Analyze Correlations", "value": "correlations"},
            {"name": "⚖️  Optimize Weights (Kelly/Risk Parity)", "value": "optimize"},
            {"name": "🔙 Back to Main Menu", "value": "back"},
        ]

        choice = questionary.select(
            "Portfolio Management:",
            choices=choices,
            style=CUSTOM_STYLE
        ).ask()

        if choice == "back" or choice is None:
            break
        
        if choice == "summary":
            _show_summary(menu._portfolio_manager)
        elif choice == "add_asset":
            _add_asset_workflow(menu)
        elif choice == "correlations":
            console.print("[yellow]Correlation analysis requires multiple active assets with history...[/]")
        elif choice == "optimize":
            console.print("[yellow]Optimization logic being implemented...[/]")

def _show_summary(manager: PortfolioManager) -> None:
    summary = manager.get_portfolio_summary()
    
    table = Table(title="Portfolio Summary")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="magenta")
    
    table.add_row("Total Assets", str(summary["total_assets"]))
    table.add_row("Active Assets", str(summary["active_assets"]))
    table.add_row("Initial Capital", f"${summary['initial_capital']:.2f}")
    
    console.print(table)
    
    if summary["weights"]:
        weight_table = Table(title="Asset Weights")
        weight_table.add_column("Asset ID", style="cyan")
        weight_table.add_column("Weight", style="green")
        
        for asset_id, weight in summary["weights"].items():
            weight_table.add_row(asset_id, f"{weight:.2%}")
        
        console.print(weight_table)

def _add_asset_workflow(menu: InteractiveMenu) -> None:
    # In a real app, this would list generated indicators from exports/production
    import os
    from pathlib import Path
    
    production_dir = Path("exports/production")
    if not production_dir.exists():
        console.print("[red]No production indicators found in exports/production[/]")
        return
        
    indicators = list(production_dir.glob("*.json"))
    if not indicators:
        console.print("[red]No .json indicators found[/]")
        return
        
    indicator_choices = [{"name": idx.name, "value": str(idx)} for idx in indicators]
    selected_idx = questionary.select(
        "Select indicator to add:",
        choices=indicator_choices,
        style=CUSTOM_STYLE
    ).ask()
    
    if selected_idx:
        from monte_neo.core.portfolio import PortfolioAsset
        asset_id = Path(selected_idx).stem
        asset = PortfolioAsset(
            id=asset_id,
            indicator_path=selected_idx,
            symbol=menu._selected_symbol
        )
        menu._portfolio_manager.add_asset(asset)
        console.print(f"[green]Successfully added {asset_id} to portfolio![/]")
