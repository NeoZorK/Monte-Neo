"""``monte-neo alpha`` command."""

from __future__ import annotations

import json

import pytest

from monte_neo.alpha import demo_panel
from monte_neo.cli.alpha_cmd import main


def test_demo_runs(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--demo"])
    out = capsys.readouterr().out
    assert code == 2  # with the demo capital the noise score loses money after impact: REJECT
    assert "planted edge" in out and "pure noise score" in out and "Demo capital: 200,000" in out
    assert "Not investment advice" in out
    assert out.strip().splitlines()[-1].startswith("Checks whether a score predicts returns")


def test_files_json_and_exit_code(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    prices, real, noise = demo_panel(2, 20, 200)
    prices.to_csv(tmp_path / "p.csv", index=False)
    real.to_csv(tmp_path / "r.csv", index=False)
    noise.to_csv(tmp_path / "n.csv", index=False)
    out_path = tmp_path / "rep.json"
    assert main(["--ohlcv", str(tmp_path / "p.csv"), "--scores", str(tmp_path / "r.csv"), "--format", "json", "--out", str(out_path)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["schema"] == "alpha-report/1"
    assert json.loads(out_path.read_text())["verdict"] == printed["verdict"]
    assert main(["--ohlcv", str(tmp_path / "p.csv"), "--scores", str(tmp_path / "n.csv"), "--format", "json"]) in (0, 1)


def test_usage_and_input_errors(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 3
    prices, real, _ = demo_panel(0, 5, 20)
    prices.to_csv(tmp_path / "p.csv", index=False)
    real[real["symbol"] == "S00"].assign(symbol="ZZZ").to_csv(tmp_path / "s.csv", index=False)
    assert main(["--ohlcv", str(tmp_path / "p.csv"), "--scores", str(tmp_path / "s.csv")]) == 3
    assert "missing from prices" in capsys.readouterr().err
