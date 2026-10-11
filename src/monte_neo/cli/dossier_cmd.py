"""``monte-neo dossier`` — turn a certificate into a validation dossier folder for a committee, a validator or an auditor.

Exit codes: 0 written, 3 input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from monte_neo import disclaimer


def build_parser() -> argparse.ArgumentParser:
    """The ``monte-neo dossier`` options."""
    from monte_neo.dossier import FRAMEWORKS

    p = argparse.ArgumentParser(prog="monte-neo dossier", description="Write a validation dossier from a certificate.")
    p.add_argument("--certificate", help="A strategy-verdict/1 certificate (monte-neo verify --out cert.json)")
    p.add_argument("--alpha", help="Optional alpha-report/1 JSON for the strategy's signal (monte-neo alpha --out)")
    p.add_argument("--live", help="Optional live-monitor/1 JSON (monte-neo monitor --out)")
    p.add_argument("--framework", choices=sorted(FRAMEWORKS), default="generic", help="Clause map to include (default generic)")
    p.add_argument("--out", default="dossier", help="Folder to write (default ./dossier)")
    for field in ("name", "owner", "purpose", "scope", "developer", "tier"):
        p.add_argument(f"--{field}", help=f"Model {field} shown in 'Purpose and scope'")
    p.add_argument("--demo", action="store_true", help="Build a dossier from a synthetic certificate (no files needed)")
    return p


def _read(path: str | None) -> dict[str, Any] | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def _demo_certificate() -> dict[str, Any]:
    import numpy as np

    from monte_neo.backtest import synthetic_ohlcv
    from monte_neo.verify import verify_strategy

    df = synthetic_ohlcv(1200, seed=21)
    signals = np.sign(df["close"].pct_change(20).fillna(0.0).to_numpy())
    return json.loads(json.dumps(verify_strategy(df, signals=signals, n_trials=12, probe_checks=6)))


def main(argv: list[str] | None = None) -> int:
    """Run ``monte-neo dossier``."""
    from monte_neo.dossier import build_dossier, write_dossier
    from monte_neo.verify.recheck import load_certificate

    try:
        args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code or 0)
    try:
        if args.demo:
            cert = _demo_certificate()
            meta = {"name": "Demo momentum (synthetic data)", "owner": "Research", "purpose": "Show the dossier format",
                    "scope": "One synthetic instrument, minute bars", "tier": "3"}
        elif args.certificate:
            cert = load_certificate(args.certificate)
            meta = {k: getattr(args, k) for k in ("name", "owner", "purpose", "scope", "developer", "tier")}
        else:
            print("dossier: give --certificate cert.json, or --demo", file=sys.stderr)
            return 3
        dossier = build_dossier(cert, framework=args.framework, meta=meta, alpha=_read(args.alpha), live=_read(args.live))
        out = write_dossier(dossier, cert, args.out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"dossier: {exc}", file=sys.stderr)
        return 3
    covered = sum(1 for c in dossier["framework"]["clauses"] if c["coverage"] == "covered")
    print(f"wrote {out}/dossier.html (+ dossier.json, certificate.json, environment.json, REPRODUCE.md, limitations.md)")
    print(f"verdict {dossier['verdict']} · {dossier['framework']['title']}: {covered} of {len(dossier['framework']['clauses'])} clauses covered by evidence")
    print(disclaimer.SHORT)
    return 0


__all__ = ["build_parser", "main"]
