"""``monte-neo verify --quotes``: strategy against the time its quotes arrived (see ``monte_neo.verify.arrival``)."""

from __future__ import annotations

import argparse
from typing import Any

from rich.console import Console

from monte_neo.cli.verify_cmd import _VERDICT_STYLE, _finish, _render_summary


def run_quotes(args: argparse.Namespace, console: Console) -> int:
    """Verify ``--strategy`` on ``--quotes``; exit codes as for ``monte-neo verify``."""
    from monte_neo.verify.quotes_verdict import verify_quotes

    if not args.strategy:
        console.print("[red]--quotes needs --strategy (signal(df) on bars of open, high, low, close, volume)[/]")
        return 3
    if args.recheck:
        from monte_neo.verify.quotes_verdict import recheck_quotes

        try:
            result = recheck_quotes(args.recheck, args.quotes, strategy=args.strategy)
        except Exception as exc:
            console.print(f"[red]recheck failed: {exc}[/]")
            return 3
        console.print_json(data=result)
        return 0 if result["reproduced"] else 4
    try:
        report = verify_quotes(
            args.quotes, strategy=args.strategy, bar_ms=args.bar_ms, commission_bps=args.commission_bps,
            slippage_bps=args.slippage_bps, warmup_bars=args.warmup_bars, samples=args.latency_samples,
            positions=args.positions, symbol=args.symbol, order_latency_ms=args.order_latency_ms,
        )
    except Exception as exc:  # input errors must not look like a verdict
        console.print(f"[red]verify failed: {exc}[/]")
        return 3
    return _finish(report, args, console)


def run_quotes_demo(console: Console) -> int:
    """A strategy that needs data before it arrived, and an honest slow one, on synthetic quotes."""
    import numpy as np

    from monte_neo.verify.quotes import synthetic_quotes
    from monte_neo.verify.quotes_verdict import verify_quotes
    from monte_neo.verify.verdict import model_from_costs

    def needs_data_before_it_arrives(df: Any) -> Any:
        return np.sign(df["close"].diff().fillna(0.0).to_numpy())  # reacts to a 10 ms bar the moment it closes

    def honest_slow_trend(df: Any) -> Any:
        return np.sign(df["close"].diff(3).fillna(0.0).to_numpy())  # three 1 s bars

    model = model_from_costs(commission_bps=0.2, slippage_bps=0.0)
    console.print("[bold]Demo:[/] two strategies on synthetic quotes with 5-275 ms latency (median 20 ms).\n")
    cases = (
        ("reacts to each 10 ms bar the moment it closes", needs_data_before_it_arrives, synthetic_quotes(30_000, rho=0.5), 10.0),
        ("three-bar trend on 1 s bars", honest_slow_trend, synthetic_quotes(40_000, rho=0.0, drift=1.5e-5, regime_steps=3000), 1000.0),
    )
    for name, fn, quotes, bar_ms in cases:
        report = verify_quotes(quotes, signal_fn=fn, bar_ms=bar_ms, model=model, samples=20)
        console.print(f"[bold]{name}[/]")
        console.print(f"[{_VERDICT_STYLE[report['verdict']]}]{report['verdict']}[/]  certificate {report['certificate_id']}")
        row = next(c for c in report["checks"] if c["id"] == "arrival_lookahead")
        console.print(f"Arrival look-ahead: {row['summary']}")
        _render_summary(report, console)
        console.print()
    console.print("Now try your own: [bold]monte-neo verify --quotes quotes.csv --strategy my_strategy.py --bar-ms 1000[/]")
    return 0


__all__ = ["run_quotes", "run_quotes_demo"]
