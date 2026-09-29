"""Security tests: hostile certificates, signatures, HTML and oversized inputs."""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_strategy
from monte_neo.verify.limits import (
    MAX_CERTIFICATE_BYTES,
    check_size,
    loads_strict,
    read_source,
    table_limit_bytes,
)
from monte_neo.verify.recheck import load_certificate
from monte_neo.verify.report_html import CSP, render_html

pytest.importorskip("cryptography")
from monte_neo.verify.signing import (  # noqa: E402
    canonical_payload,
    check_signature,
    generate_keypair,
    sign_certificate,
)

HOSTILE = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    '"><svg onload=alert(1)>',
    "javascript:alert(1)",
    "</style><script>x</script>",
    "'; DROP TABLE t; --",
    "‮\u0000퟿{{7*7}}${jndi:ldap://x}",
]


@pytest.fixture(scope="module")
def signed(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Any], str]:
    df = synthetic_ohlcv(500, seed=2)
    sig = (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy()
    cert = json.loads(json.dumps(verify_strategy(df, signals=sig, n_trials=2)))
    keys = generate_keypair(tmp_path_factory.mktemp("keys") / "k")
    pub = Path(keys["public_key"]).read_text().strip()
    return sign_certificate(cert, keys["private_key"]), pub


def _paths(node: Any, prefix: tuple = ()) -> list[tuple]:
    out = [prefix] if prefix else []
    if isinstance(node, dict):
        for k, v in node.items():
            out += _paths(v, prefix + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += _paths(v, prefix + (i,))
    return out


def _set(root: Any, path: tuple, value: Any) -> None:
    for step in path[:-1]:
        root = root[step]
    root[path[-1]] = value


def _mutate(cert: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    out = copy.deepcopy(cert)
    pool: list[Any] = [None, "", 0, 1, -1, 2**70, 0.5, -0.0, True, [], {}, [1, 2], {"a": 1}, "PASS", "é", *HOSTILE]
    for _ in range(rng.randint(1, 3)):
        path = rng.choice([p for p in _paths(out) if p[0] != "signature"])  # the block has its own test
        if rng.random() < 0.25 and isinstance(path[-1], str):
            parent = out
            for step in path[:-1]:
                parent = parent[step]
            parent.pop(path[-1], None)
        else:
            _set(out, path, rng.choice(pool))
    return out


def test_signature_mutation_fuzz(signed: tuple[dict[str, Any], str]) -> None:
    """A changed certificate is never 'valid' unless its canonical bytes are unchanged; nothing crashes."""
    cert, pub = signed
    original = canonical_payload(cert)
    rng = random.Random(20260929)
    changed = 0
    for _ in range(600):
        mutated = _mutate(cert, rng)
        try:
            same = canonical_payload(mutated) == original
        except (ValueError, TypeError):
            same = False
        result = check_signature(mutated, pub)  # must not raise
        assert result["valid"] is same, (result, mutated)
        changed += not same
    assert changed > 400  # the fuzzer really changes things


def test_signature_block_garbage_never_crashes(signed: tuple[dict[str, Any], str]) -> None:
    cert, pub = signed
    junk = [None, 0, 1.5, "", "x", [], {}, [1], {"a": 1}, True, "ed25519:", "ed25519:AAAA", "=" * 10, "é" * 50, 2**80]
    for alg in ["ed25519", *junk]:
        for public_key in [cert["signature"]["public_key"], *junk]:
            for value in [cert["signature"]["value"], *junk]:
                broken = copy.deepcopy(cert)
                broken["signature"] = {"alg": alg, "key_id": junk[2], "public_key": public_key, "value": value}
                result = check_signature(broken, pub)
                assert result["signed"] is True
                assert result["valid"] is (alg == "ed25519" and public_key == cert["signature"]["public_key"] and value == cert["signature"]["value"])
    for sig in junk[:9]:
        broken = copy.deepcopy(cert)
        broken["signature"] = sig
        assert check_signature(broken, pub)["valid"] is False


def test_signing_with_another_key_is_valid_but_not_the_expected_key(signed: tuple[dict[str, Any], str], tmp_path: Path) -> None:
    """A forger can sign a fake certificate with their own key: only the issuer's key tells them apart."""
    cert, pub = signed
    forged = copy.deepcopy(cert)
    forged["verdict"] = "PASS"
    forged.pop("signature")
    other = generate_keypair(tmp_path / "forger")
    forged = sign_certificate(forged, other["private_key"])
    intact = check_signature(forged)
    assert intact["valid"] is True and intact["key_matches"] is None  # "integrity only"
    against_issuer = check_signature(forged, pub)
    assert against_issuer["valid"] is True and against_issuer["key_matches"] is False


def test_duplicate_keys_nan_and_depth_are_rejected(tmp_path: Path) -> None:
    for text in ['{"schema": "strategy-verdict/1", "schema": "x"}', '{"a": NaN}', '{"a": Infinity}', '{"a": -Infinity}', "[" * 150 + "]" * 150]:
        with pytest.raises(ValueError):
            loads_strict(text)
        path = tmp_path / "c.json"
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError):
            load_certificate(path)
    path = tmp_path / "list.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_certificate(path)


def test_extreme_nesting_is_a_value_error() -> None:
    """Deeper than Python's recursion limit: a clear error, not a crash of the verifier."""
    with pytest.raises(ValueError, match="nested too deeply"):
        loads_strict("[" * 100_000 + "]" * 100_000)


def test_certificate_loader_garbage_only_raises_value_errors(tmp_path: Path) -> None:
    rng = random.Random(5)
    path = tmp_path / "garbage.json"
    for _ in range(200):
        blob = bytes(rng.randrange(256) for _ in range(rng.randint(0, 200)))
        path.write_bytes(blob)
        try:
            load_certificate(path)
        except ValueError:  # includes JSON and UTF-8 decoding errors
            pass


def test_input_size_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    big = tmp_path / "prices.csv"
    big.write_bytes(b"x" * 2048)
    monkeypatch.setenv("MONTE_NEO_MAX_INPUT_MB", "0.001")  # about 1 KB
    assert table_limit_bytes() == int(0.001 * 1024 * 1024)
    from monte_neo.verify import load_ohlcv

    with pytest.raises(ValueError, match="MB limit.*MONTE_NEO_MAX_INPUT_MB"):
        load_ohlcv(big)
    monkeypatch.setenv("MONTE_NEO_MAX_INPUT_MB", "not a number")
    assert table_limit_bytes() == 2048 * 1024 * 1024
    monkeypatch.delenv("MONTE_NEO_MAX_INPUT_MB")
    assert table_limit_bytes() == 2048 * 1024 * 1024

    cert = tmp_path / "cert.json"
    cert.write_bytes(b" " * 10)
    with pytest.raises(ValueError, match="certificate file cert.json"):
        check_size(cert, 5, "certificate")
    assert MAX_CERTIFICATE_BYTES > 10 * 1024 * 1024

    src = tmp_path / "strategy.py"
    src.write_text("x = 1\n" + "#" * (6 * 1024 * 1024), encoding="utf-8")
    with pytest.raises(ValueError, match="strategy file strategy.py"):
        read_source(src)


def test_npy_signals_never_unpickle(tmp_path: Path) -> None:
    """A .npy file with a pickled object array must be refused, not executed."""
    from monte_neo.verify import load_signals

    path = tmp_path / "evil.npy"
    np.save(path, np.array([{"a": 1}, None], dtype=object), allow_pickle=True)
    with pytest.raises(ValueError, match="pickle"):
        load_signals(path)


def _all_strings(node: Any, fn: Any) -> Any:
    if isinstance(node, dict):
        return {k: _all_strings(v, fn) for k, v in node.items()}
    if isinstance(node, list):
        return [_all_strings(v, fn) for v in node]
    return fn(node) if isinstance(node, str) else node


def test_html_report_escapes_every_field_and_ships_a_csp(signed: tuple[dict[str, Any], str]) -> None:
    cert, _ = signed
    rng = random.Random(1)
    for _ in range(25):
        hostile = _all_strings(cert, lambda s: rng.choice(HOSTILE) + s[:5])
        page = render_html(hostile)
        assert "<script" not in page.lower()  # the report has no scripts at all
        for payload in HOSTILE:
            if any(ch in payload for ch in "<>\"'"):
                assert payload not in page  # markup only ever appears escaped
        assert 'href="javascript' not in page.lower() and "href='javascript" not in page.lower()
        assert f'content="{CSP}"' in page
        assert "default-src 'none'" in CSP and "script" not in CSP.replace("default-src 'none'", "")
    assert "rel=\"noopener noreferrer\"" in render_html(cert)


def test_mcp_render_report_only_writes_html(signed: tuple[dict[str, Any], str], tmp_path: Path) -> None:
    from monte_neo.mcp.tools import render_report

    cert, _ = signed
    src = tmp_path / "cert.json"
    src.write_text(json.dumps(cert), encoding="utf-8")
    victim = tmp_path / "authorized_keys"
    victim.write_text("keep me", encoding="utf-8")
    for target in (victim, tmp_path / "x.sh", tmp_path / "no_suffix", tmp_path / ".bashrc"):
        result = render_report(str(src), str(target))
        assert "html_path must end with .html" in result["error"]
    assert victim.read_text(encoding="utf-8") == "keep me"
    assert render_report(str(src), str(tmp_path / "ok.HTML"))["bytes"] > 1000


def test_embedded_public_key_is_never_read_as_a_file(signed: tuple[dict[str, Any], str], tmp_path: Path) -> None:
    """The key inside a certificate is text: a path there must not make the verifier open the file."""
    cert, pub = signed
    secret = tmp_path / "secret.txt"
    secret.write_text("ed25519:" + "A" * 43 + "=", encoding="utf-8")  # a well-formed key, in a file
    broken = copy.deepcopy(cert)
    broken["signature"]["public_key"] = str(secret)
    result = check_signature(broken, pub)
    assert result["valid"] is False and result["key_id"] is None
    assert "must look like" in result["reason"]
    # The key the user passes to check against may still be a file.
    assert check_signature(cert, Path(tmp_path / "expected.pub").write_text(pub) and tmp_path / "expected.pub")["key_matches"] is True
