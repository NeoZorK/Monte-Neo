"""``catalog-rules/1``: the category, tags, type mask and readable tag of a strategy, derived by rules (never by hand).

Input is a ``catalog-spec/1`` specification (what the strategy declares) and, optionally, the metrics measured from its
positions (:func:`monte_neo.catalog.measure.measure`). The twelve category rules are applied in order and the first one that
fires gives the main category; the record keeps every rule that fired, the metric values and the rules version, so the label
can be recomputed. A measured label that contradicts the declared one sets ``label_mismatch``; it never changes a verdict.

Specification fields (all optional except ``instruments``)::

    {"name": "...", "instruments": [{"symbol": "EURUSD", "type": "spot", "asset_class": "FX"}],
     "legs": [{"symbol": "...", "sign": 1}], "inputs": ["prices", "funding", ...], "forecast": true,
     "sizing": "signal|fixed|equal|inverse_vol|risk_parity|optimizer|views|liability|grid|martingale|averaging",
     "rank_on": "past_return|value|quality|size|low_vol|other", "relation": "cointegration|deal|index_nav|basis_price|funding",
     "option_structure": false, "vol_sized": false, "patterns": false, "model": false, "copies": false, "hedge_of": null,
     "quotes_both_sides": false, "fundamentals_equity": false, "bar_seconds": 86400,
     "components": [{"category": "VOL", "role": "filter|overlay|blend|sleeve", "share": 0.3}],
     "declared": {"category": "TSM", "structure": "MN"}}
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from monte_neo.catalog.mask import categories, encode, readable_tag, rules

SCHEMA_ID = "catalog-label/1"
SPEC_SCHEMA_ID = "catalog-spec/1"
GRID_SIZING = {"grid", "martingale", "averaging", "anti_martingale", "pyramiding"}
ALLOC_SIZING = {"fixed", "equal", "inverse_vol", "risk_parity"}
PORTFOLIO_SIZING = {"optimizer", "views", "liability"}
RANK_TO_CAT = {"past_return": "XSM", "value": "VAL"}
ROLE_KIND = {"filter": "filter", "overlay": "overlay", "blend": "blend", "sleeve": "portfolio"}


def spec_hash(spec: dict[str, Any]) -> str:
    """``sha256:`` of the canonical JSON of the specification: the identity of one exact experiment."""
    raw = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


ASSET_ALIASES = {
    "CRYPTO": "CRY", "CRYPTOCURRENCY": "CRY", "CRYPTOCURRENCIES": "CRY", "DIGITAL ASSETS": "CRY",
    "EQUITY": "EQ", "EQUITIES": "EQ", "STOCK": "EQ", "STOCKS": "EQ", "SHARES": "EQ",
    "INDEX": "IDX", "INDICES": "IDX", "INDEXES": "IDX",
    "RATES": "RAT", "BOND": "RAT", "BONDS": "RAT", "FIXED INCOME": "RAT", "FIXED_INCOME": "RAT",
    "FOREX": "FX", "CURRENCY": "FX", "CURRENCIES": "FX",
    "COMMODITY": "CMD", "COMMODITIES": "CMD",
    "VOLATILITY": "VLX", "VOL": "VLX",
    "CREDIT": "CRD",
}


def asset_code(value: Any) -> str:
    """The catalog code of an ``asset_class`` value: a code (``CRY``) or a common name (``crypto``); anything else is an error."""
    v = str(value).strip().upper()
    codes = rules()["asset_classes"]
    if v in codes:
        return v
    if v in ASSET_ALIASES:
        return ASSET_ALIASES[v]
    raise ValueError(f"unknown asset_class {value!r}: use one of {', '.join(codes)} (or a common name such as crypto, equity, fx)")


def _asset_classes(spec: dict[str, Any]) -> list[str]:
    classes = sorted({asset_code(i["asset_class"]) for i in spec.get("instruments", []) if i.get("asset_class")})
    order = rules()["asset_classes"]
    return [a for a in order if a in classes] or ["MULTI"]


def _category_rules(spec: dict[str, Any], m: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Every (rule id, category, reason) that fires, in the order of catalog-rules/1 section 3."""
    t = rules()["thresholds"]
    inputs = set(spec.get("inputs", []))
    types = {str(i.get("type", "")).lower() for i in spec.get("instruments", [])}
    sizing = spec.get("sizing", "signal")
    fired: list[tuple[str, str, str]] = []
    hold = m.get("hold_median_seconds")
    bar = float(spec.get("bar_seconds", 86400))
    if (hold is not None and hold < t["hft_hold_seconds"]) or (hold is None and bar < t["hft_hold_seconds"]):
        fired.append(("R1", "HFT", "holding under one minute"))
    if "option" in types and spec.get("option_structure"):
        fired.append(("R2", "VOL" if spec.get("vol_sized") else "OPS", "option structure" + (" sized on implied vs realised volatility" if spec.get("vol_sized") else "")))
    sal = m.get("size_after_loss")
    if sizing in GRID_SIZING or (sal is not None and sal > t["grid_size_after_loss"]):
        fired.append(("R3", "GRD", f"sizing {sizing}" if sizing in GRID_SIZING else f"size after a loss x{sal:.2f}"))
    if spec.get("forecast", True) is False or sizing in ALLOC_SIZING | PORTFOLIO_SIZING:
        if sizing in PORTFOLIO_SIZING:
            fired.append(("R4", "PRT", f"weights by {sizing}"))
        elif spec.get("forecast", True) is False:
            fired.append(("R4", "ALC", f"no return forecast, weights by {sizing}"))
    legs = spec.get("legs") or []
    rel = spec.get("relation")
    if len(legs) >= 2 and len({int(lg.get("sign", 1)) for lg in legs}) == 2:
        if rel == "funding":
            fired.append(("R5", "CAR", "opposite legs earning funding or roll"))
        elif rel in ("basis_price", "deal", "index_nav"):
            fired.append(("R5", "ARB", f"opposite legs on a {rel} relation"))
        elif rel == "cointegration" or rel is None:
            fired.append(("R5", "SA", "opposite legs on a spread"))
    if inputs & {"funding", "rates", "roll", "forward_points"} and not any(r[1] == "CAR" for r in fired):
        fired.append(("R6", "CAR", "funding, rate or roll inputs"))
    cal = m.get("calendar_conc")
    if "events" in inputs:
        fired.append(("R7", "EVT", "dated events in the inputs"))
    if (cal is not None and cal > t["calendar_conc"]) or "calendar" in inputs:
        fired.append(("R7", "SEA", "calendar inputs" if "calendar" in inputs else f"exposure concentrated in calendar windows ({cal:.2f})"))
    n_act = m.get("n_assets_active")
    n_decl = len(spec.get("instruments", []))
    rank = spec.get("rank_on")
    if rank and (n_act if n_act is not None else n_decl) >= t["cross_section_min_assets"] - 0.5:
        net = m.get("net_exposure")
        if spec.get("fundamentals_equity") and (net is None or -0.3 <= net <= 0.7):
            fired.append(("R8", "EQL", "equity long/short on fundamentals"))
        else:
            fired.append(("R8", RANK_TO_CAT.get(rank, "FAC"), f"cross-sectional rank on {rank}"))
    corr = [v for v in (m.get("sign_corr_past_ret") or {}).values() if v is not None]
    if corr and not rank:
        best = max(corr, key=abs)
        if best > t["trend_sign_corr"]:
            fired.append(("R9", "TSM", f"position sign follows past return (corr {best:.2f})"))
        elif best < -t["trend_sign_corr"]:
            fired.append(("R9", "MR", f"position sign opposes past return (corr {best:.2f})"))
    if "macro" in inputs:
        fired.append(("R10", "MAC", "macro series in the inputs"))
    if inputs & {"order_book", "volume_imbalance"}:
        fired.append(("R10", "OFL", "order book or volume imbalance inputs"))
    if spec.get("patterns"):
        fired.append(("R10", "TEC", "declared price-pattern rules"))
    if spec.get("model"):
        fired.append(("R10", "MLP", "a trained model"))
    if spec.get("copies"):
        fired.append(("R11", "COP", "positions follow another strategy"))
    if spec.get("hedge_of"):
        fired.append(("R11", "HED", f"hedge of {spec['hedge_of']}"))
    if spec.get("quotes_both_sides"):
        fired.append(("R11", "MM", "resting quotes on both sides"))
    return fired


