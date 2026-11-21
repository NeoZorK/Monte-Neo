"""``verify_strategy`` — the one-call verifier behind CLI, MCP and CI."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo._version import __version__
from monte_neo.backtest.bar_engine import run_bar_backtest
from monte_neo.backtest.jit import warn_if_slow
from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify import checks as rows
from monte_neo.verify.alpha_beta import alpha_after_beta_row
from monte_neo.verify.basket_checks import alpha_two_betas_row, selection_timing_row
from monte_neo.verify.breakdown import buy_and_hold, periods, regime_masks, regimes, series
from monte_neo.verify.claim import claim_row, parse_claim
from monte_neo.verify.confidence import (
    bootstrap_ci,
    confidence_row,
    serial_correlation_row,
    track_record,
    track_record_row,
)
from monte_neo.verify.cost_profiles import cost_sensitivity_row, realism_row
from monte_neo.verify.costs import breakeven_cost_bps, delay_scan
from monte_neo.verify.dynamic_mc import (
    regime_mix_bootstrap,
    regime_mix_row,
    regime_swap_null,
    regime_swap_row,
    run_reversed,
    time_reversal_row,
)
from monte_neo.verify.engine import is_weights, simulate
from monte_neo.verify.executor import ProcessRunner, resolve_jobs, split_spec
from monte_neo.verify.ingest import (
    POSITION_MODES,
    SignalFn,
    load_ohlcv,
    load_signal_fn,
    resolve_positions,
    to_positions,
)
from monte_neo.verify.io_guard import IOWatch
from monte_neo.verify.limits import read_source
from monte_neo.verify.lint import lint_source
from monte_neo.verify.market import SingleMarket, UniverseMarket, market_for
from monte_neo.verify.microstructure import capacity, capacity_row, spread_estimate, spread_row
from monte_neo.verify.notebook import Certificate
from monte_neo.verify.quality import data_quality, quality_row, spike_profit_share
from monte_neo.verify.rebalance_phase import rebalance_phase_row
from monte_neo.verify.regime_checks import regime_stability_row
from monte_neo.verify.repaint import MODES as REPAINT_MODES
from monte_neo.verify.repaint import TIMINGS as SIGNAL_TIMINGS
from monte_neo.verify.repaint import repaint_rows
from monte_neo.verify.report_data import MAX_TRADES_FOR_STATS, build_charts, trade_stats
from monte_neo.verify.schema import DISCLAIMER, VERDICT_SCHEMA_ID, aggregate_verdict, to_jsonable
from monte_neo.verify.stability import rolling_stability, stability_row
from monte_neo.verify.stats import (
    bar_returns,
    deflated_sharpe,
    infer_periods_per_year,
    lo_adjusted_sharpe,
    sharpe_per_bar,
)
from monte_neo.verify.symbol_costs import apply_symbol_costs
from monte_neo.verify.timing import timing_significance


def _sha256(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()


def certificate_id(repro: dict[str, Any], verdict: str) -> str:
    """The certificate id: a hash of everything that makes the test (inputs, model, settings, policy) and its verdict."""
    return _sha256(json.dumps({"r": repro, "v": verdict}, sort_keys=True, default=str).encode())[:16]


def _holdout(rets: np.ndarray, fraction: float) -> dict[str, Any]:
    cut = int(round(rets.size * (1.0 - float(fraction))))
    train, hold = rets[:cut], rets[cut:]
    return {
        "holdout_fraction": float(fraction),
        "train_bars": int(train.size),
        "holdout_bars": int(hold.size),
        "train_sharpe": sharpe_per_bar(train),
        "holdout_sharpe": sharpe_per_bar(hold),
    }


def _default_model(n_bars: int) -> ExecutionModel:
    # Signals are +1 / 0 / -1 everywhere (CLI, MCP, docs): shorts must trade by default.
    return ExecutionModel(side_mode="long_short", warmup_bars=max(0, min(60, n_bars // 10)))


def _resolve_strategy(
    strategy: str | Path | None, signal_fn: SignalFn | None, source: str | None
) -> tuple[SignalFn | None, str | None]:
    if strategy is not None:
        fn, text = load_signal_fn(strategy)
        return fn, source if source is not None else text
    return signal_fn, source


def verify_strategy(
    ohlcv: pd.DataFrame | str | Path,
    *,
    signals: Any = None,
    strategy: str | Path | None = None,
    signal_fn: SignalFn | None = None,
    source: str | None = None,
    model: ExecutionModel | None = None,
    n_trials: int | None = None,
    trial_sharpes: Any = None,
    periods_per_year: float | None = None,
    holdout_fraction: float = 0.3,
    min_trades: int = 30,
    probe_checks: int = 24,
    positions: str = "auto",
    extra_checks: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
    io_watch: IOWatch | None = None,
    jobs: int | str | None = 1,
    timeout: float | None = None,
    isolate: bool = False,
    claim: dict[str, Any] | str | Path | None = None,
    symbol_costs: dict[str, Any] | str | Path | None = None,
    ledger: str | Path | bool | None = None,
    registration: str | None = None,
    repaint: str = "auto",
    signal_timing: str = "close",
    policy: str | Path | dict[str, Any] | None = None,
    model_cutoff: str | None = None,
    events: Any = None,
    events_delay: float = 0.0,
    events_sha256: str | None = None,
    cost_profile: str | tuple[float, float] | None = None,
    maker_share: float = 0.0,
    allow_rebate: bool = False,
    adverse_selection_bps: float = 0.0,
    quotes_half_spread_bps: float | None = None,
    delisted: Any = None,
    delist_return: float = -0.30,
    reference_symbol: str | None = None,
    rebalance_every: int | None = None,
    corporate_actions: Any = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Verify one strategy and return a ``strategy-verdict/1`` report.

    Provide either ``signals`` (positions per bar) or strategy code via
    ``strategy`` (``file.py[:func]``) / ``signal_fn``. Code enables the
    look-ahead probes; ``source`` (or the strategy file) enables static lint.
    ``n_trials`` is how many variants were tried before picking this one.
    ``positions`` reads the signal as ``sign`` (+1 / 0 / -1), ``weight`` (fraction of
    equity in [-1, 1]) or ``auto`` (weights when all values are in [-1, 1] and some
    are fractional).
    ``extra_checks`` / ``extra`` let wrappers (e.g. grid search) add check
    rows and report sections that take part in the verdict and certificate.
    ``io_watch`` lets a wrapper pass the watch that already covered the strategy
    import (grid search), so data read at import still counts.
    ``jobs`` (a number or ``"auto"``), ``timeout`` (seconds per ``signal()`` call) and
    ``isolate`` (no network, subprocesses or file writes) run a strategy file in worker
    processes; see :mod:`monte_neo.verify.executor`.
    ``claim`` (a dict, JSON text or a JSON file: ``sharpe``, ``total_return``, ``max_drawdown``,
    ``n_trades``, ``win_rate``, ``profit_factor``) is compared with the verified numbers; an
    overclaim fails the ``claim_consistency`` check.
    ``ledger`` (``True`` for ``.monte-neo/ledger.jsonl``, or a path) counts the variants tried on this data in an
    append-only, hash-chained file; the larger of that count and ``n_trials`` is used for the Deflated Sharpe.
    ``registration`` is the id of a pre-registered hypothesis (``monte-neo register``): the certificate says whether the
    verified code is the registered one and, with ``ledger``, whether the registration came before its first run.
    ``repaint`` (``off``, ``auto`` or ``strict``) sets how densely the signal is checked for changing after it was shown
    (history) and while the bar forms; ``signal_timing="open"`` declares the signal known at the bar's open, so a signal
    that needs the bar's own prices fails. See :mod:`monte_neo.verify.repaint`.
    ``symbol_costs`` (a dict, JSON text or a JSON file: ``{"AAA": {"commission_bps": 2, "slippage_bps": 1},
    "default": {...}}``) gives a universe different costs per symbol; see :mod:`monte_neo.verify.symbol_costs`.
    ``policy`` (a TOML file, TOML text or dict) applies an institution's thresholds: its inputs before the run, its
    rules to the result (check row ``policy``); the policy goes into the certificate. See :mod:`monte_neo.verify.policy`.
    ``model_cutoff`` (``YYYY-MM`` or ``YYYY-MM-DD``) is the training-data cutoff of a language or foundation model the
    strategy uses: the edge must survive that date (check row ``model_cutoff``). See :mod:`monte_neo.verify.cutoff`.
    ``events`` (a table or file with ``published_at``, optional ``event_time`` and ``symbol``, and value columns) is joined
    to the OHLCV by publication time plus ``events_delay`` seconds, as ``ev_<column>`` columns the strategy reads; with
    ``event_time`` the strategy also runs on the leaky join (row ``pit_events``). ``events_sha256`` is set by a recheck
    to make sure the same events are used. See :mod:`monte_neo.verify.events_run`.
    ``cost_profile`` (a name from :data:`monte_neo.verify.cost_profiles.FEE_PROFILES` or a ``(maker, taker)`` pair in bps)
    replaces the model's commission with the exchange fee, ``maker_share`` is the fraction of fills that are maker orders; ``allow_rebate=True`` accepts a negative maker fee in a
    ``(maker, taker)`` pair inside the realism envelope of :func:`monte_neo.verify.execution_calib.rebate_fee_bps`.
    ``quotes_half_spread_bps`` is the median half-spread of real quotes (see ``quotes_half_spread_bps`` in
    :mod:`monte_neo.verify.cost_profiles`); it makes the ``cost_realism`` gate a failure instead of a warning.
    ``delisted`` (symbols, ``(symbol, assumed total return)`` pairs, or a table ``symbol[, delist_return]``; ``[]`` declares
    none) lists names that belonged to a universe but are missing from the data; ``delist_return`` is the default assumed
    return of a missing name. Without it a universe whose symbols all survive is capped at ARL 4
    (see :mod:`monte_neo.verify.survivorship`). ``reference_symbol`` (a symbol of the universe, for example BTC) adds
    ``alpha_after_reference``; ``rebalance_every`` sets the cadence for ``rebalance_timing_luck`` (default: detected). ``corporate_actions`` is a table
    of declared splits and dividends (columns ``bar`` or ``date``, ``kind``, ``value``; one instrument) checked against the
    prices, see :mod:`monte_neo.verify.corporate_actions`.
    ``profile`` (an id from :mod:`monte_neo.profiles`, for example ``trend_cta``) adds a ``profile`` block to the certificate:
    which checks the strategy type requires, which ran, what is not assessed. It never changes the verdict.
    """
    if profile is not None:
        from monte_neo.profiles import get_profile

        get_profile(profile)  # fail early on an unknown id
    if policy is not None:
        from monte_neo.verify.policy import apply_policy, load_policy, run_inputs

        rules = load_policy(policy)
        fixed = run_inputs(rules)
        min_trades = int(fixed.get("min_trades", min_trades))
        frame = load_ohlcv(ohlcv)
        if "cost_multiplier" in fixed:
            base = model or _default_model(market_for(frame).n_bars)
            k = float(fixed["cost_multiplier"])
            model = replace(base, commission_bps=base.commission_bps * k, slippage_bps=base.slippage_bps * k)
        report = verify_strategy(
            frame, signals=signals, strategy=strategy, signal_fn=signal_fn, source=source, model=model,
            n_trials=n_trials, trial_sharpes=trial_sharpes, periods_per_year=periods_per_year,
            holdout_fraction=holdout_fraction, min_trades=min_trades, probe_checks=probe_checks, positions=positions,
            extra_checks=extra_checks, extra=extra, io_watch=io_watch, jobs=jobs, timeout=timeout, isolate=isolate,
            claim=claim, symbol_costs=symbol_costs, ledger=ledger, registration=registration, repaint=repaint,
            signal_timing=signal_timing, model_cutoff=model_cutoff, events=events, events_delay=events_delay,
            events_sha256=events_sha256, cost_profile=cost_profile, maker_share=maker_share,
            allow_rebate=allow_rebate, adverse_selection_bps=adverse_selection_bps,
            quotes_half_spread_bps=quotes_half_spread_bps, delisted=delisted, delist_return=delist_return,
            reference_symbol=reference_symbol, rebalance_every=rebalance_every,
            corporate_actions=corporate_actions, profile=profile,
        )
        return apply_policy(report, rules)
    if n_trials is not None and int(n_trials) < 1:
        raise ValueError(f"n_trials must be >= 1 (the chosen variant counts), got {n_trials}")
    if int(min_trades) < 1:
        raise ValueError(f"min_trades must be >= 1, got {min_trades}")
    if not 0.0 < float(holdout_fraction) < 1.0:
        raise ValueError(f"holdout_fraction must be between 0 and 1, got {holdout_fraction}")
    if positions not in POSITION_MODES:
        raise ValueError(f"positions must be one of {POSITION_MODES}, got {positions!r}")
    if repaint not in REPAINT_MODES:
        raise ValueError(f"repaint must be one of {REPAINT_MODES}, got {repaint!r}")
    if signal_timing not in SIGNAL_TIMINGS:
        raise ValueError(f"signal_timing must be one of {SIGNAL_TIMINGS}, got {signal_timing!r}")
    df = load_ohlcv(ohlcv)
    joined_events = None
    if events is not None:
        from monte_neo.verify.events_run import prepare_events

        df, leaky_df, event_table, event_hash = prepare_events(df, events, float(events_delay))
        if events_sha256 is not None and events_sha256 != event_hash:
            raise ValueError("the events differ from the ones the certificate was issued for")
        joined_events = (leaky_df, event_table, event_hash)
    elif events_sha256 is not None:
        raise ValueError("this certificate was issued with events: pass the same events file")
    market = market_for(df)
    n = market.n_bars
    if cost_profile is not None:
        from monte_neo.verify.cost_profiles import with_profile

        model = with_profile(model or _default_model(n), cost_profile, maker_share, allow_rebate=allow_rebate, adverse_selection_bps=adverse_selection_bps)  # written into the certificate's model
    if symbol_costs is not None:
        model = apply_symbol_costs(market, model or _default_model(n), symbol_costs)  # written into the certificate's model
    # Every knob that can change the verdict goes into the certificate, so a recheck
    # reruns the same test and a reader sees e.g. a lowered min_trades.
    settings = {
        "min_trades": int(min_trades),
        "holdout_fraction": float(holdout_fraction),
        "probe_checks": int(probe_checks),
        "periods_per_year": float(periods_per_year) if periods_per_year else None,
        "positions": positions,
        "repaint": repaint,
        "signal_timing": signal_timing,
    }
    if cost_profile is not None:  # only when set: older certificate ids stay the same
        settings["cost_profile"] = cost_profile if isinstance(cost_profile, str) else [float(x) for x in cost_profile]
        settings["maker_share"] = float(maker_share)
        if allow_rebate:  # only when set: older certificate ids stay the same
            settings["allow_rebate"] = True
            settings["adverse_selection_bps"] = float(adverse_selection_bps)
    if delisted is not None:
        from monte_neo.verify.survivorship import parse_delisted

        settings["delisted"] = [list(x) for x in parse_delisted(delisted, float(delist_return))]  # pairs: a recheck passes them back
    if profile is not None:
        settings["profile"] = str(profile)  # only when set: older certificate ids stay the same
    if reference_symbol is not None:
        settings["reference_symbol"] = str(reference_symbol)
    if rebalance_every is not None:
        settings["rebalance_every"] = int(rebalance_every)
    if corporate_actions is not None and market.kind == "single":
        from monte_neo.verify.corporate_actions import parse_actions

        settings["corporate_actions"] = [[b, k, v] for b, k, v in parse_actions(corporate_actions, n, market.timestamps)]  # bars: a recheck passes them back
    if quotes_half_spread_bps is not None:
        settings["quotes_half_spread_bps"] = float(quotes_half_spread_bps)
    if model_cutoff is not None:
        from monte_neo.verify.cutoff import parse_cutoff

        parse_cutoff(model_cutoff)  # fail early on a bad date
        settings["model_cutoff"] = str(model_cutoff)  # only when set: older certificate ids stay the same
    if joined_events is not None:
        settings["events_sha256"] = joined_events[2]  # only when set: older certificate ids stay the same
        settings["events_delay"] = float(events_delay)
    if claim is not None:
        settings["claim"] = parse_claim(claim)  # part of the certificate: a recheck compares the same claim
    if io_watch is None:
        io_watch = IOWatch(tuple(p for p in (df.attrs.get("source_path"),) if p))
    runner = _runner_for(strategy, market, df, jobs, timeout, isolate)
    if runner is not None:
        # Workers load the strategy; this process only reads its source for the lint.
        fn, src = runner, source if source is not None else read_source(runner.path)
    else:
        if (timeout is not None or isolate or resolve_jobs(jobs) > 1) and not isinstance(signal_fn, ProcessRunner):
            raise ValueError("jobs, timeout and isolate run the strategy in a worker, so they need strategy code in a file: pass --strategy file.py (with --signals the positions are already computed: drop --jobs/--timeout/--isolate)")
        with io_watch:
            fn, src = _resolve_strategy(strategy, signal_fn, source)
    from monte_neo.verify.model_protocol import ModelSignal

    local_fn = fn if runner is None else _local_strategy(strategy, src, isolate, joined_events is not None)
    if joined_events is not None:
        from monte_neo.verify.events_run import events_rows

        extra_checks = [*(extra_checks or []), *events_rows(df, joined_events[0], joined_events[1], local_fn, model or _default_model(n), positions)]
    if isinstance(local_fn, ModelSignal):
        from monte_neo.verify.model_rows import model_rows

        extra_checks = [*(extra_checks or []), *model_rows(df, local_fn, model or _default_model(n), positions, n_trials)]
        if local_fn.n_configs > int(n_trials or 1):
            n_trials = local_fn.n_configs  # every configuration tried counts into the Deflated Sharpe
    book = None
    if ledger:
        from monte_neo.verify.ledger import Ledger, ledger_row, variant_id

        book = Ledger(None if ledger is True else ledger)
        data_id = _sha256(market.data_bytes())[:16]
        variant = variant_id(src, _signals_array(signals))
        chain = book.check()
        counted = book.count_with(variant, data_id)
        declared = n_trials
        n_trials = max(int(n_trials or 1), counted)
        row = ledger_row(counted, declared, chain, book.path)
        if row["status"] != "pass":
            row["status"] = "info"  # context only: a recheck has no ledger, so it must not move the verdict
        extra_checks = [*(extra_checks or []), row]
    if registration:
        from monte_neo.verify.ledger import variant_id as _variant_id
        from monte_neo.verify.register import Registry, registration_row

        settings["registration"] = str(registration)
        mine = _variant_id(src, _signals_array(signals))
        first_at = None
        if book is not None:
            data_here = _sha256(market.data_bytes())[:16]
            first_at = next((e["at"] for e in book.entries() if e.get("variant") == mine and e.get("data") == data_here), None)
        reg_row = registration_row(str(registration), Registry(), mine, first_at, ledger_used=book is not None)
        extra_checks = [*(extra_checks or []), reg_row]
    try:
        report = _checks_and_report(
            df, market, fn, src, signals, settings, io_watch, model, n_trials, trial_sharpes,
            periods_per_year, holdout_fraction, min_trades, probe_checks, positions, extra_checks, extra,
        )
        if book is not None:
            entry = book.record(
                variant=variant, data_id=data_id, sharpe=float(report["metrics"].get("sharpe_annualized") or float("nan")),
                verdict=report["verdict"], certificate_id=report["certificate_id"],
            )
            report["ledger"] = {"path": str(book.path), "variants_counted": counted, "n_trials_used": n_trials, "entry": entry["seq"], "chain_ok": chain["ok"]}
        return report
    finally:
        if runner is not None:
            runner.close()


