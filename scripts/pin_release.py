"""Write a hash-locked requirements line for a Monte-Neo release that is on PyPI.

The verifier image installs the release with ``--require-hashes``; this prints what that needs:

    python3 scripts/pin_release.py 0.50.0 > docker/verify/monte-neo.txt

The hashes are the sha256 of every file PyPI holds for the version (the wheel and the sdist), so pip accepts the one it picks.
"""

from __future__ import annotations

import json
import sys
import urllib.request


def pin_lines(version: str, files: list[dict]) -> str:
    """``monte-neo==VERSION`` with one ``--hash=sha256:...`` per distinct file digest."""
    hashes = sorted({f["digests"]["sha256"] for f in files})
    if not hashes:
        raise SystemExit(f"PyPI lists no files for monte-neo {version}")
    return f"monte-neo=={version} \\\n" + " \\\n".join(f"    --hash=sha256:{h}" for h in hashes) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0][:1].isdigit():
        raise SystemExit("usage: pin_release.py X.Y.Z")
    version = argv[0]
    with urllib.request.urlopen(f"https://pypi.org/pypi/monte-neo/{version}/json", timeout=30) as response:  # noqa: S310  # nosec B310 - fixed https URL
        files = json.load(response)["urls"]
    sys.stdout.write(pin_lines(version, files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
