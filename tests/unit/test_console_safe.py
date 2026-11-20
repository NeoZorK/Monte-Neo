from __future__ import annotations

import io
import sys

from monte_neo._console import ensure_safe_stdio


def test_legacy_code_page_does_not_crash(monkeypatch) -> None:
    buf = io.BytesIO()
    stream = io.TextIOWrapper(buf, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    ensure_safe_stdio()
    print("check ✓ → é")
    stream.flush()
    assert buf.getvalue().decode("cp1252") == "check ? ? é\n"


def test_utf8_stream_is_left_alone(monkeypatch) -> None:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    ensure_safe_stdio()
    assert stream.errors == "strict"
