"""The browser verifier (docs/assets/verify-certificate.js) must agree with Python.

Runs the JavaScript in Node; skipped when Node is not installed.
"""

from __future__ import annotations

import json
import math
import random
import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from monte_neo.backtest import synthetic_ohlcv  # noqa: E402
from monte_neo.verify import generate_keypair, sign_certificate, verify_strategy  # noqa: E402
from monte_neo.verify.signing import canonical_payload  # noqa: E402

NODE = shutil.which("node")
JS = Path(__file__).resolve().parents[2] / "docs" / "assets" / "verify-certificate.js"
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _node(script: str, payload: dict) -> dict:
    code = f"const v = require({json.dumps(str(JS))});\nconst input = JSON.parse(process.argv[1]);\n{script}"
    out = subprocess.run([NODE, "-e", code, json.dumps(payload)], capture_output=True, text=True, check=True, timeout=60)
    return json.loads(out.stdout)


def test_float_repr_matches_python() -> None:
    rng = random.Random(7)
    values = [0.0, -0.0, 1.0, -2.5, 1e16, 1e15, 1e-4, 1e-5, 123456789.125, 5e-324, 1.7976931348623157e308, 0.1 + 0.2]
    values += [rng.uniform(-1, 1) * 10 ** rng.randint(-12, 20) for _ in range(500)]
    got = _node("console.log(JSON.stringify(input.map(v.pyFloatRepr)))", values)  # type: ignore[arg-type]
    assert got == [repr(v) for v in values]


def test_canonical_payload_and_signature_match(tmp_path) -> None:
    df = synthetic_ohlcv(600, seed=11)
    sig = (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy()
    cert = json.loads(json.dumps(verify_strategy(df, signals=sig, n_trials=3)))
    cert["notes"] = {"unicode": "Δ ü 日本  ", "ctrl": "tab\tnl\nq\"b\\", "floats": [1.0, 1e-7, -0.0, 2e16, math.pi]}
    keys = generate_keypair(tmp_path / "k")
    signed = sign_certificate(cert, keys["private_key"])
    pub = Path(keys["public_key"]).read_text().strip()
    tampered = json.loads(json.dumps(signed))
    tampered["verdict"] = "PASS" if signed["verdict"] != "PASS" else "REJECT"
    payload = {"text": json.dumps(signed, indent=2), "tampered": json.dumps(tampered), "pub": pub}
    res = _node(
        """
(async () => {
  const good = await v.checkSignature(input.text, input.pub);
  const noKey = await v.checkSignature(input.text, "");
  const bad = await v.checkSignature(input.tampered, input.pub);
  console.log(JSON.stringify({canon: v.canonicalPayload(input.text), good, noKey, bad}));
})();
""",
        payload,
    )
    assert res["canon"] == canonical_payload(signed).decode("utf-8")
    assert res["good"]["valid"] is True and res["good"]["key_matches"] is True
    assert res["good"]["key_id"] == keys["key_id"]
    assert res["noKey"]["valid"] is True and res["noKey"]["key_matches"] is None
    assert res["bad"]["valid"] is False
