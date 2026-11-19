"""Mirror the big Lab series (strategy_lab/data_wide, data_extra) to the mbp2014 HDD with resume, and write a SHA-256 manifest.

    python scripts/strategy_lab/sync_archive.py            # manifest + rsync DRY RUN (rsync -n) + free-space check; changes nothing remote
    python scripts/strategy_lab/sync_archive.py --go       # the real copy (rsync --partial, resumable), refuses if the volume would pass 90 %

Remote: mbp2014:/Volumes/Dis/MonteNeoRates/strategy_lab/ . Only the manifest (hashes) goes into git, never the series.
On mbp2014 read parquet with fastparquet (pyarrow crashes there). Run it from a normal terminal if the sandbox blocks ssh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "strategy_lab"
REMOTE, HOST = "mbp2014:/Volumes/Dis/MonteNeoRates/strategy_lab/", "mbp2014"
DIRS = ["data_wide", "data_extra"]


def manifest() -> dict:
    files = {}
    for d in DIRS:
        for p in sorted((ROOT / d).rglob("*")):
            if p.is_file() and p.suffix in (".parquet", ".zip") and ".part" not in p.name:
                files[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    out = {"remote": REMOTE, "files": len(files), "sha256": files}
    (ROOT / "archive_manifest.json").write_text(json.dumps(out, indent=0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    m = manifest()
    size = sum(p.stat().st_size for d in DIRS for p in (ROOT / d).rglob("*") if p.is_file())
    print(f"manifest: {m['files']} files, {size / 1e6:.0f} MB -> strategy_lab/archive_manifest.json")
    df = subprocess.run(["ssh", HOST, "df -k /Volumes/Dis | tail -1"], capture_output=True, text=True, timeout=60)
    if df.returncode != 0:
        print("ssh to mbp2014 failed (sandbox or network?): run this script from a normal terminal.\n", df.stderr[-300:])
        return 2
    parts = df.stdout.split()
    total_k, used_k = int(parts[1]), int(parts[2])
    after = (used_k * 1024 + size) / (total_k * 1024)
    print(f"remote volume: {used_k / total_k:.0%} used now, about {after:.0%} after the copy")
    if after > 0.90:
        print("REFUSED: the volume would pass 90 %")
        return 3
    cmd = ["rsync", "-a", "--partial", "--info=progress2", *(["-n", "-v"] if not a.go else []), *[str(ROOT / d) for d in DIRS], REMOTE]
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
