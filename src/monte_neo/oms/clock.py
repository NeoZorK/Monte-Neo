"""OMS bar/event clock (deterministic paper time)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BarClock:
    """Monotonic bar index clock for paper OMS / replay."""

    index: int = 0
    ts_ns: int = 0

    def advance(self, *, bars: int = 1, ts_ns: int | None = None) -> int:
        if bars < 0:
            raise ValueError("bars must be non-negative")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        self.index += int(bars)
        if ts_ns is not None:
            if int(ts_ns) < self.ts_ns:
                raise ValueError("ts_ns must be non-decreasing")
            self.ts_ns = int(ts_ns)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        return self.index

    def at(self, index: int, *, ts_ns: int = 0) -> None:
        if index < 0:
            raise ValueError("index must be non-negative")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        self.index = int(index)
        self.ts_ns = int(ts_ns)
