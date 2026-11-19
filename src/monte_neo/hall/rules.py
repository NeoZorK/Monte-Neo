"""The Hall of Fame rules: one machine-readable file (``hall_rules_v1.json``) is the source of truth.

The tables of ``docs/guides/hall-of-fame.md`` are generated from it (:func:`sync_page`) and a test compares them with the page.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

RULES_FILE = Path(__file__).with_name("hall_rules_v1.json")
REQUIRED = ("schema", "version", "status", "arl_rules_version", "top_n", "score", "tiers", "categories", "limits", "dedupe", "medals", "honesty")


@lru_cache(maxsize=1)
def load_rules() -> dict[str, Any]:
    """The current rules (``hall-of-fame/1``).

    Raises:
        ValueError: The file lacks a section.
    """
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    validate(rules)
    return rules


def validate(rules: dict[str, Any]) -> None:
    """Structural checks of a rules file.

    Raises:
        ValueError: A missing section, no ranked tier or a medal list that is not 1..n.
    """
    missing = [k for k in REQUIRED if k not in rules]
    if missing:
        raise ValueError(f"Hall of Fame rules lack: {', '.join(missing)}")
    if not any(t["ranked"] for t in rules["tiers"].values()):
        raise ValueError("Hall of Fame rules need at least one ranked tier")
    if sorted(rules["medals"].values()) != list(range(1, len(rules["medals"]) + 1)):
        raise ValueError("medals must take ranks 1..n")


def markdown_score(rules: dict[str, Any] | None = None) -> str:
    """The ordering of the table as a numbered list."""
    r = rules or load_rules()
    steps = "\n".join(f"{i}. {t}" for i, t in enumerate(r["score"]["order"], 1))
    return f"{steps}\n\n{r['score']['note']} Verdicts never ranked: {', '.join(f'`{v}`' for v in r['score']['excluded_verdicts'])}."


def markdown_tiers(rules: dict[str, Any] | None = None) -> str:
    """The trust tiers as a table."""
    r = rules or load_rules()
    rows = [f"| {k} | {t['name']} | {'yes' if t['ranked'] else 'no'} | {t['meaning']} |" for k, t in r["tiers"].items()]
    return "\n".join(["| Tier | Name | Ranked | Meaning |", "|---|---|---|---|", *rows])


def markdown_limits(rules: dict[str, Any] | None = None) -> str:
    """Limits, categories, medals and the duplicate rule as a list."""
    r = rules or load_rules()
    lim = r["limits"]
    medals = ", ".join(f"{m} = rank {n}" for m, n in r["medals"].items())
    return "\n".join([
        f"- Table size: top {r['top_n']} overall and in each category; ranked under `{r['version']}` with ARL rules `{r['arl_rules_version']}`.",
        f"- Categories: {', '.join(f'`{c}`' for c in r['categories'])}.",
        f"- Medals ({medals}) are given per table: overall and per category.",
        f"- At most {lim['entries_per_author_per_month']} entries per author per month; `n_trials` of at least {lim['min_n_trials']} is required.",
        f"- {r['dedupe']}",
    ])


def markdown_honesty(rules: dict[str, Any] | None = None) -> str:
    """The honesty rules as a numbered list."""
    r = rules or load_rules()
    return "\n".join(f"{i}. {t}" for i, t in enumerate(r["honesty"], 1))


BLOCKS = {"score": markdown_score, "tiers": markdown_tiers, "limits": markdown_limits, "honesty": markdown_honesty}
_MARK = re.compile(r"(<!-- hall:(\w+):start -->)(.*?)(<!-- hall:\2:end -->)", re.S)


def sync_page(text: str, rules: dict[str, Any] | None = None) -> str:
    """``text`` with every ``<!-- hall:NAME:start --> ... <!-- hall:NAME:end -->`` block regenerated from the rules.

    Raises:
        ValueError: A marker with an unknown block name.
    """
    def fill(m: re.Match[str]) -> str:
        if m.group(2) not in BLOCKS:
            raise ValueError(f"unknown Hall of Fame block {m.group(2)!r}")
        return m.group(1) + "\n" + BLOCKS[m.group(2)](rules) + "\n" + m.group(4)

    return _MARK.sub(fill, text)


__all__ = ["BLOCKS", "RULES_FILE", "load_rules", "markdown_honesty", "markdown_limits", "markdown_score", "markdown_tiers", "sync_page", "validate"]
