"""validation-dossier/1: framework maps, limitations, the folder, the CLI and the MCP tool."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from monte_neo import disclaimer
from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli import dossier_cmd
from monte_neo.dossier import FRAMEWORKS, build_dossier, framework_map, write_dossier
from monte_neo.verify import verify_strategy


@pytest.fixture(scope="module")
def cert() -> dict:
    df = synthetic_ohlcv(900, seed=4)
    sig = np.sign(df["close"].pct_change(15).fillna(0.0).to_numpy())
    return json.loads(json.dumps(verify_strategy(df, signals=sig, n_trials=5, probe_checks=4)))


@pytest.mark.parametrize("name", sorted(FRAMEWORKS))
def test_every_framework_maps(cert: dict, name: str) -> None:
    fw = framework_map(cert, name)
    assert fw["clauses"] and all(c["coverage"] in ("covered", "partial", "not covered") for c in fw["clauses"])
    # a clause that needs a person is never shown as fully covered
    assert all(c["coverage"] != "covered" for c in fw["clauses"] if c["human_judgement"])


def test_monitoring_needs_a_live_report(cert: dict) -> None:
    without = {c["clause"]: c["coverage"] for c in framework_map(cert, "sr11-7")["clauses"]}
    with_live = {c["clause"]: c["coverage"] for c in framework_map(cert, "sr11-7", live=True)["clauses"]}
    assert without["Ongoing monitoring"] == "not covered" and with_live["Ongoing monitoring"] == "covered"
    with pytest.raises(ValueError, match="unknown framework"):
        framework_map(cert, "basel-99")


def test_dossier_folder(cert: dict, tmp_path: Path) -> None:
    d = build_dossier(cert, framework="ss1-23", meta={"name": "Mom 15", "owner": "Desk A", "purpose": "test"})
    assert d["schema"] == "validation-dossier/1" and d["certificate_id"] == cert["certificate_id"]
    assert any("Fills at the next bar's open" in x for x in d["limitations"])
    assert any("human judgement" in x for x in d["limitations"])
    out = write_dossier(d, cert, tmp_path / "dz")
    names = {p.name for p in out.iterdir()}
    assert names == {"dossier.html", "dossier.json", "certificate.json", "environment.json", "REPRODUCE.md", "limitations.md"}
    page = (out / "dossier.html").read_text(encoding="utf-8")
    assert "<script" not in page and "Sign-off" in page and disclaimer.FULL in page and "Mom 15" in page
    assert "not compliance" in page
    assert json.loads((out / "certificate.json").read_text())["certificate_id"] == cert["certificate_id"]
    assert cert["certificate_id"] in (out / "REPRODUCE.md").read_text()


def test_same_inputs_same_dossier_id(cert: dict) -> None:
    a = build_dossier(cert, framework="rts6", meta={"name": "x"})
    b = build_dossier(cert, framework="rts6", meta={"name": "x"})
    c = build_dossier(cert, framework="generic", meta={"name": "x"})
    assert a["dossier_id"] == b["dossier_id"] != c["dossier_id"]


def test_cli(cert: dict, tmp_path: Path) -> None:
    path = tmp_path / "cert.json"
    path.write_text(json.dumps(cert), encoding="utf-8")
    assert dossier_cmd.main(["--certificate", str(path), "--framework", "sr11-7", "--out", str(tmp_path / "d"), "--name", "X"]) == 0
    assert (tmp_path / "d" / "dossier.html").exists()
    assert dossier_cmd.main(["--out", str(tmp_path / "e")]) == 3
    assert dossier_cmd.main(["--certificate", str(tmp_path / "missing.json")]) == 3


def test_mcp_tool(cert: dict, tmp_path: Path) -> None:
    from monte_neo.mcp import tools

    path = tmp_path / "cert.json"
    path.write_text(json.dumps(cert), encoding="utf-8")
    out = tools.build_dossier(str(path), str(tmp_path / "m"), framework="generic", name="Y")
    assert out["dossier_id"] and Path(out["html"]).exists()
