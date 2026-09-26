"""Ed25519 signatures for ``strategy-verdict/1`` certificates.

A signature binds a certificate to a key: anyone holding the public key can
confirm that the certificate was issued by that key and not edited afterwards.
It does not re-run the checks; ``recheck_certificate`` does that.

The signed payload is the canonical JSON of the certificate without its
``signature`` field (sorted keys, no whitespace, UTF-8). Needs the optional
``cryptography`` package: ``pip install "monte-neo[sign]"``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from monte_neo.verify.recheck import load_certificate

SIGNATURE_ALG = "ed25519"
SIGNATURE_CHECK_SCHEMA_ID = "strategy-signature-check/1"
_PUB_PREFIX = "ed25519:"


def _crypto() -> Any:
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError('certificate signing needs the "sign" extra: pip install "monte-neo[sign]"') from exc
    return ed25519


def canonical_payload(certificate: dict[str, Any]) -> bytes:
    """Bytes that are signed: canonical JSON of the certificate minus ``signature``."""
    body = {k: v for k, v in certificate.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def key_id(public_raw: bytes) -> str:
    """Short fingerprint of a raw public key (first 16 hex chars of its SHA-256)."""
    return hashlib.sha256(public_raw).hexdigest()[:16]


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _public_raw(private_key: Any) -> bytes:
    from cryptography.hazmat.primitives import serialization

    return bytes(
        private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    )


def generate_keypair(prefix: str | Path) -> dict[str, str]:
    """Write ``<prefix>.key`` (PEM, owner-only) and ``<prefix>.pub`` (``ed25519:<base64>``)."""
    from cryptography.hazmat.primitives import serialization

    ed25519 = _crypto()
    base = Path(prefix)
    key_path, pub_path = base.with_name(base.name + ".key"), base.with_name(base.name + ".pub")
    if key_path.exists():
        raise FileExistsError(f"{key_path} already exists; refusing to overwrite a private key")
    private_key = ed25519.Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(pem)
    raw = _public_raw(private_key)
    pub_path.write_text(_PUB_PREFIX + _b64(raw) + "\n", encoding="utf-8")
    return {"private_key": str(key_path), "public_key": str(pub_path), "key_id": key_id(raw)}


def _load_private(key: str | Path | bytes) -> Any:
    from cryptography.hazmat.primitives import serialization

    ed25519 = _crypto()
    pem = key if isinstance(key, bytes) else Path(key).read_bytes()
    private_key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("signing key must be an Ed25519 private key")
    return private_key


def load_public_key(spec: str | Path) -> bytes:
    """Raw public key from ``ed25519:<base64>`` text or a file containing it."""
    text = str(spec).strip()
    if not text.startswith(_PUB_PREFIX):
        text = Path(spec).read_text(encoding="utf-8").strip()
    if not text.startswith(_PUB_PREFIX):
        raise ValueError(f"public key must look like '{_PUB_PREFIX}<base64>'")
    raw = base64.b64decode(text[len(_PUB_PREFIX) :], validate=True)
    if len(raw) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    return raw


def sign_certificate(certificate: dict[str, Any], private_key: str | Path | bytes) -> dict[str, Any]:
    """Return a copy of ``certificate`` with a ``signature`` block."""
    cert = json.loads(json.dumps(certificate))
    key = _load_private(private_key)
    raw = _public_raw(key)
    cert["signature"] = {
        "alg": SIGNATURE_ALG,
        "key_id": key_id(raw),
        "public_key": _PUB_PREFIX + _b64(raw),
        "value": _b64(key.sign(canonical_payload(cert))),
    }
    return cert


def check_signature(
    certificate: dict[str, Any] | str | Path, public_key: str | Path | None = None
) -> dict[str, Any]:
    """Check a certificate's signature (``strategy-signature-check/1``).

    ``valid`` means the certificate was not changed after signing. Without
    ``public_key`` that only proves integrity: anyone can sign with a new key.
    Pass the issuer's published key to also check who signed (``key_matches``).
    """
    ed25519 = _crypto()
    from cryptography.exceptions import InvalidSignature

    cert = load_certificate(certificate)
    sig = cert.get("signature")
    result: dict[str, Any] = {
        "schema": SIGNATURE_CHECK_SCHEMA_ID,
        "certificate_id": cert.get("certificate_id"),
        "verdict": cert.get("verdict"),
        "signed": isinstance(sig, dict),
        "valid": False,
        "key_id": None,
        "key_matches": None,
    }
    if not isinstance(sig, dict):
        result["reason"] = "certificate is not signed"
        return result
    try:
        if sig.get("alg") != SIGNATURE_ALG:
            raise ValueError(f"unsupported signature algorithm {sig.get('alg')!r}")
        embedded = load_public_key(str(sig["public_key"]))
        result["key_id"] = key_id(embedded)
        ed25519.Ed25519PublicKey.from_public_bytes(embedded).verify(
            base64.b64decode(str(sig["value"]), validate=True), canonical_payload(cert)
        )
        result["valid"] = True
    except (InvalidSignature, ValueError, KeyError) as exc:
        result["reason"] = f"signature does not match: {exc}" if str(exc) else "signature does not match the certificate"
        return result
    if public_key is not None:
        result["key_matches"] = load_public_key(public_key) == embedded
        if not result["key_matches"]:
            result["reason"] = "signed with a different key than the one expected"
    else:
        result["reason"] = "integrity only: pass the issuer's public key to check who signed"
    return result


def signature_ok(result: dict[str, Any]) -> bool:
    """True when the signature is valid and, if a key was expected, matches it."""
    return bool(result["valid"]) and result["key_matches"] is not False


__all__ = [
    "SIGNATURE_ALG",
    "SIGNATURE_CHECK_SCHEMA_ID",
    "canonical_payload",
    "check_signature",
    "generate_keypair",
    "key_id",
    "load_public_key",
    "sign_certificate",
    "signature_ok",
]
