"""Watch strategy code for data it reads outside ``df`` (data files, network).

The look-ahead probes rewrite ``df`` and compare signals. A strategy that loads the
dataset itself sees the untouched future and slips past them. While strategy code
runs, a ``sys.audit`` hook records reads of data files and socket connections.

Only data-file reads count (by suffix, plus the OHLCV file itself); library and
interpreter files are ignored, so importing packages inside ``signal()`` is fine.
A watch sees only its own thread: the MCP server runs tool calls in worker threads,
and one verification must not record the data file another one is loading.
"""

from __future__ import annotations

import os
import site
import sys
import threading
from pathlib import Path
from typing import Any

DATA_SUFFIXES = frozenset(
    {
        ".csv", ".tsv", ".parquet", ".pq", ".feather", ".arrow", ".ipc", ".pkl", ".pickle",
        ".npy", ".npz", ".h5", ".hdf5", ".hdf", ".xlsx", ".xls", ".db", ".sqlite", ".duckdb",
    }
)
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR

_ACTIVE: list[IOWatch] = []
_installed = False
_system_roots: tuple[str, ...] = ()


def _roots() -> tuple[str, ...]:
    """Interpreter and site-packages directories: files there belong to libraries."""
    dirs = {sys.prefix, sys.base_prefix, sys.exec_prefix, *site.getsitepackages()}
    user_site = site.getusersitepackages()
    if isinstance(user_site, str):
        dirs.add(user_site)
    return tuple(os.path.join(os.path.abspath(d), "") for d in dirs if d)


def _is_read(mode: Any, flags: Any) -> bool:
    if isinstance(mode, str):
        return not any(ch in mode for ch in "wax+")
    return isinstance(flags, int) and not flags & _WRITE_FLAGS


def _watching() -> list[IOWatch]:
    thread = threading.get_ident()
    return [watch for watch in _ACTIVE if watch.thread == thread]


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if not _ACTIVE:
        return
    try:
        if event == "open":
            path, mode, flags = (tuple(args) + (None, None, None))[:3]
            if isinstance(path, bytes):
                path = os.fsdecode(path)
            if not isinstance(path, str) or not _is_read(mode, flags):
                return
            full = os.path.abspath(path)
            for watch in _watching():
                watch.note_file(full)
        elif event == "socket.connect":
            address = args[1] if len(args) > 1 else None
            host = str(address[0]) if isinstance(address, tuple) and address else str(address)
            for watch in _watching():
                watch.note_connection(host)
    except Exception:  # pragma: no cover - an audit hook must never break the audited call
        return


def _install() -> None:
    global _installed, _system_roots
    if not _installed:
        _system_roots = _roots()
        sys.addaudithook(_hook)
        _installed = True


class IOWatch:
    """Collect data-file reads and connections made while the watch is entered.

    Re-enterable: enter it around every call into strategy code (module import,
    ``signal()``, probes) and read ``files`` / ``connections`` at the end.
    """

    def __init__(self, data_paths: tuple[str | Path, ...] = ()) -> None:
        self._data_paths = {os.path.abspath(str(p)) for p in data_paths}
        self.files: list[str] = []
        self.connections: list[str] = []
        self.thread: int | None = None

    def note_file(self, path: str) -> None:
        if path.startswith(_system_roots):
            return
        if path in self._data_paths or os.path.splitext(path)[1].lower() in DATA_SUFFIXES:
            name = os.path.basename(path)  # certificates are shared: no local directories
            if name not in self.files:
                self.files.append(name)

    def note_connection(self, host: str) -> None:
        if host not in self.connections:
            self.connections.append(host)

    def __enter__(self) -> IOWatch:
        _install()
        self.thread = threading.get_ident()
        _ACTIVE.append(self)
        return self

    def __exit__(self, *exc: object) -> None:
        _ACTIVE.remove(self)


__all__ = ["DATA_SUFFIXES", "IOWatch"]
