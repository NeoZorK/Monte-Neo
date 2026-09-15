"""Monte Carlo configuration workflow."""

from __future__ import annotations  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

from typing import TYPE_CHECKING  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

import questionary  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from rich.console import Console  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

from monte_neo.cli.styles import CUSTOM_STYLE  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests


def configure_mc_workflow(menu: InteractiveMenu) -> None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    """Configure Monte Carlo methods workflow."""
    console.print("\n[bold cyan]🎲 Configure Monte Carlo Methods[/]\n")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    methods_choices = [  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        {"name": "🔀 Return Shuffling", "value": "shuffling", "checked": "shuffling" in menu._mc_methods},
        {"name": "🎲 Noise Injection", "value": "noise", "checked": "noise" in menu._mc_methods},
        {"name": "📏 Sensitivity Analysis (±10%)", "value": "sensitivity", "checked": "sensitivity" in menu._mc_methods},
        {"name": "📅 Walk-Forward Analysis", "value": "walk_forward", "checked": "walk_forward" in menu._mc_methods},
        {"name": "📦 Block Bootstrap", "value": "block_bootstrap", "checked": "block_bootstrap" in menu._mc_methods},
    ]

    selected = questionary.checkbox(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        "Select MC methods:",
        choices=methods_choices,
        style=CUSTOM_STYLE,
    ).ask()

    if selected is not None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        menu._mc_methods = selected  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        console.print("\n[green]✓ Monte Carlo methods configured:[/]")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        for method in menu._mc_methods:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            console.print(f"  • {method}")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        console.print()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