def _sample_rows(market: Any, stat_rows: list[dict[str, Any]], rets: np.ndarray, sig: np.ndarray, warmup: int, n_closed: int, min_trades: int) -> list[dict[str, Any]]:
    """A market that earns by accrual (carry) replaces the closed-trade count with its own sample rule."""
    if not getattr(market, "carry", False):
        return stat_rows
    from monte_neo.verify.carry_market import sample_row

    held = market.held(sig, warmup, rets.size)
    return [sample_row(rets, held, n_closed, min_trades) if r["id"] == "sample_size" else r for r in stat_rows]


def _beta_reference(market: Any, bench: dict[str, Any], warmup: int) -> np.ndarray:
    """The returns the strategy's beta is measured against: the underlying for carry, the passive benchmark otherwise."""
    if getattr(market, "carry", False):
        return np.asarray(market.reference_returns(warmup), dtype=np.float64)
    return bar_returns(bench["equity"], start=warmup)


def _attribution_rows(rets: np.ndarray, reference: np.ndarray, ppy: float, extra: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Rows ``residual_alpha`` and ``hidden_short_volatility`` of one strategy against what it trades (ARL level 5).

    Skipped when a specialised path (carry, a basket) already gives them in ``extra``.
    """
    have = {c.get("id") for c in (extra or [])}
    if {"residual_alpha", "hidden_short_volatility"} <= have:
        return []
    from monte_neo.alpha.attribution import check_residual_alpha
    from monte_neo.alpha.attribution_tail import check_hidden_short_vol

    n = min(rets.size, reference.size)
    r, ref = np.asarray(rets[-n:], dtype=np.float64), np.asarray(reference[-n:], dtype=np.float64)
    ok = np.isfinite(r) & np.isfinite(ref)
    f = pd.DataFrame({"market": ref[ok]})
    out = [check_residual_alpha(r[ok], f, ppy), check_hidden_short_vol(r[ok], f)]
    for row in out:  # like alpha_after_beta: it blocks ARL level 5, it does not turn a beta strategy into a failed backtest
        if row["status"] == "fail":
            row["status"] = "warn"
    return [row for row in out if row["id"] not in have]


def _local_strategy(strategy: Any, src: str | None, isolate: bool, has_events: bool) -> Any:
    """The strategy in this process, only when a check needs it here (events, fit/predict) and isolation allows it."""
    looks_like_model = bool(src) and "def fit(" in src and "def predict(" in src and "def signal(" not in src
    if isolate or strategy is None or not (has_events or looks_like_model):
        return None
    try:
        return load_signal_fn(strategy)[0]
    except Exception:  # it may import only in a worker; the check that needs it is skipped
        return None


def _signals_array(signals: Any) -> np.ndarray | None:
    """Positions given as an array or a file, for the ledger's variant id (``None`` when they cannot be read cheaply)."""
    if signals is None:
        return None
    if isinstance(signals, str | Path):
        try:
            return np.frombuffer(Path(signals).read_bytes(), dtype=np.uint8)
        except OSError:
            return None
    try:
        return np.asarray(signals)
    except (TypeError, ValueError):
        return None


def _runner_for(
    strategy: str | Path | None, market: Any, df: pd.DataFrame, jobs: int | str | None, timeout: float | None, isolate: bool
) -> ProcessRunner | None:
    """Worker processes for a strategy file when parallel, time-limited or isolated runs are asked for."""
    n_jobs = resolve_jobs(jobs)
    if strategy is None or (n_jobs == 1 and timeout is None and not isolate):
        return None
    path, func = split_spec(strategy)
    if not path.is_file():
        raise FileNotFoundError(f"strategy file not found: {path}")
    data_paths = tuple(p for p in (df.attrs.get("source_path"),) if p)
    return ProcessRunner(path, func, market.frame, jobs=n_jobs, timeout=timeout, isolate=isolate, data_paths=data_paths)


def _checks_and_report(
    df: pd.DataFrame,
    market: SingleMarket | UniverseMarket,
    fn: Any,
    src: str | None,
    signals: Any,
    settings: dict[str, Any],
    io_watch: IOWatch,
    model: ExecutionModel | None,
    n_trials: int | None,
    trial_sharpes: Any,
    periods_per_year: float | None,
    holdout_fraction: float,
    min_trades: int,
    probe_checks: int,
    positions: str,
    extra_checks: list[dict[str, Any]] | None,
    extra: dict[str, Any] | None,
) -> dict[str, Any]:
    n = market.n_bars
    if fn is None and signals is None:
        raise ValueError("provide signals or strategy code (strategy= / signal_fn=)")
    warn_if_slow(n)
    model = model or _default_model(n)
    if n < model.warmup_bars + 2:
        raise ValueError(f"need at least warmup_bars + 2 = {model.warmup_bars + 2} bars, got {n}")
    ohlc = market.ohlc

    integrity = market.integrity()
    if integrity["status"] == "fail":
        checks = [integrity]
        return _report(checks, {}, market, None, src, model, n_trials, settings)

    with io_watch:
        values = market.read_values(fn, signals)
        # One reading for every probe and backtest: resolved once from the full signal.
        mode = resolve_positions(values, positions)
        settings["positions"] = mode
        full = to_positions(values, mode)  # per row: what the probes compare and the hash covers
        sig, traded = market.positions(values, mode, model)
        determinism = truncation = perturbation = independence = repaint_history = repaint_live = None
        if fn is not None:
            determinism, truncation, perturbation = market.probes(fn, full, mode, probe_checks)
            independence = market.independence(fn, full, mode)
            repaint_history, repaint_live = market.repaint(fn, full, mode, settings["repaint"], settings["signal_timing"])
    lint = lint_source(src) if src else None

    run = simulate(ohlc, sig, model)
    rets = bar_returns(run["equity"], start=model.warmup_bars)
    timestamps = market.timestamps
    ppy = float(periods_per_year) if periods_per_year else infer_periods_per_year(timestamps)
    trials = np.asarray(trial_sharpes, dtype=np.float64) if trial_sharpes is not None else None
    dsr = deflated_sharpe(rets, n_trials=int(n_trials or 1), trial_sharpes=trials, periods_per_year=ppy)
    holdout = _holdout(rets, holdout_fraction)
    interval = bootstrap_ci(rets, ppy)
    windows = rolling_stability(rets, ppy)
    spread = spread_estimate(ohlc, model)
    room = capacity(ohlc, market.capacity_volume, traded, model, market.symbols)
    history = track_record(dsr, ppy)
    breakeven = breakeven_cost_bps(ohlc, sig, model)
    delay = delay_scan(ohlc, sig, model)
    timing = timing_significance(ohlc, sig, model) if run["total_return"] > 0.0 else None
    accuracy = market.accuracy(traded)
    total_return = float(run["total_return"])
    n_closed = int(run["n_closed_trades"])
    journal = _trade_journal(ohlc, sig, model, n_closed)
    journal_stats = trade_stats(journal) if journal else {}
    quality = data_quality(ohlc, timestamps, market.volume)
    profit_share = spike_profit_share(run["equity"], quality["spike_mask"], traded)
    bench = buy_and_hold(ohlc, model, market.benchmark_positions(), ppy)
    by_period = periods(run["equity"], bench["equity"], traded, timestamps, model.warmup_bars, ppy)
    by_regime = regimes(run["equity"], market.market_close(), model.warmup_bars, ppy)

    dynamic_rows = _dynamic_mc_rows(market, fn, mode, model, run, bench, total_return, ppy)
    universe_rows = _universe_rows(market, settings, bench, total_return, traded)
    basket_rows = _basket_rows(market, settings, traded, rets, bench, model, ppy)
    checks = [
        integrity,
        *universe_rows,
        quality_row(quality, profit_share, market.symbols),
        rows.probe_row("determinism", determinism, "determinism"),
        rows.probe_row("lookahead_truncation", truncation, "truncation probe"),
        rows.probe_row("lookahead_perturbation", perturbation, "future-perturbation probe"),
        rows.external_data_row(*(_outside_data(io_watch, fn) if fn is not None else (None, None))),
        *repaint_rows(repaint_history, repaint_live),
        rows.lint_row(lint),
        rows.accuracy_row(accuracy),
        rows.independence_row(independence, float(dsr["sharpe_annualized"])),
        rows.performance_row(float(dsr["sharpe_annualized"]), int(rets.size)),
        *rows.economics_rows(model, total_return, breakeven, delay),
        rows.timing_row(timing),
        *_sample_rows(market, rows.statistics_rows(dsr, n_closed, int(min_trades), trials_declared=n_trials is not None, holdout=holdout),
                      rets, sig, model.warmup_bars, n_closed, int(min_trades)),
        rows.period_row(by_period, total_return),
        stability_row(windows),
        confidence_row(interval),
        serial_correlation_row(lo_adjusted_sharpe(rets, ppy)),
        track_record_row(history),
        *([claim_row(settings["claim"], _verified(dsr, run, n_closed, journal_stats))] if "claim" in settings else []),
        rows.benchmark_row(total_return, dsr["sharpe_annualized"], bench),
        alpha_after_beta_row(rets, _beta_reference(market, bench, model.warmup_bars), ppy),
        *_attribution_rows(rets, _beta_reference(market, bench, model.warmup_bars), ppy, extra_checks),
        regime_stability_row(by_regime, total_return),
        *dynamic_rows,
        rebalance_phase_row(ohlc, sig, model, settings.get("rebalance_every")),
        *_corporate_rows(market, settings, ohlc, traded, total_return),
        *basket_rows,
        cost_sensitivity_row(ohlc, sig, model),
        realism_row(ohlc, sig, model, spread, settings.get("quotes_half_spread_bps")),
        spread_row(spread),
        *([capacity_row(room)] if market.capacity_volume is not None else []),
        *(extra_checks or []),
    ]
    if settings.get("model_cutoff"):
        from monte_neo.verify.cutoff import cutoff_row

        bench_rets = bar_returns(bench["equity"], start=model.warmup_bars)
        checks.append(cutoff_row(rets, timestamps[-rets.size:], settings["model_cutoff"], ppy, bench_rets[-rets.size:]))
    active = np.abs(traded) if traded.ndim == 1 else np.abs(traded).sum(axis=1)
    metrics = {
        "bars": n,
        "total_return": total_return,
        "max_drawdown": float(run["max_drawdown"]),
        "n_fills": int(run["n_trades"]),
        "n_closed_trades": n_closed,
        "positions": mode,
        "exposure": float(np.mean(active != 0)),
        "mean_abs_position": float(np.mean(active)),
        "sharpe_annualized": dsr["sharpe_annualized"],
        "psr": dsr["psr"],
        "deflated_sharpe": dsr["deflated_sharpe"],
        "breakeven_cost_bps": float(breakeven["breakeven_bps"]),
        "hit_rate": accuracy.get("hit_rate"),
        "timing_p_value": timing["p_value"] if timing else None,
        "sharpe_ci95": interval.get("sharpe_annualized"),
        "return_ci95": interval.get("total_return"),
        "min_track_record_bars": history["need_bars"],
        "windows_positive": windows.get("positive"),
        "estimated_spread_bps": spread.get("spread_bps"),
        "capacity_5pct": room["capital"][1] if room else None,
        "benchmark_total_return": bench["total_return"],
        "benchmark_sharpe_annualized": bench["sharpe_annualized"],
        **market.describe(traded),
    }
    sections = {
        "benchmark": {
            "description": market.benchmark_description,
            **{k: bench[k] for k in ("total_return", "max_drawdown", "sharpe_annualized")},
        },
        "breakdown": {**by_period, **by_regime},
        "series": series(run["equity"], bench["equity"], timestamps, model.warmup_bars),
        "charts": build_charts(
            run=run, ohlc=ohlc, positions=sig, model=model, timestamps=timestamps, periods_per_year=ppy,
            timing=timing, trades=journal, spread=spread,
        ),
    }
    return _report(checks, metrics, market, full, src, model, n_trials, settings, extra, sections)


def _corporate_rows(market: Any, settings: dict[str, Any], ohlc: dict[str, Any], traded: np.ndarray, total_return: float) -> list[dict[str, Any]]:
    """The ``corporate_actions`` row when declared actions were given (one instrument)."""
    if "corporate_actions" not in settings:
        return []
    from monte_neo.verify.corporate_actions import corporate_actions_row

    actions = [(int(b), str(k), float(v)) for b, k, v in settings["corporate_actions"]]
    return [corporate_actions_row(ohlc, actions, np.asarray(traded, dtype=np.float64), total_return)]


def _dynamic_mc_rows(market: Any, fn: Any, mode: str, model: ExecutionModel, run: dict[str, Any], bench: dict[str, Any], total_return: float, ppy: float) -> list[dict[str, Any]]:
    """Regime-swap null, regime-mix bootstrap and time-reversal null (single instrument, see ``dynamic_mc``)."""
    if market.kind != "single":
        why = "not assessed: the dynamic Monte Carlo covers one instrument"
        return [rows.check(i, "statistics", "skip", why) for i in ("regime_swap_null", "regime_mix_bootstrap", "time_reversal_null")]
    equity = run["equity"]
    masks, usable, _ = regime_masks(market.market_close(), model.warmup_bars)
    s_ret = np.zeros(equity.size)
    prev = np.where(equity[:-1] > 0, equity[:-1], 1.0)
    s_ret[1:] = np.where(equity[:-1] > 0, equity[1:] / prev - 1.0, 0.0)
    reversed_run = why = None
    if total_return > 0.0 and fn is not None:
        reversed_run, why = run_reversed(market.frame, fn, mode, model, total_return)
    elif fn is None:
        why = "not assessed: needs the strategy code (a signals file cannot be re-run on reversed history)"
    return [
        regime_swap_row(regime_swap_null(s_ret, masks, usable) if masks else {}, total_return),
        regime_mix_row(regime_mix_bootstrap(s_ret, masks, ppy) if masks else {}, total_return),
        time_reversal_row({"total_return": total_return}, reversed_run, why or ""),
    ]


def _universe_rows(market: Any, settings: dict[str, Any], bench: dict[str, Any], total_return: float, traded: np.ndarray) -> list[dict[str, Any]]:
    """The structural survivorship row, priced with the declared missing names when there are any."""
    rows_ = market.universe_checks()
    if not rows_:
        return []
    from monte_neo.verify.survivorship import survivorship_bias_row

    declared = settings.get("delisted")
    exposure = float(np.mean(np.clip(traded, 0.0, None).sum(axis=1))) if traded.ndim == 2 else 0.0
    return [survivorship_bias_row(
        rows_[0], delisted=None if declared is None else [(a, float(b)) for a, b in declared], n_symbols=len(market.symbols),
        bench_return=float(bench["total_return"]), total_return=total_return, exposure=exposure)]


def _basket_rows(market: Any, settings: dict[str, Any], traded: np.ndarray, rets: np.ndarray, bench: dict[str, Any],
                 model: ExecutionModel, ppy: float) -> list[dict[str, Any]]:
    """Selection-vs-timing and alpha after the basket and a reference symbol (universe markets only)."""
    ref = settings.get("reference_symbol")
    if traded.ndim != 2:
        return []
    close = market.ohlc["close"]
    step = close[1:] / close[:-1] - 1.0
    out = [selection_timing_row(traded[:-1][-rets.size:], step[-rets.size:], ppy)]
    if ref is not None:
        if ref not in market.symbols:
            raise ValueError(f"reference_symbol {ref!r} is not a symbol of the universe: {', '.join(map(str, market.symbols[:10]))}")
        col = list(market.symbols).index(ref)
        basket = bar_returns(bench["equity"], start=model.warmup_bars)
        out.append(alpha_two_betas_row(rets, basket[-rets.size:], step[-rets.size:, col], ppy, str(ref)))
    return out


def _trade_journal(ohlc: dict[str, np.ndarray], sig: np.ndarray, model: ExecutionModel, n_closed: int) -> list[dict[str, Any]] | None:
    """Closed trades for the report (sign engine only; skipped for very active strategies, where the journal is slow)."""
    if is_weights(sig) or n_closed == 0 or n_closed > MAX_TRADES_FOR_STATS:
        return None
    return list(run_bar_backtest(ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model)["trades"])


def _verified(dsr: dict[str, Any], run: dict[str, Any], n_closed: int, stats: dict[str, Any]) -> dict[str, float | None]:
    """The verified value of every metric a claim may name (win rate and profit factor need a trade journal)."""
    return {
        "sharpe": float(dsr["sharpe_annualized"]),
        "total_return": float(run["total_return"]),
        "max_drawdown": float(run["max_drawdown"]),
        "n_trades": float(n_closed),
        "win_rate": stats.get("win_rate"),
        "profit_factor": stats.get("profit_factor"),
    }


def _outside_data(io_watch: IOWatch, fn: Any) -> tuple[list[str], list[str]]:
    """Data read by the strategy here and, for a runner, in its worker processes."""
    files, conns = list(io_watch.files), list(io_watch.connections)
    if isinstance(fn, ProcessRunner):
        root = fn._owner or fn
        files += [f for f in root.files if f not in files]
        conns += [c for c in root.connections if c not in conns]
    return files, conns


def _report(
    checks: list[dict[str, Any]],
    metrics: dict[str, Any],
    market: SingleMarket | UniverseMarket,
    sig: np.ndarray | None,
    src: str | None,
    model: ExecutionModel,
    n_trials: int | None,
    settings: dict[str, Any],
    extra: dict[str, Any] | None = None,
    sections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verdict = aggregate_verdict(checks)
    data_bytes = market.data_bytes()
    repro = {
        "engine": "monte-neo",
        "engine_version": __version__,
        "data_sha256": _sha256(data_bytes),
        "signals_sha256": _sha256(np.ascontiguousarray(sig).tobytes()) if sig is not None else None,
        "source_sha256": _sha256(src.encode("utf-8")) if src else None,
        "model": model.to_dict(),
        "n_trials": int(n_trials or 1),
        "settings": settings,
    }
    if market.kind == "universe":
        repro["universe"] = {"symbols": len(market.symbols), "bars": market.n_bars}
    if extra:
        repro["extra_sha256"] = _sha256(json.dumps(to_jsonable(extra), sort_keys=True).encode())
    cert_id = certificate_id(repro, verdict)
    reasons = [f"{c['id']}: {c['summary']}" for c in checks if c["status"] == "fail"]
    reasons += [f"{c['id']}: {c['summary']}" for c in checks if c["status"] == "warn"]
    body = {
        "schema": VERDICT_SCHEMA_ID, "verdict": verdict, "certificate_id": cert_id, "reasons": reasons, "checks": checks,
        "metrics": metrics, "reproducibility": repro,
    }
    if settings.get("profile"):
        from monte_neo.profiles import profile_block

        sections = {**(sections or {}), "profile": profile_block(str(settings["profile"]), checks)}
    from monte_neo.readiness import arl_block, readiness

    ready = readiness(certificate=body)
    next_actions = rows.next_actions(checks) + [f"{a['criterion']} of ARL {a['level']}: {a['command']}" for a in ready["next_actions"] if a["state"] != "met"][:4]
    return Certificate(to_jsonable(
        {
            "schema": VERDICT_SCHEMA_ID,
            "verdict": verdict,
            "certificate_id": cert_id,
            "reasons": reasons,
            "checks": checks,
            "metrics": metrics,
            "next_actions": next_actions,
            "arl": arl_block(ready),  # derived from the checks and the rules version: not part of the certificate id
            "reproducibility": repro,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "disclaimer": DISCLAIMER,
            **(sections or {}),  # derived from the hashed inputs: not part of the certificate id
            **(extra or {}),
        }
    ))


def model_from_costs(
    *,
    commission_bps: float = 5.0,
    slippage_bps: float = 5.0,
    side_mode: str = "long_short",
    warmup_bars: int | None = None,
    n_bars: int | None = None,
    funding_bps_per_bar: float = 0.0,
    borrow_bps_per_bar: float = 0.0,
    sl_pct: float = 0.0,
    tp_pct: float = 0.0,
    trail_pct: float = 0.0,
) -> ExecutionModel:
    """Convenience ExecutionModel for CLI / MCP callers.

    ``funding_bps_per_bar`` is charged on every open position, ``borrow_bps_per_bar`` on short
    positions only (bps of the position's value per bar: 300 bps a year on hourly bars is about 0.034).
    ``sl_pct``, ``tp_pct`` and ``trail_pct`` (percent of the entry price; 0 = off) add stops inside the bar
    to every position the engine opens, for signs, weights and universes alike.
    """
    base = _default_model(int(n_bars or 600))
    return replace(
        base,
        commission_bps=float(commission_bps),
        slippage_bps=float(slippage_bps),
        side_mode=side_mode,  # type: ignore[arg-type]
        warmup_bars=int(warmup_bars) if warmup_bars is not None else base.warmup_bars,
        funding_bps_per_bar=float(funding_bps_per_bar),
        borrow_bps_per_bar=float(borrow_bps_per_bar),
        sl_pct=float(sl_pct),
        tp_pct=float(tp_pct),
        trail_pct=float(trail_pct),
    )


__all__ = ["certificate_id", "model_from_costs", "verify_strategy"]
