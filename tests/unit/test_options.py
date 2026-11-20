"""Options verification: pricer, loader, each check on a trap and on an honest control, CLI."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from monte_neo.options import bs, verify_options
from monte_neo.options.load import load_trades
from monte_neo.profiles import get_profile


def table(n: int = 40, step: int = 5, **over) -> pd.DataFrame:
    d0 = pd.Timestamp("2024-01-02")
    rows = []
    for i in range(n):
        d = d0 + pd.Timedelta(days=step * i)
        rows.append(dict(date=d, expiry=d + pd.Timedelta(days=30), right="P", strike=95.0, qty=-1, fill_price=1.0, bid=0.5, ask=1.5,
                         underlying_price=100.0, iv_used=0.2, iv_asof=d, exit_date=d + pd.Timedelta(days=30), exit_price=0.8, exit_bid=0.6, exit_ask=1.0))
    df = pd.DataFrame(rows)
    for k, v in over.items():
        df[k] = v
    return df


def case(name: str):
    if name == "opt_mid_fill":
        return table(), None
    if name == "opt_iv_future":
        t = table()
        t["iv_asof"] = t["date"] + pd.Timedelta(days=5)
        return t, None
    if name == "opt_tail_sale":
        t = table(qty=-80, strike=80.0, fill_price=0.06, bid=0.05, ask=0.07, exit_price=0.0, exit_bid=0.0, exit_ask=0.01)
        return t, 100_000.0
    if name == "opt_honest":
        short = table(qty=-1, strike=95.0, bid=1.0, ask=1.4, exit_price=0.3, exit_bid=0.2, exit_ask=0.3)
        short["fill_price"] = short["bid"]  # sold at the bid, bought back at the ask
        long_ = table(qty=1, strike=90.0, bid=0.2, ask=0.3, exit_price=0.1, exit_bid=0.1, exit_ask=0.2)
        long_["fill_price"] = long_["ask"]  # bought at the ask, sold at the bid
        return pd.concat([short, long_]), 100_000.0
    if name == "opt_no_quotes":
        return table()[["date", "expiry", "right", "strike", "qty", "fill_price"]], None
    raise KeyError(name)


def by_id(rep: dict) -> dict:
    return {c["id"]: c for c in rep["checks"]}


def test_profile_traps_and_controls() -> None:
    prof = get_profile("options")
    for item in prof["traps"] + prof["controls"]:
        df, equity = case(item["case"])
        rep = verify_options(df, equity=equity)
        rows, ex = by_id(rep), item["expect"]
        if "check" in ex:
            assert rows[ex["check"]]["status"] == ex["status"], item["id"]
        for cid in ex.get("checks_not_failing", []):
            assert rows[cid]["status"] != "fail", (item["id"], cid, rows[cid]["summary"])
        for cid in ex.get("all_skipped", []):
            assert rows[cid]["status"] == "skip" and rows[cid]["details"]["not_assessed"]
        if "verdict_not" in ex:
            assert rep["verdict"] != ex["verdict_not"]


def test_trap_verdicts_are_not_pass_and_certificate_shape() -> None:
    rep = verify_options(*[case("opt_mid_fill")[0]])
    assert rep["verdict"] != "PASS" and rep["schema"] == "strategy-verdict/1" and rep["profile"]["id"] == "options"
    assert rep["certificate_id"] and "not investment advice" in rep["disclaimer"].lower()
    assert "options_chain" in by_id(rep) and by_id(rep)["options_chain"]["details"]["not_assessed"]


def test_certificate_is_deterministic() -> None:
    a, b = verify_options(table()), verify_options(table())
    assert a["certificate_id"] == b["certificate_id"]


def test_mid_fill_passes_when_filled_at_touch() -> None:
    t = table(fill_price=0.5)  # sells at the bid
    assert by_id(verify_options(t))["bid_ask_fill"]["status"] != "fail"


def test_fill_better_than_mid_fails() -> None:
    t = table(fill_price=1.4)  # sold above the mid
    assert by_id(verify_options(t))["bid_ask_fill"]["status"] == "fail"


def test_crossed_quote_fails() -> None:
    t = table(bid=2.0, ask=1.0)
    assert by_id(verify_options(t))["bid_ask_fill"]["status"] == "fail"


def test_iv_asof_boundary_same_day_passes() -> None:
    assert by_id(verify_options(table()))["iv_asof"]["status"] == "pass"


def test_assignment_dividend_and_pin_warnings() -> None:
    t = table(right="C", strike=100.0, ex_div_date=pd.Timestamp("2024-01-20"), dividend=1.0, underlying_at_expiry=100.2)
    rep = by_id(verify_options(t))
    assert rep["early_exercise_pin"]["status"] == "warn" and "pin" in rep["early_exercise_pin"]["summary"]
    t2 = t.drop(columns=["dividend"])
    assert by_id(verify_options(t2))["dividends"]["status"] == "warn"


def test_no_short_options_means_no_assignment_risk() -> None:
    rep = by_id(verify_options(table(qty=1)))
    assert rep["early_exercise_pin"]["status"] == "pass" and rep["dividends"]["status"] == "pass"


def test_margin_over_equity_fails_and_small_passes() -> None:
    t = table(qty=-30, strike=80.0, fill_price=0.06, bid=0.05, ask=0.07, exit_price=0.0, exit_bid=0.0, exit_ask=0.01)
    assert by_id(verify_options(t, equity=20_000.0))["margin_simplified"]["status"] == "fail"
    assert by_id(verify_options(table(), equity=10_000_000.0))["margin_simplified"]["status"] == "pass"
    assert by_id(verify_options(table()))["margin_simplified"]["status"] == "info"


def test_stress_without_equity_is_a_note_not_a_pass_claim() -> None:
    t = table(qty=-30, strike=80.0, fill_price=0.06, bid=0.05, ask=0.07, exit_price=0.0, exit_bid=0.0, exit_ask=0.01)
    row = by_id(verify_options(t))["tail_stress"]
    assert row["status"] == "warn" and "equity" in row["details"]


def test_loader_errors() -> None:
    with pytest.raises(ValueError, match="lacks required"):
        load_trades(pd.DataFrame({"date": ["2024-01-01"]}))
    bad = table()[["date", "expiry", "right", "strike", "qty", "fill_price"]]
    with pytest.raises(ValueError, match="right must be"):
        load_trades(bad.assign(right="X"))
    with pytest.raises(ValueError, match="qty must not be zero"):
        load_trades(bad.assign(qty=0))
    with pytest.raises(ValueError, match="valid dates"):
        load_trades(bad.assign(date="soon"))
    with pytest.raises(ValueError, match="numbers"):
        load_trades(bad.assign(strike="x"))
    with pytest.raises(ValueError, match="equity"):
        verify_options(table(), equity=-1)


def test_black_scholes_known_values() -> None:
    call = float(bs.price(100, 100, 1.0, 0.2, True, 0.05, 0.0)[0])
    put = float(bs.price(100, 100, 1.0, 0.2, False, 0.05, 0.0)[0])
    assert call == pytest.approx(10.4506, abs=1e-3) and put == pytest.approx(5.5735, abs=1e-3)
    assert call - put == pytest.approx(100 - 100 * np.exp(-0.05), abs=1e-6)  # parity
    assert float(bs.price(110, 100, 0.0, 0.2, True)[0]) == 10.0  # expiry: intrinsic
    assert float(bs.price(90, 100, 0.5, 0.0, False)[0]) == 10.0  # zero vol: intrinsic
    assert float(bs.gamma(100, 100, 1.0, 0.2)[0]) == pytest.approx(0.0198, abs=1e-4)
    assert float(bs.gamma(100, 100, 0.0, 0.2)[0]) == 0.0


def test_cli_end_to_end(tmp_path, capsys) -> None:
    from monte_neo.cli.verify_cmd import main

    csv = tmp_path / "opt.csv"
    case("opt_tail_sale")[0].to_csv(csv, index=False)
    out = tmp_path / "cert.json"
    code = main(["--options", str(csv), "--equity", "100000", "--out", str(out)])
    cert = json.loads(out.read_text())
    assert code == 2 and cert["verdict"] == "REJECT" and cert["profile"]["id"] == "options"
    assert main(["--options", str(tmp_path / "missing.csv")]) == 3


def test_remaining_branches() -> None:
    quotes_only = table()[["date", "expiry", "right", "strike", "qty", "fill_price", "bid", "ask"]].assign(fill_price=1.4)
    assert by_id(verify_options(quotes_only))["bid_ask_fill"]["status"] == "fail"  # better than the mid, no exits to compare
    no_iv_date = table().drop(columns=["iv_asof"])
    assert by_id(verify_options(no_iv_date))["iv_asof"]["status"] == "skip"
    t = table(qty=-30, strike=80.0, fill_price=0.06, bid=0.05, ask=0.07, exit_price=0.0, exit_bid=0.0, exit_ask=0.01)
    assert by_id(verify_options(t, equity=250_000.0))["tail_stress"]["status"] in ("warn", "pass")
    assert by_id(verify_options(t, equity=1_000_000_000.0))["tail_stress"]["status"] == "pass"
    mid = by_id(verify_options(t, equity=200_000.0))["tail_stress"]["status"]
    assert mid in ("warn", "fail", "pass")
    deep = table(right="P", strike=130.0)  # short put 30% in the money at entry
    assert "deep in the money" in by_id(verify_options(deep))["early_exercise_pin"]["summary"]
    no_div_col = table(right="C")
    assert by_id(verify_options(no_div_col))["dividends"]["status"] == "skip"


def test_margin_warn_band() -> None:
    t = table(qty=-30, strike=80.0, fill_price=0.06, bid=0.05, ask=0.07, exit_price=0.0, exit_bid=0.0, exit_ask=0.01)
    peak = by_id(verify_options(t, equity=1.0))["margin_simplified"]["details"]["peak_margin"]
    assert by_id(verify_options(t, equity=peak / 0.8))["margin_simplified"]["status"] == "warn"


def test_stress_warn_band() -> None:
    t = table(qty=-30, strike=80.0, fill_price=0.06, bid=0.05, ask=0.07, exit_price=0.0, exit_bid=0.0, exit_ask=0.01)
    loss = -by_id(verify_options(t, equity=1.0))["tail_stress"]["details"]["worst_stress_pnl"]
    assert by_id(verify_options(t, equity=loss / 0.3))["tail_stress"]["status"] == "warn"


def test_hashing_date_columns_raises_no_warning_and_keeps_the_hash() -> None:
    import warnings

    from monte_neo.options.verify import _rounded

    t = table()
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # DataFrame.round on date columns used to warn
        rep = verify_options(t)
    assert rep["reproducibility"]["data_sha256"] == verify_options(t)["reproducibility"]["data_sha256"]
    r = _rounded(pd.DataFrame({"d": pd.to_datetime(["2024-01-01"]), "x": [1.123456789012], "b": [True], "s": ["a"]}))
    assert r["x"].iloc[0] == 1.1234567890 and bool(r["b"].iloc[0]) is True and r["s"].iloc[0] == "a" and r["d"].iloc[0] == pd.Timestamp("2024-01-01")


def test_pin_risk_without_underlying_at_expiry_is_skip_not_info() -> None:
    t = table(right="P", strike=100.0)
    if "underlying_at_expiry" in t.columns:
        t = t.drop(columns=["underlying_at_expiry"])
    row = by_id(verify_options(t))["early_exercise_pin"]
    assert (t["qty"] < 0).any()
    assert row["status"] == "skip"
    assert row["details"]["not_assessed"] and "underlying_at_expiry" in row["summary"]


def test_pin_risk_assessed_when_underlying_at_expiry_is_far_from_strike() -> None:
    t = table(right="P", strike=100.0, underlying_at_expiry=130.0)
    row = by_id(verify_options(t))["early_exercise_pin"]
    if (t["qty"] < 0).any():
        assert row["status"] in {"info", "warn"}
