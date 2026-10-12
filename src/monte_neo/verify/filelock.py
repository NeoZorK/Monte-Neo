"""Small cross-process exclusive file lock (stdlib only) for files shared on a team drive."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]
try:  # Windows
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]

DEFAULT_TIMEOUT = 30.0
_POLL = 0.02


class LockTimeoutError(TimeoutError):
    """The lock could not be acquired in time."""


def _fail(path: Path, timeout: float) -> LockTimeoutError:
    return LockTimeoutError(
        f"could not lock {path} within {timeout:g}s: another process is writing to the same ledger "
        "(if no one is, remove the stale lock file or directory and retry)"
    )


@contextmanager
def file_lock(path: str | Path, timeout: float = DEFAULT_TIMEOUT) -> Iterator[None]:
    """Hold an exclusive lock on ``path`` (a sibling lock file) for the ``with`` block.

    Uses ``fcntl.flock`` on POSIX, ``msvcrt.locking`` on Windows, and an atomically created lock
    directory as a last resort.

    Args:
        path: Lock file path (created if missing).
        timeout: Seconds to wait before raising ``LockTimeoutError``.

    Yields:
        None, while the lock is held.
    """
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    if fcntl is not None or msvcrt is not None:
        with lock_path.open("a+b") as handle:
            while True:
                try:
                    if fcntl is not None:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    else:
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[union-attr]
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise _fail(lock_path, timeout) from None
                    time.sleep(_POLL)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                else:  # pragma: no cover
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[union-attr]
        return
    lock_dir = Path(str(lock_path) + ".d")  # pragma: no cover - no locking primitive available
    while True:  # pragma: no cover
        try:
            os.mkdir(lock_dir)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise _fail(lock_dir, timeout) from None
            time.sleep(_POLL)
    try:  # pragma: no cover
        yield
    finally:  # pragma: no cover
        os.rmdir(lock_dir)


__all__ = ["DEFAULT_TIMEOUT", "LockTimeoutError", "file_lock"]