def _structure(spec: dict[str, Any], m: dict[str, Any], main: str) -> str | None:
    t = rules()["thresholds"]
    types = {str(i.get("type", "")).lower() for i in spec.get("instruments", [])}
    if main in ("ALC", "PRT"):
        return "PRT"
    if "option" in types:
        return "OPT"
    legs = spec.get("legs") or []
    if len(legs) >= 2:
        return "BAS" if spec.get("relation") in ("basis_price", "funding") else "SPR"
    ls, net, beta = m.get("long_share"), m.get("net_exposure"), m.get("beta_bench")
    if ls is None:
        return None
    if ls >= 0.999:
        return "LO"
    if net is not None and abs(net) < t["market_neutral_net"] and (beta is None or abs(beta) < t["market_neutral_beta"]):
        return "MN"
    return "LS"


def _bucket(value: float | None, edges: list[float], labels: list[str]) -> str | None:
    if value is None:
        return None
    for edge, label in zip(edges, labels, strict=False):
        if value <= edge:
            return label
    return labels[-1]


def classify(spec: dict[str, Any], measured: dict[str, Any] | None = None) -> dict[str, Any]:
    """The ``catalog-label/1`` record of one strategy (see the module docstring)."""
    r, t = rules(), rules()["thresholds"]
    m = dict(measured or {})
    fired = _category_rules(spec, m)
    declared = (spec.get("declared") or {}).get("category")
    flags: list[str] = []
    comps = {c["category"]: c.get("role", "blend") for c in spec.get("components", []) if c.get("category") in categories()}
    shares = {c["category"]: float(c["share"]) for c in spec.get("components", []) if "share" in c}
    if fired:
        main, rule_id = fired[0][1], fired[0][0]
    elif declared in categories():
        main, rule_id = declared, "R12"
        flags.append("unconfirmed")
    else:
        raise ValueError("no catalog rule fires and no declared category: describe the inputs, sizing or legs in the specification")
    # combined strategies (section 8): filters and overlays keep the base as main; a dominant GRD overlay takes over
    if comps.get("GRD") == "overlay" and (m.get("size_after_loss") or 0) > t["grid_size_after_loss"]:
        comps.pop("GRD")
        comps[main] = "overlay"
        main, rule_id = "GRD", "R3"
    if comps and all(role == "blend" for role in comps.values()) and shares:
        top = max(shares, key=shares.get)
        if shares[top] > t["blend_main_share"]:
            main = top
        else:
            flags.append("no_dominant_component")
        if sum(shares.values()) < 1 - t["unexplained_share"]:
            flags.append("unexplained_component")
    comps.pop(main, None)
    tags = sorted({c for _, c, _ in fired} - {main} - set(comps), key=categories().index)
    kinds = sorted({ROLE_KIND[role] for role in comps.values() if role in ROLE_KIND}, key=r["kinds"].index)
    assets = _asset_classes(spec)
    hold = m.get("hold_median_seconds")
    hold_days = hold / 86400 if hold is not None else None
    breadth = _bucket(m.get("n_assets_active") if m.get("n_assets_active") is not None else len(spec.get("instruments", [])),
                      t["breadth_assets"], r["breadth"])
    skew = m.get("skew")
    risk = None if skew is None else ("NEG" if skew < t["negative_skew"] else "POS" if skew > t["positive_skew"] else "SYM")
    if main == "GRD":
        risk = "NEG"  # a sizing scheme that adds after losses has a negative risk shape whatever the past skew shows
    structure = _structure(spec, m, main)
    verifiable = "PART" if main in ("HFT", "MM", "OFL") else "NONE" if spec.get("discretionary") else "FULL"
    dstruct = (spec.get("declared") or {}).get("structure")
    if declared and declared in categories() and rule_id != "R12" and declared != main and declared not in comps and declared not in tags:
        flags.append("label_mismatch")
    if dstruct and structure and dstruct != structure:
        flags.append("label_mismatch")
    fields = {"main": main, "components": comps, "tags": tags, "kinds": kinds, "asset_classes": assets, "structure": structure,
              "holding": _bucket(hold_days, t["holding_days"], r["holding"]), "breadth": breadth, "risk_shape": risk, "verifiable": verifiable}
    asset_id = assets[0] if len(assets) == 1 else "MULTI"
    return {
        "schema": SCHEMA_ID, "rules_version": r["version"], "mask_version": r["mask_version"], "provisional": r["status"] == "provisional",
        "name": spec.get("name"), "main_category": main, "main_rule": rule_id, "declared_category": declared,
        "components": [{"category": c, "role": comps[c], **({"share": shares[c]} if c in shares else {})} for c in categories() if c in comps],
        "tags": tags, "kind": kinds or ["single"], "asset_classes": assets, "structure": structure,
        "holding": fields["holding"], "breadth": breadth, "risk_shape": risk, "verifiable": verifiable,
        "flags": sorted(set(flags)), "rules_fired": [{"rule": a, "category": b, "why": c} for a, b, c in fired],
        "type_mask": encode(fields), "type_tag": readable_tag(main, assets, comps),
        "catalog_id_prefix": f"MN-{main}-{asset_id}-", "spec_hash": spec_hash(spec),
        "metrics": {k: v for k, v in m.items()},
    }


__all__ = ["SCHEMA_ID", "SPEC_SCHEMA_ID", "classify", "spec_hash"]
