"""Unit tests for Ed25519 certificate signatures (CLI, MCP and library)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from rich.console import Console

pytest.importorskip("cryptography")

from monte_neo.backtest import synthetic_ohlcv  # noqa: E402
from monte_neo.cli import verify_cmd  # noqa: E402
from monte_neo.mcp import tools  # noqa: E402
from monte_neo.verify import check_signature, generate_keypair, sign_certificate, verify_strategy  # noqa: E402
from monte_neo.verify.signing import canonical_payload, load_public_key, signature_ok  # noqa: E402


@pytest.fixture(scope="module")
def cert() -> dict:
    df = synthetic_ohlcv(600, seed=3)
    sig = (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy()
    return json.loads(json.dumps(verify_strategy(df, signals=sig)))


@pytest.fixture()
def keys(tmp_path) -> dict[str, str]:
    return generate_keypair(tmp_path / "issuer")


def _run(argv: list[str]) -> tuple[int, str]:
    console = Console(record=True, width=200)
    code = verify_cmd.run(verify_cmd.build_parser().parse_args(argv), console)
    return code, console.export_text()


def test_sign_and_check(cert, keys, tmp_path) -> None:
    signed = sign_certificate(cert, keys["private_key"])
    assert signed["signature"]["key_id"] == keys["key_id"] and "signature" not in cert
    assert canonical_payload(signed) == canonical_payload(cert)
    res = check_signature(signed)
    assert res["valid"] and res["key_matches"] is None and "integrity only" in res["reason"]
    assert signature_ok(check_signature(signed, public_key=keys["public_key"]))
    path = tmp_path / "signed.json"
    path.write_text(json.dumps(signed, indent=2))
    assert check_signature(path, public_key=open(keys["public_key"]).read().strip())["key_matches"] is True


def test_tampering_and_wrong_key_are_detected(cert, keys, tmp_path) -> None:
    signed = sign_certificate(cert, keys["private_key"])
    edited = json.loads(json.dumps(signed))
    edited["verdict"] = "PASS" if cert["verdict"] != "PASS" else "REJECT"
    res = check_signature(edited)
    assert not res["valid"] and "does not match" in res["reason"]
    other = generate_keypair(tmp_path / "other")
    res = check_signature(signed, public_key=other["public_key"])
    assert res["valid"] and res["key_matches"] is False and not signature_ok(res)
    unsigned = check_signature(cert)
    assert unsigned["signed"] is False and not unsigned["valid"]
    bad_alg = json.loads(json.dumps(signed))
    bad_alg["signature"]["alg"] = "rsa"
    assert "unsupported" in check_signature(bad_alg)["reason"]
    bad_b64 = json.loads(json.dumps(signed))
    bad_b64["signature"]["value"] = "!!"
    assert not check_signature(bad_b64)["valid"]


def test_key_files_and_errors(keys, tmp_path) -> None:
    with pytest.raises(FileExistsError):
        generate_keypair(tmp_path / "issuer")
    assert oct((tmp_path / "issuer.key").stat().st_mode)[-3:] == "600"
    with pytest.raises(ValueError, match="look like"):
        load_public_key(tmp_path / "issuer.key")
    with pytest.raises(ValueError, match="32 bytes"):
        load_public_key("ed25519:AAAA")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    ec_pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    with pytest.raises(ValueError, match="Ed25519"):
        sign_certificate({"schema": "strategy-verdict/1"}, ec_pem)


def test_cli_keygen_sign_and_check(keys, tmp_path) -> None:
    df = synthetic_ohlcv(600, seed=5)
    ohlcv = tmp_path / "ohlcv.csv"
    df.to_csv(ohlcv, index=False)
    sig = tmp_path / "s.npy"
    np.save(sig, (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy())
    code, text = _run(["--keygen", str(tmp_path / "cli")])
    assert code == 0 and "key id" in text
    code, text = _run(["--keygen", str(tmp_path / "cli")])
    assert code == 3 and "already exists" in text
    out = tmp_path / "cert.json"
    code, _ = _run(["--ohlcv", str(ohlcv), "--signals", str(sig), "--sign", keys["private_key"], "--out", str(out)])
    assert code in (0, 1, 2) and "signature" in json.loads(out.read_text())
    code, text = _run(["--check-signature", str(out), "--public-key", keys["public_key"]])
    assert code == 0 and '"key_matches": true' in text
    code, _ = _run(["--check-signature", str(out), "--public-key", str(tmp_path / "cli.pub")])
    assert code == 5
    code, text = _run(["--ohlcv", str(ohlcv), "--signals", str(sig), "--sign", str(tmp_path / "missing.key")])
    assert code == 3 and "signing failed" in text
    code, text = _run(["--check-signature", str(tmp_path / "missing.json")])
    assert code == 3 and "signature command failed" in text


def test_mcp_check_signature(cert, keys, tmp_path) -> None:
    path = tmp_path / "signed.json"
    path.write_text(json.dumps(sign_certificate(cert, keys["private_key"])))
    assert tools.check_signature(str(path), public_key=keys["public_key"])["key_matches"] is True
    assert "error" in tools.check_signature(str(tmp_path / "missing.json"))
