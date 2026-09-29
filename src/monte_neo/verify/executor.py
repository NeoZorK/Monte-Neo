"""Run strategy code in worker processes: parallel probes, time limits, isolation.

The look-ahead probes call ``signal(df)`` about 56 times on the full table, its
prefixes and rewritten futures. :class:`ProcessRunner` loads the strategy file in
worker processes and spreads those calls over them:

* ``jobs`` workers run calls in parallel (the probes are independent);
* ``timeout`` bounds every call: a strategy that hangs ends the run with a clear
  error instead of hanging the verifier (or an agent's MCP session);
* ``isolate`` locks the workers down: no network, no subprocesses, no file writes
  outside the temp dir, and an environment without secrets.

The parent process never imports the strategy module when a runner is used: it only
reads the source for the static lint, so module-level code runs in the workers only.

Isolation is a guard against careless or buggy code, not a security boundary against
a determined attacker (Python audit hooks can be bypassed with native code); run
untrusted code in a container without network for that.
"""

from __future__ import annotations

import math
import multiprocessing as mp
import os
import signal
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

MAX_AUTO_JOBS = 8
# Parent-side backstop on top of the per-call limit: time to start workers and load the strategy.
STARTUP_SLACK = 30.0
_SAFE_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "PYTHONHASHSEED")
_NET, _PROC = "network access", "starting processes"
_BLOCKED_EVENTS = {
    "socket.connect": _NET, "socket.bind": _NET, "socket.sendto": _NET, "socket.getaddrinfo": _NET,
    "subprocess.Popen": _PROC, "os.system": _PROC, "os.exec": _PROC, "os.posix_spawn": _PROC,
    "os.spawn": _PROC, "os.fork": _PROC, "os.forkpty": _PROC, "os.startfile": _PROC,
    "os.kill": "signalling other processes",
}
_PATH_EVENTS = ("os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.truncate", "shutil.rmtree")


class StrategyTimeoutError(ValueError):
    """``signal()`` did not finish within the time limit."""


class StrategyError(ValueError):
    """``signal()`` (or the strategy module) raised in a worker process."""


@dataclass(frozen=True)
class Head:
    """Task: the first ``rows`` rows of the table the runner was built on."""

    rows: int


FULL = Head(-1)  # the whole table


def resolve_jobs(jobs: int | str | None) -> int:
    """``"auto"`` -> CPU count capped at 8; ``None`` / 0 -> 1."""
    if jobs in (None, 0, "0"):
        return 1
    if jobs == "auto":
        return max(1, min(MAX_AUTO_JOBS, os.cpu_count() or 1))
    value = int(jobs)
    if value < 1:
        raise ValueError(f"jobs must be >= 1 or 'auto', got {jobs!r}")
    return value


def split_spec(spec: str | Path) -> tuple[Path, str]:
    """``path.py[:func]`` -> (path, func); the default function is ``signal``."""
    text = str(spec)
    if ":" in text and not Path(text).exists():
        path, func = text.rsplit(":", 1)
        return Path(path), func
    return Path(text), "signal"


# -- worker side -----------------------------------------------------------------
_FRAME: pd.DataFrame | None = None
_FN: Any = None
_INIT_ERROR: str | None = None
_WATCH: Any = None
_TIMEOUT: float | None = None


class _CallTimeoutError(Exception):
    pass


def _alarm(signum: int, frame: Any) -> None:
    raise _CallTimeoutError


def _lock_down() -> None:  # pragma: no cover - runs only in worker processes (tests use real workers)
    """Isolation for the worker: clean environment and an audit hook that blocks side effects."""
    keep = {k: os.environ[k] for k in _SAFE_ENV if k in os.environ}
    os.environ.clear()
    os.environ.update(keep)
    temp = os.path.join(os.path.abspath(tempfile.gettempdir()), "")

    def allowed_path(path: Any) -> bool:
        if isinstance(path, bytes):
            path = os.fsdecode(path)
        if not isinstance(path, str | os.PathLike):
            return True
        full = os.path.abspath(os.fspath(path))
        return full.startswith(temp) or f"{os.sep}__pycache__{os.sep}" in full

    def hook(event: str, args: tuple[Any, ...]) -> None:
        what = _BLOCKED_EVENTS.get(event)
        if what:
            raise PermissionError(f"isolated run: {what} is blocked ({event})")
        if event == "open" and len(args) >= 3:
            path, mode, flags = args[0], args[1], args[2]
            writing = any(ch in mode for ch in "wax+") if isinstance(mode, str) else bool(
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
            )
            if writing and not allowed_path(path):
                raise PermissionError(f"isolated run: writing files is blocked ({path})")
        elif event in _PATH_EVENTS and args and not allowed_path(args[0]):
            raise PermissionError(f"isolated run: changing files is blocked ({event} {args[0]})")

    sys.addaudithook(hook)


def _init(
    path: str, func: str, frame: pd.DataFrame, data_paths: tuple[str, ...], isolate: bool, timeout: float | None
) -> None:
    global _FRAME, _FN, _INIT_ERROR, _WATCH, _TIMEOUT
    sys.dont_write_bytecode = True
    _FRAME = frame
    _TIMEOUT = timeout
    try:
        from monte_neo.verify.ingest import load_signal_fn
        from monte_neo.verify.io_guard import IOWatch

        if isolate:
            _lock_down()  # pragma: no cover - worker processes only
        _WATCH = IOWatch(data_paths)
        _WATCH.__enter__()  # records data reads during the import and every call in this worker
        _FN, _ = load_signal_fn(f"{path}:{func}")
    except BaseException as exc:  # reported on every call: a failing initializer would respawn forever
        _INIT_ERROR = f"{type(exc).__name__}: {exc}"


