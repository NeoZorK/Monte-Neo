"""Monte-Neo verdict on the forward record: ``verify_returns`` in-process, recorded in the journal.

The forward net daily returns of the paper book and a buy-and-hold benchmark (equal weight of the run's symbols) are
written as CSV next to the journal; their SHA-256 and the certificate's id and verdict are journaled as ``certify``.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from monte_neo.deploy import account
from monte_neo.deploy.journal import Journal


def _write(path: Path, rows: list[tuple[str, float]]) -> str:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "return"])
        w.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def series(entries: list[dict[str, Any]]) -> dict[str, list[tuple[str, float]]]:
    marks = account.replay(entries, "paper")["marks"]
    strat = [(b["day"], b["nav"] / a["nav"] - 1.0) for a, b in zip(marks, marks[1:], strict=False) if a["nav"]]
    bench: list[tuple[str, float]] = []
    for a, b in zip(marks, marks[1:], strict=False):
        common = [s for s in a["prices"] if s in b["prices"]]
        if common:
            bench.append((b["day"], sum(b["prices"][s] / a["prices"][s] - 1.0 for s in common) / len(common)))
    return {"strategy": strat, "benchmark": bench}


def default_n_strategies(journal: Journal) -> int:
    st = journal.find("start")
    n = ((st[0]["body"].get("certificate") or {}).get("n_trials")) if st else None
    return max(1, int(n)) if n else 1


def certify(journal: Journal, n_strategies: int | None = None) -> dict[str, Any]:
    """Run Monte-Neo's own ``verify_returns`` on the recorded paper returns and journal the result."""
    from monte_neo.verify.returns_dd import load_returns, verify_returns

    n = default_n_strategies(journal) if n_strategies is None else max(1, int(n_strategies))
    s = series(list(journal.entries()))
    out = journal.path.parent / "certify"
    out.mkdir(exist_ok=True)
    rf, bf, cf = out / "forward_returns.csv", out / "benchmark_returns.csv", out / "certificate.json"
    r_sha, b_sha = _write(rf, s["strategy"]), _write(bf, s["benchmark"])
    try:
        cert = verify_returns(load_returns(rf), benchmark=load_returns(bf), n_strategies=n, periods_per_year=365)
    except ValueError as exc:  # too few days, flat series: not a verdict
        raise ValueError(f"cannot certify the forward returns yet: {exc}") from exc
    cf.write_text(json.dumps(cert, indent=2, default=str), encoding="utf-8")
    body = {"days": len(s["strategy"]), "returns_sha256": r_sha, "benchmark_sha256": b_sha, "n_strategies": n,
            "verdict": cert.get("verdict"), "certificate_id": cert.get("certificate_id"),
            "certificate_sha256": hashlib.sha256(cf.read_bytes()).hexdigest(),
            "engine_version": (cert.get("reproducibility") or {}).get("engine_version"),
            "reasons": list(cert.get("reasons", []))[:5]}
    journal.append("certify", body)
    return body
