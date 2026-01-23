"""Metrics display module."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


class MetricsDisplay:
    """Display trading metrics."""

    def show_metrics_table(self, metrics: dict) -> None:
        """Display metrics in a formatted table.

        Args:
            metrics: Dictionary of metric names to values.
        """
        table = Table(title="Trading Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Status", style="bold")

        targets = {
            "profit_factor": (2.0, ">="),
            "sharpe_ratio": (1.0, ">="),
            "sortino_ratio": (1.5, ">="),
            "max_drawdown": (0.20, "<="),
            "winrate": (0.45, ">="),
            "recovery_factor": (2.0, ">="),
            "calmar_ratio": (0.5, ">="),
        }

        for name, value in metrics.items():
            if isinstance(value, float):
                formatted = f"{value:.4f}"
            else:
                formatted = str(value)

            # Check against target
            status = ""
            if name in targets:
                target, op = targets[name]
                if op == ">=" and value >= target:
                    status = "[green]✓[/]"
                elif op == "<=" and value <= target:
                    status = "[green]✓[/]"
                else:
                    status = "[red]✗[/]"

            table.add_row(name, formatted, status)

        console.print(table)

    def show_metrics_panel(self, metrics: dict, title: str = "Metrics") -> None:
        """Display metrics in a panel.

        Args:
            metrics: Dictionary of metrics.
            title: Panel title.
        """
        lines = []
        for name, value in metrics.items():
            if isinstance(value, float):
                lines.append(f"[cyan]{name}:[/] {value:.4f}")
            else:
                lines.append(f"[cyan]{name}:[/] {value}")

        panel = Panel(
            "\n".join(lines),
            title=f"[bold]{title}[/]",
            border_style="cyan",
        )
        console.print(panel)

    def compare_metrics(
        self,
        before: dict,
        after: dict,
        title: str = "Metrics Comparison",
    ) -> None:
        """Compare two sets of metrics.

        Args:
            before: Before metrics.
            after: After metrics.
            title: Table title.
        """
        table = Table(title=title)
        table.add_column("Metric", style="cyan")
        table.add_column("Before", style="yellow")
        table.add_column("After", style="green")
        table.add_column("Change", style="bold")

        all_keys = set(before.keys()) | set(after.keys())

        for key in sorted(all_keys):
            before_val = before.get(key)
            after_val = after.get(key)

            before_str = (
                f"{before_val:.4f}"
                if isinstance(before_val, float)
                else str(before_val or "-")
            )
            after_str = (
                f"{after_val:.4f}"
                if isinstance(after_val, float)
                else str(after_val or "-")
            )

            # Calculate change
            change = ""
            if isinstance(before_val, (int, float)) and isinstance(
                after_val, (int, float)
            ):
                diff = after_val - before_val
                if diff > 0:
                    change = f"[green]+{diff:.4f}[/]"
                elif diff < 0:
                    change = f"[red]{diff:.4f}[/]"
                else:
                    change = "="

            table.add_row(key, before_str, after_str, change)

        console.print(table)
