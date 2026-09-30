"""First-run experience: the zero-input demo and the plain-language summary under the table."""

from __future__ import annotations

import io

from rich.console import Console

from monte_neo.cli.verify_cmd import EXIT_CODES, _render_summary, main


def _run(argv: list[str]) -> tuple[int, str]:
    import monte_neo.cli.verify_cmd as cmd

    buf = io.StringIO()
    original = cmd.Console
    cmd.Console = lambda *a, **k: Console(file=buf, width=200, force_terminal=False)  # type: ignore[assignment]
    try:
        code = main(argv)
    finally:
        cmd.Console = original  # type: ignore[assignment]
    return code, buf.getvalue()


def test_demo_needs_no_files_and_shows_a_leak_and_a_clean_run() -> None:
    code, out = _run(["--demo"])
    assert code == 0
    assert "leak found" in out and "clean, no future data used" in out
    assert out.count("certificate") == 2 and "In short:" in out and "Why:" in out
    assert "monte-neo verify --ohlcv" in out


def test_demo_is_deterministic() -> None:
    assert _run(["--demo"])[1] == _run(["--demo"])[1]


def test_summary_names_the_verdict_first_reason_and_step() -> None:
    buf = io.StringIO()
    report = {"verdict": "REJECT", "reasons": ["a: bad", "b: worse"], "next_actions": ["fix a", "fix b"]}
    _render_summary(report, Console(file=buf, width=200), with_next=True)
    out = buf.getvalue()
    assert "REJECT, do not trust" in out and "a: bad (+1 more)" in out and "Next: fix a" in out and "fix b" not in out


def test_summary_survives_a_report_without_reasons_or_steps() -> None:
    buf = io.StringIO()
    _render_summary({"verdict": "PASS"}, Console(file=buf, width=200))
    assert "no problem found" in buf.getvalue() and "Why:" not in buf.getvalue()
    _render_summary({"verdict": "SOMETHING_NEW"}, Console(file=buf, width=200))  # unknown verdict must not crash
    assert set(EXIT_CODES) >= {"PASS", "REJECT"}
