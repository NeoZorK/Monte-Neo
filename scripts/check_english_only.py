"""Fail when Cyrillic text or private working files reach the public repository.

Public files, pull requests and commit messages are English only (docs/development/rules.md). This check runs in CI
(`.github/workflows/language-guard.yml`) and can be run locally:

    python scripts/check_english_only.py                  # every tracked text file and path
    python scripts/check_english_only.py --text "..."     # a title, a body or a message
    git log origin/main..HEAD --format=%B | python scripts/check_english_only.py --stdin
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

CYRILLIC = re.compile("[\u0400-\u04ff\u0500-\u052f]")  # Cyrillic and Cyrillic Supplement
PRIVATE_DIRS = ("docs/internal/", "scripts/internal/", "tests/internal/")
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".o", ".so", ".dylib", ".whl", ".gz", ".zip", ".parquet", ".woff", ".woff2"}
MAX_SHOWN = 20


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout  # noqa: S607 - fixed argv
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def check_paths(paths: list[str]) -> list[str]:
    problems = []
    for path in paths:
        if path.startswith(PRIVATE_DIRS):
            problems.append(f"{path}: private working files must not be committed")
        if CYRILLIC.search(path):
            problems.append(f"{path}: Cyrillic in a file name")
    return problems


def check_file(path: str) -> list[str]:
    if Path(path).suffix.lower() in BINARY_SUFFIXES:
        return []
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    if b"\0" in data:
        return []
    text = data.decode("utf-8", "replace")
    return [f"{path}:{n}: Cyrillic text" for n, line in enumerate(text.splitlines(), 1) if CYRILLIC.search(line)]


def check_text(label: str, text: str) -> list[str]:
    return [f"{label}:{n}: Cyrillic text" for n, line in enumerate(text.splitlines(), 1) if CYRILLIC.search(line)]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--text", action="append", default=[], help="Check this text (a title or a body); may be repeated")
    p.add_argument("--stdin", action="store_true", help="Check text from standard input (for example commit messages)")
    args = p.parse_args(argv)
    problems: list[str] = []
    if args.text or args.stdin:
        for i, text in enumerate(args.text, 1):
            problems += check_text(f"text #{i}", text)
        if args.stdin:
            problems += check_text("stdin", sys.stdin.read())
    else:
        files = tracked_files()
        problems += check_paths(files)
        for path in files:
            problems += check_file(path)
    for line in problems[:MAX_SHOWN]:
        print(line)
    if len(problems) > MAX_SHOWN:
        print(f"... and {len(problems) - MAX_SHOWN} more")
    if problems:
        print("English only: public repositories carry no Cyrillic text and no private working files (docs/development/rules.md).")
        return 1
    print("ok: no Cyrillic text and no private files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
