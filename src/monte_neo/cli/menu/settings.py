"""Evolutionary settings workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import questionary
from rich.console import Console

from monte_neo.cli.styles import CUSTOM_STYLE

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()


def settings_workflow(menu: InteractiveMenu) -> None:
    """Settings menu for evolutionary parameters."""
    console.print("\n[bold cyan]⚙️  Evolutionary Settings[/]\n")

    choices = [
        {"name": f"👥 Population Size ({menu._pop_size})", "value": "pop_size"},
        {"name": f"🔄 Generations ({menu._generations})", "value": "generations"},
        {"name": f"🧪 Mutation Rate ({menu._mutation_rate:.2f})", "value": "mutation"},
        {"name": f"🧬 Crossover Rate ({menu._crossover_rate:.2f})", "value": "crossover"},
        {"name": f"🛡️  Stop Loss ({menu._stop_loss_pct:.1f}%)", "value": "sl"},
        {"name": f"🎯 Take Profit ({menu._take_profit_pct:.1f}%)", "value": "tp"},
        {"name": f"⚖️  Use SL/TP ({'✅' if menu._use_sl_tp else '❌'})", "value": "use_sl_tp"},
        {"name": "🔙 Back", "value": "back"},
    ]

    choice = questionary.select("Select setting to modify:", choices=choices, style=CUSTOM_STYLE).ask()

    if choice == "pop_size":
        val = questionary.text("Population Size:", default=str(menu._pop_size)).ask()
        if val: menu._pop_size = int(val)
    elif choice == "generations":
        val = questionary.text("Generations:", default=str(menu._generations)).ask()
        if val: menu._generations = int(val)
    elif choice == "mutation":
        val = questionary.text("Mutation Rate (0.0-1.0):", default=str(menu._mutation_rate)).ask()
        if val: menu._mutation_rate = float(val)
    elif choice == "crossover":
        val = questionary.text("Crossover Rate (0.0-1.0):", default=str(menu._crossover_rate)).ask()
        if val: menu._crossover_rate = float(val)
    elif choice == "sl":
        rr_choices = [
            {"name": f"Custom (%)", "value": "custom"},
            {"name": f"Conservative (0.5%)", "value": 0.5},
            {"name": f"Standard (1.0%)", "value": 1.0},
            {"name": f"Aggressive (2.0%)", "value": 2.0},
        ]
        val = questionary.select("Select Stop Loss:", choices=rr_choices, style=CUSTOM_STYLE).ask()
        if val == "custom":
            val = questionary.text("Stop Loss Percentage:", default=str(menu._stop_loss_pct)).ask()
            if val: menu._stop_loss_pct = float(val)
        elif val is not None:
            menu._stop_loss_pct = val
    elif choice == "tp":
        rr_choices = [
            {"name": f"Custom (%)", "value": "custom"},
            {"name": f"Risk Ratio 1:1 ({menu._stop_loss_pct * 1.0:.1f}%)", "value": menu._stop_loss_pct * 1.0},
            {"name": f"Risk Ratio 1.5:1 ({menu._stop_loss_pct * 1.5:.1f}%)", "value": menu._stop_loss_pct * 1.5},
            {"name": f"Risk Ratio 2:1 ({menu._stop_loss_pct * 2.0:.1f}%)", "value": menu._stop_loss_pct * 2.0},
            {"name": f"Risk Ratio 3:1 ({menu._stop_loss_pct * 3.0:.1f}%)", "value": menu._stop_loss_pct * 3.0},
        ]
        val = questionary.select("Select Take Profit (Risk Ratio):", choices=rr_choices, style=CUSTOM_STYLE).ask()
        if val == "custom":
            val = questionary.text("Take Profit Percentage:", default=str(menu._take_profit_pct)).ask()
            if val: menu._take_profit_pct = float(val)
        elif val is not None:
            menu._take_profit_pct = val
    elif choice == "use_sl_tp":
        menu._use_sl_tp = not menu._use_sl_tp
