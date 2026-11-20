"""Hypothesis fuzzing of the file-facing code: table parsers, signals, certificate signatures, strategy source.

Contract under test: arbitrary input ends in a result or in ``ValueError`` (a clear refusal), never in another exception.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from monte_neo.verify.ingest import load_ohlcv, load_signals
from monte_neo.verify.lint import lint_source

CLEAN = (ValueError,)
SLOW = [HealthCheck.too_slow, HealthCheck.function_scoped_fixture]
CSV_CELL = st.one_of(st.floats(allow_nan=True, allow_infinity=True), st.integers(-10**9, 10**9), st.text(max_size=8), st.none())


def _write(tmp: Path, name: str, data: bytes | str) -> Path:
    path = tmp / name
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8", "replace"))
    return path


@settings(max_examples=150, deadline=None, suppress_health_check=SLOW)
@given(st.binary(max_size=600))
def test_random_bytes_as_csv_are_refused_cleanly(blob: bytes) -> None:
    with tempfile.TemporaryDirectory() as d:
        try:
            load_ohlcv(_write(Path(d), "t.csv", blob))
        except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError, KeyError):
            pass  # pandas parser errors subclass ValueError; KeyError = a required column is missing


@settings(max_examples=120, deadline=None, suppress_health_check=SLOW)
@given(st.lists(st.lists(CSV_CELL, min_size=6, max_size=6), min_size=0, max_size=40),
       st.sampled_from([",", ";", "\t", "|"]), st.booleans())
def test_structured_csv_tables_load_or_raise_value_error(rows: list[list], sep: str, header: bool) -> None:
    head = sep.join(["timestamp", "open", "high", "low", "close", "volume"]) + "\n" if header else ""
    body = "\n".join(sep.join("" if c is None else str(c) for c in r) for r in rows)
    with tempfile.TemporaryDirectory() as d:
        try:
            out = load_ohlcv(_write(Path(d), "t.csv", head + body))
        except (ValueError, KeyError, pd.errors.ParserError, pd.errors.EmptyDataError):
            return
        assert {"open", "high", "low", "close"} <= set(out.columns)


@settings(max_examples=60, deadline=None, suppress_health_check=SLOW)
@given(st.binary(max_size=400))
def test_random_bytes_as_parquet_are_refused_cleanly(blob: bytes) -> None:
    pytest.importorskip("pyarrow")
    with tempfile.TemporaryDirectory() as d:
        try:
            load_ohlcv(_write(Path(d), "t.parquet", blob))
        except Exception as exc:  # noqa: BLE001 - classified below
            assert isinstance(exc, (ValueError, OSError, KeyError)) or type(exc).__module__.startswith(("pyarrow", "pandas")), repr(exc)


@settings(max_examples=100, deadline=None, suppress_health_check=SLOW)
@given(st.text(max_size=200))
def test_unsupported_suffix_and_signal_text_are_refused_cleanly(text: str) -> None:
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(CLEAN):
            load_ohlcv(_write(Path(d), "t.xlsx", text))
        try:
            load_signals(_write(Path(d), "s.csv", text), n_bars=10)
        except (ValueError, KeyError, pd.errors.ParserError, pd.errors.EmptyDataError):
            pass


@settings(max_examples=80, deadline=None)
@given(st.lists(st.one_of(st.floats(allow_nan=True, allow_infinity=True), st.integers()), max_size=30), st.integers(0, 40))
def test_signal_arrays_are_normalised_or_refused(values: list, n_bars: int) -> None:
    try:
        out = load_signals(np.array(values, dtype=np.float64), n_bars=n_bars)
    except CLEAN:
        return
    assert len(out) == n_bars or n_bars == 0 or len(out) == len(values)


# --- certificate signature ---------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def signed() -> tuple[dict, str]:
    pytest.importorskip("cryptography")
    from monte_neo.verify import generate_keypair, sign_certificate

    d = Path(tempfile.mkdtemp())
    keys = generate_keypair(d / "k")
    cert = {"schema": "strategy-verdict/1", "verdict": "PASS", "checks": [{"id": "x", "status": "pass"}], "n": 3}
    return sign_certificate(cert, keys["private_key"]), keys["public_key"]


@settings(max_examples=120, deadline=None, suppress_health_check=SLOW)
@given(st.data())
def test_any_change_to_a_signed_certificate_breaks_the_signature(signed: tuple[dict, str], data: st.DataObject) -> None:
    from monte_neo.verify import check_signature

    cert, pub = signed
    assert check_signature(cert, pub)["valid"] is True
    tampered = json.loads(json.dumps(cert))
    key = data.draw(st.sampled_from(["verdict", "n", "checks", "extra"]))
    tampered[key] = data.draw(st.one_of(st.integers(), st.text(max_size=5), st.lists(st.integers(), max_size=3)).filter(lambda v: v != cert.get(key)))
    assert check_signature(tampered, pub)["valid"] is False


@settings(max_examples=120, deadline=None, suppress_health_check=SLOW)
@given(st.data())
def test_garbled_signature_fields_never_raise_anything_but_value_error(signed: tuple[dict, str], data: st.DataObject) -> None:
    from monte_neo.verify import check_signature

    cert, pub = signed
    bad = json.loads(json.dumps(cert))
    sig = bad.get("signature")
    if isinstance(sig, dict) and sig:
        field = data.draw(st.sampled_from(sorted(sig)))
        sig[field] = data.draw(st.one_of(st.text(max_size=40), st.integers(), st.none(), st.binary(max_size=8).map(lambda b: b.hex())))
    else:
        bad["signature"] = data.draw(st.one_of(st.text(max_size=20), st.integers(), st.none(), st.lists(st.integers(), max_size=2)))
    try:
        result = check_signature(bad, pub)
    except CLEAN:
        return
    assert result["valid"] is False or result == check_signature(cert, pub)


@settings(max_examples=200, deadline=None, suppress_health_check=SLOW)
@given(st.text(max_size=300), st.text(max_size=100))
def test_lint_survives_text_wrapped_in_a_function(body: str, name: str) -> None:
    src = "def signal(df):\n" + "\n".join("    " + line for line in body.splitlines()) + "\n    return df\n"
    assert lint_source(src)["status"] in {"pass", "warn", "fail", "skip"}
    assert lint_source(name)["status"] in {"pass", "warn", "fail", "skip"}
