"""Batch due diligence for allocators: one table for a folder of manager return files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from monte_neo import disclaimer

BATCH_SCHEMA_ID = "returns-batch/1"
SUFFIXES = (".csv", ".parquet")
_SEVERITY = {"REJECT": 0, "NEEDS_MORE_EVIDENCE": 1, "PASS_WITH_WARNINGS": 2, "PASS": 3}
_TONE = {"PASS": "good", "PASS_WITH_WARNINGS": "warn", "NEEDS_MORE_EVIDENCE": "note", "REJECT": "bad"}


def _files(paths_or_dir: str | Path | list[str | Path]) -> list[Path]:
    if isinstance(paths_or_dir, (str, Path)):
        folder = Path(paths_or_dir)
        if not folder.is_dir():
            raise ValueError(f"{folder} is not a folder")
        return sorted(p for p in folder.iterdir() if p.suffix.lower() in SUFFIXES and p.is_file())
    return [Path(p) for p in paths_or_dir]


def verify_returns_batch(
    paths_or_dir: str | Path | list[str | Path], *, n_strategies: int = 1, benchmark: Any = None
) -> dict[str, Any]:
    """Run the return-series due diligence on every manager file.

    Args:
        paths_or_dir: A folder (its ``.csv`` and ``.parquet`` files) or a list of files.
        n_strategies: How many strategies each manager ran (selection bias for the deflated Sharpe).
        benchmark: Optional benchmark (path or series) used for every manager.

    Returns:
        ``{"schema": "returns-batch/1", "rows", "errors", "disclaimer"}``; a file that cannot be read goes to ``errors``.
    """
    from monte_neo.verify.returns_dd import load_returns, verify_returns

    files = _files(paths_or_dir)
    bench = load_returns(benchmark) if isinstance(benchmark, (str, Path)) else benchmark
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in files:
        try:
            rep = verify_returns(load_returns(path), benchmark=bench, n_strategies=n_strategies)
        except Exception as exc:  # one broken file must not stop the batch
            errors.append({"file": path.name, "error": str(exc)})
            continue
        m = rep.get("metrics", {})
        rows.append({
            "manager": path.stem, "verdict": rep["verdict"], "certificate_id": rep["certificate_id"],
            "sharpe": m.get("sharpe"), "unsmoothed_sharpe": m.get("unsmoothed_sharpe"), "max_drawdown": m.get("max_drawdown"),
            "red_flags": [c["id"] for c in rep["checks"] if c["status"] in ("fail", "warn")],
        })
    rows.sort(key=lambda r: (_SEVERITY.get(r["verdict"], 0), -(r["sharpe"] or 0.0)))
    return {"schema": BATCH_SCHEMA_ID, "rows": rows, "errors": errors, "disclaimer": disclaimer.FULL}


def _f(value: Any, pct: bool = False) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.1f}%" if pct else f"{value:.2f}"


def render_batch_markdown(result: dict[str, Any]) -> str:
    """The batch as a Markdown table (managers sorted by verdict severity, then Sharpe)."""
    lines = ["| Manager | Verdict | Sharpe | Unsmoothed Sharpe | Max drawdown | Red flags | Certificate |", "|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        flags = ", ".join(r["red_flags"]) or "none"
        lines.append(f"| {r['manager']} | {r['verdict']} | {_f(r['sharpe'])} | {_f(r['unsmoothed_sharpe'])} | "
                     f"{_f(r['max_drawdown'], True)} | {flags} | `{r['certificate_id']}` |")
    if result["errors"]:
        lines += ["", "Files that could not be read:", ""] + [f"- {e['file']}: {e['error']}" for e in result["errors"]]
    return "\n".join(lines) + f"\n\n{result['disclaimer']}\n"


def render_batch_html(result: dict[str, Any]) -> str:
    """The batch as one page without scripts, printable to PDF."""
    from monte_neo.verify.report_html import _CSS, CSP, _e

    body = "".join(
        f"<tr><td><b>{_e(r['manager'])}</b></td><td><span class='pill {_TONE.get(r['verdict'], 'mute')}'>{_e(r['verdict'])}</span></td>"
        f"<td class='num'>{_f(r['sharpe'])}</td><td class='num'>{_f(r['unsmoothed_sharpe'])}</td>"
        f"<td class='num'>{_f(r['max_drawdown'], True)}</td><td>{_e(', '.join(r['red_flags']) or 'none')}</td>"
        f"<td class='mono'>{_e(r['certificate_id'])}</td></tr>"
        for r in result["rows"]
    )
    errs = "".join(f"<li>{_e(e['file'])}: {_e(e['error'])}</li>" for e in result["errors"])
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<meta http-equiv='Content-Security-Policy' content=\"{CSP}\">"
        f"<title>Manager due diligence</title><style>{_CSS}{disclaimer.HTML_CSS}</style></head><body><main>"
        "<h1>Manager due diligence</h1><p class='muted'>Return series only: smoothing, missing small losses, implausible "
        "consistency and significance. Sorted by verdict severity, then Sharpe.</p>"
        "<div class='card'><table><tr><th>Manager</th><th>Verdict</th><th class='num'>Sharpe</th><th class='num'>Unsmoothed Sharpe</th>"
        f"<th class='num'>Max drawdown</th><th>Red flags</th><th>Certificate</th></tr>{body}</table></div>"
        + (f"<h2>Files that could not be read</h2><div class='card'><ul>{errs}</ul></div>" if errs else "")
        + f"{disclaimer.html_footer()}</main></body></html>\n"
    )


__all__ = ["BATCH_SCHEMA_ID", "render_batch_html", "render_batch_markdown", "verify_returns_batch"]
