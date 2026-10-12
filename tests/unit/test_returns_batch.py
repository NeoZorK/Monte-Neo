"""Batch due diligence on a folder of manager return files."""

from __future__ import annotations

from pathlib import Path

import pytest

from monte_neo.cli import verify_cmd
from monte_neo.verify.returns_batch import render_batch_html, render_batch_markdown, verify_returns_batch
from monte_neo.verify.returns_dd import demo_returns


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    for name, series in demo_returns(0).items():
        series.rename("return").rename_axis("date").reset_index().to_csv(tmp_path / f"{name}.csv", index=False)
    (tmp_path / "broken.csv").write_text("date,return\nnot-a-date,abc\n", encoding="utf-8")
    return tmp_path


def test_batch_rows_and_errors(folder: Path) -> None:
    res = verify_returns_batch(folder, n_strategies=3)
    assert res["schema"] == "returns-batch/1"
    assert {r["manager"] for r in res["rows"]} == {"honest", "smoothed", "too_good"}
    assert [e["file"] for e in res["errors"]] == ["broken.csv"]
    order = {"REJECT": 0, "NEEDS_MORE_EVIDENCE": 1, "PASS_WITH_WARNINGS": 2, "PASS": 3}
    assert [order[r["verdict"]] for r in res["rows"]] == sorted(order[r["verdict"]] for r in res["rows"])
    assert "honest" in render_batch_markdown(res)
    page = render_batch_html(res)
    assert "<script" not in page and "too_good" in page


def test_batch_cli(folder: Path, tmp_path: Path) -> None:
    out, html = tmp_path / "b.json", tmp_path / "b.html"
    code = verify_cmd.main(["--returns-dir", str(folder), "--n-strategies", "3", "--out", str(out), "--html", str(html)])
    assert code == 1 and out.exists() and "<script" not in html.read_text(encoding="utf-8")
    assert verify_cmd.main(["--returns-dir", str(tmp_path / "missing")]) == 3
