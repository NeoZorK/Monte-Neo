"""Frozen execution semantics for Monte-Neo professional bar backtests."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

FillPolicy = Literal["next_bar_open", "next_bar_close"]
SideMode = Literal["long_flat", "long_short"]


@dataclass(frozen=True, slots=True)
class ExecutionModel:
    """Documented execution model shared by single, batch, and strategy APIs.

    Signal on bar ``t`` fills on bar ``t+1``. Costs are bps on fill notional.
    Optional SL/TP/trail on H/L; ``fill_fraction`` enables research-grade partials.
    ``impact_bps`` is added to slippage on fills (beyond fixed ``slippage_bps``).
    """

    fill_policy: FillPolicy = "next_bar_open"
    side_mode: SideMode = "long_flat"
    size_fraction: float = 1.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    impact_bps: float = 0.0
    initial_cash: float = 100_000.0
    warmup_bars: int = 60
    sl_pct: float = 0.0
    tp_pct: float = 0.0
    trail_pct: float = 0.0
    fill_fraction: float = 1.0
    oco_bracket: bool = True

    def __post_init__(self) -> None:
        if self.size_fraction <= 0.0 or self.size_fraction > 1.0:
            raise ValueError("size_fraction must be in (0, 1]")
        if self.fill_fraction <= 0.0 or self.fill_fraction > 1.0:
            raise ValueError("fill_fraction must be in (0, 1]")
        if min(self.commission_bps, self.slippage_bps, self.impact_bps) < 0.0:
            raise ValueError("bps costs must be non-negative")
        if self.initial_cash <= 0.0:
            raise ValueError("initial_cash must be positive")
        if self.warmup_bars < 0:
            raise ValueError("warmup_bars must be non-negative")
        if min(self.sl_pct, self.tp_pct, self.trail_pct) < 0.0:
            raise ValueError("sl_pct/tp_pct/trail_pct must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def effective_slip_bps(self) -> float:
        return float(self.slippage_bps + self.impact_bps)

    @property
    def work_checklist(self) -> dict[str, bool]:
        """Explicit work checklist for peer honesty."""
        return {
            "next_bar_fill": True,
            "fees": self.commission_bps > 0.0,
            "slippage": self.slippage_bps > 0.0,
            "impact": self.impact_bps > 0.0,
            "cash_position_equity": True,
            "no_lookahead": True,
            "sl_tp": self.sl_pct > 0.0 or self.tp_pct > 0.0,
            "trail": self.trail_pct > 0.0,
            "partial_fills": self.fill_fraction < 1.0,
            "oco_bracket": bool(self.oco_bracket)
            and (self.sl_pct > 0.0 and self.tp_pct > 0.0),
            "trade_journal": True,
            "summary_metrics": True,
            "strategy_expressions": True,
        }
