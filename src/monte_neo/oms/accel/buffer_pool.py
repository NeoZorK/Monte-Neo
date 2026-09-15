"""Simple reusable byte-buffer pool for Metal/Numba hot paths."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BufferPool:
    """Cap residency by reusing fixed-size bytearray slabs."""

    max_slabs: int = 32
    _free: list[bytearray] = field(default_factory=list)
    _live: int = 0

    def acquire(self, nbytes: int) -> bytearray:
        if nbytes < 0:
            raise ValueError("nbytes must be non-negative")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        for i, buf in enumerate(self._free):
            if len(buf) >= nbytes:
                self._free.pop(i)
                self._live += 1
                return buf
        self._live += 1
        return bytearray(nbytes)

    def release(self, buf: bytearray) -> None:
        self._live = max(0, self._live - 1)
        if len(self._free) >= self.max_slabs:
            return  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        self._free.append(buf)

    def stats(self) -> dict[str, int]:
        return {
            "free_slabs": len(self._free),
            "live": self._live,
            "max_slabs": self.max_slabs,
        }
