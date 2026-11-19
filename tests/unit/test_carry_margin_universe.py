"""Collateral policy and bar highs for the carry margin, attribution against the underlying, an ex-ante universe rule, capacity units, basket independence."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.readiness import readiness
from monte_neo.verify.carry import (
    attribution_rows,
    carry_table,
    membership_from_rule,
    quote_volume,
    universe_rule_row,
    verify_carry,
)
from monte_neo.verify.carry_market import margin_rows, simulate_margin
from monte_neo.verify.market import market_for

HEAD = "import numpy as np\ndef signal(df):\n"
ALWAYS = HEAD + "    return np.ones(len(df))\n"


def _by_id(rep):
    return {c["id"]: c for c in rep["checks"]}


def _path(rise: list[tuple[int, float]], n: int = 40) -> np.ndarray:
    """Perpetual price: 100, then multiplied by (1 + r) at each listed bar (cumulative)."""
    p = np.full(n, 100.0)
    for bar, r in rise:
        p[bar:] = 100.0 * (1.0 + r)
    return p


W = np.ones(40)


# ---------------------------------------------------------------- margin policy
def test_five_times_leverage_without_a_policy_is_liquidated_and_says_so() -> None:
    rows = margin_rows(W, np.linspace(100, 122, 40), 5.0)
    assert rows[0]["status"] == "fail" and "no collateral management" in rows[0]["summary"] and len(rows) == 1


def test_a_declared_policy_that_keeps_up_survives_but_costs_reserve_and_shows_the_no_topup_row() -> None:
    perp = np.linspace(100, 122, 40)
    policy = {"trigger": 0.15, "delay_bars": 0, "cost_bps": 20.0}
    main, info = margin_rows(W, perp, 5.0, policy=policy)
    assert main["status"] == "warn" and main["details"]["topups"] >= 1 and main["details"]["transfer_cost_share"] == pytest.approx(main["details"]["topup_total_share"] * 0.002)
    assert info["id"] == "carry_margin_no_topup" and info["status"] == "info" and info["details"]["liquidated_episodes"] == 1


def test_a_policy_that_arrives_too_late_for_a_gap_is_caught() -> None:
    gap = _path([(10, 0.10), (13, 0.30)])  # +10% (order placed), then a +20% gap before the transfer arrives
    main, info = margin_rows(W, gap, 5.0, policy={"trigger": 0.15, "delay_bars": 4, "cost_bps": 0.0})
    assert main["status"] == "fail" and "even with the declared top-ups" in main["summary"] and main["details"]["liquidated_with_transfer_pending"] == 1
    instant = margin_rows(W, _path([(10, 0.10), (13, 0.15)]), 5.0, policy={"trigger": 0.15, "delay_bars": 0, "cost_bps": 0.0})[0]
    assert instant["status"] == "warn"  # the same policy with an instant transfer would have kept up


def test_liquidation_is_tested_on_the_bar_high_not_the_close() -> None:
    close = _path([(10, 0.03)])
    high = close.copy()
    high[10] = 100.0 * 1.25  # a spike inside the bar, back to +3% at the close
    assert margin_rows(W, close, 5.0, perp_high=high)[0]["status"] == "fail"
    only_close = margin_rows(W, close, 5.0)[0]
    assert only_close["status"] == "warn" and "closes only" in only_close["summary"] and only_close["details"]["intrabar"] is False
    assert margin_rows(W, close, 5.0, perp_high=close)[0]["status"] == "pass"


def test_negative_funding_drains_the_margin_without_any_price_move() -> None:
    flat = np.full(80, 100.0)
    drain = np.full(80, -0.002)  # -0.2% of notional per bar
    assert margin_rows(np.ones(80), flat, 20.0, perp_high=flat, funding=drain)[0]["status"] == "fail"
    assert margin_rows(np.ones(80), flat, 20.0, perp_high=flat, funding=-drain)[0]["status"] == "pass"


def test_margin_inputs_and_episodes() -> None:
    perp = np.linspace(100, 110, 40)
    for bad in ({"trigger": 0.0}, {"trigger": 0.5}, {}):
        with pytest.raises(ValueError, match="trigger"):
            margin_rows(W, perp, 5.0, policy=bad)
    with pytest.raises(ValueError, match="leverage"):
        margin_rows(W, perp, 0.5)
    two = np.zeros(40)
    two[3:10] = 1
    two[20:30] = 1
    assert simulate_margin(two, perp, None, None, 5.0, 0.005, None)["episodes"] == 2
    assert margin_rows(np.zeros(40), perp, 5.0)[0]["status"] == "skip"
    gap = perp.copy()
    gap[15] = np.nan
    assert simulate_margin(W, gap, None, None, 3.0, 0.005, None)["episodes"] == 1


def test_margin_policy_reaches_the_certificate(tmp_path) -> None:
    rng = np.random.default_rng(2)
    n = 600
    spot = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    perp = spot * (1 + rng.normal(0, 0.0005, n))
    raw = pd.DataFrame({"timestamp": pd.date_range("2022-01-01", periods=n, freq="8h", tz="UTC"), "spot_close": spot, "perp_close": perp,
                        "perp_high": perp * 1.002, "funding_rate": 2e-4 + rng.normal(0, 2e-5, n)})
    f = tmp_path / "s.py"
    f.write_text(ALWAYS)
    ids = _by_id(verify_carry(raw, strategy=f, perp_leverage=3.0, margin_policy={"trigger": 0.2, "delay_bars": 1, "cost_bps": 5.0}))
    assert "carry_margin" in ids and ids["carry_margin_no_topup"]["status"] == "info" and ids["carry_margin"]["details"]["intrabar"] is True


# ---------------------------------------------------------------- attribution
def _raw(n: int = 800, seed: int = 3, fund=3e-4, sym: str | None = None, vol: float = 1e7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    spot = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    df = pd.DataFrame({"timestamp": pd.date_range("2022-01-01", periods=n, freq="8h", tz="UTC"), "spot_close": spot, "perp_close": spot * (1 + rng.normal(0, 0.0005, n)),
                       "funding_rate": fund + rng.normal(0, 3e-5, n) if np.isscalar(fund) else fund})
    if sym:
        df["symbol"] = sym
        df["perp_quote_volume"] = vol
        df["spot_quote_volume"] = vol
    return df


def test_certificate_carries_residual_alpha_and_hidden_short_vol_for_carry(tmp_path) -> None:
    f = tmp_path / "s.py"
    f.write_text(ALWAYS)
    rep = verify_carry(_raw(), strategy=f)
    ids = _by_id(rep)
    assert {"residual_alpha", "hidden_short_volatility"} <= set(ids) and ids["residual_alpha"]["details"]["alpha_t"] > 2
    d = ids["hidden_short_volatility"]["details"]
    assert d["funding_earned"] > 0 and d["worst_basis_bar_while_held"] < 0 and "tm_gamma" in d
    lv5 = next(lv for lv in readiness(rep)["levels"] if lv["level"] == 5)
    assert lv5["state"] != "not assessed" and lv5["depth_criteria"][0]["state"] == "met"  # level 5 is assessed now: it needed these two rows


def test_negative_funding_spikes_make_carry_a_hidden_short_vol() -> None:
    n = 800
    fund = np.full(n, 1e-4)
    fund[::40] = -0.004  # a rare spike takes back most of what accrues
    t = carry_table(_raw(n=n, fund=fund))
    m = market_for(t)
    rows = attribution_rows(np.random.default_rng(0).normal(0.0002, 0.001, n - 61), m, 60, 1095.0, None, np.ones((n, 1)))
    hsv = rows[1]
    assert hsv["status"] == "warn" and "takes back" in hsv["summary"] and hsv["details"]["negative_funding_share_of_earned"] >= 0.5


def test_basket_attribution_uses_the_named_coin_and_the_equal_weight_spot() -> None:
    t = carry_table(pd.concat([_raw(seed=s, sym=c) for s, c in ((1, "BTC"), (2, "ETH"), (3, "SOL"))], ignore_index=True))
    m = market_for(t)
    w = np.ones((m.n_bars, 3))
    r = np.random.default_rng(1).normal(0.0003, 0.001, m.n_bars - 61)
    rows = attribution_rows(r, m, 60, 1095.0, "BTC", w)
    assert rows[0]["id"] == "residual_alpha"
    with pytest.raises(ValueError, match="not a coin of the basket"):
        attribution_rows(r, m, 60, 1095.0, "XRP", w)


# ---------------------------------------------------------------- ex-ante composition rule and survivorship
def _pool(late: bool, early: bool, n: int = 600) -> pd.DataFrame:
    parts = []
    for i, c in enumerate("ABCDE"):
        d = _raw(n=n, seed=20 + i, sym=c, vol=1e7 * (5 - i))
        if late and c == "E":
            d = d.iloc[120:].reset_index(drop=True)
        if early and c == "D":
            d = d.iloc[:480].reset_index(drop=True)
        parts.append(d)
    return pd.concat(parts, ignore_index=True)


RULE = {"top_n": 3, "lookback_bars": 30, "rebalance_every": 30, "on": "perp_quote_volume"}
BASKET_RULE_STRATEGY = HEAD + "    return df['in_universe'].to_numpy().astype(float)\n"
BASKET_OUTSIDE = HEAD + "    return np.ones(len(df))\n"


def test_membership_is_recomputed_from_earlier_bars_only() -> None:
    raw = _pool(False, False)
    m = membership_from_rule(raw, RULE)
    wide = m.groupby([raw["timestamp"], raw["symbol"]]).first().unstack()
    assert not wide.iloc[:30].any().any() and (wide.iloc[30:].sum(axis=1) == 3).all()
    assert list(wide.columns[wide.iloc[40]]) == ["A", "B", "C"]  # the three largest by volume
    spike = raw.copy()
    row = spike[(spike["symbol"] == "E")].index[60]
    spike.loc[row, "perp_quote_volume"] = 1e15  # a spike at bar 60 may only count from the next rebalance after it
    w2 = membership_from_rule(spike, RULE).groupby([spike["timestamp"], spike["symbol"]]).first().unstack()
    assert not w2["E"].iloc[:90].any() and w2["E"].iloc[90]
    for bad in ({"top_n": 3}, {**RULE, "top_n": 0}):
        with pytest.raises(ValueError, match="universe_rule needs"):
            membership_from_rule(raw, bad)
    with pytest.raises(ValueError, match="needs a symbol column"):
        membership_from_rule(raw.rename(columns={"perp_quote_volume": "q"}), RULE)


def test_rule_lifts_the_cap_only_when_the_pool_is_not_a_static_list(tmp_path) -> None:
    f = tmp_path / "rule.py"
    f.write_text(BASKET_RULE_STRATEGY)
    dynamic = _by_id(verify_carry(_pool(False, True), strategy=f, universe_rule=RULE))
    assert dynamic["survivorship"]["status"] == "pass" and "ex-ante rule" in dynamic["survivorship"]["summary"] and dynamic["universe_rule"]["status"] == "pass"
    for late, early in ((False, False), (True, False)):  # nobody ever leaves: the pool looks like survivors, listings alone do not help
        static = _by_id(verify_carry(_pool(late, early), strategy=f, universe_rule=RULE))
        assert static["survivorship"]["status"] == "warn" and "cap stays" in static["survivorship"]["summary"]
        assert static["universe_rule"]["status"] == "pass"
    direct = carry_table(_pool(False, False), universe_rule=RULE)
    assert direct["in_universe"].dtype == bool and 0.0 < direct["in_universe"].mean() < 1.0


def test_a_hand_made_list_keeps_the_cap_even_when_declared_complete(tmp_path) -> None:
    f = tmp_path / "all.py"
    f.write_text(BASKET_OUTSIDE)
    rep = verify_carry(_pool(False, False), strategy=f, delisted=[])  # "there were none": a manual list
    s = _by_id(rep)["survivorship"]
    assert s["status"] == "warn" and "no ex-ante composition rule" in s["summary"]
    assert "universe_rule" not in _by_id(rep)


def test_holding_coins_the_rule_did_not_select_fails(tmp_path) -> None:
    f = tmp_path / "all.py"
    f.write_text(BASKET_OUTSIDE)
    row = _by_id(verify_carry(_pool(True, True), strategy=f, universe_rule=RULE))["universe_rule"]
    assert row["status"] == "fail" and row["details"]["held_outside_rule"] > 0 and "not selected" in row["summary"]
    assert universe_rule_row(market_for(carry_table(_raw())), np.ones((800, 1)), RULE)["status"] == "skip"


# ---------------------------------------------------------------- capacity units
def test_capacity_uses_the_smaller_leg_in_quote_currency_and_the_spread_bars(tmp_path) -> None:
    raw = _raw(n=400).assign(spot_quote_volume=2e6, perp_quote_volume=5e6)
    f = tmp_path / "toggle.py"
    f.write_text(HEAD + "    return np.tile(np.array([1.0] * 20 + [0.0] * 20), len(df) // 40 + 1)[: len(df)]\n")
    cap = _by_id(verify_carry(raw, strategy=f))["capacity"]["details"]
    assert cap["capital"] == pytest.approx([2e6 * 0.01, 2e6 * 0.05, 2e6 * 0.10], rel=1e-6)  # min of the legs x participation, not x the index level
    wide = _by_id(verify_carry(raw, strategy=f, capacity_spread_bars=3))["capacity"]["details"]
    assert wide["capital"] == pytest.approx([c * 3 for c in cap["capital"]], rel=1e-6)  # three bars of volume to work the order in
    legacy = _by_id(verify_carry(_raw(n=400).assign(volume=4e6), strategy=f))["capacity"]["details"]
    assert legacy["capital"][0] == pytest.approx(4e6 * 0.01, rel=1e-6)
    assert quote_volume(pd.DataFrame({"a": [1.0]})) is None
    assert quote_volume(pd.DataFrame({"spot_quote_volume": [3.0, np.nan], "perp_quote_volume": [5.0, 7.0]})).tolist() == [3.0, 7.0]


# ---------------------------------------------------------------- independence in a basket
def test_data_independence_runs_on_a_basket(tmp_path) -> None:
    regime = np.repeat([1.0, -1.0, 1.0, 1.0, -1.0, 1.0, -1.0, 1.0], 100)[:800]
    raw = pd.concat([_raw(seed=s, sym=c, fund=3e-4 * regime) for s, c in ((1, "A"), (2, "B"), (3, "C"))], ignore_index=True)
    honest = tmp_path / "h.py"
    honest.write_text(HEAD + "    f = df.groupby('symbol')['funding_rate'].transform(lambda x: x.rolling(9).mean().shift(1))\n    return np.where(f.fillna(0).to_numpy() > 0.0, 1.0, 0.0)\n")
    stored = tmp_path / "s.py"
    stored.write_text(HEAD + "    return np.tile(np.array([1.0] * 40 + [0.0] * 40), len(df) // 80 + 1)[: len(df)]\n")
    assert _by_id(verify_carry(raw, strategy=honest))["data_independence"]["status"] == "pass"
    assert _by_id(verify_carry(raw, strategy=stored))["data_independence"]["status"] in ("warn", "fail")


def test_one_coin_basket_has_no_survivorship_verdict_and_the_cli_takes_the_new_flags(tmp_path, capsys) -> None:
    from monte_neo.cli.verify_cmd import main

    one = _raw(sym="A")
    assert market_for(carry_table(one)).universe_checks()[0]["status"] == "skip"
    pool = _pool(False, True)
    csv, f = tmp_path / "p.csv", tmp_path / "r.py"
    pool.to_csv(csv, index=False)
    f.write_text(BASKET_RULE_STRATEGY)
    code = main(["--carry", str(csv), "--strategy", str(f), "--carry-universe-rule", '{"top_n": 3, "lookback_bars": 30, "rebalance_every": 30}',
                 "--carry-margin-policy", '{"trigger": 0.2, "delay_bars": 1, "cost_bps": 5}', "--carry-reference", "A", "--carry-spread-bars", "2"])
    out = capsys.readouterr().out
    assert code in (0, 1, 2) and "universe_rule" in out and "carry_margin" in out, out[-400:]
    from monte_neo.mcp import tools

    rep = tools.verify_carry(str(csv), str(f), universe_rule={"top_n": 3, "lookback_bars": 30, "rebalance_every": 30}, margin_policy={"trigger": 0.2}, reference_symbol="A")
    assert any(c["id"] == "universe_rule" for c in rep["checks"])
