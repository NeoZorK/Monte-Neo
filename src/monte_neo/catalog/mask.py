"""``type-mask/1``: a fixed-layout fingerprint of which strategy categories a strategy uses and in what role.

Layout, from the most significant bit: 24 categories x 2 bits (``00`` absent, ``01`` tag, ``10`` component, ``11`` main),
4 kind bits (filter, overlay, blend, portfolio; all zero = single), 9 asset-class bits, structure (3 bits), holding (3),
breadth (2), risk shape (2), verifiable (2): 73 bits, written as ``tm1:`` and 19 hex digits. In every tag field code 0 means
not known; code n is the n-th value of the list in the rules file. Bit positions are never
reassigned; a new category needs ``type-mask/2``. The readable tag is derived from the mask by :func:`readable_tag` only.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RULES_FILE = Path(__file__).with_name("catalog_rules_v1.json")
ROLE_BITS = {"tag": 1, "component": 2, "main": 3}
BITS = 73
FIELDS = (("structures", "structure", 3), ("holding", "holding", 3), ("breadth", "breadth", 2), ("risk_shape", "risk_shape", 2), ("verifiable", "verifiable", 2))


@lru_cache(maxsize=1)
def rules() -> dict[str, Any]:
    """The ``catalog-rules/1`` file: categories, asset classes, tag codes and thresholds."""
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


def categories() -> list[str]:
    return [c for c, _ in rules()["categories"]]


def encode(fields: dict[str, Any]) -> str:
    """``tm1:<hex>`` of ``{"main", "components": {cat: role}, "tags": [cat], "kinds", "asset_classes", "structure", ...}``."""
    r, cats = rules(), categories()
    roles = {c: 0 for c in cats}
    for c in fields.get("tags", []):
        roles[c] = max(roles[c], ROLE_BITS["tag"])
    for c in fields.get("components", {}):
        roles[c] = max(roles[c], ROLE_BITS["component"])
    roles[fields["main"]] = ROLE_BITS["main"]
    v = 0
    for c in cats:
        v = (v << 2) | roles[c]
    for k in r["kinds"]:
        v = (v << 1) | int(k in fields.get("kinds", []))
    for a in r["asset_classes"]:
        v = (v << 1) | int(a in fields.get("asset_classes", []))
    for name, key, width in FIELDS:
        val = fields.get(key)
        v = (v << width) | (r[name].index(val) + 1 if val in r[name] else 0)
    return f"tm1:{v:0{-(-BITS // 4)}x}"


def decode(mask: str) -> dict[str, Any]:
    """The fields of a ``tm1:`` mask (inverse of :func:`encode`; unknown tag codes come back as ``None``)."""
    if not mask.startswith("tm1:"):
        raise ValueError(f"not a type-mask/1 code: {mask!r}")
    r, cats, v = rules(), categories(), int(mask[4:], 16)
    out: dict[str, Any] = {}
    for name, key, width in reversed(FIELDS):
        code = v & ((1 << width) - 1)
        v >>= width
        out[key] = r[name][code - 1] if 0 < code <= len(r[name]) else None
    assets = []
    for a in reversed(r["asset_classes"]):
        if v & 1:
            assets.append(a)
        v >>= 1
    kinds = []
    for k in reversed(r["kinds"]):
        if v & 1:
            kinds.append(k)
        v >>= 1
    roles = {}
    for c in reversed(cats):
        roles[c] = v & 3
        v >>= 2
    out["asset_classes"] = [a for a in r["asset_classes"] if a in assets]
    out["kinds"] = [k for k in r["kinds"] if k in kinds]
    out["main"] = next((c for c in cats if roles[c] == 3), None)
    out["components"] = [c for c in cats if roles[c] == 2]
    out["tags"] = [c for c in cats if roles[c] == 1]
    return out


def readable_tag(main: str, asset_classes: list[str], components: dict[str, str]) -> str:
    """``#TSM.FX+f:VOL``: main category, asset classes, then components in category order as ``+<role>:<CAT>``."""
    r, cats = rules(), categories()
    assets = "-".join(a for a in r["asset_classes"] if a in asset_classes) or "MULTI"
    parts = [f"+{r['roles'][components[c]]}:{c}" for c in cats if c in components and c != main]
    return f"#{main}.{assets}" + "".join(parts)


def similarity(a: str, b: str) -> float:
    """Jaccard similarity of the categories two masks use (any role): 1.0 = same kinds of strategy inside."""
    da, db = decode(a), decode(b)
    sa = {da["main"], *da["components"], *da["tags"]} - {None}
    sb = {db["main"], *db["components"], *db["tags"]} - {None}
    return len(sa & sb) / len(sa | sb) if sa | sb else 1.0


__all__ = ["RULES_FILE", "categories", "decode", "encode", "readable_tag", "rules", "similarity"]
