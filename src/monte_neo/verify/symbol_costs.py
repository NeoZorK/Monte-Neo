"""Trading costs that differ by symbol, for universes.

A universe mixes liquid and illiquid names, so one commission and one slippage for every symbol is
often wrong. The costs are given as a mapping (a dict, JSON text or a JSON file)::

    {"default": {"commission_bps": 5, "slippage_bps": 5},
     "AAA": {"commission_bps": 2, "slippage_bps": 1},
     "ZZZ": {"slippage_bps": 30}}

A symbol takes its own keys, then ``default``, then the model's uniform costs. A name that is not in the
data is an error (a typo would otherwise be ignored). The result is written into the certificate as one row per
symbol, in the table's column order, so a recheck needs no other input.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.limits import MAX_GRID_BYTES, loads_strict, read_text_limited

KEYS = ("commission_bps", "slippage_bps")
DEFAULT = "default"


def parse_symbol_costs(spec: dict[str, Any] | str | Path) -> dict[str, dict[str, float]]:
    """A validated mapping ``{symbol: {commission_bps, slippage_bps}}`` from a dict, JSON text or a JSON file."""
    if isinstance(spec, dict):
        raw: Any = spec
    else:
        text = str(spec).strip()
        raw = loads_strict(text if text[:1] in ("{", "[") else read_text_limited(text, MAX_GRID_BYTES, "costs"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError('symbol costs must be a non-empty JSON object, e.g. {"AAA": {"commission_bps": 2, "slippage_bps": 1}}')
    out: dict[str, dict[str, float]] = {}
    for name, row in raw.items():
        if not isinstance(row, dict) or not row:
            raise ValueError(f"costs of {name!r} must be an object with {' and/or '.join(KEYS)}")
        clean: dict[str, float] = {}
        for key, value in row.items():
            if key not in KEYS:
                raise ValueError(f"unknown cost key {key!r} for {name!r}; use {' and/or '.join(KEYS)}")
            if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} of {name!r} must be a finite number of at least 0, got {value!r}")
            clean[key] = float(value)
        out[str(name)] = clean
    return out


def resolve_symbol_costs(
    spec: dict[str, Any] | str | Path, symbols: list[str] | tuple[str, ...], model: ExecutionModel
) -> tuple[tuple[str, float, float], ...]:
    """One ``(symbol, commission_bps, slippage_bps)`` row per symbol, in ``symbols`` order."""
    costs = parse_symbol_costs(spec)
    names = [str(s) for s in symbols]
    unknown = sorted(set(costs) - set(names) - {DEFAULT})
    if unknown:
        raise ValueError(f"costs name symbols that are not in the data: {unknown}; the data has {names}")
    base = costs.get(DEFAULT, {})
    rows = []
    for name in names:
        own = costs.get(name, {})
        commission = own.get("commission_bps", base.get("commission_bps", model.commission_bps))
        slippage = own.get("slippage_bps", base.get("slippage_bps", model.slippage_bps))
        rows.append((name, float(commission), float(slippage)))
    return tuple(rows)


def apply_symbol_costs(market: Any, model: ExecutionModel, spec: dict[str, Any] | str | Path | None) -> ExecutionModel:
    """``model`` with the per-symbol costs resolved against the market's symbols (a universe only)."""
    if spec is None:
        return model
    symbols = getattr(market, "symbols", None)
    if getattr(market, "kind", "") != "universe" or not symbols:
        raise ValueError("per-symbol costs need a universe: a table with a symbol column")
    return replace(model, symbol_costs=resolve_symbol_costs(spec, list(symbols), model))


__all__ = ["apply_symbol_costs", "parse_symbol_costs", "resolve_symbol_costs"]
