"""Dossier lite: the plain-language page, its disclaimer box and the --lite flag."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from monte_neo import disclaimer
from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli import dossier_cmd
from monte_neo.dossier import build_dossier, write_dossier
from monte_neo.dossier.lite import key_numbers, render_lite, top_reasons
from monte_neo.verify import verify_strategy


@pytest.fixture(scope="module")
def cert() -> dict:
    df = synthetic_ohlcv(900, seed=4)
    sig = np.sign(df["close"].pct_change(15).fillna(0.0).to_numpy())
    return json.loads(json.dumps(verify_strategy(df, signals=sig, n_trials=5, probe_checks=4)))


def test_lite_page(cert: dict) -> None:
    d = build_dossier(cert, meta={"name": "Demo"})
    page = render_lite(d)
    assert "<script" not in page
    assert page.count(disclaimer.FULL) >= 2  # box at the top and footer
    assert page.index(disclaimer.FULL) < page.index("Verdict:")
    assert d["verdict"] in page and "What this does not tell you" in page and d["reproduce"]["command"] in page
    assert 0 < len(key_numbers(d)) <= 5 and len(top_reasons(d)) <= 3


def test_write_and_cli(cert: dict, tmp_path: Path) -> None:
    d = build_dossier(cert)
    assert not (write_dossier(d, cert, tmp_path / "a") / "dossier-lite.html").exists()
    assert (write_dossier(d, cert, tmp_path / "b", lite=True) / "dossier-lite.html").exists()
    path = tmp_path / "cert.json"
    path.write_text(json.dumps(cert), encoding="utf-8")
    assert dossier_cmd.main(["--certificate", str(path), "--lite", "--out", str(tmp_path / "c")]) == 0
    assert (tmp_path / "c" / "dossier-lite.html").exists()
