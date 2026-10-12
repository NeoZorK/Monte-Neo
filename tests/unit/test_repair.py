"""monte-neo repair: the four outcomes, the protocol's guarantees, the repaired file, the CLI and the MCP tool."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.repair import repair_strategy
from monte_neo.repair.demo import FLICKER, LEAK, UNSEEDED, trending_market
from monte_neo.repair.plan import candidates
from monte_neo.repair.runtime import TRANSFORMS
from monte_neo.verify import model_from_costs, recheck_certificate


def _file(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / f"{name}.py"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def flicker(tmp_path_factory) -> tuple[dict, Path, pd.DataFrame]:
    tmp = tmp_path_factory.mktemp("flicker")
    market = trending_market()
    rep = repair_strategy(market, str(_file(tmp, "flicker", FLICKER)), out_dir=tmp / "out",
                          model=model_from_costs(commission_bps=10, slippage_bps=10, n_bars=len(market)))
    return rep, tmp, market


def test_repaired_when_the_lockbox_confirms(flicker) -> None:
    rep, tmp, _ = flicker
    assert rep["outcome"] == "REPAIRED"
    assert rep["original"]["verdict"] == "REJECT" and rep["final"]["verdict"] in ("PASS", "PASS_WITH_WARNINGS")
    assert rep["lockbox"]["opened"] == 1 and rep["lockbox"]["total_return"] > 0
    assert rep["dev"]["chosen_defects"] < rep["dev"]["baseline_defects"]
    assert rep["dev"]["trials"] == 1 + len(rep["candidates"]) + 1  # every candidate is counted
    assert (tmp / "flicker.py").read_text(encoding="utf-8") == FLICKER  # the original is untouched


def test_choice_never_looks_at_returns(flicker) -> None:
    rep, _, _ = flicker
    assert set(rep["candidates"][0]) >= {"dev_defects", "dev_verdict"}
    assert not any("return" in k or "sharpe" in k for c in rep["candidates"] for k in c)


def test_repaired_file_is_self_contained_and_rechecks(flicker) -> None:
    rep, tmp, market = flicker
    target = tmp / "out" / "strategy.repaired.py"
    text = target.read_text(encoding="utf-8")
    assert "monte_neo" not in text.split('"""', 2)[2]  # runs without Monte-Neo installed
    market.to_csv(tmp / "m.csv", index=False)
    code = f"import pandas as pd, runpy; ns = runpy.run_path({str(target)!r}); print(len(ns['signal'](pd.read_csv({str(tmp / 'm.csv')!r}))))"
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == str(len(market))
    cert = json.loads((tmp / "out" / "certificate.json").read_text(encoding="utf-8"))
    assert recheck_certificate(cert, market, strategy=str(target))["reproduced"]


def test_leak_repaired_but_no_edge(tmp_path: Path) -> None:
    rep = repair_strategy(synthetic_ohlcv(1500, seed=3), str(_file(tmp_path, "leak", LEAK)), out_dir=tmp_path / "o")
    assert rep["outcome"] == "REPAIRED_NO_EDGE"
    assert any(c["id"] == "R1" for c in rep["corrections"]) and "negative" in json.dumps(rep["corrections"])


def test_not_repairable_and_nothing_to_repair(tmp_path: Path) -> None:
    bad = repair_strategy(synthetic_ohlcv(1200, seed=3), str(_file(tmp_path, "u", UNSEEDED)), out_dir=tmp_path / "u")
    assert bad["outcome"] == "NOT_REPAIRABLE" and any("determinism" in b for b in bad["not_repairable"])
    calm = "import numpy as np\n\ndef signal(df):\n    return np.zeros(len(df))\n"
    none = repair_strategy(synthetic_ohlcv(1200, seed=3), str(_file(tmp_path, "flat", calm)), out_dir=tmp_path / "f")
    assert none["outcome"] in ("NOTHING_TO_REPAIR", "REPAIRED_NO_EDGE")
    assert (tmp_path / "f" / "repair-report.json").exists()


def test_transforms_are_causal() -> None:
    df = synthetic_ohlcv(400, seed=2)
    pos = np.sign(np.random.default_rng(0).standard_normal(len(df)))
    for name, fn in TRANSFORMS.items():
        params = {"smooth": {"span": 5}, "hold": {"bars": 5}, "band": {"band": 0.3}, "tranche": {"every": 21, "sleeves": 4},
                  "voltarget": {"annual": 0.1, "span": 20}, "neutral": {}, "cap": {"cap": 0.5}, "liquidity": {"quantile": 0.2},
                  "delay": {"bars": 1}}[name]
        full = fn(pos, df, **params)
        cut = fn(pos[:250], df.iloc[:250].reset_index(drop=True), **params)
        assert np.allclose(full[:250], cut), name


def test_candidates_follow_defects() -> None:
    rows = [{"id": "net_profitability", "status": "fail"}, {"id": "capacity", "status": "warn"}, {"id": "sample_size", "status": "fail"}]
    got = candidates(rows, rebalance_every=21, budget=6)
    assert len(got) == 6 and {c["id"] for c in got} >= {"R5", "R9"} and any(c["id"] == "R7" for c in candidates(rows, 21, 50))
    assert candidates([{"id": "net_profitability", "status": "pass"}]) == []


def test_cli_and_mcp(tmp_path: Path) -> None:
    from monte_neo.cli import repair_cmd
    from monte_neo.mcp import tools

    data = tmp_path / "d.csv"
    synthetic_ohlcv(1200, seed=3).to_csv(data, index=False)
    leak = _file(tmp_path, "leak", LEAK)
    assert repair_cmd.main(["--ohlcv", str(data), "--strategy", str(leak), "--out", str(tmp_path / "c")]) == 1
    assert (tmp_path / "c" / "repair-report.html").exists()
    assert repair_cmd.main(["--out", str(tmp_path / "x")]) == 3
    res = tools.repair_strategy(str(data), str(leak), out_dir=str(tmp_path / "m"))
    assert res["outcome"] == "REPAIRED_NO_EDGE" and any(f.endswith("strategy.repaired.py") for f in res["files"])
