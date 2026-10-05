"""Verified discovery: a causal grammar, a search that counts its trials and is tested against its own luck."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "traps"))
from trap_data import planted_momentum_ohlcv  # noqa: E402

from monte_neo.backtest import synthetic_ohlcv  # noqa: E402
from monte_neo.discover import Config, discover, dsl  # noqa: E402
from monte_neo.discover import search as search_mod  # noqa: E402


def _walk(n: int = 1500, seed: int = 1) -> pd.DataFrame:
    df = synthetic_ohlcv(n, seed=seed)
    df["timestamp"] = pd.date_range("2022-01-03", periods=n, freq="h")
    return df


def _run(df: pd.DataFrame, **kw) -> dict:  # noqa: ANN003
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return discover(df, Config(**{"budget": 120, "null_runs": 19, **kw}))


def test_trees_evaluate_like_their_source_and_are_causal() -> None:
    df = _walk(700)
    rng = np.random.default_rng(5)
    cands = dsl.make(rng, 60)
    assert len(cands) == 60 and len({f"{dsl.key(t)}|{m}" for t, m in cands}) == 60
    env = dsl.environment(df)
    for tree, m in cands:
        src = dsl.strategy_source(tree, m, "long_short")
        scope: dict = {}
        exec(compile(src, "<t>", "exec"), scope)  # noqa: S102
        from_source = np.asarray(scope["signal"](df.copy()), dtype=float)
        f = dsl.evaluate(tree, env, {})
        by_tree = search_mod._positions(f, m, "long_short", {}, dsl.key(tree))
        assert np.array_equal(from_source, by_tree), dsl.key(tree)
        assert search_mod.causality_gate(src, df), dsl.key(tree)
        assert dsl.depth(tree) <= 4 and dsl.lookback(tree) >= 0


def test_the_canonical_key_ignores_operand_order_and_unknown_operations_are_refused() -> None:
    a, b = dsl.leaf("close"), dsl.leaf("open")
    assert dsl.key(dsl.op("add", (a, b))) == dsl.key(dsl.op("add", (b, a)))
    assert dsl.key(dsl.op("sub", (a, b))) != dsl.key(dsl.op("sub", (b, a)))
    with pytest.raises(ValueError):
        dsl.op("shift_forward", (a,), (3,))
    assert "df[\"close\"]" in dsl.to_source(a)


def test_the_surrogate_keeps_the_bars_but_not_their_order() -> None:
    df = _walk(800)
    out = search_mod.surrogate(df, np.random.default_rng(1))
    assert len(out) == len(df) and (out["high"] >= out[["open", "close"]].max(axis=1) - 1e-9).all() and (out["low"] <= out[["open", "close"]].min(axis=1) + 1e-9).all()
    ratio = lambda d: np.sort((d["close"] / d["close"].shift(1).fillna(d["close"].iloc[0])).to_numpy())  # noqa: E731
    assert np.allclose(ratio(out), ratio(df), rtol=1e-9)
    assert not np.allclose(out["close"].to_numpy(), df["close"].to_numpy())
    assert not np.allclose(out["close"].to_numpy(), search_mod.surrogate(df, np.random.default_rng(2))["close"].to_numpy())


def test_duplicates_are_one_trial_and_independent_candidates_are_many() -> None:
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, 500)
    dup = np.vstack([base + rng.normal(0, 0.05, 500) for _ in range(30)])
    assert len(search_mod._clusters(dup, np.arange(30.0), 0.8)) == 1
    indep = rng.normal(0, 1, (30, 500))
    assert len(search_mod._clusters(indep, np.arange(30.0), 0.8)) == 30
    assert search_mod._clusters(np.zeros((3, 50)), np.zeros(3), 0.8) == []


def test_a_broken_gate_stops_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_mod, "causality_gate", lambda source, df: True)
    with pytest.raises(RuntimeError, match="leaky canary"):
        _run(_walk(), budget=30, null_runs=2)
    monkeypatch.setattr(search_mod, "causality_gate", lambda source, df: False)
    with pytest.raises(RuntimeError, match="canar|genuine"):
        _run(_walk(), budget=30, null_runs=2)


def test_every_canary_is_rejected_by_the_gate() -> None:
    for seed in (1, 2, 3):
        window = _walk(600, seed)
        assert not any(search_mod.causality_gate(search_mod._canary_source(e), window) for e in search_mod.CANARIES)


def test_the_lockbox_is_not_seen_by_the_search() -> None:
    df = _walk(1500)
    changed = df.copy()
    split = int(len(df) * 0.8)
    changed.loc[split:, ["open", "high", "low", "close"]] = changed.loc[split:, ["open", "high", "low", "close"]].to_numpy()[::-1] * 2.0
    a, b = _run(df), _run(changed)
    assert a["search"] == b["search"] and a["journal_sha256"] == b["journal_sha256"] and a["best"]["key"] == b["best"]["key"]
    assert a["lockbox"] != b["lockbox"] and a["lockbox"]["opened"] == 1


def test_same_inputs_same_answer() -> None:
    df = _walk(1200)
    a, b = _run(df, seed=4), _run(df, seed=4)
    assert a["journal_sha256"] == b["journal_sha256"] and a["search"] == b["search"] and a["certificate"]["certificate_id"] == b["certificate"]["certificate_id"]
    assert _run(df, seed=5)["journal_sha256"] != a["journal_sha256"]


def test_noise_is_not_discovered_although_every_search_finds_something_great() -> None:
    """On random walks the best candidate looks excellent, and the honest search says there is nothing."""
    results = [_run(_walk(1500, seed=100 + i), seed=i) for i in range(12)]
    naive = [r["search"]["best_sharpe"] for r in results]
    assert float(np.median(naive)) > 1.5, "a naive search would report these as strategies"
    assert sum(r["found"] for r in results) <= 1, [r["reasons"] for r in results if r["found"]]
    assert all(r["search"]["p_search_null"] is not None and r["search"]["effective_trials"] > 10 for r in results)


def test_a_planted_edge_is_found_and_certified() -> None:
    result = _run(planted_momentum_ohlcv(4000), budget=300, cost_bps=0.5)
    assert result["found"], result["reasons"]
    assert result["search"]["p_search_null"] <= 0.05 and result["lockbox"]["sharpe"] > 0
    cert = result["certificate"]
    assert cert["verdict"] != "REJECT" and cert["reproducibility"]["n_trials"] == result["search"]["effective_trials"]
    assert "def signal(df)" in result["best"]["source"] and result["selftest"]["canaries_rejected"] == result["selftest"]["canaries"]


def test_costs_can_take_the_edge_away() -> None:
    assert not _run(planted_momentum_ohlcv(4000), budget=300, cost_bps=5.0)["found"]


@pytest.mark.parametrize("kw", [{"lockbox": 0.01}, {"lockbox": 0.9}, {"side": "sideways"}])
def test_bad_settings_are_refused(kw: dict) -> None:
    with pytest.raises(ValueError):
        _run(_walk(), **kw)
    with pytest.raises(ValueError):
        discover(_walk(300))


def test_the_result_reports_repainting_and_the_repainting_canaries_are_in_the_list() -> None:
    assert sum("groupby" in c or "center=True" in c or "shift(-1)" in c for c in search_mod.CANARIES) >= 3
    result = _run(_walk(), budget=40, null_runs=2)
    assert result["repaint"]["confirmation"] == "close" and result["repaint"]["history"] == "pass"
    assert result["repaint"]["flicker_rate"] is not None
