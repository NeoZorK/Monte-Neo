"""Trade visualization module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    pass

console = Console()


class TradeVisualizer:
    """Visualize trade results."""

    def show_trades_table(
        self,
        trades: list,
        limit: int = 20,
    ) -> None:
        """Display trades in a table.

        Args:
            trades: List of TradeResult objects.
            limit: Maximum trades to show.
        """
        table = Table(
            title=f"Trades (showing {min(limit, len(trades))} of {len(trades)})"
        )

        table.add_column("#", style="dim")
        table.add_column("Entry", style="cyan")
        table.add_column("Exit", style="cyan")
        table.add_column("Direction", style="blue")
        table.add_column("Entry Price", style="white")
        table.add_column("Exit Price", style="white")
        table.add_column("P&L %", style="green")

        for i, trade in enumerate(trades[:limit]):
            pnl_style = "green" if trade.pnl_pct > 0 else "red"
            direction = "LONG" if trade.direction == 1 else "SHORT"

            table.add_row(
                str(i + 1),
                str(trade.entry_idx),
                str(trade.exit_idx),
                direction,
                f"{trade.entry_price:.2f}",
                f"{trade.exit_price:.2f}",
                f"[{pnl_style}]{trade.pnl_pct * 100:.2f}%[/]",
            )

        console.print(table)

    def show_trade_summary(self, trades: list) -> None:
        """Show trade summary statistics.

        Args:
            trades: List of TradeResult objects.
        """
        if not trades:
            console.print("[yellow]No trades to display[/]")
            return

        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl < 0]

        table = Table(title="Trade Summary")
        table.add_column("Stat", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Trades", str(len(trades)))
        table.add_row("Winners", str(len(winners)))
        table.add_row("Losers", str(len(losers)))
        table.add_row("Win Rate", f"{len(winners) / len(trades) * 100:.1f}%")

        if winners:
            avg_win = sum(t.pnl_pct for t in winners) / len(winners)
            table.add_row("Avg Win", f"{avg_win * 100:.2f}%")

        if losers:
            avg_loss = sum(t.pnl_pct for t in losers) / len(losers)
            table.add_row("Avg Loss", f"{avg_loss * 100:.2f}%")

        console.print(table)
