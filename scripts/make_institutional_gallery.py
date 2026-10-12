"""Regenerate the institutional example pages of the documentation gallery.

Writes docs/assets/reports/dossier-sr11-7.html (from `monte-neo dossier --demo --framework
sr11-7`) and docs/assets/reports/repair-flicker.html (the flicker case of `monte-neo repair
--demo`). There is no alpha HTML renderer, so the alpha demo has no page. The pages come from
real runs of the CLI in a temporary folder; the repository is not touched except for the output.

Run: uv run python scripts/make_institutional_gallery.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "reports"
CLI = [sys.executable, "-m", "monte_neo"]


def run(args: list[str]) -> None:
    subprocess.run([*CLI, *args], check=True, stdout=subprocess.DEVNULL)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        run(["dossier", "--demo", "--framework", "sr11-7", "--out", str(work / "dossier")])
        run(["repair", "--demo", "--out", str(work / "repair")])
        pages = {
            "dossier-sr11-7.html": work / "dossier" / "dossier.html",
            "repair-flicker.html": work / "repair" / "flicker" / "repair-report.html",
        }
        for name, source in pages.items():
            shutil.copyfile(source, OUT / name)
            print(f"{name:22s} {(OUT / name).relative_to(ROOT)} ({(OUT / name).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