def _call(task: tuple[Any, dict[str, Any]]) -> tuple[str, Any, list[str], list[str]]:
    target, params = task
    files = list(_WATCH.files) if _WATCH is not None else []
    conns = list(_WATCH.connections) if _WATCH is not None else []
    if _INIT_ERROR is not None:
        return "error", f"loading the strategy failed: {_INIT_ERROR}", files, conns
    try:
        from monte_neo.verify.ingest import signal_values

        assert _FRAME is not None
        if isinstance(target, Head):
            df = _FRAME.copy() if target.rows < 0 else _FRAME.iloc[: target.rows].reset_index(drop=True)
        else:
            df = target
        # The exact per-call limit: an alarm in the worker (Unix). The parent keeps a looser
        # deadline as a backstop, and for platforms without SIGALRM.
        timed = _TIMEOUT is not None and hasattr(signal, "SIGALRM")
        if timed:
            signal.signal(signal.SIGALRM, _alarm)
            signal.setitimer(signal.ITIMER_REAL, float(_TIMEOUT))
        try:
            values = signal_values(_FN(df, **params))
        finally:
            if timed:
                signal.setitimer(signal.ITIMER_REAL, 0.0)
    except _CallTimeoutError:
        return "timeout", None, list(_WATCH.files), list(_WATCH.connections)
    except BaseException as exc:
        return "error", f"{type(exc).__name__}: {exc}", list(_WATCH.files), list(_WATCH.connections)
    return "ok", values, list(_WATCH.files), list(_WATCH.connections)


# -- parent side -----------------------------------------------------------------
@dataclass
class ProcessRunner:
    """Calls ``signal()`` from a strategy file in worker processes.

    Callable like a strategy function (``runner(df)`` returns raw values), and
    :meth:`run` evaluates a batch of tasks in parallel.
    """

    path: Path
    func: str
    frame: pd.DataFrame
    jobs: int = 1
    timeout: float | None = None
    isolate: bool = False
    data_paths: tuple[str, ...] = ()
    params: dict[str, Any] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    connections: list[str] = field(default_factory=list)
    _pool: Any = None
    _owner: ProcessRunner | None = None

    def __post_init__(self) -> None:
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")

    # batches
    def _ensure_pool(self) -> Any:
        root = self._owner or self
        if root._pool is None:
            ctx = mp.get_context("spawn")
            root._pool = ctx.Pool(
                root.jobs, initializer=_init,
                initargs=(str(root.path), root.func, root.frame, root.data_paths, root.isolate, root.timeout),
            )
        return root._pool

    def _note(self, files: list[str], conns: list[str]) -> None:
        root = self._owner or self
        for name in files:
            if name not in root.files:
                root.files.append(name)
        for host in conns:
            if host not in root.connections:
                root.connections.append(host)

    def run(self, tasks: list[Any], params: list[dict[str, Any]] | None = None) -> list[np.ndarray]:
        """Raw signal values for each task (a :class:`Head` or an explicit DataFrame)."""
        pool = self._ensure_pool()
        plist = params if params is not None else [self.params] * len(tasks)
        pending = [pool.apply_async(_call, ((task, p),)) for task, p in zip(tasks, plist, strict=True)]
        root = self._owner or self
        # A call may wait behind others in the queue: the budget grows with the batch.
        waves = math.ceil(len(tasks) / max(root.jobs, 1))
        deadline = None if root.timeout is None else time.monotonic() + root.timeout * waves + STARTUP_SLACK
        out = []
        for job in pending:
            left = None if deadline is None else max(0.0, deadline - time.monotonic())
            try:
                status, value, files, conns = job.get(timeout=left)
            except mp.TimeoutError:
                status, value, files, conns = "timeout", None, [], []
            if status == "timeout":
                self.close()
                raise StrategyTimeoutError(f"signal() did not finish within the time limit ({root.timeout:g} s per call)")
            self._note(files, conns)
            if status != "ok":
                self.close()
                raise StrategyError(f"signal() failed in a worker process: {value}")
            out.append(np.asarray(value, dtype=np.float64))
        return out

    def __call__(self, df: pd.DataFrame, **params: Any) -> np.ndarray:
        task = FULL if df is self.frame or df.equals(self.frame) else df
        return self.with_params(params).run([task])[0] if params else self.run([task])[0]

    def with_params(self, params: dict[str, Any]) -> ProcessRunner:
        """A view that calls ``signal(df, **params)`` on the same workers."""
        root = self._owner or self
        return ProcessRunner(
            root.path, root.func, root.frame, root.jobs, root.timeout, root.isolate, root.data_paths,
            params=dict(params), _owner=root,
        )

    def close(self) -> None:
        root = self._owner or self
        if root._pool is not None:
            root._pool.terminate()
            root._pool.join()
            root._pool = None

    def __enter__(self) -> ProcessRunner:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def evaluate(fn: Any, frame: pd.DataFrame, tasks: list[Any]) -> list[np.ndarray]:
    """Raw values of ``fn`` on each task, in parallel when ``fn`` is a runner."""
    from monte_neo.verify.ingest import signal_values

    if isinstance(fn, ProcessRunner):
        return fn.run(tasks)
    out = []
    for task in tasks:
        if isinstance(task, Head):
            df = frame.copy() if task.rows < 0 else frame.iloc[: task.rows].reset_index(drop=True)
        else:
            df = task.copy()
        out.append(signal_values(fn(df)))
    return out


__all__ = [
    "FULL",
    "Head",
    "ProcessRunner",
    "StrategyError",
    "StrategyTimeoutError",
    "evaluate",
    "resolve_jobs",
    "split_spec",
]
