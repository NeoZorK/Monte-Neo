"""Label every record of docs/catalog/strategies.yaml by catalog-rules/1 and write docs/catalog/labels.json.

    python scripts/catalog_migrate.py           write the labels
    python scripts/catalog_migrate.py --check   exit 1 if the file is out of date

The draft-v0 ``type`` of each record is turned into a catalog-spec/1 specification (instruments, inputs, sizing,
legs, ranking) and labelled by ``monte_neo.catalog.classify``. No positions are measured here, so a label comes
from the specification only: ``basis`` says whether a rule fired on the specification ("spec") or the label
rests on the declared category alone ("declared", rule R12). Controls (null strategies) are listed, not labelled.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from monte_neo.catalog import classify

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "catalog" / "strategies.yaml"
OUT = ROOT / "docs" / "catalog" / "labels.json"

# Asset class by keywords in the id or the data line; the first match wins.
ASSET_WORDS = [
    ("MULTI", ("sixty", "three_fund", "permanent", "all_weather", "ivy", "inverse_vol", "erc_", "min_variance",
               "max_diversification", "hrp", "mean_variance", "constant_mix", "cppi", "target_date", "dual_momentum",
               "paa_", "eaa_", "hop_trend", "tsmom_mop", "global_carry", "macro_regimes", "tail_trend", "residual")),
    ("CRY", ("btc", "eth", "crypto", "multi-coin", "perp", "cash_and_carry")),
    ("VLX", ("vix", "svxy")),
    ("FX", ("fx_", "fx ")),
    ("CMD", ("commodity",)),
    ("RAT", ("bond", "yield")),
    ("IDX", ("spy", "index", "bxm", "put_write", "collar", "iron_condor", "straddle", "vol_managed", "vol_target",
             "faber", "sma200", "golden", "blb_", "turn_of_month", "halloween", "overnight", "fomc", "industry")),
    ("EQ", ("equity", "fundamentals", "market cap", "dow ", "earnings", "deal", "convertible", "stock")),
]
NO_FORECAST = {"passive_index", "balanced_60_40", "equal_weight", "dca", "rebalancing_policy", "risk_parity", "vol_managed"}
OPTIMIZED = {"min_variance", "max_diversification", "hrp", "mean_variance_naive", "erc_risk_parity"}
DECLARED = {"trend_following": "TSM", "mean_reversion": "MR", "short_volatility": "VOL", "convertible_arb": "ARB",
            "options_overlay": "OPS"}
RANK = {"hml_value": "value", "dogs_of_dow": "value", "magic_formula": "value"}
CONTROLS = {"random_entry_null", "always_flat"}
BY_ID_DECLARED = {"crypto_tsmom": "TSM"}  # crypto_specific records differ: trend, ranking, equal weight, carry


def _asset(rec: dict[str, Any]) -> str:
    """Asset-class code, or "" when the rule applies to any price series."""
    text = (rec["id"] + " " + " ".join(map(str, rec.get("data", [])))).lower()
    for code, words in ASSET_WORDS:
        if any(w in text for w in words):
            return code
    return ""  # generic price rule: the asset class is not fixed by the strategy


def spec_of(rec: dict[str, Any]) -> dict[str, Any] | None:
    """A catalog-spec/1 specification for one draft-v0 record, or None for a control."""
    rid, typ = rec["id"], rec["type"]
    if rid in CONTROLS:
        return None
    asset = _asset(rec)
    cls = {"asset_class": asset} if asset else {}
    one = [{"symbol": "X", "type": "spot", **cls}]
    many = [{"symbol": f"S{i}", "type": "spot", **cls} for i in range(20)]
    s: dict[str, Any] = {"schema": "catalog-spec/1", "name": rec["name"], "instruments": one, "inputs": ["prices"]}
    if typ in NO_FORECAST or rid in OPTIMIZED or rid == "crypto_equal_weight":
        s.update(forecast=False, sizing="optimizer" if rid in OPTIMIZED else "inverse_vol" if typ in ("risk_parity", "vol_managed") else "fixed",
                 instruments=many if asset == "MULTI" or typ == "equal_weight" or rid == "crypto_equal_weight" else one)
    elif typ == "xs_momentum" or (typ == "crypto_specific" and "xs" in rid):
        s.update(instruments=many, rank_on="past_return")
    elif typ == "factor_premia":
        s.update(instruments=many, rank_on=RANK.get(rid, "characteristic"), inputs=["prices", "fundamentals"])
    elif typ == "long_short_equity":
        s.update(instruments=many, rank_on="characteristic", fundamentals_equity=True, inputs=["prices", "fundamentals"])
    elif typ == "controls":
        s["sizing"] = "martingale" if "martingale" in rid else "grid"
    elif typ == "stat_arb_pairs":
        s.update(legs=[{"symbol": "A", "sign": 1}, {"symbol": "B", "sign": -1}], relation="cointegration")
    elif typ == "carry" or rid == "crypto_funding_carry":
        if rid == "crypto_funding_carry":
            s.update(legs=[{"symbol": "SPOT", "sign": 1}, {"symbol": "PERP", "sign": -1}], relation="funding")
        else:
            s.update(instruments=many if asset == "MULTI" else one, inputs=["prices", "rates" if asset in ("FX", "RAT") else "roll"])
    elif rid == "cash_and_carry":
        s.update(legs=[{"symbol": "SPOT", "sign": 1}, {"symbol": "FUT", "sign": -1}], relation="basis_price")
    elif typ in ("options_overlay", "short_volatility") and "option" in " ".join(map(str, rec.get("data", []))).lower():
        s.update(instruments=[{"symbol": "X", "type": "option", **cls}], option_structure=True,
                 vol_sized=typ == "short_volatility")
    elif typ == "event_merger_arb":
        s["inputs"] = ["prices", "events"]
    elif typ == "global_macro":
        s["inputs"] = ["prices", "macro"]
    elif typ == "calendar_anomaly":
        s["inputs"] = ["prices", "calendar"]
    elif typ == "market_making":
        s.update(quotes_both_sides=True, bar_seconds=60)
    declared = BY_ID_DECLARED.get(rid) or DECLARED.get(typ)
    if declared:
        s["declared"] = {"category": declared}
    return s


def labels() -> list[dict[str, Any]]:
    out = []
    for rec in yaml.safe_load(SRC.read_text(encoding="utf-8")):
        spec = spec_of(rec)
        row: dict[str, Any] = {"id": rec["id"], "name": rec["name"], "draft_type": rec["type"], "tier": rec["tier"]}
        if spec is None:
            row.update(control=True, label=None, why="null strategy used as a control; not a strategy type")
        else:
            lab = classify(spec)
            row.update(type_tag=lab["type_tag"], type_mask=lab["type_mask"], main_category=lab["main_category"],
                       main_rule=lab["main_rule"], basis="declared" if lab["main_rule"] == "R12" else "spec",
                       structure=lab["structure"], verifiable=lab["verifiable"], flags=lab["flags"],
                       rules_version=lab["rules_version"])
        out.append(row)
    return out


def render() -> str:
    doc = {"schema": "catalog-labels/1", "source": "docs/catalog/strategies.yaml", "provisional": True,
           "note": "Labels from the specification only; measured labels need positions (monte-neo catalog classify --positions).",
           "labels": labels()}
    return json.dumps(doc, indent=1, ensure_ascii=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    text = render()
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("labels.json is up to date" if ok else "labels.json is out of date: run python scripts/catalog_migrate.py")
        return 0 if ok else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
