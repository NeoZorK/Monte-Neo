"""Strategy verifier: look-ahead probes, cost stress and selection-aware statistics.

Entry point: :func:`verify_strategy` → ``strategy-verdict/1`` report.
"""

from __future__ import annotations

from monte_neo.verify.costs import breakeven_cost_bps, delay_scan, delay_signals
from monte_neo.verify.grid import expand_grid, verify_grid, walk_forward
from monte_neo.verify.ingest import (
    call_signal_fn,
    load_ohlcv,
    load_signal_fn,
    load_signals,
    normalize_signals,
)
from monte_neo.verify.lint import lint_source
from monte_neo.verify.lookahead import (
    implausible_accuracy,
    mirror_future,
    probe_determinism,
    probe_perturbation,
    probe_truncation,
)
from monte_neo.verify.recheck import RECHECK_SCHEMA_ID, load_certificate, recheck_certificate
from monte_neo.verify.schema import (
    VERDICT_JSON_SCHEMA,
    VERDICT_SCHEMA_ID,
    VERDICTS,
    aggregate_verdict,
    to_jsonable,
)
from monte_neo.verify.signing import (
    SIGNATURE_CHECK_SCHEMA_ID,
    check_signature,
    generate_keypair,
    sign_certificate,
)
from monte_neo.verify.stats import (
    bar_returns,
    deflated_sharpe,
    expected_max_sharpe,
    infer_periods_per_year,
    probabilistic_sharpe,
    sharpe_per_bar,
)
from monte_neo.verify.verdict import model_from_costs, verify_strategy

__all__ = [
    "RECHECK_SCHEMA_ID",
    "SIGNATURE_CHECK_SCHEMA_ID",
    "VERDICTS",
    "VERDICT_JSON_SCHEMA",
    "VERDICT_SCHEMA_ID",
    "aggregate_verdict",
    "bar_returns",
    "breakeven_cost_bps",
    "call_signal_fn",
    "check_signature",
    "deflated_sharpe",
    "delay_scan",
    "delay_signals",
    "expand_grid",
    "expected_max_sharpe",
    "generate_keypair",
    "implausible_accuracy",
    "infer_periods_per_year",
    "lint_source",
    "load_certificate",
    "load_ohlcv",
    "load_signal_fn",
    "load_signals",
    "mirror_future",
    "model_from_costs",
    "normalize_signals",
    "probabilistic_sharpe",
    "probe_determinism",
    "probe_perturbation",
    "probe_truncation",
    "recheck_certificate",
    "sharpe_per_bar",
    "sign_certificate",
    "to_jsonable",
    "verify_grid",
    "verify_strategy",
    "walk_forward",
]
