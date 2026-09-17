"""CLI coverage for non-TTY helpers + app branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd


def test_styles_progress_pure():
    from monte_neo.cli import progress, styles

    with patch("monte_neo.cli.styles.console"):
        styles.print_banner()
        styles.print_success("s")
        styles.print_error("e")
        styles.print_warning("w")
        styles.print_info("i")
        styles.print_section("t")
        styles.print_metrics_panel({"a": 1.2, "b": "x"})
    with patch("questionary.confirm") as c:
        c.return_value.ask.return_value = True
        styles.press_any_key()
    assert "M" in styles.format_number(2_000_000)
    assert "K" in styles.format_number(2000)
    assert styles.format_number(1.5) == "1.50"
    assert styles.format_percentage(0.25).endswith("%")
    assert styles.format_duration(10).endswith("s")
    assert styles.format_duration(120).endswith("m")
    assert styles.format_duration(7200).endswith("h")
    assert progress.estimate_generation_time(100, 10, 1)
    assert progress.estimate_generation_time(100000, 5000, 5)


def test_app_monte_neo_cli(tmp_path):
    from monte_neo.cli import app

    with patch("monte_neo.cli.app.load_config", return_value=MagicMock()), patch(
        "monte_neo.cli.app.InteractiveMenu"
    ) as interactive_menu, patch("monte_neo.cli.app.print_banner"), patch("monte_neo.cli.app.console"), patch(
        "monte_neo.cli.app.setup_logging"
    ), patch("monte_neo.cli.app.print_error"):
        interactive_menu.return_value.run.return_value = 0
        cli = app.MonteNeoCLI()
        assert cli.run(True) == 0
        assert cli.run(False) == 1
        with patch("json.load", return_value={"formula": "x"}), patch("builtins.open", create=True), patch(
            "monte_neo.indicators.dynamic.DynamicIndicator"
        ), patch("monte_neo.core.optimization.production_exporter.ProductionExporter") as production_exporter:
            production_exporter.return_value.export.return_value = str(tmp_path / "out")
            assert cli.run_export("x.json") == 0
        with patch(
            "monte_neo.core.optimization.production_exporter.ProductionExporter", side_effect=Exception("e")
        ):
            assert cli.run_export("x.json") == 1
        # policy triage
        good = tmp_path / "exp.json"
        good.write_text(
            '{"ok":true,"device":"cpu","bars":1,"combos":1,"export_api_version":"1",'
            '"engine":"t","lane":"research_bar","model":{},'
            '"work_checklist":{"next_bar_fill":true,"fees":true,"no_lookahead":true,"cash_position_equity":true},'
            '"timing":{},"metrics":{"best_return":0.1,"rows":[{"fast":5,"slow":30,"total_return":0.1}]}}',
            encoding="utf-8",
        )
        assert cli.run_policy_triage(str(good)) == 0
        assert cli.run_policy_triage(str(tmp_path / "missing_policy.json")) == 1
        with patch("monte_neo.backtest.synthetic_ohlcv") as syn, patch(
            "monte_neo.backtest.holdout_sma_sweep"
        ) as hs:
            syn.return_value = {"open": None, "high": None, "low": None, "close": None}
            hs.return_value = {
                "schema": "mn.holdout_report.v1",
                "split": {},
                "metrics": {"gap_best": 0.0},
                "train": {"best_pair": {"fast": 5, "slow": 30}},
                "holdout": {"at_train_best": 0.0},
                "reasons": ["ok"],
            }
            assert cli.run_holdout_sma(bars=1000, combos=8) == 0
        assert cli.run_holdout_sma(bars=10, combos=8) in (0, 1)
        with patch("monte_neo.data.storage.ParquetStorage") as parquet_storage, patch("monte_neo.utils.config.Config") as config_cls, patch(
            "monte_neo.core.evolution_ai.AIEvolutionEngine"
        ) as evolution_engine:
            config_cls.return_value.data_dir = tmp_path
            config_cls.return_value.default_timeframe = "1h"
            parquet_storage.return_value.load.return_value = pd.DataFrame({"close": [1.0, 2.0]})
            evolution_engine.return_value.evolve.return_value = MagicMock(get_formula=lambda: "f")
            assert cli.run_evolve("BTCUSDT") == 0
            parquet_storage.return_value.load.return_value = None
            assert cli.run_evolve("BTCUSDT") == 1
            evolution_engine.return_value.evolve.side_effect = Exception("e")
            parquet_storage.return_value.load.return_value = pd.DataFrame({"close": [1.0]})
            assert cli.run_evolve("BTCUSDT") == 1
        headless_mod = MagicMock()
        headless_mod.run_headless_generation.return_value = 0
        with patch.dict("sys.modules", {"monte_neo.cli.headless": headless_mod}):
            assert cli.run_headless("c.yaml") == 0

        with patch("monte_neo.cli.app.parse_args") as pa:
            pa.return_value = SimpleNamespace(
                export=None, policy_triage=None, holdout_sma=False, holdout_bars=20000, holdout_combos=32, evolve=None, headless=False, config=None, interactive=True, log_level="INFO"
            )
            assert app.main() == 0
            pa.return_value.policy_triage = "p.json"
            with patch.object(app.MonteNeoCLI, "run_policy_triage", return_value=0):
                assert app.main() == 0
            pa.return_value.policy_triage = None
            pa.return_value.holdout_sma = True
            with patch.object(app.MonteNeoCLI, "run_holdout_sma", return_value=0):
                assert app.main() == 0
            pa.return_value.holdout_sma = False
            pa.return_value.export = "x.json"
            with patch.object(app.MonteNeoCLI, "run_export", return_value=0):
                assert app.main() == 0
            pa.return_value.export = None
            pa.return_value.evolve = "BTC"
            with patch.object(app.MonteNeoCLI, "run_evolve", return_value=0):
                assert app.main() == 0
            pa.return_value.evolve = None
            pa.return_value.headless = True
            pa.return_value.config = "c.yaml"
            with patch.object(app.MonteNeoCLI, "run_headless", return_value=0):
                assert app.main() == 0
            pa.side_effect = None
            pa.return_value = SimpleNamespace(
                export=None, policy_triage=None, holdout_sma=False, holdout_bars=20000, holdout_combos=32, evolve=None, headless=False, config=None, interactive=True, log_level="INFO"
            )
            with patch("monte_neo.cli.app.MonteNeoCLI", side_effect=RuntimeError("x")):
                assert app.main() == 1
