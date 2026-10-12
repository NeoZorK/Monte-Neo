"""Allocator due diligence on return series: three demo managers through ``verify_returns``.

``demo_returns()`` returns an honest manager, a smoothed one (returns averaged over three months) and one that rounds
small losses up to small gains. The table shows the verdict and the red flags per manager.

Run: uv run python examples/allocator_dd.py
"""

from __future__ import annotations

from monte_neo.disclaimer import SHORT
from monte_neo.verify.returns_dd import demo_returns, verify_returns


def main() -> None:
    print(f"{'manager':10s} {'verdict':14s} {'fail':>4s} {'warn':>4s}  first flag")
    for name, series in demo_returns().items():
        report = verify_returns(series)
        rows = report["checks"]
        flagged = [r for r in rows if r["status"] in ("fail", "warn")]
        first = flagged[0]["id"] if flagged else "-"
        print(f"{name:10s} {report['verdict']:14s} {sum(r['status'] == 'fail' for r in rows):4d} {sum(r['status'] == 'warn' for r in rows):4d}  {first}")


if __name__ == "__main__":
    main()
    print(SHORT)
