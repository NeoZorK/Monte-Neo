"""Bybit venue adapter: paper default; live env-gated + dry-run."""

from __future__ import annotations

import os
from typing import Any

from monte_neo.oms.adapters.base import FillReport, OrderIntent, OrderReport
from monte_neo.oms.adapters.paper_exchange import PaperExchangeAdapter
from monte_neo.oms.adapters.safety import dry_run_enabled, require_live_allowed


class BybitAdapter:
    """Bybit-facing adapter. Default mode is local paper (no network)."""

    name = "bybit"

    def __init__(
        self,
        *,
        mode: str = "paper",
        initial_cash: float = 100_000.0,
        mid: float = 100.0,
        commission_bps: float = 5.0,
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        mode = str(mode).lower()
        if mode not in {"paper", "live"}:
            raise ValueError("mode must be paper or live")
        self.mode = mode
        self._paper = PaperExchangeAdapter(
            initial_cash=initial_cash, mid=mid, commission_bps=commission_bps
        )
        self._api_key = api_key if api_key is not None else os.getenv("BYBIT_API_KEY", "")
        self._api_secret = (
            api_secret if api_secret is not None else os.getenv("BYBIT_API_SECRET", "")
        )
        self._live_dry: list[dict[str, Any]] = []
        if mode == "live":
            require_live_allowed(venue="bybit")
            if not self._api_key or not self._api_secret:
                raise RuntimeError("BYBIT_API_KEY/SECRET required for live mode")

    def set_mid(self, mid: float) -> None:
        self._paper.set_mid(mid)

    def submit(self, intent: OrderIntent) -> OrderReport:
        if self.mode == "paper" or dry_run_enabled():
            report = self._paper.submit(intent)
            if self.mode == "live":
                self._live_dry.append(
                    {
                        "action": "submit",
                        "dry_run": True,
                        "symbol": intent.symbol,
                        "side": int(intent.side),
                        "qty": intent.qty,
                        "order_type": int(intent.order_type),
                    }
                )
                report.raw["dry_run"] = True
                report.raw["venue"] = "bybit"
            return report
        raise RuntimeError(
            "bybit live submit without dry-run is not enabled in this build"
        )

    def cancel(self, venue_order_id: str) -> bool:
        if self.mode == "paper" or dry_run_enabled():
            ok = self._paper.cancel(venue_order_id)
            if self.mode == "live":
                self._live_dry.append(
                    {"action": "cancel", "dry_run": True, "id": venue_order_id}
                )
            return ok
        raise RuntimeError("bybit live cancel without dry-run not enabled")

    def poll_fills(self) -> list[FillReport]:
        return self._paper.poll_fills()

    def get_balances(self) -> dict[str, float]:
        return self._paper.get_balances()

    def get_positions(self) -> dict[str, float]:
        return self._paper.get_positions()

    def work_checklist(self) -> dict[str, bool]:
        return {
            "venue_bybit": True,
            "paper": self.mode == "paper",
            "live": self.mode == "live",
            "dry_run": self.mode == "live" and dry_run_enabled(),
            "credentials_present": bool(self._api_key and self._api_secret),
            "submit": True,
            "cancel": True,
            "poll_fills": True,
        }

    def dry_run_log(self) -> list[dict[str, Any]]:
        return list(self._live_dry)
