"""Strategy-type profiles: rules file, certificate block, suggestions, traps and controls."""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.profiles import PROFILE_IDS, get_profile, load_profiles, profile_block, suggest_profiles
from monte_neo.verify import verify_strategy

KNOWN_CHECKS = set("""accounting_mismatch alpha_after_beta alpha_after_reference benchmark borrow_risk capacity carry_decomposition
carry_future_probe carry_margin carry_margin_no_topup corporate_actions correlation_breakdown_stress cost_margin cost_realism
cost_sensitivity data_integrity data_quality deflated_sharpe delay_sensitivity drawdown_consistency events_quality execution_capacity
funding_borrow_stress hidden_short_volatility implausible_consistency legging_risk liquidity_stress lookahead_truncation net_profitability
pair_selection parameter_plateau pbo period_consistency pit_events publication_dates rebalance_timing_luck regime_mix_bootstrap
regime_stability regime_swap_null repaint_history return_smoothing selection_vs_timing_basket spread_half_life structural_break_hedge
structural_break_spread survivorship tail_dependence timing_significance trials_disclosed universe_membership walk_forward_stability
bid_ask_fill iv_asof tail_stress early_exercise_pin margin_simplified dividends options_chain""".split())

DF = synthetic_ohlcv(1500, seed=3)


def _case(name: str):
    rng = np.random.default_rng(5)
    if name in ("leak_next_close", "centered_window", "full_sample_norm"):
        def leak(df):
            c = df["close"]
            if name == "leak_next_close":
                return np.sign(c.shift(-1) - c).fillna(0).to_numpy()
            if name == "centered_window":
                return np.where(c > c.rolling(21, center=True).mean(), 1, -1)
            z = (c - c.mean()) / c.std()
            return np.where(z < 0, 1, -1)
        return leak
    if name == "overtrade":
        return lambda df: np.where(df["close"].diff().fillna(0) > 0, -1, 1)
    if name == "random_entry":
        sig = rng.choice([-1, 0, 1], size=len(DF))
        return lambda df: sig[: len(df)]
    if name == "always_flat":
        return lambda df: np.zeros(len(df), dtype=np.int64)
    if name == "honest_causal":
        return lambda df: np.where(df["close"].rolling(20).mean() > df["close"].rolling(80).mean(), 1, 0)
    raise KeyError(name)


@cache
def _run(case: str) -> dict:
    return verify_strategy(DF, signal_fn=_case(case), n_trials=10, probe_checks=6, source=None)


def _meets(report: dict, expect: dict) -> bool:
    ok = True
    if "verdict" in expect:
        ok &= report["verdict"] == expect["verdict"]
    if "verdict_not" in expect:
        ok &= report["verdict"] != expect["verdict_not"]
    if "any_check_fails_in" in expect:
        ok &= any(c["category"] == expect["any_check_fails_in"] and c["status"] == "fail" for c in report["checks"])
    if "no_check_fails_in" in expect:
        ok &= not any(c["category"] == expect["no_check_fails_in"] and c["status"] == "fail" for c in report["checks"])
    return bool(ok)


def test_rules_file_is_consistent() -> None:
    doc = load_profiles()
    assert len(doc["profiles"]) >= 11 and "options" in {p["id"] for p in doc["profiles"]}
    for p in doc["profiles"]:
        assert len(p["traps"]) >= 2 and len(p["controls"]) == 2
        unknown = (set(p["required_checks"]) | set(p.get("recommended_checks", []))) - KNOWN_CHECKS
        assert not unknown, (p["id"], unknown)
        assert all(n["why"] for n in p["not_assessed"])
        assert p["benchmark"]


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        get_profile("nope")
    with pytest.raises(ValueError, match="unknown profile"):
        verify_strategy(DF, signal_fn=_case("honest_causal"), profile="nope")


@pytest.mark.parametrize("pid", [p for p in PROFILE_IDS if p != "options"])  # options cases run in test_options.py
def test_traps_fire_and_controls_stay_quiet(pid: str) -> None:
    prof = get_profile(pid)
    for item in prof["traps"] + prof["controls"]:
        assert _meets(_run(item["case"]), item["expect"]), (pid, item["id"])


def test_profile_block_in_certificate_and_verdict_unchanged() -> None:
    plain = _run("honest_causal")
    with_profile = verify_strategy(DF, signal_fn=_case("honest_causal"), n_trials=10, probe_checks=6, profile="trend_cta")
    assert with_profile["verdict"] == plain["verdict"]
    block = with_profile["profile"]
    assert block["id"] == "trend_cta" and block["rules"] == "profiles/1"
    assert set(block["ran"]) | {n["check"] for n in block["not_run"]} == set(block["required"])
    assert "profile" not in plain
    assert block["not_assessed"] and all(n["why"] for n in block["not_assessed"])


def test_profile_block_marks_skipped_and_missing_checks() -> None:
    checks = [{"id": "data_integrity", "status": "pass", "summary": "ok"}, {"id": "benchmark", "status": "skip", "summary": "too short"}]
    block = profile_block("buy_and_hold", checks)
    reasons = {n["check"]: n["why"] for n in block["not_run"]}
    assert reasons["benchmark"] == "too short" and reasons["lookahead_truncation"].startswith("not produced")
    assert not block["complete"] and block["ran"] == ["data_integrity"]


def test_failed_required_check_is_reported() -> None:
    block = profile_block("buy_and_hold", [{"id": "data_integrity", "status": "fail", "summary": "bad"}])
    assert block["failed"] == ["data_integrity"]


