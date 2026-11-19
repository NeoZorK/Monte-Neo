"""Atheris target: arbitrary bytes as an OHLCV table, a signals table and strategy source.

Allowed outcomes are a result or ``ValueError``-like refusals; any other exception is a finding.
"""

import sys
import tempfile
from pathlib import Path

import atheris

with atheris.instrument_imports():
    import pandas as pd

    from monte_neo.verify.ingest import load_ohlcv, load_signals
    from monte_neo.verify.lint import lint_source

REFUSALS = (ValueError, KeyError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError)


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    suffix = fdp.PickValueInList([".csv", ".txt", ".parquet"])
    payload = fdp.ConsumeBytes(fdp.remaining_bytes())
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"t{suffix}"
        path.write_bytes(payload)
        for loader in (load_ohlcv, lambda p: load_signals(p, n_bars=50)):
            try:
                loader(path)
            except REFUSALS:
                pass
            except Exception as exc:  # noqa: BLE001 - parquet errors come from pyarrow
                if not type(exc).__module__.startswith(("pyarrow", "pandas")):
                    raise
    lint_source(payload.decode("utf-8", "replace"))


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
