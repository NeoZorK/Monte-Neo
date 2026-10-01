"""Strategy verifier: look-ahead probes, cost stress and selection-aware statistics.

Entry point: :func:`verify_strategy` → ``strategy-verdict/1`` report.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

# Public names load on first access, so importing one submodule (for example in a
# strategy worker process) does not pull in the backtest engine and numba.
_LAZY = {
    "arrival_lookahead": "monte_neo.verify.arrival",
    "bars_from_quotes": "monte_neo.verify.quotes",
    "latency_monte_carlo": "monte_neo.verify.arrival",
    "latency_scan": "monte_neo.verify.arrival",
    "load_quotes": "monte_neo.verify.quotes",
    "quote_quality": "monte_neo.verify.quotes",
    "verify_quotes": "monte_neo.verify.quotes_verdict",
    "Certificate": "monte_neo.verify.notebook",
    "badge_payload": "monte_neo.verify.badge",
    "from_backtesting_py": "monte_neo.verify.adapters",
    "from_backtrader": "monte_neo.verify.adapters",
    "from_bt": "monte_neo.verify.adapters",
    "from_nautilus": "monte_neo.verify.adapters",
    "from_fills": "monte_neo.verify.adapters",
    "from_freqtrade": "monte_neo.verify.adapters",
    "from_lean": "monte_neo.verify.adapters",
    "from_vectorbt": "monte_neo.verify.adapters",
    "from_zipline": "monte_neo.verify.adapters",
    "show": "monte_neo.verify.notebook",
    "POSITION_MODES": "monte_neo.verify.ingest",
    "RECHECK_SCHEMA_ID": "monte_neo.verify.recheck",
    "SIGNATURE_CHECK_SCHEMA_ID": "monte_neo.verify.signing",
    "VERDICTS": "monte_neo.verify.schema",
    "VERDICT_JSON_SCHEMA": "monte_neo.verify.schema",
    "VERDICT_SCHEMA_ID": "monte_neo.verify.schema",
    "aggregate_verdict": "monte_neo.verify.schema",
    "bar_returns": "monte_neo.verify.stats",
    "breakeven_cost_bps": "monte_neo.verify.costs",
    "call_signal_fn": "monte_neo.verify.ingest",
    "check_signature": "monte_neo.verify.signing",
    "deflated_sharpe": "monte_neo.verify.stats",
    "delay_scan": "monte_neo.verify.costs",
    "delay_signals": "monte_neo.verify.costs",
    "expand_grid": "monte_neo.verify.grid",
    "expected_max_sharpe": "monte_neo.verify.stats",
    "generate_keypair": "monte_neo.verify.signing",
    "implausible_accuracy": "monte_neo.verify.lookahead",
    "infer_periods_per_year": "monte_neo.verify.stats",
    "lint_source": "monte_neo.verify.lint",
    "load_certificate": "monte_neo.verify.recheck",
    "load_ohlcv": "monte_neo.verify.ingest",
    "load_signal_fn": "monte_neo.verify.ingest",
    "load_signal_values": "monte_neo.verify.ingest",
    "load_signals": "monte_neo.verify.ingest",
    "mirror_future": "monte_neo.verify.lookahead",
    "model_from_costs": "monte_neo.verify.verdict",
    "normalize_signals": "monte_neo.verify.ingest",
    "probabilistic_sharpe": "monte_neo.verify.stats",
    "probe_determinism": "monte_neo.verify.lookahead",
    "probe_perturbation": "monte_neo.verify.lookahead",
    "probe_truncation": "monte_neo.verify.lookahead",
    "recheck_certificate": "monte_neo.verify.recheck",
    "resolve_positions": "monte_neo.verify.ingest",
    "sharpe_per_bar": "monte_neo.verify.stats",
    "sign_certificate": "monte_neo.verify.signing",
    "signal_values": "monte_neo.verify.ingest",
    "simulate": "monte_neo.verify.engine",
    "to_jsonable": "monte_neo.verify.schema",
    "to_positions": "monte_neo.verify.ingest",
    "verify_grid": "monte_neo.verify.grid",
    "verify_strategy": "monte_neo.verify.verdict",
    "walk_forward": "monte_neo.verify.grid",
}

__all__ = [
    "arrival_lookahead",
    "bars_from_quotes",
    "latency_monte_carlo",
    "latency_scan",
    "load_quotes",
    "quote_quality",
    "verify_quotes",
    "POSITION_MODES",
    "RECHECK_SCHEMA_ID",
    "SIGNATURE_CHECK_SCHEMA_ID",
    "VERDICTS",
    "VERDICT_JSON_SCHEMA",
    "VERDICT_SCHEMA_ID",
    "Certificate",
    "aggregate_verdict",
    "badge_payload",
    "bar_returns",
    "breakeven_cost_bps",
    "call_signal_fn",
    "check_signature",
    "deflated_sharpe",
    "delay_scan",
    "delay_signals",
    "expand_grid",
    "expected_max_sharpe",
    "from_backtesting_py",
    "from_backtrader",
    "from_bt",
    "from_fills",
    "from_freqtrade",
    "from_lean",
    "from_nautilus",
    "from_vectorbt",
    "from_zipline",
    "generate_keypair",
    "implausible_accuracy",
    "infer_periods_per_year",
    "lint_source",
    "load_certificate",
    "load_ohlcv",
    "load_signal_fn",
    "load_signal_values",
    "load_signals",
    "mirror_future",
    "model_from_costs",
    "normalize_signals",
    "probabilistic_sharpe",
    "probe_determinism",
    "probe_perturbation",
    "probe_truncation",
    "recheck_certificate",
    "resolve_positions",
    "sharpe_per_bar",
    "show",
    "sign_certificate",
    "signal_values",
    "simulate",
    "to_jsonable",
    "to_positions",
    "verify_grid",
    "verify_strategy",
    "walk_forward",
]


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module 'monte_neo.verify' has no attribute {name!r}")
    value = getattr(import_module(module), name)
    globals()[name] = value  # later lookups skip __getattr__
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