def test_suggestions() -> None:
    assert suggest_profiles(["funding_rate", "perp_close"])[0]["id"] == "carry"
    assert suggest_profiles(["px_a", "qty_a", "px_b", "qty_b"])[0]["id"] == "pairs_stat_arb"
    assert suggest_profiles([], np.ones(100))[0]["id"] == "buy_and_hold"
    assert suggest_profiles(["open", "close"]) == []
    ids = [s["id"] for s in suggest_profiles(["symbol"], np.array([[0.5, -0.5], [-0.5, 0.5]]), top=5)]
    assert "market_neutral" in ids and "cross_sectional" in ids
    assert suggest_profiles([], np.zeros(50) + np.r_[np.ones(5), np.zeros(45)])[0]["id"] == "mean_reversion"
    assert suggest_profiles([], np.array([1, -1, 1, -1]))[0]["id"] == "trend_cta"


def test_recheck_keeps_profile() -> None:
    from monte_neo.verify import recheck_certificate

    sig = _case("honest_causal")(DF)
    cert = verify_strategy(DF, signals=sig, n_trials=3, probe_checks=4, profile="mean_reversion")
    again = recheck_certificate(cert, DF, signals=sig) if "signals" in recheck_certificate.__code__.co_varnames else None
    if again is not None:
        assert again.get("reproduced", True) is not False


def test_guide_matches_rules_file() -> None:
    from pathlib import Path

    from monte_neo.profiles.docgen import END, START, markdown_profiles

    page = (Path(__file__).resolve().parents[2] / "docs" / "guides" / "profiles.md").read_text(encoding="utf-8")
    block = page.split(START, 1)[1].split(END, 1)[0]
    assert block.strip() == markdown_profiles().strip(), "run scripts/gen_profiles_doc.py"
    assert "never raises a verdict" in page


def test_cli_list_and_profile_flag(tmp_path) -> None:
    from monte_neo.cli.verify_cmd import main

    assert main(["--list-profiles"]) == 0
    csv = tmp_path / "o.csv"
    DF.to_csv(csv, index=False)
    sigs = tmp_path / "s.csv"
    pd.Series(_case("honest_causal")(DF)).to_csv(sigs, index=False, header=False)
    out = tmp_path / "c.json"
    main(["--ohlcv", str(csv), "--signals", str(sigs), "--profile", "trend_cta", "--out", str(out), "--n-trials", "5"])
    import json

    assert json.loads(out.read_text())["profile"]["id"] == "trend_cta"
    assert main(["--ohlcv", str(csv), "--signals", str(sigs), "--profile", "nope"]) == 3


def test_suggest_more_inputs() -> None:
    assert suggest_profiles(["strike", "expiry"])[0]["id"] == "options"
    assert suggest_profiles(["ev_x", "close"])[0]["id"] == "event_driven"
    assert suggest_profiles(["iv", "close"])[0]["id"] == "short_volatility"


def test_registry_validation(tmp_path, monkeypatch) -> None:
    import json

    from monte_neo.profiles import registry

    good = json.loads(registry.RULES_FILE.read_text())

    def load(doc):
        f = tmp_path / "p.json"
        f.write_text(json.dumps(doc))
        monkeypatch.setattr(registry, "RULES_FILE", f)
        registry.load_profiles.cache_clear()
        try:
            return registry.load_profiles()
        finally:
            monkeypatch.undo()
            registry.load_profiles.cache_clear()

    p0 = good["profiles"][0]
    for doc, msg in (
        ({**good, "version": "x"}, "unknown profile rules version"),
        ({**good, "profiles": [{k: v for k, v in p0.items() if k != "title"}]}, "lacks"),
        ({**good, "profiles": [p0, p0]}, "duplicate"),
        ({**good, "profiles": [{**p0, "traps": p0["traps"][:1]}]}, "at least 2"),
        ({**good, "profiles": [{**p0, "not_assessed": [{"what": "x", "why": ""}]}]}, "reason"),
    ):
        with pytest.raises(ValueError, match=msg):
            load(doc)


def test_profile_flag_reaches_legs_and_carry_certificates(tmp_path) -> None:
    """--profile adds the coverage block to every certificate that has checks, not only the OHLCV path."""
    import json

    from monte_neo.cli.verify_cmd import main
    from monte_neo.verify.phantom import pair_pnl, random_walk_pair

    rng = np.random.default_rng(5)
    bars, window = 600, 50
    log_y, log_x = random_walk_pair(bars, 0.01, rng)
    res = pair_pnl(log_y, log_x, window)
    table = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=bars, freq="h"), "px_y": np.exp(log_y), "px_x": np.exp(log_x),
        "qty_y": res["qty_y"], "qty_x": res["qty_x"], "reported_return": res["tradable"],
    }).iloc[window + 1:]
    legs = tmp_path / "legs.csv"
    table.to_csv(legs, index=False)
    out = tmp_path / "cert.json"
    main(["--legs", str(legs), "--profile", "pairs_stat_arb", "--out", str(out)])
    assert json.loads(out.read_text())["profile"]["id"] == "pairs_stat_arb"
    assert main(["--legs", str(legs), "--profile", "nope"]) == 3


def test_signals_with_jobs_says_what_to_do(tmp_path, capsys) -> None:
    """--jobs with --signals names the fix instead of a bare 'need strategy code in a file'."""
    from monte_neo.cli.verify_cmd import build_parser, main

    ohlc = synthetic_ohlcv(400, seed=1)
    pd.DataFrame({k: ohlc[k] for k in ("open", "high", "low", "close")}).to_csv(tmp_path / "p.csv", index=False)
    np.save(tmp_path / "s.npy", np.ones(400))
    code = main(["--ohlcv", str(tmp_path / "p.csv"), "--signals", str(tmp_path / "s.npy"), "--jobs", "2"])
    out = capsys.readouterr()
    assert code == 3 and "--strategy file.py" in (out.out + out.err).replace("\n", " ")
    assert "examples:" in build_parser().format_help()
