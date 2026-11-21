"""catalog-rules/1: synthetic strategies with known labels are labelled correctly; the mask is exact and deterministic."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.catalog import categories, classify, decode, encode, measure, readable_tag, similarity
from monte_neo.cli.catalog_cmd import main as catalog_main

DAYS = pd.date_range("2018-01-01", periods=1500, freq="D", tz="UTC")


def _prices(n: int = 1, seed: int = 0, drift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    r = drift + 0.02 * rng.standard_normal((len(DAYS), n))
    trend = np.repeat(np.sin(np.linspace(0, 12, len(DAYS)))[:, None] * 0.003, n, axis=1)  # slow cycles a trend rule can follow
    return pd.DataFrame(100 * np.exp(np.cumsum(r + trend, axis=0)), index=DAYS, columns=[f"S{i}" for i in range(n)])


def _spec(**kw) -> dict:
    base = {"name": "s", "instruments": [{"symbol": "S0", "type": "spot", "asset_class": "CRY"}], "inputs": ["prices"]}
    base.update(kw)
    return base


def test_trend_and_mean_reversion_are_measured_from_positions() -> None:
    px = _prices()
    past = np.log(px).diff(60)
    trend = np.sign(past).fillna(0)
    rec = classify(_spec(), measure(trend, px))
    assert rec["main_category"] == "TSM" and rec["main_rule"] == "R9" and rec["type_tag"] == "#TSM.CRY"
    rev = -np.sign(np.log(px).diff(20)).fillna(0)
    assert classify(_spec(), measure(rev, px))["main_category"] == "MR"


def test_declared_rules_in_order() -> None:
    opt = [{"symbol": "X", "type": "option", "asset_class": "IDX"}]
    assert classify(_spec(instruments=opt, option_structure=True))["main_category"] == "OPS"
    assert classify(_spec(instruments=opt, option_structure=True, vol_sized=True))["main_category"] == "VOL"
    assert classify(_spec(sizing="martingale"))["main_category"] == "GRD"
    assert classify(_spec(forecast=False, sizing="inverse_vol"))["main_category"] == "ALC"
    assert classify(_spec(sizing="optimizer"))["main_category"] == "PRT"
    legs = [{"symbol": "A", "sign": 1}, {"symbol": "B", "sign": -1}]
    assert classify(_spec(legs=legs, relation="cointegration"))["main_category"] == "SA"
    assert classify(_spec(legs=legs, relation="funding"))["structure"] == "BAS"
    assert classify(_spec(inputs=["prices", "funding"]))["main_category"] == "CAR"
    assert classify(_spec(inputs=["events"]))["main_category"] == "EVT"
    many = [{"symbol": f"S{i}", "type": "spot", "asset_class": "EQ"} for i in range(20)]
    assert classify(_spec(instruments=many, rank_on="past_return"))["main_category"] == "XSM"
    assert classify(_spec(instruments=many, rank_on="value"))["main_category"] == "VAL"
    assert classify(_spec(instruments=many, rank_on="quality"))["main_category"] == "FAC"
    assert classify(_spec(instruments=many[:3], rank_on="past_return", declared={"category": "XSM"}))["flags"] == ["unconfirmed"]
    assert classify(_spec(inputs=["macro"]))["main_category"] == "MAC"
    assert classify(_spec(patterns=True))["main_category"] == "TEC"
    assert classify(_spec(model=True))["main_category"] == "MLP"
    assert classify(_spec(copies=True))["main_category"] == "COP"
    assert classify(_spec(bar_seconds=1))["main_category"] == "HFT"
    assert classify(_spec(bar_seconds=1))["verifiable"] == "PART"
    with pytest.raises(ValueError, match="no catalog rule"):
        classify(_spec())


def test_grid_sizing_is_measured_and_has_negative_risk_shape() -> None:
    px = _prices(seed=3)
    pos = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    size, side, i = 1.0, 1.0, 0
    ret = px["S0"].pct_change().fillna(0).to_numpy()
    while i < len(pos) - 10:
        pos.iloc[i : i + 5, 0] = side * size
        pnl = float(np.sum(side * ret[i + 1 : i + 6]))
        size = size * 2 if pnl < 0 else 1.0  # martingale: double after a loss
        size = min(size, 64.0)
        i += 6
    m = measure(pos, px)
    assert m["size_after_loss"] > 1.5
    rec = classify(_spec(declared={"category": "TSM"}), m)
    assert rec["main_category"] == "GRD" and rec["risk_shape"] == "NEG" and "label_mismatch" in rec["flags"]


def test_calendar_concentration_gives_seasonality() -> None:
    px = _prices()
    day = px.index.day
    pos = pd.DataFrame(((day <= 3) | (day >= px.index.days_in_month - 1)).astype(float), index=px.index, columns=px.columns)
    rec = classify(_spec(), measure(pos, px))
    assert rec["main_category"] == "SEA" and rec["structure"] == "LO"


def test_market_neutral_claim_is_checked() -> None:
    px = _prices()
    pos = pd.DataFrame(1.0, index=px.index, columns=px.columns)  # always long, declared market neutral
    rec = classify(_spec(forecast=False, sizing="fixed", declared={"category": "ALC", "structure": "MN"}), measure(pos, px))
    assert rec["main_category"] == "ALC" and rec["structure"] == "PRT" and "label_mismatch" in rec["flags"]
    rec2 = classify(_spec(inputs=["funding"], declared={"structure": "MN"}), measure(pos, px))
    assert rec2["structure"] == "LO" and "label_mismatch" in rec2["flags"]


def test_combined_strategies() -> None:
    spec = _spec(inputs=["prices", "funding"], components=[{"category": "VOL", "role": "filter"}, {"category": "ALC", "role": "overlay"}])
    rec = classify(spec)
    assert rec["main_category"] == "CAR" and rec["kind"] == ["filter", "overlay"] and rec["type_tag"] == "#CAR.CRY+f:VOL+o:ALC"
    blend = _spec(model=True, components=[{"category": "VAL", "role": "blend", "share": 0.3}, {"category": "XSM", "role": "blend", "share": 0.25}])
    b = classify(blend)
    assert "no_dominant_component" in b["flags"] and "unexplained_component" in b["flags"]
    dom = _spec(model=True, components=[{"category": "VAL", "role": "blend", "share": 0.7}, {"category": "XSM", "role": "blend", "share": 0.3}])
    assert classify(dom)["main_category"] == "VAL"


def test_mask_round_trip_tag_and_similarity() -> None:
    assert len(categories()) == 24
    fields = {"main": "TSM", "components": {"VOL": "filter"}, "tags": ["CAR"], "kinds": ["filter"], "asset_classes": ["FX"],
              "structure": "LS", "holding": "MD", "breadth": "FEW", "risk_shape": "POS", "verifiable": "FULL"}
    mask = encode(fields)
    assert mask.startswith("tm1:") and len(mask) == 4 + 19
    d = decode(mask)
    assert d["main"] == "TSM" and d["components"] == ["VOL"] and d["tags"] == ["CAR"] and d["asset_classes"] == ["FX"]
    assert (d["structure"], d["holding"], d["breadth"], d["risk_shape"], d["verifiable"], d["kinds"]) == ("LS", "MD", "FEW", "POS", "FULL", ["filter"])
    unknown = decode(encode({"main": "MR"}))
    assert unknown["structure"] is None and unknown["holding"] is None
    assert readable_tag("TSM", ["FX"], {"VOL": "filter"}) == "#TSM.FX+f:VOL"
    assert similarity(mask, mask) == 1.0 and similarity(mask, encode({"main": "MR"})) == 0.0
    with pytest.raises(ValueError):
        decode("xx:1")


def test_deterministic_and_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    px = _prices()
    pos = np.sign(np.log(px).diff(60)).fillna(0)
    a, b = classify(_spec(), measure(pos, px)), classify(_spec(), measure(pos, px))
    assert a == b and a["spec_hash"].startswith("sha256:")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(_spec()))
    pos.to_csv(tmp_path / "pos.csv")
    px.to_csv(tmp_path / "px.csv")
    assert catalog_main(["classify", str(spec), "--positions", str(tmp_path / "pos.csv"), "--prices", str(tmp_path / "px.csv")]) == 0
    out = capsys.readouterr().out
    assert "#TSM.CRY" in out and "R9" in out
    assert catalog_main(["classify", str(spec), "--json"]) == 3  # nothing declared and nothing measured
    assert catalog_main(["mask", a["type_mask"]]) == 0 and '"main": "TSM"' in capsys.readouterr().out
    assert catalog_main(["categories"]) == 0 and "HFT" in capsys.readouterr().out


def test_catalog_records_are_labelled_and_the_file_is_current() -> None:
    import importlib.util

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("catalog_migrate", root / "scripts" / "catalog_migrate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert (root / "docs" / "catalog" / "labels.json").read_text(encoding="utf-8") == mod.render()
    rows = json.loads(mod.render())["labels"]
    assert len(rows) == 100 and sum(1 for r in rows if r.get("control")) == 2
    labelled = [r for r in rows if not r.get("control")]
    assert all(r["type_tag"].startswith("#") and r["type_mask"].startswith("tm1:") for r in labelled)
    assert not [r["id"] for r in labelled if "label_mismatch" in r["flags"]]
