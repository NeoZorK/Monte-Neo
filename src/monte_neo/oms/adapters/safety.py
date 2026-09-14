"""Live-trading safety gates (env-only; never default on)."""

from __future__ import annotations

import os


def live_trading_enabled() -> bool:
    """Return True only when explicitly enabled via environment."""
    return os.getenv("MONTE_NEO_LIVE_TRADING", "").strip() == "1"


def require_live_allowed(*, venue: str) -> None:
    if not live_trading_enabled():
        raise RuntimeError(
            f"{venue} live mode blocked: set MONTE_NEO_LIVE_TRADING=1 "
            "and provide credentials via env (never commit secrets)."
        )


def dry_run_enabled() -> bool:
    """Live adapters default to dry-run unless MONTE_NEO_LIVE_DRY_RUN=0."""
    return os.getenv("MONTE_NEO_LIVE_DRY_RUN", "1").strip() != "0"
