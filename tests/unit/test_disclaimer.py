"""Every output carries the one "not investment advice" notice: certificates, HTML, MCP answers, README and docs."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo import disclaimer
from monte_neo.backtest import synthetic_ohlcv
from monte_neo.mcp.server import reporting_errors
from monte_neo.verify import verify_strategy
from monte_neo.verify.report_html import render_html

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def report() -> dict:
    df = synthetic_ohlcv(600, seed=3)
    signals = pd.Series(np.sign(df["close"].pct_change(5).fillna(0.0)).to_numpy())
    return json.loads(json.dumps(verify_strategy(df, signals=signals, probe_checks=4)))


def test_texts_say_what_they_must() -> None:
    for text in (disclaimer.SHORT, disclaimer.FULL):
        assert text.startswith("Not investment advice")
        assert "promise of profit" in text
        assert "do not predict future returns" in text
    assert "call to buy, sell or trade" in disclaimer.FULL


def test_certificate_carries_scope_and_notice(report: dict) -> None:
    assert report["disclaimer"] == f"{disclaimer.SCOPE} {disclaimer.SHORT}"


def test_html_footer_is_full_readable_and_last(report: dict) -> None:
    page = render_html(report)
    assert disclaimer.FULL in page
    assert page.rindex(disclaimer.FULL) > page.rindex("<h2>")  # at the bottom, after every section
    size = re.search(r"\.disclaimer\{font-size:(\d+)px", page)
    assert size is not None and int(size.group(1)) >= 12  # small, but not fine print


def test_every_mcp_answer_has_the_notice() -> None:
    def tool() -> dict:
        return {"ok": True}

    def failing() -> dict:
        raise ValueError("bad path")

    assert reporting_errors(tool)()["disclaimer"] == disclaimer.SHORT
    assert "error" in reporting_errors(failing)()
    kept = reporting_errors(lambda: {"disclaimer": "own"})()
    assert kept["disclaimer"] == "own"


def test_readme_and_docs_footer() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert disclaimer.FULL.replace("Not investment advice. ", "") in readme
    assert "Not investment advice." in (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
