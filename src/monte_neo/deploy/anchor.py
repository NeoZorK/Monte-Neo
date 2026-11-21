"""External time evidence for the journal head: an RFC 3161 timestamp from a public time-stamping authority.

Only the SHA-256 of a small text (journal head seq and hash, date) leaves the machine; the journal itself never does.
Each anchor is saved as ``<dir>/<date>.txt`` (what was stamped), ``.tsq`` (request) and ``.tsr`` (signed reply), and is
journaled as an ``anchor`` entry. Anyone can later check the reply with ``openssl ts -verify`` against the authority's
certificates, which proves the head existed at that time. Needs the ``openssl`` command (LibreSSL on macOS has ``ts``).
The authorities are tried in order until one answers; one anchor per UTC day.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

from monte_neo.deploy.journal import Journal

TSAS = ["https://freetsa.org/tsr", "http://timestamp.digicert.com", "http://timestamp.sectigo.com"]
UA = "monte-neo-deploy/1"


def make_query(text: Path, tsq: Path) -> None:
    if shutil.which("openssl") is None:
        raise RuntimeError("the openssl command is needed for RFC 3161 anchors")
    subprocess.run(["openssl", "ts", "-query", "-data", str(text), "-sha256", "-cert", "-out", str(tsq)], check=True, capture_output=True)  # noqa: S607


def post(tsa: str, data: bytes) -> bytes:
    req = urllib.request.Request(tsa, data=data, method="POST", headers={"Content-Type": "application/timestamp-query", "User-Agent": UA})  # noqa: S310
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed hosts, listed above)
        return r.read()  # type: ignore[no-any-return]


def anchor(journal: Journal, out_dir: Path, tsas: list[str] | None = None) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    head = journal.head()
    day = time.strftime("%Y-%m-%d", time.gmtime())
    text = out_dir / f"{day}.txt"
    tsq, tsr = text.with_suffix(".tsq"), text.with_suffix(".tsr")
    if tsr.exists():  # one anchor a day; a rerun the same day changes nothing
        return {"day": day, "skipped": "already anchored today"}
    text.write_text(f"monte-neo deploy journal head\nseq {head['seq']}\nhash {head['hash']}\nutc {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n", encoding="utf-8")
    make_query(text, tsq)
    errors: list[str] = []
    for tsa in tsas or TSAS:
        try:
            reply = post(tsa, tsq.read_bytes())
        except Exception as exc:  # try the next authority
            errors.append(f"{tsa}: {type(exc).__name__}")
            continue
        if not reply:
            errors.append(f"{tsa}: empty reply")
            continue
        tsr.write_bytes(reply)
        body = {"day": day, "seq": head["seq"], "head": head["hash"], "tsa": tsa, "text_sha256": hashlib.sha256(text.read_bytes()).hexdigest(),
                "tsr_sha256": hashlib.sha256(tsr.read_bytes()).hexdigest(), "files": [text.name, tsq.name, tsr.name]}
        journal.append("anchor", body)
        return body
    raise RuntimeError("no time-stamping authority answered: " + "; ".join(errors))
