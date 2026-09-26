"""Trap Suite: known ways a backtest lies, each with its expected verdict.

Add a trap = add ``strategies/<name>.py`` with ``signal(df)`` + a row in TRAPS.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from monte_neo.backtest import run_bar_backtest
from monte_neo.verify import model_from_costs, verify_grid, verify_strategy

STRATEGY_DIR = Path(__file__).parent / "strategies"

LOOKAHEAD_IDS = ("lookahead_truncation", "lookahead_perturbation", "lookahead_static_lint", "implausible_accuracy")

# name, dataset, allowed verdicts, required check statuses
TRAPS = [
    ("lookahead_shift", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail", "implausible_accuracy": "fail"}),
    ("centered_window", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("global_zscore", "random_walk", {"REJECT"}, {"lookahead_perturbation": "fail"}),
    ("bfill_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("high_turnover", "random_walk", {"REJECT"}, {"net_profitability": "fail"}),
    ("hourly_close_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("reverse_rolling", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("full_polyfit", "random_walk", {"REJECT"}, {"lookahead_perturbation": "fail", "lookahead_static_lint": "warn"}),
    ("full_rank", "random_walk", {"REJECT"}, {"lookahead_perturbation": "fail", "lookahead_static_lint": "warn"}),
    ("resample_max_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("target_encoding_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("diff_negative", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("pct_change_negative", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("roll_negative", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("merge_asof_forward", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("interpolate_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("cumsum_total_norm", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("last_row_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("idxmax_leak", "random_walk", {"REJECT"}, {"lookahead_perturbation": "fail", "lookahead_static_lint": "warn"}),
    ("numpy_global_stat", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("gradient_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("convolve_same", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("fft_denoise", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("qcut_full", "random_walk", {"REJECT"}, {"lookahead_perturbation": "fail", "lookahead_static_lint": "warn"}),
    ("argsort_rank", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("reversed_cummax", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("reindex_nearest", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("bars_left_in_hour", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("hour_size_leak", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("hourly_close_map", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("sort_values_rank", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("forward_window_indexer", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("np_sort_rank", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("cut_auto_bins", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("reversed_accumulate", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("tail_threshold", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("iat_last", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("builtin_max", "random_walk", {"REJECT"}, {"lookahead_perturbation": "fail", "lookahead_static_lint": "warn"}),
    ("describe_threshold", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("nlargest_dates", "random_walk", {"REJECT"}, {"lookahead_perturbation": "fail", "lookahead_static_lint": "warn"}),
    ("agg_zscore", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("flip_cumsum", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("resample_ffill_max", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("np_interp_fill", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("mode_level", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("value_counts_level", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "warn"}),
    ("centered_variable", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    ("shift_variable", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "fail"}),
    # Invisible to the static lint: only the dynamic probes catch these.
    ("dataset_fraction", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "pass"}),
    ("block_mean_reshape", "random_walk", {"REJECT"}, {"lookahead_truncation": "fail", "lookahead_static_lint": "pass"}),
    ("sma_cross", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE"}, {}),
    ("resample_shifted", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("expanding_rank", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("expanding_zscore", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("cummax_drawdown", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("ewm_cross", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("convolve_causal", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("rolling_quantile_band", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("prev_hour_close_map", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("bars_into_hour", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("expanding_quantile_band", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("cut_fixed_bins", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("hour_running_high", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("rolling_min_periods", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("rolling_apply_span", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("hour_open_ref", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("expanding_max_breakout", "random_walk", {"REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS"}, {"lookahead_static_lint": "pass"}),
    ("momentum", "planted", {"PASS", "PASS_WITH_WARNINGS"}, {"net_profitability": "pass", "deflated_sharpe": "pass"}),
]
HONEST = {"high_turnover", "sma_cross", "momentum", "expanding_zscore", "resample_shifted", "expanding_rank", "cummax_drawdown",
          "ewm_cross", "convolve_causal", "rolling_quantile_band",
          "prev_hour_close_map", "bars_into_hour", "expanding_quantile_band",
          "cut_fixed_bins", "hour_running_high", "rolling_min_periods",
          "rolling_apply_span", "hour_open_ref", "expanding_max_breakout"}
# Parameterized strategies exercised through verify_grid (not in TRAPS).
GRID_STRATEGIES = {"sma_params", "momentum_params"}


def _statuses(report: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in report["checks"]}


def test_every_strategy_file_is_in_manifest() -> None:
    files = {p.stem for p in STRATEGY_DIR.glob("*.py")}
    assert files == {t[0] for t in TRAPS} | GRID_STRATEGIES


def test_every_strategy_file_is_in_catalogue() -> None:
    guide = (Path(__file__).parents[2] / "docs" / "guides" / "trap-suite.md").read_text(encoding="utf-8")
    missing = sorted(p.stem for p in STRATEGY_DIR.glob("*.py") if f"`{p.stem}`" not in guide)
    assert not missing, f"add to docs/guides/trap-suite.md: {missing}"


@pytest.mark.parametrize(("name", "dataset", "verdicts", "required"), TRAPS, ids=[t[0] for t in TRAPS])
def test_trap_verdict(name: str, dataset: str, verdicts: set[str], required: dict[str, str], request: pytest.FixtureRequest) -> None:
    df = request.getfixturevalue(dataset)
    model = model_from_costs(commission_bps=1.0, slippage_bps=1.0, n_bars=len(df)) if dataset == "planted" else None
    report = verify_strategy(df, strategy=STRATEGY_DIR / f"{name}.py", model=model)
    statuses = _statuses(report)
    assert report["verdict"] in verdicts, report["reasons"]
    for check_id, status in required.items():
        assert statuses[check_id] == status, (check_id, report["reasons"])
    if name in HONEST:
        # Honest code must never be accused of look-ahead (false positives kill trust).
        assert all(statuses[c] != "fail" for c in LOOKAHEAD_IDS), report["reasons"]


def test_data_snooping_is_priced_by_n_trials(random_walk) -> None:
    """Best of 200 random strategies passes only if the agent hides n_trials."""
    df = random_walk
    model = model_from_costs(commission_bps=0.5, slippage_bps=0.5, n_bars=len(df))
    rng = np.random.default_rng(0)
    best_ret, best_sig = -np.inf, None
    for _ in range(200):
        sig = np.repeat(rng.integers(0, 2, size=len(df) // 20 + 1), 20)[: len(df)]
        ret = run_bar_backtest(df.open.values, df.high.values, df.low.values, df.close.values, sig, model=model)["total_return"]
        if ret > best_ret:
            best_ret, best_sig = ret, sig
    assert best_ret > 0.0
    hidden = verify_strategy(df, signals=best_sig, model=model)
    honest = verify_strategy(df, signals=best_sig, model=model, n_trials=200)
    assert _statuses(hidden)["deflated_sharpe"] != "fail"
    assert _statuses(honest)["deflated_sharpe"] == "fail"
    assert honest["verdict"] in {"NEEDS_MORE_EVIDENCE", "REJECT"}


def test_grid_on_random_walk_fails_walk_forward(random_walk) -> None:
    grid = {"fast": [5, 10, 20, 40], "slow": [50, 80, 120, 200]}
    report = verify_grid(random_walk, grid, strategy=STRATEGY_DIR / "sma_params.py")
    statuses = _statuses(report)
    assert report["reproducibility"]["n_trials"] == 16
    assert statuses["walk_forward_oos"] == "fail"
    assert report["verdict"] == "REJECT"
    assert all(statuses[c] != "fail" for c in LOOKAHEAD_IDS)


def test_grid_on_planted_edge_passes(planted) -> None:
    model = model_from_costs(commission_bps=1.0, slippage_bps=1.0, n_bars=len(planted))
    report = verify_grid(planted, {"lookback": [1, 2, 3, 5, 8]}, strategy=STRATEGY_DIR / "momentum_params.py", model=model)
    assert report["grid"]["best_params"] == {"lookback": 1}
    assert _statuses(report)["walk_forward_oos"] == "pass"
    assert report["verdict"] in {"PASS", "PASS_WITH_WARNINGS"}
