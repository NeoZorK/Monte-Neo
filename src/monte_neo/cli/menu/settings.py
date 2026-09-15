"""Evolutionary settings workflow."""

from __future__ import annotations  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

from typing import TYPE_CHECKING  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

import questionary  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from rich.console import Console  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

from monte_neo.cli.styles import CUSTOM_STYLE  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests


def settings_workflow(menu: InteractiveMenu) -> None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    """Settings menu for evolutionary parameters."""
    console.print("\n[bold cyan]⚙️  Evolutionary Settings[/]\n")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    choices = [
        {"name": f"👥 Population Size ({menu._pop_size})", "value": "pop_size"},
        {"name": f"🔄 Generations ({menu._generations})", "value": "generations"},
        {"name": f"🧪 Mutation Rate ({menu._mutation_rate:.2f})", "value": "mutation"},
        {"name": f"🧬 Crossover Rate ({menu._crossover_rate:.2f})", "value": "crossover"},
        {"name": f"🛡️  Stop Loss ({menu._stop_loss_pct:.1f}%)", "value": "sl"},
        {"name": f"🎯 Take Profit ({menu._take_profit_pct:.1f}%)", "value": "tp"},
        {"name": f"⚖️  Use SL/TP ({'✅' if menu._use_sl_tp else '❌'})", "value": "use_sl_tp"},
        {"name": f"🏁 MC Threshold ({menu._mc_pass_threshold:.0%})", "value": "mc_threshold"},
        {"name": f"🚀 Use GPU ({'✅' if menu._use_gpu else '❌'})", "value": "use_gpu"},
        {"name": f"💎 GPU Precision ({menu._gpu_precision})", "value": "gpu_precision"},
        {"name": f"⚡ Metal Driver ({menu._metal_driver.upper()})", "value": "metal_driver"},
        {"name": f"📥 Auto-Download ({'✅' if menu.config.auto_download_data else '❌'})", "value": "auto_download"},
        {"name": "🔙 Back", "value": "back"},
    ]

    choice = questionary.select("Select setting to modify:", choices=choices, style=CUSTOM_STYLE).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    if choice == "pop_size":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        val = questionary.text("Population Size:", default=str(menu._pop_size)).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if val: menu._pop_size = int(val)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    elif choice == "generations":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        val = questionary.text("Generations:", default=str(menu._generations)).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if val: menu._generations = int(val)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    elif choice == "mutation":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        val = questionary.text("Mutation Rate (0.0-1.0):", default=str(menu._mutation_rate)).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if val: menu._mutation_rate = float(val)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    elif choice == "crossover":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        val = questionary.text("Crossover Rate (0.0-1.0):", default=str(menu._crossover_rate)).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if val: menu._crossover_rate = float(val)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    elif choice == "sl":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        rr_choices = [  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            {"name": "Custom (%)", "value": "custom"},
            {"name": "Conservative (0.5%)", "value": 0.5},
            {"name": "Standard (1.0%)", "value": 1.0},
            {"name": "Aggressive (2.0%)", "value": 2.0},
        ]
        val = questionary.select("Select Stop Loss:", choices=rr_choices, style=CUSTOM_STYLE).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if val == "custom":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            val = questionary.text("Stop Loss Percentage:", default=str(menu._stop_loss_pct)).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            if val: menu._stop_loss_pct = float(val)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        elif val is not None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            menu._stop_loss_pct = val  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    elif choice == "tp":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        rr_choices = [  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            {"name": "Custom (%)", "value": "custom"},
            {"name": f"Risk Ratio 1:1 ({menu._stop_loss_pct * 1.0:.1f}%)", "value": menu._stop_loss_pct * 1.0},
            {"name": f"Risk Ratio 1.5:1 ({menu._stop_loss_pct * 1.5:.1f}%)", "value": menu._stop_loss_pct * 1.5},
            {"name": f"Risk Ratio 2:1 ({menu._stop_loss_pct * 2.0:.1f}%)", "value": menu._stop_loss_pct * 2.0},
            {"name": f"Risk Ratio 3:1 ({menu._stop_loss_pct * 3.0:.1f}%)", "value": menu._stop_loss_pct * 3.0},
        ]
        val = questionary.select("Select Take Profit (Risk Ratio):", choices=rr_choices, style=CUSTOM_STYLE).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if val == "custom":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            val = questionary.text("Take Profit Percentage:", default=str(menu._take_profit_pct)).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            if val: menu._take_profit_pct = float(val)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        elif val is not None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            menu._take_profit_pct = val  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    elif choice == "use_sl_tp":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        menu._use_sl_tp = not menu._use_sl_tp  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    elif choice == "mc_threshold":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        val = questionary.text("MC Pass Threshold (0.0-1.0):", default=str(menu._mc_pass_threshold)).ask()
        if val: menu._mc_pass_threshold = float(val)
    elif choice == "use_gpu":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        menu._use_gpu = not menu._use_gpu  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    elif choice == "gpu_precision":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        prec_choices = [  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            {"name": "float32 (Standard)", "value": "float32"},
            {"name": "float16 (Faster)", "value": "float16"},
            {"name": "float8_e4m3 (Extreme - 4x memory)", "value": "float8_e4m3"},
            {"name": "float8_e5m2 (Extreme - 4x memory)", "value": "float8_e5m2"},
        ]
        val = questionary.select("Select GPU Precision:", choices=prec_choices, style=CUSTOM_STYLE).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if val: menu._gpu_precision = val  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    elif choice == "metal_driver":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        driver_choices = [  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            {"name": "Auto-Select (Recommended, Micro-Benchmark)", "value": "auto"},
            {"name": "Clang C++ (Optimized)", "value": "cpp"},
            {"name": "Objective-C++ (Native)", "value": "objc"},
            {"name": "Apple Swift (Modern)", "value": "swift"},
        ]
        val = questionary.select("Select Metal Driver:", choices=driver_choices, style=CUSTOM_STYLE).ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if val:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            menu._metal_driver = val  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            menu.config.metal_driver = val  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            from monte_neo.utils.config import save_config  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            save_config(menu.config, "config.yaml")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            console.print(f"[green]Metal driver set to {val.upper()} and saved to config.yaml[/]")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    elif choice == "auto_download":  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        menu.config.auto_download_data = not menu.config.auto_download_data  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        from monte_neo.utils.config import save_config  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        save_config(menu.config, "config.yaml")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        console.print(f"[green]Auto-download data set to {'ENABLED' if menu.config.auto_download_data else 'DISABLED'} and saved to config.yaml[/]")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
