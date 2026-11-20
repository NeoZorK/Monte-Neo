"""Split ``path.py:function`` without breaking a Windows drive letter (``C:\\x\\s.py:signal``)."""

from __future__ import annotations

import os
import shlex


def strategy_file(spec: str) -> str:
    """The file part of ``file.py`` or ``file.py:function``; ``C:\\dir\\s.py`` stays whole."""
    path, sep, func = str(spec).rpartition(":")
    if not sep or not path or not func.isidentifier() or (len(path) == 1 and path.isalpha()):
        return str(spec)
    return path


def split_args(line: str) -> list[str]:
    """Split a command line like a POSIX shell; on Windows keep backslashes in paths (``C:\\Users\\x.csv``)."""
    if os.name != "nt":
        return shlex.split(line)
    out = []
    for tok in shlex.split(line, posix=False):
        if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "'\"":
            tok = tok[1:-1]
        out.append(tok)
    return out


__all__ = ["split_args", "strategy_file"]
