"""Console safety: never crash on a legacy code page (Windows cp1252 and similar).

Symbols such as a check mark or an arrow cannot be encoded on some Windows consoles; printing them raises
``UnicodeEncodeError``. :func:`ensure_safe_stdio` keeps the console's encoding and replaces only what it cannot show.
"""

from __future__ import annotations

import sys
from typing import Any


def ensure_safe_stdio() -> None:
    """Make stdout and stderr replace unencodable characters instead of raising. Safe to call more than once."""
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        reconfigure: Any = getattr(stream, "reconfigure", None)
        if reconfigure is None or enc in ("utf8", "utf16", "utf32"):
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):  # pragma: no cover - a closed or detached stream
            pass


__all__ = ["ensure_safe_stdio"]
