"""Testnet keys: environment, then the macOS Keychain, then consented discovery in local files. Values are never printed.

Order of lookup in :func:`resolve`: ``MONTE_NEO_TESTNET_KEY`` / ``MONTE_NEO_TESTNET_SECRET`` in the environment, then the
Keychain (services ``monte_neo_testnet_key`` / ``monte_neo_testnet_secret``). :func:`find` scans known places for files that
define a Binance key and secret (it prints file names and variable names, never values), asks for consent per candidate,
then checks the pair against the spot TESTNET account endpoint ONLY: a mainnet key fails there, so a live account can
never be wired in by mistake. A pair that works is stored in the Keychain; the source file is not changed. Nothing is
written to any file, log or journal.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from monte_neo.deploy import binance

ENV_KEY, ENV_SECRET = "MONTE_NEO_TESTNET_KEY", "MONTE_NEO_TESTNET_SECRET"
KEYCHAIN_KEY, KEYCHAIN_SECRET = "monte_neo_testnet_key", "monte_neo_testnet_secret"
KEYCHAIN_ACCOUNT = "monte-neo"

KEY_RE = re.compile(r"(?i)\b([A-Z0-9_]*BINANCE[A-Z0-9_]*(?:API_?)?KEY)\b\s*[=:]\s*['\"]?([A-Za-z0-9]{32,})")
SECRET_RE = re.compile(r"(?i)\b([A-Z0-9_]*BINANCE[A-Z0-9_]*SECRET[A-Z0-9_]*)\b\s*[=:]\s*['\"]?([A-Za-z0-9]{32,})")
JSON_KEYS = (("api_key", "apikey", "key"), ("api_secret", "secret", "secret_key"))
PLACES = ["~/.config/monte-neo", "~/.config/binance", "~/.binance", "~/.secrets", "~/.config", "~"]
SKIP = {"node_modules", ".git", ".venv", "site-packages", "Library", ".cache", ".Trash"}
NAMES = re.compile(r"(?i)(\.env(\..+)?|.*binance.*|.*secret.*|.*keys?\.(json|env|txt|toml|ini))$")


def _keychain(service: str) -> str:
    if sys.platform != "darwin":
        return ""
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", service, "-w"], capture_output=True, text=True, check=False)  # noqa: S607
    except OSError:
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def resolve() -> tuple[str, str, str] | None:
    """``(key, secret, source)`` from the environment or the Keychain, or None. ``source`` is ``env`` or ``keychain``."""
    k, s = os.environ.get(ENV_KEY, ""), os.environ.get(ENV_SECRET, "")
    if k and s:
        return k, s, "env"
    k, s = _keychain(KEYCHAIN_KEY), _keychain(KEYCHAIN_SECRET)
    if k and s:
        return k, s, "keychain"
    return None


def _files(max_depth: int = 5) -> Iterator[Path]:
    seen: set[Path] = set()
    for place in PLACES:
        root = Path(os.path.expanduser(place))
        if not root.exists():
            continue
        base = len(root.parts)
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP and len(Path(dirpath).parts) - base < max_depth]
            for f in files:
                p = Path(dirpath) / f
                try:
                    small = p.stat().st_size < 200_000
                except OSError:
                    continue
                if NAMES.match(f) and not f.endswith(".example") and p not in seen and small:
                    seen.add(p)
                    yield p


def _pairs(p: Path) -> list[tuple[str, str, str, str]]:
    """(key name, key, secret name, secret) found in one file; values stay in memory only."""
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    out: list[tuple[str, str, str, str]] = []
    keys, secrets = KEY_RE.findall(text), SECRET_RE.findall(text)
    if keys and secrets:
        out.append((keys[0][0], keys[0][1], secrets[0][0], secrets[0][1]))
    if p.suffix == ".json":
        def walk(o: Any) -> None:
            if isinstance(o, dict):
                lower = {k.lower(): v for k, v in o.items() if isinstance(v, str)}
                k = next((lower[n] for n in JSON_KEYS[0] if n in lower), None)
                s = next((lower[n] for n in JSON_KEYS[1] if n in lower), None)
                if k and s and len(k) >= 32 and len(s) >= 32 and k.isalnum() and s.isalnum():
                    out.append(("json api_key", k, "json api_secret", s))
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        try:
            walk(json.loads(text))
        except ValueError:
            pass
    return out


def candidates() -> list[dict[str, Any]]:
    return [{"file": str(p), "names": [k, s], "pair": (kv, sv)} for p in _files() for k, kv, s, sv in _pairs(p)]


def check_pair(key: str, secret: str) -> tuple[bool, str]:
    """Does the SPOT TESTNET accept this pair? Only the testnet host is called; a mainnet key is rejected there."""
    try:
        bal = binance.SpotTestnet(key=key, secret=secret).balances()
    except binance.ExchangeError:
        return False, "the spot testnet does not accept this pair (a mainnet key is never used)"
    return True, f"the spot testnet account answered ({len(bal)} assets)"


def store(key: str, secret: str) -> None:
    """Put the pair into the macOS Keychain."""
    for service, value in ((KEYCHAIN_KEY, key), (KEYCHAIN_SECRET, secret)):
        subprocess.run(["security", "add-generic-password", "-U", "-s", service, "-a", KEYCHAIN_ACCOUNT, "-w", value], check=True, capture_output=True)  # noqa: S607


def status() -> dict[str, Any]:
    """Where keys come from and whether the testnet accepts them (no values)."""
    found = resolve()
    if not found:
        return {"found": False, "source": None, "testnet_accepts": None}
    ok, why = check_pair(found[0], found[1])
    return {"found": True, "source": found[2], "testnet_accepts": ok, "detail": why}


def find(interactive: bool = True, assume_yes: bool = False) -> int:
    """Scan, ask, check against the testnet, store in the Keychain; returns how many pairs were stored."""
    stored = 0
    found = candidates()
    if not found:
        print("no file with a Binance key and secret found in: " + ", ".join(PLACES))
        return 0
    for c in found:
        print(f"candidate: {c['file']}  ({' / '.join(c['names'])})")
        question = "  check this pair against the Binance spot TESTNET and store it in the Keychain? [y/N] "
        if not (assume_yes or (interactive and input(question).strip().lower() == "y")):
            continue
        key, secret = c["pair"]
        ok, why = check_pair(key, secret)
        print(f"  {why}")
        if ok:
            store(key, secret)
            print(f"  stored in the Keychain as {KEYCHAIN_KEY} / {KEYCHAIN_SECRET}")
            stored += 1
    return stored
