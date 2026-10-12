"""Every HTML page Monte-Neo writes is static: a Content-Security-Policy, no scripts, the notice at the bottom."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).parents[2] / "src" / "monte_neo"


def test_every_html_renderer_sets_a_content_security_policy() -> None:
    renderers = [p for p in SRC.rglob("*.py") if "<!doctype html>" in p.read_text(encoding="utf-8")]
    assert len(renderers) >= 5
    for path in renderers:
        text = path.read_text(encoding="utf-8")
        assert "Content-Security-Policy" in text, path
        assert "<script" not in text, path
        assert "html_footer()" in text, path  # the full not-investment-advice notice
        ast.parse(text)
