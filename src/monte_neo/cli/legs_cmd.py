"""``monte-neo verify --legs`` and ``--null-test``: catch P&L that the legs of a spread strategy never earned."""

from __future__ import annotations

import argparse
from functools import partial

from rich.console import Console

from monte_neo import disclaimer


def _exit(report: dict, args: argparse.Namespace, console: Console) -> int:
    from monte_neo.cli.verify_cmd import EXIT_CODES, _finish

    code = _finish(report, args, console)
    return code if code in EXIT_CODES.values() else 3


def run_legs(args: argparse.Namespace, console: Console) -> int:
    """Re-derive the P&L from the leg positions in ``--legs`` and compare it with the reported return."""
    from monte_neo.verify.legs import load_legs, verify_legs, write_fixed_returns

    try:
        body = load_legs(args.legs)
        report = verify_legs(body, tolerance=args.legs_tol, pnl=args.legs_pnl, periods_per_year=args.periods_per_year)
        if args.legs_fixed_out:
            path = write_fixed_returns(body, args.legs_fixed_out, pnl=args.legs_pnl)
            console.print(f"corrected returns (what the legs earn) written to {path}: check them with verify --returns")
    except Exception as exc:  # input errors must not look like a verdict
        console.print(f"[red]verify --legs failed: {exc}[/]")
        return 3
    return _exit(report, args, console)


def run_null_test(args: argparse.Namespace, console: Console) -> int:
    """Run the pairs strategy in ``--null-test`` on independent random walks."""
    from monte_neo.verify.nulltest import null_test

    try:
        bars, vol = args.null_bars, args.null_vol
        if args.null_like:
            import numpy as np

            from monte_neo.verify.legs import load_legs

            body = load_legs(args.null_like)
            bars = len(body)
            first = next(c for c in body.columns if c.startswith("px_"))
            vol = float(np.diff(np.log(body[first].to_numpy())).std(ddof=1))
        report = null_test(
            args.null_test, n_paths=args.null_paths, bars=bars, vol=vol, seed=args.null_seed, legs=args.null_legs,
            periods_per_year=args.periods_per_year or 252.0,
        )
    except Exception as exc:
        console.print(f"[red]verify --null-test failed: {exc}[/]")
        return 3
    return _exit(report, args, console)


def run_phantom_demo(console: Console) -> int:
    """The phantom-profit trap without files: the same pairs rule booked wrongly and booked correctly."""
    import numpy as np
    import pandas as pd

    from monte_neo.cli.verify_cmd import _VERDICT_STYLE
    from monte_neo.verify.legs import verify_legs
    from monte_neo.verify.nulltest import null_test
    from monte_neo.verify.phantom import pair_pnl, random_walk_pair

    log_y, log_x = random_walk_pair(5000, 0.01, np.random.default_rng(20261015))
    res = pair_pnl(log_y, log_x, 100)
    idx = pd.date_range("2024-01-01", periods=5000, freq="h")
    console.print("[bold]Demo:[/] a z-score pairs rule on two independent random walks (no relationship, no edge possible).\n")
    for name, key, booking in (("spread-change accounting (wrong)", "booked", "spread_change"), ("leg accounting (tradable)", "tradable", "legs")):
        table = pd.DataFrame({"px_y": np.exp(log_y), "px_x": np.exp(log_x), "qty_y": res["qty_y"], "qty_x": res["qty_x"], "reported_return": res[key]}, index=idx)
        report = verify_legs(table.iloc[101:], periods_per_year=8760.0)
        null = null_test(partial(_pnl, booking=booking), n_paths=40, bars=2000, periods_per_year=8760.0)
        console.print(f"[bold]{name}[/]")
        console.print(f"  --legs      [{_VERDICT_STYLE[report['verdict']]}]{report['verdict']}[/]  {report['checks'][1]['summary']}")
        console.print(f"  --null-test [{_VERDICT_STYLE[null['verdict']]}]{null['verdict']}[/]  {null['checks'][1]['summary']}")
    console.print("\nThe fix is one line: book pnl = position.shift(1) * (d_y - beta.shift(1) * d_x), not position * diff(spread).")
    console.print("Your own: [bold]monte-neo verify --legs legs.csv[/]  or  [bold]monte-neo verify --null-test pairs.py:pnl[/]")
    console.print(f"[dim]{disclaimer.SHORT}[/]")
    return 0


def _pnl(prices, booking: str):
    import numpy as np

    from monte_neo.verify.phantom import pair_pnl

    out = pair_pnl(np.log(prices["leg1"].to_numpy()), np.log(prices["leg2"].to_numpy()), 100, booking=booking)
    return out["pnl"]


__all__ = ["run_legs", "run_null_test", "run_phantom_demo"]
