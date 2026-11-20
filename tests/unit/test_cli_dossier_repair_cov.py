"""Branches of the dossier and repair command lines: the demo, a research funnel, plain-word explanations and previews."""

from __future__ import annotations

import json

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli import dossier_cmd, repair_cmd
from monte_neo.verify import verify_strategy

DF = synthetic_ohlcv(1200, seed=4)
LEAKY = "import numpy as np\n\ndef signal(df):\n    return np.sign(df['close'].shift(-1) - df['close']).fillna(0).to_numpy()\n"
CAUSAL = "import numpy as np\n\ndef signal(df):\n    return np.where(df['close'].rolling(20).mean() > df['close'].rolling(80).mean(), 1, 0)\n"


def _file(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def _cert(tmp_path, code):
    strat = _file(tmp_path, "s.py", code)
    rep = verify_strategy(DF, strategy=str(strat), n_trials=3, probe_checks=4)
    f = tmp_path / "cert.json"
    f.write_text(json.dumps(rep, default=str))
    return f, strat


# ---------------------------------------------------------------- dossier
def test_dossier_demo_lite_and_missing_inputs(tmp_path, capsys) -> None:
    assert dossier_cmd.main(["--demo", "--out", str(tmp_path / "d"), "--lite"]) == 0
    out = capsys.readouterr().out
    assert "wrote" in out and (tmp_path / "d" / "dossier-lite.html").exists() and (tmp_path / "d" / "dossier.html").exists()
    assert dossier_cmd.main([]) == 3 and "give --certificate" in capsys.readouterr().err
    assert dossier_cmd.main(["--certificate", str(tmp_path / "missing.json"), "--out", str(tmp_path / "x")]) == 3
    assert dossier_cmd.main(["--bogus"]) == 3


def test_dossier_with_a_research_funnel_and_a_second_certificate(tmp_path, capsys) -> None:
    cert, _ = _cert(tmp_path, CAUSAL)
    from monte_neo.research import ResearchProject

    ResearchProject.create(tmp_path / "proj", DF, DF["timestamp"].iloc[500], DF["timestamp"].iloc[900])
    code = dossier_cmd.main(["--certificate", str(cert), "--research", str(tmp_path / "proj"), "--also", str(cert), "--out", str(tmp_path / "dd")])
    assert code == 0 and "wrote" in capsys.readouterr().out and (tmp_path / "dd" / "dossier.json").exists()


# ---------------------------------------------------------------- repair: printing
def test_print_covers_every_branch_of_a_report(capsys) -> None:
    from rich.console import Console

    rep = {"outcome": "REPAIRED", "headline": "ok", "original": {"verdict": "REJECT"}, "corrections": [{"id": "C1", "rule": "r", "why": "w"}],
           "chosen": {"id": "R1", "steps": [("smooth", {"span": 5})], "why": "fewest defects"}, "dev": {"baseline_defects": 4, "chosen_defects": 1, "trials": 9},
           "lockbox": {"from": "2020-01-01T00:00:00", "verdict": "PASS", "total_return": 0.12}, "not_repairable": ["a defect only you can fix"]}
    repair_cmd._print("demo", rep, Console(width=200))
    out = capsys.readouterr().out
    for fragment in ("before: REJECT", "correction C1", "chosen on the first part", "defects on the development part", "lockbox (opened once", "needs you"):
        assert fragment in out
    repair_cmd._print("demo", {**rep, "original": {"verdict": "REJECT", "total_return": -0.2}, "chosen": None, "dev": None, "lockbox": None, "corrections": [], "not_repairable": []}, Console(width=200))
    assert "net -20.0%" in capsys.readouterr().out


# ---------------------------------------------------------------- repair: explain and preview
def test_explain_json_text_empty_and_bad_file(tmp_path, capsys) -> None:
    cert, _ = _cert(tmp_path, LEAKY)
    assert repair_cmd.main(["--explain", str(cert)]) == 0 and "why:" in capsys.readouterr().out
    assert repair_cmd.main(["--explain", str(cert), "--format", "json"]) == 0 and isinstance(json.loads(capsys.readouterr().out), list)
    quiet = _file(tmp_path, "q.json", json.dumps({"checks": [{"id": "x", "status": "pass", "category": "c", "summary": "", "details": {}}]}))
    assert repair_cmd.main(["--explain", str(quiet)]) == 0 and "No failed or warned check" in capsys.readouterr().out
    assert repair_cmd.main(["--explain", str(tmp_path / "none.json")]) == 3


def test_preview_paths(tmp_path, capsys) -> None:
    data = tmp_path / "d.csv"
    DF.to_csv(data, index=False)
    leaky = _file(tmp_path, "leaky.py", LEAKY)
    causal = _file(tmp_path, "causal.py", CAUSAL)
    assert repair_cmd.main(["--preview", "F03"]) == 3 and "needs --ohlcv" in capsys.readouterr().out
    assert repair_cmd.main(["--preview", "F03", "--ohlcv", str(data), "--strategy", str(leaky)]) == 0 and "before:" in capsys.readouterr().out
    assert repair_cmd.main(["--preview", "F03", "--ohlcv", str(data), "--strategy", str(leaky), "--format", "json"]) == 0 and json.loads(capsys.readouterr().out)["finding"] == "F03"
    assert repair_cmd.main(["--preview", "F01", "--ohlcv", str(data), "--strategy", str(causal)]) == 4 and "not applied" in capsys.readouterr().out
    assert repair_cmd.main(["--preview", "F99", "--ohlcv", str(data), "--strategy", str(causal)]) == 3


# ---------------------------------------------------------------- repair: main
def test_repair_main_inputs_and_a_single_strategy(tmp_path, capsys) -> None:
    assert repair_cmd.main([]) == 3 and "repair needs" in capsys.readouterr().out
    assert repair_cmd.main(["--bogus"]) == 3
    data = tmp_path / "d.csv"
    DF.to_csv(data, index=False)
    leaky = _file(tmp_path, "leaky.py", LEAKY)
    code = repair_cmd.main(["--ohlcv", str(data), "--strategy", str(leaky), "--out", str(tmp_path / "r"), "--budget", "6", "--n-trials", "2"])
    assert code in (0, 1, 2, 4) and (tmp_path / "r").is_dir()
    capsys.readouterr()
    assert repair_cmd.main(["--ohlcv", str(data), "--strategy", str(leaky), "--out", str(tmp_path / "r2"), "--budget", "6", "--format", "json"]) in (0, 1, 2, 4)
    assert '"outcome"' in capsys.readouterr().out
    assert repair_cmd.main(["--ohlcv", str(tmp_path / "nope.csv"), "--strategy", str(leaky)]) == 3


def test_repair_demo_writes_three_outcomes(tmp_path) -> None:
    assert repair_cmd.main(["--demo", "--out", str(tmp_path / "demo")]) == 0
