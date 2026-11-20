"""Write the generated profile tables into docs/guides/profiles.md (run after editing profiles_v1.json)."""

from __future__ import annotations

import sys
from pathlib import Path

from monte_neo.profiles.docgen import END, START, markdown_profiles

PAGE = Path(__file__).resolve().parents[1] / "docs" / "guides" / "profiles.md"


def main() -> int:
    """Replace the block between the markers; exit 1 when the page lacks them."""
    text = PAGE.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print("markers missing", file=sys.stderr)
        return 1
    head, rest = text.split(START, 1)
    tail = rest.split(END, 1)[1]
    PAGE.write_text(f"{head}{START}\n{markdown_profiles()}{END}{tail}", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
