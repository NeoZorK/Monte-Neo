"""``monte-neo deploy``: run a verified strategy as a forward record on the Binance spot DEMO testnet.

Exit codes: 0 ok, 1 a check failed (journal chain, report verify), 2 target not available yet, 3 usage or input error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

EPILOG = """\
quick start (no keys, no network orders):
  monte-neo verify --ohlcv data.csv --strategy my_strategy.py --out cert.json
  monte-neo deploy init --strategy my_strategy.py --certificate cert.json --mode dry --first-day 2026-10-01
  monte-neo deploy run          # records every missing day up to today; safe to run again
  monte-neo deploy status
  monte-neo deploy serve        # dashboard on http://127.0.0.1:8787/ (--host 0.0.0.0 for the LAN)

my_strategy.py defines: target_weights(closes_by_symbol: dict[str, list[float]]) -> dict[str, float]
(long-only weights of total capital, each 0..1, sum <= 1). Guide: docs/guides/deploy.md.
Demo execution is not live trading. Not investment advice.
"""


def _common() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--var", default=os.environ.get("MONTE_NEO_DEPLOY_VAR", "var"), help="folder for the journal and its files (default ./var or $MONTE_NEO_DEPLOY_VAR)")
    p.add_argument("--run", default="default", help="run name: a folder under --var (default 'default')")
    p.add_argument("--target", default="local", help="where it runs: local (ssh, aws and gcp are not available yet)")
    return p


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="monte-neo deploy", description="Forward record of a verified strategy on the Binance spot demo testnet, with an evidence journal and a dashboard.",
                                 epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = _common()
    s = sub.add_parser("init", parents=[c], help="check eligibility and write the start entry (once per run)")
    s.add_argument("--strategy", required=True, help="Python file defining target_weights(closes_by_symbol)")
    s.add_argument("--certificate", required=True, help="Monte-Neo certificate JSON for this strategy (verdict must not be REJECT)")
    s.add_argument("--capital", type=float, default=10_000.0)
    s.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="comma-separated USDT pairs (spot pairs, or perpetuals with --market usdm)")
    s.add_argument("--first-day", default=None, help="first UTC day to record, YYYY-MM-DD (default today)")
    s.add_argument("--mode", default="testnet", help="testnet (demo orders), paper (no orders) or dry (simulated orders, no keys)")
    s.add_argument("--rebalance", default="weekly", help="daily or weekly")
    s.add_argument("--weekday", default="monday", help="rebalance weekday when weekly (default monday)")
    s.add_argument("--fee-bps", type=float, default=10.0, help="fee per side in basis points of the cost model")
    s.add_argument("--slippage-bps", type=float, default=5.0, help="slippage per side in basis points of the cost model")
    s.add_argument("--kill-drawdown", type=float, default=-0.15, help="paper drawdown from peak that stops trading (default -0.15)")
    s.add_argument("--market", default="spot", help="spot (Binance spot testnet, long-only) or usdm (Binance USD-M futures testnet, long and short)")
    s.add_argument("--leverage", type=float, default=1.0, help="gross exposure limit, the sum of |weights|: 1 on spot, up to 2 on usdm (default 1)")
    r = sub.add_parser("run", parents=[c], help="record every missing day up to today (idempotent)")
    r.add_argument("--until", default=None, help="last UTC day to record, YYYY-MM-DD (default today)")
    sub.add_parser("status", parents=[c], help="metrics and the journal check as JSON")
    sub.add_parser("verify", parents=[c], help="check the journal chain and the strategy file hash")
    sub.add_parser("dashboard", parents=[c], help="write <var>/<run>/site/index.html")
    sv = sub.add_parser("serve", parents=[c], help="serve the dashboard read-only")
    sv.add_argument("--host", default="127.0.0.1", help="bind address (use 0.0.0.0 for the LAN)")
    sv.add_argument("--port", type=int, default=8787)
    sub.add_parser("anchor", parents=[c], help="RFC 3161 timestamp of the journal head (one per day)")
    rp = sub.add_parser("report", parents=[c], help="write the evidence report and its manifest")
    rp.add_argument("--no-stress", action="store_true", help="skip the stress replays (no network)")
    rp.add_argument("--stress", action="append", default=[], metavar="NAME=START:END", help="stress window, repeatable (default: three public crypto stress windows)")
    rp.add_argument("--verify", action="store_true", help="recompute every number and compare with the saved manifest")
    ce = sub.add_parser("certify", parents=[c], help="Monte-Neo verdict on the recorded paper returns")
    ce.add_argument("--n-strategies", type=int, default=None, help="trials to price (default: n_trials of the start certificate)")
    ky = sub.add_parser("keys", parents=[c], help="testnet keys: status, or find them in local files (with consent) and store them in the Keychain")
    ky.add_argument("--list", action="store_true", help="only list candidate files (names, never values)")
    ky.add_argument("--yes", action="store_true", help="consent given: check and store every candidate without asking")
    ky.add_argument("--status", action="store_true", help="where keys come from and whether the testnet accepts them")
    ky.add_argument("--venue", default="binance_spot", help="binance_spot (spot testnet) or binance_usdm (futures testnet): separate accounts and keys")
    return ap


def _dump(obj: Any) -> None:
    print(json.dumps(obj, indent=1, default=str))


def _paths(a: argparse.Namespace) -> tuple[Path, Path]:
    folder = Path(a.var) / a.run
    return folder, folder / "journal.jsonl"


def _date(text: str | None, what: str) -> dt.date:
    if text is None:
        from monte_neo.deploy.runner import utc_today

        return utc_today()
    try:
        return dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{what} must be YYYY-MM-DD (got {text!r})") from exc


def _exchange(cfg: dict[str, Any]) -> Any:
    from monte_neo.deploy import connectors, keys

    v = connectors.venue(cfg)
    found = keys.resolve(v.id) if cfg["mode"] == "testnet" else None
    return connectors.exchange(v, cfg["mode"], capital=float(cfg["capital"]), fee_bps=cfg["cost_model"]["fee_bps"],
                               slippage_bps=cfg["cost_model"]["slippage_bps"], keys=found[:2] if found else None)


def _frozen(folder: Path, cfg: dict[str, Any]) -> Path:
    """The strategy copy made at init; refuses to run when it no longer matches the start entry."""
    from monte_neo.deploy.eligibility import file_sha256

    p = folder / "strategy.py"
    if not p.is_file():
        raise ValueError(f"{p} is missing: the run needs the strategy copy made at init")
    if file_sha256(p) != cfg["strategy"]["sha256"]:
        raise ValueError(f"{p} no longer matches the SHA-256 in the start entry: the strategy was changed after start. Begin a new run (--run NAME).")
    return p


def _init(a: argparse.Namespace) -> int:
    from monte_neo import __version__
    from monte_neo.deploy import runner
    from monte_neo.deploy.eligibility import check_certificate, check_settings, file_sha256, parse_weekday
    from monte_neo.deploy.journal import Journal
    from monte_neo.deploy.plugin import ENTRYPOINT, load

    symbols = [x.strip().upper() for x in a.symbols.split(",") if x.strip()]
    from monte_neo.deploy.connectors import venue

    check_settings(market=a.market, leverage=a.leverage, long_only=a.market == "spot", rebalance=a.rebalance, mode=a.mode,
                   capital=a.capital, symbols=symbols, fee_bps=a.fee_bps, slippage_bps=a.slippage_bps, kill_drawdown=a.kill_drawdown)
    v = venue(a.market)
    weekday = parse_weekday(a.weekday)
    first_day = _date(a.first_day, "--first-day")
    strategy = Path(a.strategy)
    load(strategy)  # fails early when the file has no target_weights
    eligible = check_certificate(a.certificate, strategy)
    folder, jpath = _paths(a)
    journal = Journal(jpath)
    if journal.find("start"):
        raise ValueError(f"run {a.run!r} already has a start entry; use another --run NAME for a new run")
    folder.mkdir(parents=True, exist_ok=True)
    frozen = folder / "strategy.py"
    shutil.copyfile(strategy, frozen)
    entry = runner.start_entry(journal, {
        "capital": a.capital, "symbols": symbols, "mode": a.mode, "target": "local", "venue": v.id, "max_gross": a.leverage, "rebalance": a.rebalance, "weekday": weekday,
        "cost_model": {"fee_bps": a.fee_bps, "slippage_bps": a.slippage_bps}, "kill_drawdown": a.kill_drawdown,
        "first_day": first_day.isoformat(), "lookback": runner.LOOKBACK,
        "strategy": {"file": strategy.name, "sha256": file_sha256(frozen), "entrypoint": ENTRYPOINT},
        "certificate": eligible["certificate"], "warnings": eligible["warnings"], "monte_neo_version": __version__,
    })
    _dump(entry)
    for w in eligible["warnings"]:
        print(f"warning: {w}", file=sys.stderr)
    return 0


def _run(a: argparse.Namespace) -> int:
    from monte_neo.deploy import dashboard, plugin, runner
    from monte_neo.deploy.journal import Journal

    folder, jpath = _paths(a)
    j = Journal(jpath)
    moved = j.repair_tail()
    if moved:
        j.append("repair", {"moved_aside": moved.name, "why": "incomplete last line after an interrupted write"})
    cfg = runner.config(j)
    fn = plugin.load(_frozen(folder, cfg))
    for r in runner.catch_up(j, _exchange(cfg), fn, _date(a.until, "--until")):
        print(json.dumps(r))
    dashboard.build(jpath, folder / "site")
    return 0


def _status(a: argparse.Namespace) -> int:
    from monte_neo.deploy import metrics
    from monte_neo.deploy.journal import Journal, verify

    _, jpath = _paths(a)
    _dump({"journal": verify(jpath), "summary": metrics.summary(list(Journal(jpath).entries()))})
    return 0


def _verify(a: argparse.Namespace) -> int:
    from monte_neo.deploy.eligibility import file_sha256
    from monte_neo.deploy.journal import Journal, verify

    folder, jpath = _paths(a)
    v = verify(jpath)
    st = Journal(jpath).find("start")
    if st and (folder / "strategy.py").is_file():
        v["strategy_matches_start"] = file_sha256(folder / "strategy.py") == st[0]["body"]["strategy"]["sha256"]
    _dump(v)
    return 0 if v["ok"] and v.get("strategy_matches_start", True) else 1


def _report(a: argparse.Namespace) -> int:
    from monte_neo.deploy import report as rpt

    folder, jpath = _paths(a)
    out = folder / "report"
    if a.verify:
        res = rpt.verify(jpath, out)
    else:
        if a.no_stress:
            windows = None
        elif a.stress:
            windows = dict(rpt.parse_window(x) for x in a.stress)
        else:
            windows = dict(rpt.DEFAULT_STRESS)
        res = rpt.build(jpath, out, windows)
    _dump(res)
    return 0 if res.get("ok", True) else 1


def _keys(a: argparse.Namespace) -> int:
    from monte_neo.deploy import keys as ks
    from monte_neo.deploy.connectors import venue

    v = venue(a.venue).id
    if a.status:
        _dump(ks.status(v))
    elif a.list:
        for where, _pair in ks.candidates():
            print(where["file"])
    else:
        if not (sys.stdin.isatty() or a.yes):
            print("deploy keys: no terminal to ask for consent. Use --list to see the candidate files, --status to check the "
                  "current keys, or --yes to check every candidate against the testnet.", file=sys.stderr)
            return 2
        print("scanning for files with a Binance key and secret (names only, values are never printed) ...", flush=True)
        ks.find(interactive=sys.stdin.isatty(), assume_yes=a.yes, venue=v)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run ``monte-neo deploy``."""
    from monte_neo.deploy.binance import ExchangeError
    from monte_neo.deploy.eligibility import TARGETS_UNAVAILABLE
    from monte_neo.deploy.runner import RunError

    try:
        a = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code or 0)
    if a.target in TARGETS_UNAVAILABLE:
        print(f"deploy: target {a.target!r} is not available yet; only --target local works now.", file=sys.stderr)
        return 2
    if a.target != "local":
        print(f"deploy: unknown target {a.target!r}; use local.", file=sys.stderr)
        return 3
    try:
        if a.cmd == "init":
            return _init(a)
        if a.cmd == "run":
            return _run(a)
        if a.cmd == "status":
            return _status(a)
        if a.cmd == "verify":
            return _verify(a)
        if a.cmd == "report":
            return _report(a)
        if a.cmd == "keys":
            return _keys(a)
        from monte_neo.deploy import anchor, certify, dashboard
        from monte_neo.deploy.journal import Journal

        folder, jpath = _paths(a)
        if a.cmd == "dashboard":
            print(dashboard.build(jpath, folder / "site"))
        elif a.cmd == "serve":
            dashboard.build(jpath, folder / "site")
            dashboard.serve(folder / "site", a.host, a.port)
        elif a.cmd == "anchor":
            _dump(anchor.anchor(Journal(jpath), folder / "anchors"))
        elif a.cmd == "certify":
            _dump(certify.certify(Journal(jpath), a.n_strategies))
        return 0
    except KeyboardInterrupt:
        return 130
    except (ValueError, RunError, ExchangeError, RuntimeError, OSError) as exc:  # PluginError and EligibilityError are ValueErrors
        print(f"deploy {a.cmd}: {exc}", file=sys.stderr)
        return 3


__all__ = ["main"]
