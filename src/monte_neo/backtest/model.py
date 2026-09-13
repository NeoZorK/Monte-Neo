"""Frozen execution semantics for Monte-Neo professional bar backtests."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

FillPolicy = Literal["next_bar_open", "next_bar_close"]
SideMode = Literal["long_flat", "long_short"]


@dataclass(frozen=True, slots=True)
class ExecutionModel:
    """Documented, frozen execution model for fair comparisons.

    Signal observed on bar ``t`` fills on bar ``t+1`` (no same-bar fill).
    Commission is charged on each fill notional; slippage moves the fill price
    adversely by ``slippage_bps``. Optional ``sl_pct`` / ``tp_pct`` exit on H/L
    after entry (percent of entry price; 0 disables).
    """

    fill_policy: FillPolicy = "next_bar_open"
    side_mode: SideMode = "long_flat"
    size_fraction: float = 1.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    initial_cash: float = 100_000.0
    warmup_bars: int = 60
    sl_pct: float = 0.0
    tp_pct: float = 0.0

    def __post_init__(self) -> None:
        if self.size_fraction <= 0.0 or self.size_fraction > 1.0:
            raise ValueError("size_fraction must be in (0, 1]")
        if self.commission_bps < 0.0 or self.slippage_bps < 0.0:
            raise ValueError("bps costs must be non-negative")
        if self.initial_cash <= 0.0:
            raise ValueError("initial_cash must be positive")
        if self.warmup_bars < 0:
            raise ValueError("warmup_bars must be non-negative")
        if self.sl_pct < 0.0 or self.tp_pct < 0.0:
            raise ValueError("sl_pct/tp_pct must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def work_checklist(self) -> dict[str, bool]:
        """Explicit work-per-bar checklist for peer honesty."""
        return {
            "next_bar_fill": True,
            "fees": self.commission_bps > 0.0,
            "slippage": self.slippage_bps > 0.0,
            "cash_position_equity": True,
            "no_lookahead": True,
            "sl_tp": self.sl_pct > 0.0 or self.tp_pct > 0.0,
            "trade_journal": True,
            "summary_metrics": True,
        }
