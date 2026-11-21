"""Read the strategy registry (a URL base or a local folder), check what it serves, and import a strategy. Standard library only.

A registry is a folder (or a URL base) holding ``index.json`` (schema ``registry-index/1``), the files it lists, and a
Protocolith ledger at ``ledger/ledger.jsonl``. An import is refused unless every file matches its SHA-256 in the index,
the ledger head equals the index's ``ledger_head``, and a ledger ``record`` entry names both the record and the code hash.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE = "https://raw.githubusercontent.com/Protocolith/trading-strategy-registry/main/"
INDEX_SCHEMA = "registry-index/1"
LEDGER_PATH = "ledger/ledger.jsonl"
TIMEOUT = 30
MAX_BYTES = 8_000_000


class RegistryError(RuntimeError):
    """A registry problem. ``code`` is the exit code: 2 not reachable or not supported, 3 a refused input or failed check."""

    def __init__(self, message: str, code: int = 3) -> None:
        super().__init__(message)
        self.code = code


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def user_agent() -> str:
    from monte_neo._version import __version__

    return f"monte-neo/{__version__.lstrip('v')}"


def default_source() -> str:
    return os.environ.get("MONTE_NEO_REGISTRY") or DEFAULT_BASE


def is_url(source: str) -> bool:
    return source.startswith(("https://", "http://"))


def http_get(url: str) -> bytes:
    """GET with a User-Agent and a timeout; every failure becomes a RegistryError that says what to do."""
    if not url.startswith("https://") and not url.startswith("http://localhost") and not url.startswith("http://127.0.0.1"):
        raise RegistryError(f"refusing a non-HTTPS URL: {url}", 3)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})  # noqa: S310 (scheme checked above)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310  # nosec B310 - scheme checked above
            data: bytes = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RegistryError(f"{url} answered HTTP {exc.code}", 2) from None
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise RegistryError(f"cannot reach {url}: {getattr(exc, 'reason', exc)}. Check the network, or point MONTE_NEO_REGISTRY at a local clone.", 2) from None
    if len(data) > MAX_BYTES:
        raise RegistryError(f"{url} is larger than {MAX_BYTES} bytes: refused", 3)
    return data


def read_file(source: str, path: str) -> bytes:
    """Bytes of ``path`` under the registry ``source`` (URL base or folder)."""
    if ".." in Path(path).parts or path.startswith("/"):
        raise RegistryError(f"unsafe path in the registry: {path!r}", 3)
    if is_url(source):
        return http_get(source.rstrip("/") + "/" + path)
    p = Path(source).expanduser() / path
    try:
        return p.read_bytes()
    except OSError as exc:
        raise RegistryError(f"cannot read {p}: {exc.strerror or exc}", 2) from None


def resolve_source(source: str | None) -> str:
    return source or default_source()


def load_index(source: str | None = None) -> dict[str, Any]:
    """The parsed ``index.json`` of ``source`` (default: $MONTE_NEO_REGISTRY, else the public registry)."""
    src = resolve_source(source)
    raw = read_file(src, "index.json")
    try:
        index = json.loads(raw)
    except ValueError as exc:
        raise RegistryError(f"index.json of {src} is not valid JSON: {exc}", 3) from None
    if not isinstance(index, dict) or index.get("schema") != INDEX_SCHEMA or not isinstance(index.get("records"), list):
        raise RegistryError(f"index.json of {src} is not a {INDEX_SCHEMA} index", 3)
    return index


def find_entry(index: dict[str, Any], record_id: str) -> dict[str, Any]:
    for entry in index["records"]:
        if entry.get("id") == record_id:
            return entry  # type: ignore[no-any-return]
    known = ", ".join(str(e.get("id")) for e in index["records"])
    raise RegistryError(f"no record {record_id!r} in the registry (known: {known})", 3)


def parse_ledger(raw: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            raise RegistryError(f"ledger line {n} is not valid JSON", 3) from None
        if not isinstance(row, dict):
            raise RegistryError(f"ledger line {n} is not an object", 3)
        out.append(row)
    return out


def check_ledger(source: str, index: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Check the ledger against the index and return the ledger ``record`` entry that names this record and its code."""
    rows = parse_ledger(read_file(source, LEDGER_PATH))
    if not rows:
        raise RegistryError("the ledger is empty", 3)
    for prev, row in zip(rows, rows[1:], strict=False):
        if row.get("prev") != prev.get("hash") or row.get("seq") != prev.get("seq", -1) + 1:
            raise RegistryError(f"the ledger chain is broken at seq {row.get('seq')}", 3)
    if rows[-1].get("hash") != index.get("ledger_head"):
        raise RegistryError(
            f"ledger head mismatch: the index says {index.get('ledger_head')}, the ledger ends at {rows[-1].get('hash')}", 3
        )
    wanted = {name: entry["files"][name]["sha256"] for name in ("record", "code") if name in entry["files"]}
    for row in rows:
        if row.get("type") != "record":
            continue
        sources = {s.get("sha256") for s in (row.get("body") or {}).get("sources", []) if isinstance(s, dict)}
        if all(h in sources for h in wanted.values()):
            return row
    raise RegistryError(f"no ledger 'record' entry lists the sha256 of {' and '.join(wanted)} of {entry['id']}: the record is not in the ledger", 3)


