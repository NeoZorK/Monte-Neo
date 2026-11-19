"""Split ``path.py:function`` without breaking a Windows drive letter (``C:\\x\\s.py:signal``)."""

from __future__ import annotations


def strategy_file(spec: str) -> str:
    """The file part of ``file.py`` or ``file.py:function``; ``C:\\dir\\s.py`` stays whole."""
    path, sep, func = str(spec).rpartition(":")
    if not sep or not path or not func.isidentifier() or (len(path) == 1 and path.isalpha()):
        return str(spec)
    return path


__all__ = ["strategy_file"]
