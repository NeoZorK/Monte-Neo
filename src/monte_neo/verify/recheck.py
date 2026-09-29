"""Re-check a ``strategy-verdict/1`` certificate against the original inputs.

A certificate is only worth something if a third party can reproduce it. Given
the same OHLCV and signals / strategy code, ``recheck_certificate`` confirms the
input hashes, re-runs the verifier with the recorded execution model and
``n_trials`` and compares the verdict and ``certificate_id``.
"""

from __future__ import annotations

import hashlib
import json
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo._version import __version__
from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.grid import verify_grid
from monte_neo.verify.ingest import load_ohlcv, load_signal_fn, to_positions
from monte_neo.verify.market import market_for
from monte_neo.verify.schema import VERDICT_SCHEMA_ID
from monte_neo.verify.verdict import verify_strategy

RECHECK_SCHEMA_ID = "strategy-recheck/1"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_certificate(source: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Certificate dict from a dict or a JSON file; validates the schema id."""
    cert = source if isinstance(source, dict) else json.loads(Path(source).read_text(encoding="utf-8"))
    if cert.get("schema") != VERDICT_SCHEMA_ID:
        raise ValueError(f"not a {VERDICT_SCHEMA_ID} certificate")
    return cert


def recheck_certificate(
    certificate: dict[str, Any] | str | Path,
    ohlcv: pd.DataFrame | str | Path,
    *,
    signals: Any = None,
    strategy: str | Path | None = None,
) -> dict[str, Any]:
    """Reproduce a certificate; ``reproduced`` is True only if everything matches.

    Grid certificates are reproduced by re-running the recorded grid search.
    """
    cert = load_certificate(certificate)
    repro = cert["reproducibility"]
    df = load_ohlcv(ohlcv)
    market = market_for(df)
    data_bytes = market.data_bytes()
    grid = cert.get("grid")
    settings = repro.get("settings") or {}  # absent before v0.34.0: the defaults applied
    mode = settings.get("positions") or "sign"  # before v0.35.0 every signal was read as signs
    if mode == "auto":  # the data check stopped the run before the signal was read
        mode = "sign"
    fn = source = None
    if strategy is not None:
        fn, source = load_signal_fn(strategy)
        best = (grid or {}).get("best_params") or {}
        sig = to_positions(market.read_values(partial(fn, **best), None), mode)
    elif signals is not None:
        sig = to_positions(market.read_values(None, signals), mode)
    else:
        raise ValueError("provide signals or strategy used for the certificate")

    inputs = {
        "data_sha256": _sha(data_bytes) == repro.get("data_sha256"),
        # None: the run stopped at the data check before reading the signal.
        "signals_sha256": repro.get("signals_sha256") is None
        or _sha(np.ascontiguousarray(sig).tobytes()) == repro["signals_sha256"],
        "source_sha256": repro.get("source_sha256") is None
        or (source is not None and _sha(source.encode("utf-8")) == repro["source_sha256"]),
    }
    report: dict[str, Any] = {
        "schema": RECHECK_SCHEMA_ID,
        "certificate_id": cert.get("certificate_id"),
        "original_verdict": cert.get("verdict"),
        "original_engine_version": repro.get("engine_version"),
        "engine_version": __version__,
        "inputs_match": inputs,
    }
    if not all(inputs.values()):
        report.update(reproduced=False, reason="inputs differ from the certificate")
        return report

    if grid is not None and "spec" not in grid:
        report.update(reproduced=False, reason="grid spec not recorded (certificate older than v0.20.0)")
        return report
    model = ExecutionModel(**repro["model"])
    if grid is not None and fn is not None:
        again = verify_grid(df, grid["spec"], signal_fn=fn, source=source, model=model, folds=grid["folds"], **settings)
    else:
        again = verify_strategy(
            df, signals=sig if fn is None else None, signal_fn=fn, source=source,
            model=model, n_trials=repro.get("n_trials"), **settings,
        )
    same_verdict = again["verdict"] == cert.get("verdict")
    same_id = again["certificate_id"] == cert.get("certificate_id")
    report.update(
        verdict=again["verdict"],
        recomputed_certificate_id=again["certificate_id"],
        verdict_matches=same_verdict,
        certificate_id_matches=same_id,
        reproduced=bool(same_verdict and same_id),
    )
    if not report["reproduced"]:
        if repro.get("engine_version") != __version__:
            # The engine version is part of the certificate id, and checks change between releases.
            report["reason"] = (
                f"certificate was issued by monte-neo {repro.get('engine_version')}; this is {__version__}. "
                f"Recheck with the same version: pip install monte-neo=={str(repro.get('engine_version')).lstrip('v')}"
            )
        else:
            report["reason"] = "verdict differs" if not same_verdict else "certificate id differs"
    return report


__all__ = ["RECHECK_SCHEMA_ID", "load_certificate", "recheck_certificate"]
