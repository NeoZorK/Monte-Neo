"""``monte-neo history | register | oracle | portfolio | doctor``: the project-level tools around ``verify``.

Exit codes: 0 fine, 2 regression (history diff / check) or data errors (doctor), 3 usage or input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _print(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


def history_main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="monte-neo history", description="Certificate history and diffs.")
    sub = p.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="append a certificate to the history")
    add.add_argument("certificate")
    add.add_argument("--label")
    add.add_argument("--commit")
    sub.add_parser("show", help="list the history")
    diff = sub.add_parser("diff", help="what changed between two certificates (exit 2 on a regression)")
    diff.add_argument("old")
    diff.add_argument("new")
    diff.add_argument("--markdown", action="store_true", help="print a pull-request comment")
    check = sub.add_parser("check", help="compare a certificate with the latest history entry (exit 2 on a regression)")
    check.add_argument("certificate")
    check.add_argument("--label")
    check.add_argument("--markdown", action="store_true")
    for s in (add, check):
        s.add_argument("--history", help="history file (default .monte-neo/history.jsonl)")
    show = sub.choices["show"]
    show.add_argument("--history")
    args = p.parse_args(argv)
    from monte_neo.verify.history import History, diff_certificates, render_markdown

    try:
        if args.cmd == "diff":
            d = diff_certificates(_load(args.old), _load(args.new))
        else:
            hist = History(args.history)
            if args.cmd == "add":
                _print(hist.add(_load(args.certificate), label=args.label, commit=args.commit))
                return 0
            if args.cmd == "show":
                rows = hist.log.entries()
                _print({"chain": hist.log.check(), "entries": [{k: r.get(k) for k in ("seq", "at", "label", "commit", "verdict", "certificate")} for r in rows]})
                return 0
            d = hist.compare(_load(args.certificate), args.label)
            if d is None:
                print("history is empty: nothing to compare with", file=sys.stderr)
                return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"history: {exc}", file=sys.stderr)
        return 3
    print(render_markdown(d) if args.markdown else json.dumps(d, indent=2, sort_keys=True))
    return 2 if d["regression"] else 0


def register_main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="monte-neo register", description="Write the hypothesis down before the test.")
    p.add_argument("--hypothesis", required=True, help="what you expect to find, and why")
    p.add_argument("--strategy", help="the strategy file to be tested (its normalised hash is stored)")
    p.add_argument("--params", help="parameters as JSON")
    p.add_argument("--n-trials", type=int, help="how many variants you plan to try")
    p.add_argument("--file", help="registrations file (default .monte-neo/registrations.jsonl)")
    args = p.parse_args(argv)
    from monte_neo.verify.register import Registry

    try:
        source = Path(args.strategy.split(":")[0]).read_text(encoding="utf-8") if args.strategy else None
        entry = Registry(args.file).register(args.hypothesis, source=source, params=json.loads(args.params) if args.params else None, n_trials=args.n_trials)
    except (OSError, ValueError) as exc:
        print(f"register: {exc}", file=sys.stderr)
        return 3
    print(f"registered as reg-{entry['seq']}-{entry['hash'][:8]} at {entry['at']}")
    print("use it: monte-neo verify ... --registration", f"reg-{entry['seq']}-{entry['hash'][:8]}")
    return 0


def oracle_main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="monte-neo oracle", description="Hold-out oracle (Thresholdout) for adaptive search.")
    sub = p.add_subparsers(dest="cmd", required=True)
    init = sub.add_parser("init")
    init.add_argument("--ohlcv", required=True)
    init.add_argument("--holdout", type=float, default=0.2)
    init.add_argument("--budget", type=int, default=10)
    init.add_argument("--threshold", type=float, default=0.5)
    init.add_argument("--sigma", type=float, default=0.2)
    query = sub.add_parser("query")
    query.add_argument("--ohlcv", required=True)
    query.add_argument("--strategy", required=True)
    sub.add_parser("status")
    for s in sub.choices.values():
        s.add_argument("--file", help="oracle file (default .monte-neo/oracle.jsonl)")
    args = p.parse_args(argv)
    from monte_neo.verify import load_ohlcv
    from monte_neo.verify.oracle import HoldoutOracle

    oracle = HoldoutOracle(args.file)
    try:
        if args.cmd == "init":
            e = oracle.init(load_ohlcv(args.ohlcv), holdout=args.holdout, budget=args.budget, threshold=args.threshold, sigma=args.sigma)
            print(f"oracle ready: hold-out {e['holdout']:.0%} of {e['bars']} bars, budget {e['budget']}")
        elif args.cmd == "query":
            _print(oracle.query(load_ohlcv(args.ohlcv), args.strategy))
        else:
            _print(oracle.status())
    except (OSError, ValueError) as exc:
        print(f"oracle: {exc}", file=sys.stderr)
        return 3
    return 0


def portfolio_main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="monte-neo portfolio", description="Verify a set of strategies together.")
    p.add_argument("--ohlcv", required=True)
    p.add_argument("strategies", nargs="+", help="strategy files 'path.py[:func]' (at least two)")
    args = p.parse_args(argv)
    from monte_neo.verify import load_ohlcv
    from monte_neo.verify.portfolio import verify_portfolio

    try:
        result = verify_portfolio(load_ohlcv(args.ohlcv), list(args.strategies), names=[Path(s.split(":")[0]).stem for s in args.strategies])
    except (OSError, ValueError) as exc:
        print(f"portfolio: {exc}", file=sys.stderr)
        return 3
    _print(result)
    return 0


def doctor_main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="monte-neo doctor", description="Known problems of a data provider's export.")
    p.add_argument("table", help="CSV or Parquet export")
    p.add_argument("--provider", default="auto", help="binance, yahoo, polygon, databento, tradingview, mt5 (default: guess)")
    args = p.parse_args(argv)
    from monte_neo.verify.doctor import diagnose

    try:
        result = diagnose(args.table, args.provider)
    except (OSError, ValueError, ImportError) as exc:
        print(f"doctor: {exc}", file=sys.stderr)
        return 3
    print(f"provider: {result['provider'] or 'unknown'} (match {result['confidence']}), {result['rows']} rows, status {result['status']}")
    for f in result["findings"]:
        print(f"  [{f['level']}] {f['code']}: {f['message']}\n      -> {f['advice']}")
    return 2 if result["status"] == "error" else 0
