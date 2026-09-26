"""Main CLI application.

Entry point for the Monte-Neo CLI.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from rich.console import Console

from monte_neo._version import __version__
from monte_neo.cli.menu import InteractiveMenu
from monte_neo.cli.styles import print_banner, print_error
from monte_neo.utils.config import load_config
from monte_neo.utils.logger import get_logger, setup_logging

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
console = Console()


class MonteNeoCLI:
    """Main CLI application class."""

    def __init__(self) -> None:
        """Initialize CLI."""
        self.config = load_config()
        self.menu = InteractiveMenu(self.config)

    def run(self, interactive: bool = True) -> int:
        """Run the CLI application.

        Args:
            interactive: Run in interactive mode.

        Returns:
            Exit code.
        """
        print_banner()

        if interactive:
            return self.menu.run()
        else:
            console.print("[yellow]Non-interactive mode not yet implemented[/]")
            return 1



    def run_holdout_sma(
        self,
        bars: int = 20_000,
        combos: int = 32,
        *,
        promote_mode: str = "holdout_positive",
        log_path: str | None = None,
        human_label: str | None = None,
    ) -> int:
        """Synthetic SMA holdout smoke (train/holdout split)."""
        from monte_neo.backtest import ExecutionModel, holdout_sma_sweep, synthetic_ohlcv
        from monte_neo.policy import HeuristicPolicy, append_research_label, build_research_state

        try:
            ohlc = synthetic_ohlcv(int(bars), seed=42)
            model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=50)
            report = holdout_sma_sweep(
                ohlc["open"],
                ohlc["high"],
                ohlc["low"],
                ohlc["close"],
                combos=int(combos),
                model=model,
                device="cpu_numba",
                promote_mode=promote_mode,
            )
            # Optional policy view on train export embedded via holdout metrics
            decision = HeuristicPolicy().decide(
                build_research_state(
                    {
                        "ok": report.get("ok", True),
                        "device": (report.get("train") or {}).get("device"),
                        "bars": (report.get("split") or {}).get("n_bars"),
                        "combos": (report.get("train") or {}).get("combos"),
                        "export_api_version": report.get("export_api_version"),
                        "engine": report.get("engine"),
                        "lane": report.get("lane"),
                        "model": report.get("model") or {},
                        "work_checklist": {
                            "next_bar_fill": True,
                            "fees": True,
                            "no_lookahead": True,
                            "cash_position_equity": True,
                        },
                        "timing": report.get("timing") or {},
                        "metrics": {
                            "best_return": (report.get("train") or {}).get("best_return"),
                            "rows": [
                                {
                                    "fast": r["fast"],
                                    "slow": r["slow"],
                                    "total_return": r["train_return"],
                                }
                                for r in (report.get("holdout") or {}).get("top_k") or []
                            ],
                        },
                    },
                    holdout_report=report,
                )
            )
            console.print_json(data={
                "schema": report["schema"],
                "split": report["split"],
                "metrics": report["metrics"],
                "train_best_pair": report["train"]["best_pair"],
                "holdout_at_best": report["holdout"]["at_train_best"],
                "policy": {
                    "next_action": decision.get("next_action"),
                    "promote_to_paper_oms": decision.get("promote_to_paper_oms"),
                    "overfit_risk": decision.get("overfit_risk"),
                },
            })
            for reason in report.get("reasons", []):
                console.print(f"[dim]- {reason}[/]")
            if log_path:
                append_research_label(
                    log_path,
                    holdout_report=report,
                    decision=decision,
                    human_label=human_label,
                    notes="cli --holdout-sma",
                )
                console.print(f"[green]Appended label → {log_path}[/]")
            return 0
        except Exception as e:
            console.print(f"[red]Holdout failed: {e}[/]")
            return 1

    def run_policy_triage(self, json_path: str) -> int:
        """Triage a research export JSON with HeuristicPolicy."""
        import json
        from pathlib import Path

        from monte_neo.policy import triage_export

        try:
            data = json.loads(Path(json_path).read_text(encoding="utf-8"))
            out = triage_export(data)
            console.print_json(data=out["decision"])
            for reason in out["decision"].get("reasons", []):
                console.print(f"[dim]- {reason}[/]")
            return 0
        except Exception as e:
            console.print(f"[red]Policy triage failed: {e}[/]")
            return 1

    def run_export(self, json_path: str) -> int:
        """Export an indicator to C++."""
        import json

        from monte_neo.core.optimization.production_exporter import ProductionExporter
        
        try:
            with open(json_path) as f:
                data = json.load(f)
            
            # Mock indicator for export
            from monte_neo.indicators.dynamic import DynamicIndicator
            indicator = DynamicIndicator()
            indicator.set_parameter("source_code", data.get("formula", ""))
            
            exporter = ProductionExporter()
            export_path = exporter.export(indicator, data.get("validation", {}))
            
            console.print(f"[green]Successfully exported to: {export_path}[/]")
            return 0
        except Exception as e:
            console.print(f"[red]Export failed: {e}[/]")
            return 1

    def run_evolve(self, symbol: str) -> int:
        """Run AI-driven evolution for a symbol."""
        from monte_neo.core.evolution_ai import AIEvolutionEngine
        from monte_neo.data.storage import ParquetStorage
        from monte_neo.utils.config import Config
        
        try:
            console.print(f"[bold cyan]Starting AI Evolution for {symbol}...[/]")
            config = Config()
            storage = ParquetStorage(config.data_dir)
            data = storage.load(symbol, timeframe=config.default_timeframe)
            
            if data is None or data.empty:
                console.print(f"[red]No data found for {symbol}[/]")
                return 1
                
            engine = AIEvolutionEngine()
            best_indicator = engine.evolve(data, {"profit_factor": 1.5, "sharpe_ratio": 1.0}, generations=5)
            
            console.print("[green]Evolution complete! Best formula:[/]")
            console.print(f"[bold white]{best_indicator.get_formula()}[/]")
            return 0
        except Exception as e:
            console.print(f"[red]Evolution failed: {e}[/]")
            return 1

    def run_headless(
        self,
        config_file: str,
    ) -> int:
        """Run in headless mode with config file.

        Args:
            config_file: Path to YAML config.

        Returns:
            Exit code.
        """
        from monte_neo.cli.headless import run_headless_generation

        return run_headless_generation(config_file)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="monte-neo",
        description="Monte-Neo research CLI. Strategy verifier: monte-neo verify --help",
    )

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        default=True,
        help="Run in interactive mode (default)",
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to YAML config file (for headless mode)",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode with config file",
    )

    parser.add_argument(
        "--export",
        type=str,
        help="Path to indicator JSON to export to C++",
    )
    parser.add_argument(
        "--policy-triage",
        type=str,
        help="Path to research export JSON (export_sma_sweep) for HeuristicPolicy triage",
    )
    parser.add_argument(
        "--holdout-sma",
        action="store_true",
        help="Run synthetic SMA train/holdout helper (anti-overfit smoke)",
    )
    parser.add_argument(
        "--holdout-bars",
        type=int,
        default=20_000,
        help="Bars for --holdout-sma synthetic series (default 20000)",
    )
    parser.add_argument(
        "--holdout-combos",
        type=int,
        default=32,
        help="Combos for --holdout-sma (default 32)",
    )
    parser.add_argument(
        "--promote-mode",
        type=str,
        default="holdout_positive",
        choices=["holdout_positive", "strict"],
        help="Holdout promote gate (default holdout_positive)",
    )
    parser.add_argument(
        "--holdout-log",
        type=str,
        help="Append JSONL research label (for a future LocalScorer corpus)",
    )
    parser.add_argument(
        "--human-label",
        type=str,
        help="Optional label written with --holdout-log (accept/reject/mc/skip)",
    )

    parser.add_argument(
        "--evolve",
        type=str,
        help="Symbol to run AI evolution for (e.g. BTCUSDT)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )

    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"monte-neo {__version__}",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        from monte_neo.cli.verify_cmd import main as verify_main

        return verify_main(sys.argv[2:])
    args = parse_args()

    # Setup logging
    setup_logging(args.log_level)

    try:
        app = MonteNeoCLI()

        if args.holdout_sma:
            return app.run_holdout_sma(
                bars=args.holdout_bars,
                combos=args.holdout_combos,
                promote_mode=args.promote_mode,
                log_path=args.holdout_log,
                human_label=args.human_label,
            )
        if args.policy_triage:
            return app.run_policy_triage(args.policy_triage)
        if args.export:
            return app.run_export(args.export)
        elif args.evolve:
            return app.run_evolve(args.evolve)
        elif args.headless and args.config:
            return app.run_headless(args.config)
        else:
            return app.run(interactive=args.interactive)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/]")
        sys.exit(0)

    except Exception as e:
        print_error(f"Error: {e}")
        logger.exception("Unhandled exception")
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
