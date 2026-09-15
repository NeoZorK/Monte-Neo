"""Hardware configuration workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from monte_neo.cli.styles import CUSTOM_STYLE

if TYPE_CHECKING:
    from monte_neo.cli.menu.main import InteractiveMenu

console = Console()


def hardware_workflow(menu: InteractiveMenu) -> None:
    """Hardware configuration menu."""
    console.print("\n[bold cyan]🔧 Hardware Configuration[/]\n")
    
    # Display current hardware info
    _show_hardware_info(menu)
    
    choices = [
        {"name": f"🚀 Use GPU ({'✅' if menu._use_gpu else '❌'})", "value": "toggle_gpu"},
        {"name": f"💎 GPU Precision ({menu._gpu_precision})", "value": "gpu_precision"},
        {"name": f"⚡ Metal Driver ({menu._metal_driver.upper()})", "value": "metal_driver"},
        {"name": f"🎯 MC Pass Threshold ({menu._mc_pass_threshold:.0%})", "value": "mc_threshold"},
        {"name": "📊 Benchmark Hardware", "value": "benchmark"},
        {"name": "🔙 Back", "value": "back"},
    ]
    
    choice = questionary.select("Select hardware option:", choices=choices, style=CUSTOM_STYLE).ask()
    
    if choice == "toggle_gpu":
        menu._use_gpu = not menu._use_gpu
        status = "enabled" if menu._use_gpu else "disabled"
        console.print(f"[green]GPU acceleration {status}[/]")
        
    elif choice == "gpu_precision":
        prec_choices = [
            {"name": "float32 (Standard - Best compatibility)", "value": "float32"},
            {"name": "float16 (Faster - Good performance)", "value": "float16"},
            {"name": "float8_e4m3 (Extreme - 4x memory bandwidth)", "value": "float8_e4m3"},
            {"name": "float8_e5m2 (Extreme - 4x memory bandwidth)", "value": "float8_e5m2"},
        ]
        val = questionary.select("Select GPU precision:", choices=prec_choices, style=CUSTOM_STYLE).ask()
        if val:
            menu._gpu_precision = val
            console.print(f"[green]GPU precision set to {val}[/]")
            
    elif choice == "metal_driver":
        if not menu._use_gpu:
            console.print("[yellow]⚠️  Enable GPU first to use Metal drivers[/]")
        else:
            driver_choices = [
                {"name": "Auto-Select (Recommended)", "value": "auto"},
                {"name": "Clang C++ (Optimized)", "value": "cpp"},
                {"name": "Objective-C++ (Native)", "value": "objc"},
                {"name": "Apple Swift (Modern)", "value": "swift"},
            ]
            val = questionary.select("Select Metal driver:", choices=driver_choices, style=CUSTOM_STYLE).ask()
            if val:
                menu._metal_driver = val
                # Update config object and save
                menu.config.metal_driver = val
                from monte_neo.utils.config import save_config
                save_config(menu.config, "config.yaml")
                console.print(f"[green]Metal driver set to {val.upper()} and saved to config.yaml[/]")
            
    elif choice == "mc_threshold":
        val = questionary.text("MC Pass Threshold (0.0-1.0):", default=str(menu._mc_pass_threshold)).ask()
        if val:
            menu._mc_pass_threshold = float(val)
            console.print(f"[green]MC pass threshold set to {menu._mc_pass_threshold:.0%}[/]")
            
    elif choice == "benchmark":
        _run_hardware_benchmark(menu)


def _show_hardware_info(menu: InteractiveMenu) -> None:
    """Display current hardware configuration."""
    
    # Check system capabilities
    try:
        import mlx.core as mx
        mlx_available = True
        device_info = mx.get_default_device() if hasattr(mx, 'get_default_device') else "Unknown"
    except ImportError:
        mlx_available = False
        device_info = "Not available"
    
    try:
        import Metal
        metal_available = Metal.MTLCreateSystemDefaultDevice() is not None
        if metal_available:
            device = Metal.MTLCreateSystemDefaultDevice()
            metal_info = f"{device.name()} - {device.maxThreadgroupMemoryLength()//1024}KB shared memory"
        else:
            metal_info = "No Metal device"
    except ImportError:
        metal_available = False
        metal_info = "Metal framework not available"
    
    # Create hardware info table
    table = Table(title="Hardware Configuration")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")
    
    table.add_row("GPU Acceleration", "✅ Enabled" if menu._use_gpu else "❌ Disabled",
                 f"MLX: {'Available' if mlx_available else 'Not available'}")
    table.add_row("GPU Precision", menu._gpu_precision,
                 "Memory bandwidth: 4x with float8" if menu._gpu_precision.startswith("float8") else "Standard")
    table.add_row("Metal Driver", menu._metal_driver.upper(),
                 metal_info if metal_available else "Metal not available")
    table.add_row("MC Pass Threshold", f"{menu._mc_pass_threshold:.0%}",
                 "Production readiness threshold")
    
    console.print(Panel(table, title="Current Configuration", border_style="blue"))


def _run_hardware_benchmark(menu: InteractiveMenu) -> None:
    """Run hardware performance benchmark."""
    console.print("\n[bold yellow]🏃 Running hardware benchmark...[/]\n")
    
    try:
        from monte_neo.core.acceleration.float8 import Float8Encoder
        
        # Test float8 performance
        test_sizes = [1000, 10000, 100000]
        
        table = Table(title="Float8 Performance Benchmark")
        table.add_column("Array Size", style="cyan")
        table.add_column("float32 Time (ms)", justify="right")
        table.add_column("float8 Time (ms)", justify="right")
        table.add_column("Speedup", justify="right")
        table.add_column("Memory Saved", justify="right")
        
        import time

        import numpy as np
        
        for size in test_sizes:
            # Create test data
            test_data = np.random.randn(size).astype(np.float32)
            
            # Test float32 operations
            start_time = time.time()
            result_f32 = test_data * 2.0 + 1.0
            f32_time = (time.time() - start_time) * 1000
            
            # Test float8 operations
            encoder = Float8Encoder("e4m3")
            start_time = time.time()
            packed = encoder.encode_array(test_data)
            unpacked = encoder.decode_array(packed)
            result_f8 = unpacked * 2.0 + 1.0
            f8_time = (time.time() - start_time) * 1000
            
            # Calculate metrics
            speedup = f32_time / f8_time if f8_time > 0 else 0
            memory_saved = "75%"  # 8/32 = 0.25, so 75% saved
            
            table.add_row(
                f"{size:,}",
                f"{f32_time:.2f}",
                f"{f8_time:.2f}",
                f"{speedup:.2f}x",
                memory_saved
            )
        
        console.print(table)
        console.print("\n[green]✅ Benchmark completed![/]")
        
    except Exception as e:
        console.print(f"[red]❌ Benchmark failed: {e}[/]")
        console.print("[yellow]💡 Make sure all dependencies are installed for float8 support[/]")
