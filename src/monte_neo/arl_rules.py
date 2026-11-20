"""The ARL rules: one machine-readable file (``arl_rules_v2.json``; earlier versions stay loadable for rechecks) is the single source of truth.

``readiness.py`` and ``arl_depth.py`` read only this file. The tables in the documentation are generated from it
(:func:`markdown_levels`, :func:`markdown_depth`, :func:`markdown_honesty`) and a test compares them with the pages, so a
change of a threshold that is not reflected in the docs (or the other way round) is a failing test.

The Alpha Readiness Level (ARL) was devised by Rostyslav Shcherbyna, author of Monte-Neo; it is modelled on the idea of a
technology readiness level and is a Monte-Neo scale, not an industry standard.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

RULES_FILE = Path(__file__).with_name("arl_rules_v2.json")
KNOWN_VERSIONS = {"arl-rules/1": Path(__file__).with_name("arl_rules_v1.json"), "arl-rules/2": RULES_FILE}
REQUIRED = ("schema", "version", "status", "authorship", "statuses", "levels", "caps", "depth", "honesty")
RULE_TYPES = {"status", "detail", "ratio", "tstat", "pvalue", "derived", "any", "all", "evidence", "holdout_valid", "between", "trials_declared"}


@lru_cache(maxsize=4)
def _read(path: str) -> dict[str, Any]:
    rules = json.loads(Path(path).read_text(encoding="utf-8"))
    validate(rules)
    return rules


def load_rules(version: str | None = None) -> dict[str, Any]:
    """The rules of ``version`` (default: the current one).

    Raises:
        ValueError: An unknown version (a certificate computed with rules this install does not have) or an invalid file.
    """
    if version is None:
        return _read(str(RULES_FILE))
    if version not in KNOWN_VERSIONS:
        raise ValueError(f"unknown ARL rules version {version!r}; this install knows {', '.join(sorted(KNOWN_VERSIONS))}")
    return _read(str(KNOWN_VERSIONS[version]))


def _check_rule(rule: dict[str, Any], where: str) -> None:
    if rule.get("type") not in RULE_TYPES:
        raise ValueError(f"{where}: unknown rule type {rule.get('type')!r}")
    for sub in rule.get("of", []):
        _check_rule(sub, where)


def validate(rules: dict[str, Any]) -> None:
    """Structural checks of a rules file.

    Raises:
        ValueError: A missing section, levels not numbered 1..9, a level without four criteria D1..D4, an unknown rule type.
    """
    missing = [k for k in REQUIRED if k not in rules]
    if missing:
        raise ValueError(f"ARL rules lack: {', '.join(missing)}")
    if rules["status"] not in ("provisional", "frozen"):
        raise ValueError("status must be provisional or frozen")
    if [lv["level"] for lv in rules["levels"]] != list(range(1, 10)):
        raise ValueError("levels must be numbered 1..9")
    ids = [c["id"] for c in rules["depth"]["criteria"]]
    for n in range(1, 10):
        crits = rules["depth"]["levels"].get(str(n), {})
        if sorted(crits) != sorted(ids):
            raise ValueError(f"level {n} needs the criteria {', '.join(ids)}")
        for cid, c in crits.items():
            if not c.get("text") or not c.get("needs"):
                raise ValueError(f"level {n} {cid}: text and needs are required")
            _check_rule(c["rule"], f"level {n} {cid}")
    for dv in rules.get("derived", []):
        if not {"id", "metric", "min", "why", "next_action"} <= set(dv):
            raise ValueError(f"derived check {dv.get('id')!r}: id, metric, min, why and next_action are required")


def describe_requirement(requirements: list[Any]) -> str:
    """``a or b; c`` text of a level's requirements: alternatives joined by 'or', requirements by ';'."""
    parts = []
    for alts in requirements:
        parts.append(" or ".join(" + ".join(f"`{cid}`" for cid, _ in alt) for alt in alts))
    return "; ".join(parts)


def markdown_levels(rules: dict[str, Any] | None = None) -> str:
    """The table of levels, generated from the rules."""
    r = rules or load_rules()
    lines = ["| L | Name | Required checks (alternatives joined by \"or\") |", "|---|------|------------------------------------------------|"]
    lines += [f"| {lv['level']} | {lv['name']} | {describe_requirement(lv['requirements'])} |" for lv in r["levels"]]
    return "\n".join(lines)


def markdown_depth(rules: dict[str, Any] | None = None) -> str:
    """The table of depth criteria, generated from the rules."""
    r = rules or load_rules()
    crit = r["depth"]["criteria"]
    head = "| L | " + " | ".join(f"{c['id']} {c['name']}" for c in crit) + " |"
    lines = [head, "|---|" + "---|" * len(crit)]
    for n in range(1, 10):
        lv = r["depth"]["levels"][str(n)]
        lines.append(f"| {n} | " + " | ".join(lv[c["id"]]["text"] for c in crit) + " |")
    return "\n".join(lines)


def markdown_honesty(rules: dict[str, Any] | None = None) -> str:
    """The honesty rules as a numbered list."""
    r = rules or load_rules()
    return "\n".join(f"{i}. {t}" for i, t in enumerate(r["honesty"], 1))


def markdown_caps(rules: dict[str, Any] | None = None) -> str:
    """The caps (look-ahead, ceilings, blockers, non-live sources) as a list."""
    r = rules or load_rules()
    c = r["caps"]
    lines = [f"- A failed look-ahead check caps the level at {c['lookahead_fail_max_level']}."]
    lines += [f"- `{x['check']}` warning or failing caps the level at {x['max_level']}: {x['why']}." for x in c["ceilings"]]
    lines += [f"- `{x['check']}` that ran and warned or failed blocks level {x['level']}: {x['why']}." for x in c["blockers"]]
    ns = c["non_real_sources"]
    lines.append(f"- Live data from {', '.join(ns['sources'])} (or an unstated source) caps the level at {ns['max_level']}: {ns['why']}.")
    return "\n".join(lines)


BLOCKS = {"levels": markdown_levels, "depth": markdown_depth, "honesty": markdown_honesty, "caps": markdown_caps}
_MARK = re.compile(r"(<!-- arl:(\w+):start -->)(.*?)(<!-- arl:\2:end -->)", re.S)


def sync_page(text: str, rules: dict[str, Any] | None = None) -> str:
    """``text`` with every ``<!-- arl:NAME:start --> ... <!-- arl:NAME:end -->`` block regenerated from the rules.

    Raises:
        ValueError: A marker with an unknown block name.
    """
    def fill(m: re.Match[str]) -> str:
        if m.group(2) not in BLOCKS:
            raise ValueError(f"unknown ARL block {m.group(2)!r}")
        return m.group(1) + "\n" + BLOCKS[m.group(2)](rules) + "\n" + m.group(4)

    return _MARK.sub(fill, text)


def page_in_sync(path: str | Path) -> bool:
    """Whether the generated blocks of a documentation page equal what the rules produce."""
    text = Path(path).read_text(encoding="utf-8")
    return sync_page(text) == text


__all__ = ["BLOCKS", "KNOWN_VERSIONS", "RULES_FILE", "describe_requirement", "load_rules", "markdown_caps", "markdown_depth",
           "markdown_honesty", "markdown_levels", "page_in_sync", "sync_page", "validate"]
