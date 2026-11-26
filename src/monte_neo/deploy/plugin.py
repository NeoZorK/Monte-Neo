"""The strategy plug-in contract: ``target_weights(closes_by_symbol) -> {symbol: weight}``.

The user's Python file defines ``target_weights``. It receives the complete daily closes (oldest first, the last bar is
the last one that closed before the day being recorded) and returns the weight of TOTAL capital per symbol. On a long-only
venue (spot) each weight is 0..1 and they sum to at most 1; the rest stays in cash. On a venue that allows shorts (USD-M
futures) a weight may be negative (a short) and the gross exposure, the sum of absolute weights, is at most the run's
``max_gross``. The output is validated on every call and anything else is refused.

The file is loaded with the same loader as ``monte-neo verify --strategy`` (:func:`monte_neo.verify.ingest.load_signal_fn`),
so it runs with the caller's permissions: only deploy code you would run yourself.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

ENTRYPOINT = "target_weights"
TOLERANCE = 1e-9

WeightsFn = Callable[[dict[str, list[float]]], dict[str, float]]


class PluginError(ValueError):
    """The strategy file or its output does not follow the contract."""


def load(path: Path | str) -> WeightsFn:
    """Import ``path`` and return its ``target_weights`` function (same loader as ``monte-neo verify``)."""
    from monte_neo.verify.ingest import load_signal_fn

    p = Path(path)
    if not p.is_file():
        raise PluginError(f"strategy file not found: {p}")
    try:
        fn, _source = load_signal_fn(f"{p}:{ENTRYPOINT}")
    except AttributeError as exc:
        raise PluginError(f"{p.name} must define {ENTRYPOINT}(closes_by_symbol: dict[str, list[float]]) -> dict[str, float]") from exc
    except (ImportError, SyntaxError, OSError) as exc:
        raise PluginError(f"cannot load {p.name}: {exc}") from exc
    return fn  # type: ignore[return-value]


def validate(weights: Any, symbols: list[str], allow_short: bool = False, max_gross: float = 1.0) -> dict[str, float]:
    """Check the output of ``target_weights`` and return a full ``{symbol: weight}`` map (missing symbols get 0.0)."""
    if not isinstance(weights, dict):
        raise PluginError(f"{ENTRYPOINT} must return a dict of symbol -> weight, got {type(weights).__name__}")
    out = {s: 0.0 for s in symbols}
    for key, w in weights.items():
        if key not in out:
            raise PluginError(f"{ENTRYPOINT} returned a weight for {key!r}, which is not one of the run's symbols {symbols}")
        if isinstance(w, bool) or not isinstance(w, int | float):
            raise PluginError(f"weight of {key} must be a number, got {type(w).__name__}")
        if not math.isfinite(w):
            raise PluginError(f"weight of {key} is not finite ({w})")
        if allow_short:
            if abs(w) > max_gross + TOLERANCE:
                raise PluginError(f"weight of {key} is {w}: a single weight cannot exceed the gross limit {max_gross:g}")
            out[key] = float(w)
            continue
        if w < -TOLERANCE or w > 1.0 + TOLERANCE:
            raise PluginError(f"weight of {key} is {w}: long-only weights must be between 0 and 1 (no shorts, no leverage on this venue)")
        out[key] = min(1.0, max(0.0, float(w)))
    if allow_short:
        gross = sum(abs(v) for v in out.values())
        if gross > max_gross + TOLERANCE:
            raise PluginError(f"gross exposure is {gross:.6f}: the sum of absolute weights must be at most {max_gross:g}")
        return out
    total = sum(out.values())
    if total > 1.0 + TOLERANCE:
        raise PluginError(f"weights sum to {total:.6f}: they are shares of total capital and must sum to at most 1")
    return out


def call(fn: WeightsFn, closes: dict[str, list[float]], symbols: list[str], allow_short: bool = False, max_gross: float = 1.0) -> dict[str, float]:
    """Run the plug-in on a private copy of the closes and validate its answer."""
    private = {s: list(c) for s, c in closes.items()}
    try:
        raw = fn(private)
    except PluginError:
        raise
    except Exception as exc:
        raise PluginError(f"{ENTRYPOINT} raised {type(exc).__name__}: {exc}") from exc
    return validate(raw, symbols, allow_short, max_gross)
