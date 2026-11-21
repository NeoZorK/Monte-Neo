"""``monte-neo registry``: import a public strategy from the Protocolith trading-strategy registry, re-run its verification, deploy it locally.

Exit codes: 0 ok, 1 the re-run failed, 2 not reachable or not supported yet, 3 usage error or a check failed (hash, ledger, not importable).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EPILOG = """\
five minutes:
  monte-neo registry list
  monte-neo registry show MN-TSM-CRY-002
  monte-neo registry import MN-TSM-CRY-002
  monte-neo registry try MN-TSM-CRY-002
  monte-neo deploy init --strategy strategies/MN-TSM-CRY-002/strategy.py --certificate strategies/MN-TSM-CRY-002/certificate.json --symbols BTCUSDT --rebalance daily --mode dry

The registry is MONTE_NEO_REGISTRY (a URL base or a folder) or the public one. Guide: docs/guides/registry.md.
Research examples, not investment advice.
"""


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="monte-neo registry", description="Import a public strategy from the Protocolith registry, try it yourself, deploy it locally.",
                                 epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", default=None, help="URL base or folder of the registry (default $MONTE_NEO_REGISTRY, else the public one)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="the records of the registry")
    ls.add_argument("--deployable", action="store_true", help="only records that can run on the Binance spot testnet")
    ls.add_argument("--json", action="store_true", help="machine-readable output")
    sh = sub.add_parser("show", help="one record: summary, evaluation, gate, files, next commands")
    sh.add_argument("id")
    im = sub.add_parser("import", help="download one strategy and check its hashes against the index and the ledger")
    im.add_argument("id")
    im.add_argument("--dir", default=None, help="target folder (default ./strategies/ID)")
    tr = sub.add_parser("try", help="re-run the verification on public Binance data")
    tr.add_argument("id")
    tr.add_argument("--dir", default=None, help="folder of the import (default ./strategies/ID)")
    tr.add_argument("--start", default=None, help="first day, YYYY-MM-DD (default: the record's data.start)")
    tr.add_argument("--end", default=None, help="last day, YYYY-MM-DD (default: the record's data.end)")
    return ap


def _dir(a: argparse.Namespace) -> Path:
    return Path(a.dir) if a.dir else Path("strategies") / a.id


def _mark(v: Any) -> str:
    return "yes" if v else "no"


def _deployable(e: dict[str, Any]) -> bool:
    return bool(e.get("importable") and (e.get("deploy") or {}).get("binance_spot_testnet"))


def _list(a: argparse.Namespace) -> int:
    from monte_neo.registry import client

    index = client.load_index(a.registry)
    rows = [e for e in index["records"] if not a.deployable or _deployable(e)]
    if a.json:
        print(json.dumps({"ledger_head": index.get("ledger_head"), "records": rows}, indent=1))
        return 0
    head = ("id", "name", "asset class", "verdict", "ARL", "gate", "importable", "deployable")
    table = [head] + [(str(e["id"]), str(e.get("name", ""))[:44], str(e.get("asset_class", "")), str(e.get("verdict", "")), str(e.get("arl", "")),
                       "passed" if e.get("gate_passed") else "not passed", _mark(e.get("importable")), _mark(_deployable(e))) for e in rows]
    widths = [max(len(r[i]) for r in table) for i in range(len(head))]
    for n, r in enumerate(table):
        print("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)).rstrip())
        if n == 0:
            print("  ".join("-" * w for w in widths))
    print(f"\n{len(rows)} record(s). Next: monte-neo registry show ID")
    return 0


def _record(source: str, entry: dict[str, Any]) -> dict[str, Any] | None:
    """The record file, only if it matches its SHA-256 in the index."""
    from monte_neo.registry import client

    meta = (entry.get("files") or {}).get("record")
    if not meta:
        return None
    raw = client.read_file(source, meta["path"])
    if client.sha256_hex(raw) != meta["sha256"]:
        raise client.RegistryError(f"SHA-256 mismatch for {meta['path']}: refusing to show it", 3)
    rec = json.loads(raw)
    return rec if isinstance(rec, dict) else None


def _show(a: argparse.Namespace) -> int:
    from monte_neo.registry import client

    source = client.resolve_source(a.registry)
    index = client.load_index(source)
    e = client.find_entry(index, a.id)
    rec = _record(source, e) or {}
    ev = rec.get("evaluation") or {}
    gate = ev.get("gate") or {}
    print(f"{e['id']}: {e.get('name', '')}\n")
    print(f"summary:     {e.get('summary', '')}")
    print(f"signal:      {e.get('signal', '')}   asset class: {e.get('asset_class', '')}")
    print(f"evaluation:  verdict {ev.get('verdict', e.get('verdict'))}, ARL {ev.get('arl_level', e.get('arl'))}, certificate {ev.get('certificate_id', '-')}"
          f" (verifier {ev.get('verifier', '-')} {ev.get('verifier_version', '')})")
    for k, v in (ev.get("metrics") or {}).items():
        print(f"             {k}: {v}")
    print(f"gate:        {gate.get('name', 'gate')}: {'passed' if gate.get('passed', e.get('gate_passed')) else 'not passed'}")
    if gate.get("criteria"):
        print(f"  criteria:  {gate['criteria']}")
    if gate.get("why"):
        print(f"  why:       {gate['why']}")
    print(f"ledger:      {e.get('ledger_status', '-')}")
    print("files:")
    for name, meta in (e.get("files") or {}).items():
        print(f"  {name:7s} {meta['path']}  sha256 {meta['sha256'][:16]}...")
    if not e.get("importable"):
        print(f"\nnot importable: {(e.get('deploy') or {}).get('why', 'no public code in this record')}")
        return 0
    dep = e.get("deploy") or {}
    d = f"strategies/{e['id']}"
    print(f"\nnext:\n  monte-neo registry import {e['id']}\n  monte-neo registry try {e['id']}")
    if dep.get("binance_spot_testnet"):
        print(f"  {_deploy_command(d, dep)}")
    return 0


def _deploy_command(folder: str, dep: dict[str, Any]) -> str:
    symbols = ",".join(dep.get("symbols") or [])
    return (f"monte-neo deploy init --strategy {folder}/strategy.py --certificate {folder}/certificate.json "
            f"--symbols {symbols} --rebalance {dep.get('rebalance', 'daily')} --mode dry")


def _import(a: argparse.Namespace) -> int:
    from monte_neo.registry import client

    source = client.resolve_source(a.registry)
    index = client.load_index(source)
    e = client.find_entry(index, a.id)
    dest = _dir(a)
    prov = client.import_entry(source, index, e, dest)
    print(f"imported {e['id']} into {dest}")
    print(f"  checked: sha256 of {len(prov['files'])} files against the index; ledger head {prov['ledger']['head'][:16]}...; "
          f"ledger record entry seq {prov['ledger']['seq']} ({str(prov['ledger']['hash'])[:16]}...)")
    print(f"next:\n  monte-neo registry try {e['id']} --dir {dest}")
    return 0


def _try(a: argparse.Namespace) -> int:
    from monte_neo.registry import client, trial

    dest = _dir(a)
    if not (dest / "strategy.py").is_file():
        source = client.resolve_source(a.registry)
        index = client.load_index(source)
        client.import_entry(source, index, client.find_entry(index, a.id), dest)
        print(f"imported {a.id} into {dest}")
    spec = json.loads((dest / "spec.json").read_text(encoding="utf-8"))
    record = json.loads((dest / "record.json").read_text(encoding="utf-8"))
    code_sha = (spec.get("code") or {}).get("sha256")
    if code_sha and client.sha256_hex((dest / "strategy.py").read_bytes()) != code_sha:
        raise client.RegistryError(f"{dest / 'strategy.py'} no longer matches the SHA-256 in spec.json: it was changed after the import. Import it again into a new --dir.", 3)
    data = spec.get("data") or {}
    symbols = data.get("symbols") or []
    if len(symbols) != 1:
        raise client.RegistryError(f"{a.id} uses {len(symbols)} symbols: multi-symbol records are not supported yet", 2)
    vp = (spec.get("try") or {}).get("verify")
    if not vp:
        raise client.RegistryError(f"{a.id} has no try.verify settings in its spec", 2)
    start, end = a.start or data.get("start"), a.end or data.get("end")
    print(f"downloading {symbols[0]} daily bars {start} .. {end} from Binance (public data)")
    csv = trial.download_csv(symbols[0], start, end, dest / "data")
    print(f"verifying with n_trials={vp['n_trials']}, fee {vp['fee_bps']} bps, slippage {vp['slippage_bps']} bps ...")
    try:
        report = trial.run_verify(csv, dest / "strategy.py", int(vp["n_trials"]), float(vp["fee_bps"]), float(vp["slippage_bps"]))
    except Exception as exc:  # the engine failed: not a verdict
        print(f"monte-neo registry: the verification failed: {exc}", file=sys.stderr)
        return 1
    (dest / "certificate.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    ev = record.get("evaluation") or {}
    reg_sharpe = (ev.get("metrics") or {}).get("sharpe_full_pre_holdout")
    mine = trial.summary(report)
    rows = [("", "registry", "your run"),
            ("verdict", ev.get("verdict", "-"), mine["verdict"]),
            ("ARL", ev.get("arl_level", "-"), mine["arl"]),
            ("certificate", ev.get("certificate_id", "-"), mine["certificate_id"]),
            ("Sharpe", reg_sharpe if reg_sharpe is not None else "-", f"{mine['sharpe']:.2f}" if mine["sharpe"] is not None else "-")]
    cells = [tuple(str(c) for c in r) for r in rows]
    w = [max(len(r[i]) for r in cells) for i in range(3)]
    print()
    for n, r in enumerate(cells):
        print("  ".join(c.ljust(w[i]) for i, c in enumerate(r)).rstrip())
        if n == 0:
            print("  ".join("-" * x for x in w))
    if "trial_evidence" in str((report.get("arl") or {}).get("summary", "")):
        print("\nYour ARL is capped at 3: this run uses the record's trial count without a trial ledger on your machine"
              " (arl-rules/2). The record's evidence of the trials is its pre-registration hash on the registry ledger.")
    print("\nNumbers can differ with the engine version and data revisions (the registry used verifier "
          f"{ev.get('verifier_version', '?')}). Certificate: {dest / 'certificate.json'}. Not investment advice.")
    dep = spec.get("deploy") or {}
    print()
    if dep.get("binance_spot_testnet"):
        print("deploy it locally (simulated orders, no keys), then record the days:")
        print(f"  {_deploy_command(str(dest), dep)}\n  monte-neo deploy run")
    else:
        print(f"not deployable: {dep.get('why', 'the record does not allow the Binance spot testnet')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    from monte_neo.registry.client import RegistryError

    try:
        a = _parser().parse_args(argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code or 0)
    try:
        return {"list": _list, "show": _show, "import": _import, "try": _try}[a.cmd](a)
    except RegistryError as exc:
        print(f"monte-neo registry: {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:] if len(sys.argv) > 1 else None))