def import_entry(source: str, index: dict[str, Any], entry: dict[str, Any], dest: Path) -> dict[str, Any]:
    """Download, check and write a strategy to ``dest``; return the provenance. Writes nothing if any check fails."""
    if not entry.get("importable"):
        why = (entry.get("deploy") or {}).get("why") or entry.get("not_importable_reason") or "no public code in this record"
        raise RegistryError(f"{entry['id']} is not importable: {why}", 3)
    files = entry.get("files") or {}
    for name in ("code", "spec", "record"):
        if name not in files:
            raise RegistryError(f"the index entry of {entry['id']} has no {name} file", 3)
    blobs: dict[str, bytes] = {}
    for name, meta in files.items():
        blobs[name] = read_file(source, meta["path"])
        got = sha256_hex(blobs[name])
        if got != meta["sha256"]:
            raise RegistryError(f"SHA-256 mismatch for {meta['path']}: the index says {meta['sha256']}, the file is {got}. Nothing was written.", 3)
    ledger_row = check_ledger(source, index, entry)
    dest.mkdir(parents=True, exist_ok=True)
    names = {"code": "strategy.py", "spec": "spec.json", "record": "record.json"}
    for name, target in names.items():
        (dest / target).write_bytes(blobs[name])
    base = source.rstrip("/") + "/" if is_url(source) else str(Path(source).expanduser().resolve()) + "/"
    prov = {
        "id": entry["id"],
        "registry": source,
        "files": {names[n]: {"url": base + m["path"], "sha256": m["sha256"]} for n, m in files.items() if n in names},
        "ledger": {"seq": ledger_row.get("seq"), "hash": ledger_row.get("hash"), "head": index.get("ledger_head")},
        "imported_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (dest / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    (dest / "README.md").write_text(readme(entry, dest), encoding="utf-8")
    return prov


def readme(entry: dict[str, Any], dest: Path) -> str:
    sym = ",".join((entry.get("deploy") or {}).get("symbols") or [])
    reb = (entry.get("deploy") or {}).get("rebalance") or "daily"
    return (
        f"# {entry['id']}: {entry.get('name', '')}\n\n"
        f"{entry.get('summary', '')}\n\n"
        "Imported by `monte-neo registry import`; the hashes were checked against the registry index and ledger "
        "(see provenance.json). A research example, not investment advice.\n\n"
        f"1. Try it yourself (re-run the verification on public data):\n\n    monte-neo registry try {entry['id']} --dir {dest}\n\n"
        f"2. Start a local dry run (simulated orders, no keys):\n\n    monte-neo deploy init --strategy {dest}/strategy.py "
        f"--certificate {dest}/certificate.json --symbols {sym} --rebalance {reb} --mode dry\n\n"
        "3. Record every missing day (safe to repeat):\n\n    monte-neo deploy run\n"
    )
