"""Where can a strategy run? Requirements from its specification and measured positions, matched to a venue table.

Requirements (``requirements``): asset classes and instrument types from ``instruments`` of the catalog specification,
whether it needs to sell short (declared legs or a hedge, or measured long share below 1 / net exposure near zero),
leverage (``leverage`` argument or the spec's ``sizing.leverage``), and intraday trading (``bar_seconds`` below one day).

Venues (``venues_v1.json``, provisional, indicative): asset classes, instruments, short selling, maximum leverage,
intraday trading, a typical published taker fee, a demo environment and whether a Monte-Neo connector exists.

Result (``compat``): every venue with ``compatible`` and the reasons it is not, ranked by the indicative cost of one
unit of turnover. Monte-Neo does not recommend a venue: availability depends on your country and account.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

VENUES_FILE = Path(__file__).with_name("venues_v1.json")
DAY = 86_400


@lru_cache(maxsize=1)
def venues() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(VENUES_FILE.read_text(encoding="utf-8"))
    return data


def requirements(spec: dict[str, Any], measured: dict[str, Any] | None = None, leverage: float | None = None) -> dict[str, Any]:
    inst = spec.get("instruments") or []
    classes = sorted({str(i.get("asset_class", "")).upper() for i in inst if i.get("asset_class")})
    types = sorted({str(i.get("type", "spot")).lower() for i in inst})
    m = measured or {}
    short_reasons = []
    if spec.get("legs") or spec.get("hedge_of"):
        short_reasons.append("declared legs or a hedge")
    if m.get("long_share") is not None and float(m["long_share"]) < 0.999:
        short_reasons.append(f"measured long share {float(m['long_share']):.0%}")
    if m.get("net_exposure") is not None and abs(float(m["net_exposure"])) < 0.2 and m.get("long_share") is not None and float(m["long_share"]) < 0.999:
        short_reasons.append("near-zero net exposure (market-neutral)")
    lev = leverage if leverage is not None else float((spec.get("sizing") or {}).get("leverage", 1.0) if isinstance(spec.get("sizing"), dict) else 1.0)
    bar = spec.get("bar_seconds")
    return {"asset_classes": classes, "instruments": types, "short": bool(short_reasons), "short_why": short_reasons,
            "leverage": lev, "intraday": bool(bar is not None and float(bar) < DAY)}


def _check(v: dict[str, Any], req: dict[str, Any]) -> list[str]:
    why = []
    missing = [c for c in req["asset_classes"] if c not in v["asset_classes"]]  # MULTI matches only a multi-asset strategy
    if missing:
        why.append(f"no {', '.join(missing)}")
    no_inst = [t for t in req["instruments"] if t not in v["instruments"]]
    if no_inst:
        why.append(f"no {', '.join(no_inst)} instruments")
    if req["short"] and not v["short"]:
        why.append("cannot sell short (" + "; ".join(req["short_why"]) + ")")
    if req["leverage"] > v["max_leverage"]:
        why.append(f"leverage {req['leverage']:g}x above the venue's {v['max_leverage']}x")
    if req["intraday"] and not v["intraday"]:
        why.append("no intraday trading")
    return why


def compat(spec: dict[str, Any], measured: dict[str, Any] | None = None, leverage: float | None = None) -> dict[str, Any]:
    req = requirements(spec, measured, leverage)
    if not req["asset_classes"]:
        raise ValueError("the specification lists no instrument with an asset_class: nothing to match")
    rows = []
    for v in venues()["venues"]:
        why = _check(v, req)
        rows.append({"venue": v["id"], "name": v["name"], "compatible": not why, "why_not": why, "taker_bps": v["taker_bps"],
                     "demo": v.get("demo"), "connector": v.get("connector"), "caveat": v.get("caveat")})
    rows.sort(key=lambda r: (not r["compatible"], r["taker_bps"]))
    return {"schema": "catalog-compat/1", "venues_version": venues()["version"], "requirements": req, "venues": rows,
            "note": venues()["note"]}
