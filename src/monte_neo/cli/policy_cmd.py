"""``monte-neo policy`` — write a policy template, or check and show a policy file.

``monte-neo policy init [--out policy.toml]`` writes the commented template; ``monte-neo policy show policy.toml``
validates the file and prints the rules and the hash that certificates will record. Exit codes: 0 ok, 3 input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from monte_neo.verify.policy import TEMPLATE, load_policy


def main(argv: list[str] | None = None) -> int:
    """Run ``monte-neo policy``."""
    parser = argparse.ArgumentParser(prog="monte-neo policy", description="Your institution's verifier thresholds (TOML).")
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init", help="write a commented policy template")
    init.add_argument("--out", default="policy.toml", help="file to write (default policy.toml)")
    init.add_argument("--force", action="store_true", help="overwrite an existing file")
    show = sub.add_parser("show", help="validate a policy file and print it with its hash")
    show.add_argument("path")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code or 0)
    try:
        if args.action == "init":
            out = Path(args.out)
            if out.exists() and not args.force:
                raise ValueError(f"{out} exists (use --force to overwrite)")
            out.write_text(TEMPLATE, encoding="utf-8")
            print(f"wrote {out}: edit it, then run monte-neo verify ... --policy {out}")
            return 0
        print(json.dumps(load_policy(Path(args.path)), indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"policy: {exc}", file=sys.stderr)
        return 3


__all__ = ["main"]
