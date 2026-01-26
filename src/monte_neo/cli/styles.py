"""CLI styles module.

Terminal styling and formatting.
"""

from __future__ import annotations

from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

# Questionary custom style (matches cline/claude code aesthetic)
CUSTOM_STYLE = Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "fg:white bold"),
        ("answer", "fg:green bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("separator", "fg:white"),
        ("instruction", "fg:white dim"),
        ("text", "fg:white"),
        ("disabled", "fg:white dim"),
    ]
)


def print_banner() -> None:
    """Print the application banner."""
    banner = Text()
    banner.append(
        "╔══════════════════════════════════════════════════════════╗\n", style="cyan"
    )  # noqa: E501
    banner.append("║", style="cyan")
    banner.append(
        "            🎲 Monte-Neo v0.0.1                           ",
        style="bold white",
    )  # noqa: E501
    banner.append("║\n", style="cyan")
    banner.append("║", style="cyan")
    banner.append(
        "      Monte Carlo Indicator Generator Framework           ",
        style="dim white",
    )  # noqa: E501
    banner.append("║\n", style="cyan")
    banner.append(
        "╚══════════════════════════════════════════════════════════╝", style="cyan"
    )  # noqa: E501

    console.print(banner)
    console.print()


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[bold green]✓[/] {message}")


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[bold red]✗[/] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[bold yellow]⚠[/] {message}")


def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[bold cyan]ℹ[/] {message}")


def print_section(title: str) -> None:
    """Print section header."""
    console.print(f"\n[bold cyan]━━━ {title} ━━━[/]\n")


def print_metrics_panel(metrics: dict) -> None:
    """Print metrics in a styled panel."""
    lines = []
    for key, value in metrics.items():
        if isinstance(value, float):
            lines.append(f"[cyan]{key}:[/] [green]{value:.4f}[/]")
        else:
            lines.append(f"[cyan]{key}:[/] [green]{value}[/]")

    panel = Panel(
        "\n".join(lines),
        title="[bold]Metrics[/]",
        border_style="cyan",
    )
    console.print(panel)


def format_number(value: float, decimals: int = 2) -> str:
    """Format number for display."""
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.{decimals}f}M"
    elif abs(value) >= 1_000:
        return f"{value / 1_000:.{decimals}f}K"
    else:
        return f"{value:.{decimals}f}"


def format_percentage(value: float) -> str:
    """Format as percentage."""
    return f"{value * 100:.1f}%"


def format_duration(seconds: float) -> str:
    """Format duration for display."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"
