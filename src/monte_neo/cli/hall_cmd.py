"""``monte-neo hall`` — the Hall of Fame: build the tables and badges, prepare a submission, attest an entry.

``hall build`` writes the README table, ``docs/hall-of-fame.md``, the SVG medals and the history (``--check`` only compares).
``hall submit CERT`` checks a certificate offline and writes the entry JSON for a pull request. ``hall attest`` is the maintainer's
step for tier B: it reproduces the certificate from privately received code and signs the entry. No command uses the network.
Exit codes: 0 ok, 1 files out of date (``build --check``), 3 input error or refused entry.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from monte_neo.disclaimer import SHORT
from monte_neo.hall.build import build, stale, sync_guide, write
from monte_neo.hall.entry import attest, certificate_sha256, check_entry, make_entry, summarize
from monte_neo.hall.ranking import classify, load_items, load_keys
from monte_neo.hall.rules import load_rules


def _recheck(cert: dict[str, Any], ohlcv: str | None, strategy: str | None, signals: str | None) -> dict[str, Any]:
    """Reproduce the certificate (needs the data and the strategy or signals); raises ``ValueError`` when that cannot be done."""
    if not ohlcv or not (strategy or signals):
        raise ValueError("a recheck needs --ohlcv and --strategy-file (or --signals)")
    from monte_neo.verify.recheck import recheck_certificate

    return recheck_certificate(cert, ohlcv, signals=signals, strategy=strategy)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="monte-neo hall", description=f"Hall of Fame (evidence rating). {SHORT}")
    sub = p.add_subparsers(dest="action", required=True)
    b = sub.add_parser("build", help="write the README table, docs page, badges and history")
    b.add_argument("--root", default="hall_of_fame")
    b.add_argument("--readme", default="README.md")
    b.add_argument("--docs", default="docs/hall-of-fame.md")
    b.add_argument("--guide", default="docs/guides/hall-of-fame.md")
    b.add_argument("--month", help="snapshot month YYYY-MM (default: this month; with --check: the latest in the history)")
    b.add_argument("--check", action="store_true", help="write nothing; exit 1 when a file is out of date")
    for name, text in (("submit", "check a certificate offline and prepare the entry for a pull request"),
                       ("attest", "maintainer: reproduce a tier B draft, sign it and add it to the store")):
        s = sub.add_parser(name, help=text)
        s.add_argument("certificate" if name == "submit" else "entry", help="strategy-verdict/1 JSON" if name == "submit" else "draft entry JSON")
        s.add_argument("--root", default="hall_of_fame")
        s.add_argument("--ohlcv")
        s.add_argument("--strategy-file")
        s.add_argument("--signals")
        s.add_argument("--date", help="YYYY-MM-DD (default: today, UTC)")
        if name == "submit":
            s.add_argument("--author", required=True)
            s.add_argument("--name", required=True, help="strategy name shown in the table")
            s.add_argument("--category", required=True)
            s.add_argument("--tier", required=True, choices=["A", "B", "C"])
            s.add_argument("--code-url")
            s.add_argument("--idea-credit")
            s.add_argument("--out", default="hall_submission")
        else:
            s.add_argument("--cert", required=True, help="the certificate of the draft")
            s.add_argument("--key", required=True, help="the maintainer's private key (PEM)")
    return p


def _build(args: argparse.Namespace) -> int:
    root = Path(args.root)
    month = args.month
    if not month:
        hist = root / "history.jsonl"
        last = sorted(json.loads(x)["month"] for x in hist.read_text(encoding="utf-8").splitlines() if x.strip()) if args.check and hist.exists() else []
        month = last[-1] if last else datetime.now(UTC).strftime("%Y-%m")
    res = build(root, Path(args.readme), Path(args.docs), month)
    if res.errors:
        print("hall: refused, fix these first:\n" + "\n".join(f"  - {e}" for e in res.errors), file=sys.stderr)
        return 3
    if args.check:
        bad = stale(res)
        print("hall: up to date" if not bad else "hall: out of date, run `monte-neo hall build`:\n" + "\n".join(f"  - {p}" for p in bad))
        return 1 if bad else 0
    changed = write(res)
    guide = Path(args.guide)
    if guide.exists() and sync_guide(guide):
        changed.append(guide)
    print(f"hall: {len(res.files)} files written ({len(changed)} changed)\n{SHORT}")
    return 0


def _admit(root: Path, entry: dict[str, Any], cert: dict[str, Any], rules: dict[str, Any]) -> None:
    """Refuse a new entry that the rules would not rank (REJECT, duplicate, author limit)."""
    new = {"entry": entry, "summary": summarize(cert), "errors": []}
    cls = classify([i for i in load_items(root, rules) if i["entry"].get("id") != entry["id"]] + [new], rules)
    why = next((w for i, w in cls["excluded"] if i is new), None)
    if why:
        raise ValueError(f"the rules would not rank this entry: {why}")


def _submit(args: argparse.Namespace) -> int:
    rules, cert = load_rules(), json.loads(Path(args.certificate).read_text(encoding="utf-8"))
    date = args.date or datetime.now(UTC).strftime("%Y-%m-%d")
    rc = _recheck(cert, args.ohlcv, args.strategy_file, args.signals) if args.tier == "A" else None
    entry = make_entry(cert, author=args.author, strategy=args.name, category=args.category, tier=args.tier, submitted_at=date,
                       rules=rules, code_url=args.code_url, idea_credit=args.idea_credit, recheck=rc)
    errs = check_entry(entry, cert, rules, load_keys(Path(args.root)), draft=True)
    if errs:
        raise ValueError("; ".join(errs))
    _admit(Path(args.root), entry, cert, rules)
    out = Path(args.out)
    for sub, doc in (("entries", entry), ("certificates", cert)):
        (out / sub).mkdir(parents=True, exist_ok=True)
        (out / sub / f"{entry['id']}.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    nxt = {"A": "open a pull request that adds both files under hall_of_fame/; the maintainer reproduces the certificate before merging",
           "B": "send the code and data privately to the maintainer, who runs `monte-neo hall attest`; then open the pull request",
           "C": "open a pull request; self-reported entries are listed apart and never ranked"}[args.tier]
    print(f"hall: entry {entry['id']} prepared in {out} (certificate SHA-256 {certificate_sha256(cert)})\nnext: {nxt}\n{SHORT}")
    return 0


def _attest(args: argparse.Namespace) -> int:
    rules, root = load_rules(), Path(args.root)
    entry = json.loads(Path(args.entry).read_text(encoding="utf-8"))
    cert = json.loads(Path(args.cert).read_text(encoding="utf-8"))
    if entry.get("tier") != "B":
        raise ValueError("only tier B entries are attested")
    if errs := check_entry(entry, cert, rules, {}, draft=True):
        raise ValueError("; ".join(errs))
    report = _recheck(cert, args.ohlcv, args.strategy_file, args.signals)
    if not report.get("reproduced"):
        raise ValueError(f"the certificate was not reproduced: {report.get('reason', 'see the recheck report')}")
    date = args.date or datetime.now(UTC).strftime("%Y-%m-%d")
    entry["recheck"] = {"reproduced": True, "engine_version": report.get("engine_version"), "checked_at": date, "by": "maintainer"}
    signed = attest(entry, args.key)
    _admit(root, signed, cert, rules)
    for sub, doc in (("entries", signed), ("certificates", cert)):
        (root / sub).mkdir(parents=True, exist_ok=True)
        (root / sub / f"{signed['id']}.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"hall: {signed['id']} reproduced, signed with key {signed['signature']['key_id']} and added to {root}\n{SHORT}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run ``monte-neo hall``."""
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code or 0)
    try:
        return {"build": _build, "submit": _submit, "attest": _attest}[args.action](args)
    except (OSError, ValueError, KeyError) as exc:
        print(f"hall: {exc}", file=sys.stderr)
        return 3


__all__ = ["main"]
