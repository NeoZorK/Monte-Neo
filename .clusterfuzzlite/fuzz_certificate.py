"""Atheris target: arbitrary text as a certificate for load, recheck input validation and signature check."""

import sys
import tempfile
from pathlib import Path

import atheris

with atheris.instrument_imports():
    from monte_neo.verify.recheck import load_certificate
    from monte_neo.verify.signing import check_signature


def test_one_input(data: bytes) -> None:
    text = data.decode("utf-8", "replace")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cert.json"
        path.write_text(text, encoding="utf-8")
        try:
            load_certificate(path)
            check_signature(path)
        except (ValueError, KeyError):
            pass


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
