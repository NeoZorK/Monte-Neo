"""A Hall of Fame entry (``hall-entry/1``): build it from a certificate, check it, attest it.

An entry never stores the strategy. It stores who and what (author, name, category), the SHA-256 of the certificate, the
result of a local ``recheck`` and, for tier B, the maintainer's Ed25519 signature over the whole entry. Everything the
table shows about the evidence (verdict, ARL, depth, Deflated Sharpe, ``n_trials``) is read from the certificate, never from the entry.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any

from monte_neo.verify.signing import canonical_payload, check_signature, key_id, load_public_key, sign_certificate

ENTRY_SCHEMA_ID = "hall-entry/1"
REQUIRED = ("schema", "id", "author", "strategy", "category", "tier", "submitted_at", "hall_rules_version", "arl_rules_version",
            "provisional", "certificate_sha256")
TEXT = re.compile(r"^[^\x00-\x1f|<>\[\]`\\&\"]{1,80}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL = re.compile(r"^https://[A-Za-z0-9._~:/?#@!$'()*+,;=%-]{4,200}$")


def certificate_sha256(certificate: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON of the whole certificate (key order and white space do not matter)."""
    raw = json.dumps(certificate, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def summarize(certificate: dict[str, Any]) -> dict[str, Any]:
    """What the table shows, read from the certificate: verdict, ARL, depth, Deflated Sharpe, ``n_trials``, date and hashes."""
    repro, arl = certificate.get("reproducibility") or {}, certificate.get("arl") or {}
    dsr = next(((c.get("details") or {}).get("deflated_sharpe") for c in certificate.get("checks", []) if c.get("id") == "deflated_sharpe"), None)
    return {
        "verdict": certificate.get("verdict"), "certificate_id": certificate.get("certificate_id"),
        "arl": arl.get("level"), "depth": arl.get("depth"), "arl_rules_version": arl.get("rules_version"), "provisional": arl.get("provisional"),
        "deflated_sharpe": dsr, "n_trials": repro.get("n_trials"), "date": str(certificate.get("generated_at") or "")[:10],
        "engine_version": repro.get("engine_version"), "data_sha256": repro.get("data_sha256"),
        "signals_sha256": repro.get("signals_sha256"), "source_sha256": repro.get("source_sha256"),
    }


def slug(text: str) -> str:
    """Lower-case file-name fragment of ``text``."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:30] or "strategy"


def make_entry(certificate: dict[str, Any], *, author: str, strategy: str, category: str, tier: str, submitted_at: str,
               rules: dict[str, Any], code_url: str | None = None, idea_credit: str | None = None,
               recheck: dict[str, Any] | None = None) -> dict[str, Any]:
    """An entry for ``certificate`` (not yet checked: run :func:`check_entry`).

    ``recheck`` is the ``strategy-recheck/1`` report (or any dict with ``reproduced``); the entry keeps only what the table needs.
    """
    sha, arl = certificate_sha256(certificate), certificate.get("arl") or {}
    entry: dict[str, Any] = {
        "schema": ENTRY_SCHEMA_ID, "id": f"{submitted_at}-{slug(strategy)}-{sha[:8]}", "author": author, "strategy": strategy,
        "category": category, "tier": tier, "submitted_at": submitted_at, "hall_rules_version": rules["version"],
        "arl_rules_version": arl.get("rules_version"), "provisional": arl.get("provisional"), "certificate_sha256": sha,
    }
    if code_url:
        entry["code_url"] = code_url
    if idea_credit:
        entry["idea_credit"] = idea_credit
    if recheck is not None:
        entry["recheck"] = {"reproduced": bool(recheck.get("reproduced")), "engine_version": recheck.get("engine_version"),
                            "checked_at": submitted_at, "by": recheck.get("by", "author")}
    return entry


def attest(entry: dict[str, Any], private_key: Any) -> dict[str, Any]:
    """``entry`` signed by the maintainer's key (tier B): the signature covers every other field."""
    return sign_certificate(entry, private_key)


def attestation_error(entry: dict[str, Any], trusted: dict[str, str]) -> str | None:
    """Why the maintainer signature of ``entry`` is not valid, or ``None``. ``trusted`` maps key id to ``ed25519:<base64>``."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric import ed25519

    sig = entry.get("signature")
    try:
        if not isinstance(sig, dict):
            return "tier B entry is not signed by the maintainer"
        raw = load_public_key(str(sig["public_key"]), allow_file=False)
        if trusted.get(key_id(raw)) != sig["public_key"]:
            return f"signing key {key_id(raw)} is not in maintainer_keys.json"
        ed25519.Ed25519PublicKey.from_public_bytes(raw).verify(base64.b64decode(str(sig["value"]), validate=True), canonical_payload(entry))
    except (InvalidSignature, ValueError, KeyError, TypeError) as exc:
        return f"maintainer signature does not match the entry: {exc}" if str(exc) else "maintainer signature does not match the entry"
    return None


def _text_errors(entry: dict[str, Any]) -> list[str]:
    errs = [f"{k} must be 1-80 plain characters (no | < > [ ] ` \\ & \")" for k in ("author", "strategy", "idea_credit")
            if k in entry and not (isinstance(entry[k], str) and TEXT.match(entry[k]))]
    errs += [f"{k} must be YYYY-MM-DD" for k in ("submitted_at",) if not (isinstance(entry[k], str) and DATE.match(entry[k]))]
    if "code_url" in entry and not (isinstance(entry["code_url"], str) and URL.match(entry["code_url"])):
        errs.append("code_url must be an https URL")
    return errs


def check_entry(entry: dict[str, Any], certificate: dict[str, Any] | None, rules: dict[str, Any], trusted: dict[str, str], *,
                draft: bool = False) -> list[str]:
    """Every reason ``entry`` cannot be accepted (empty list: it can). Offline: hashes, signatures and recorded rechecks only.

    A ``draft`` tier B entry may still lack the maintainer's recheck and signature (the maintainer adds both with ``hall attest``).
    """
    missing = [k for k in REQUIRED if k not in entry]
    if missing:
        return [f"missing fields: {', '.join(missing)}"]
    errs = _text_errors(entry)
    if entry["schema"] != ENTRY_SCHEMA_ID:
        errs.append(f"schema must be {ENTRY_SCHEMA_ID}")
    if entry["tier"] not in rules["tiers"]:
        errs.append(f"unknown tier {entry['tier']!r}")
    if entry["category"] not in rules["categories"]:
        errs.append(f"unknown category {entry['category']!r}")
    if certificate is None:
        return [*errs, "certificate file is missing"]
    if certificate_sha256(certificate) != entry["certificate_sha256"]:
        return [*errs, "certificate SHA-256 differs from the entry (the certificate was changed)"]
    errs += _certificate_errors(entry, certificate, rules)
    tier = entry["tier"]
    rc = entry.get("recheck") or {}
    if draft and tier == "B":
        return errs
    if tier in ("A", "B") and rc.get("reproduced") is not True:
        errs.append(f"tier {tier} needs a recheck that reproduced the certificate")
    if tier == "A" and "code_url" not in entry:
        errs.append("tier A needs code_url (the open code)")
    if tier == "B" and (err := attestation_error(entry, trusted)):
        errs.append(err)
    return errs


def _certificate_errors(entry: dict[str, Any], certificate: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if certificate.get("schema") != "strategy-verdict/1":
        return ["certificate must be a strategy-verdict/1 certificate"]
    if "signature" in certificate and not check_signature(certificate)["valid"]:
        errs.append("certificate signature is not valid")
    s = summarize(certificate)
    n = s["n_trials"]
    if not isinstance(n, int) or isinstance(n, bool) or n < rules["limits"]["min_n_trials"]:
        errs.append("certificate has no valid n_trials (it is mandatory)")
    if not isinstance(s["arl"], int) or not isinstance(s["depth"], int):
        errs.append("certificate has no ARL block (issued before the ARL depth rules)")
    if (entry["arl_rules_version"], entry["provisional"]) != (s["arl_rules_version"], s["provisional"]):
        errs.append("arl_rules_version / provisional differ from the certificate")
    return errs


__all__ = ["ENTRY_SCHEMA_ID", "REQUIRED", "attest", "attestation_error", "certificate_sha256", "check_entry", "make_entry", "slug", "summarize"]
