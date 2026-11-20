"""Load and validate the profile rules file."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RULES_FILE = Path(__file__).with_name("profiles_v1.json")
RULES_VERSION = "profiles/1"
_REQUIRED = ("id", "title", "summary", "benchmark", "required_checks", "metrics_focus", "not_assessed", "traps", "controls")


@lru_cache(maxsize=1)
def load_profiles() -> dict[str, Any]:
    """The parsed rules file, validated: every profile has two traps, two controls and a reason for each not-assessed item."""
    doc = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    if doc.get("version") != RULES_VERSION:
        raise ValueError(f"unknown profile rules version {doc.get('version')!r}")
    seen: set[str] = set()
    for p in doc["profiles"]:
        missing = [k for k in _REQUIRED if k not in p]
        if missing:
            raise ValueError(f"profile {p.get('id')!r} lacks {missing}")
        if p["id"] in seen:
            raise ValueError(f"duplicate profile id {p['id']!r}")
        seen.add(p["id"])
        if len(p["traps"]) < 2 or len(p["controls"]) < 2:
            raise ValueError(f"profile {p['id']!r} needs at least 2 traps and 2 controls")
        if any(not n.get("why") for n in p["not_assessed"]):
            raise ValueError(f"profile {p['id']!r}: every not-assessed item needs a reason")
    return doc


def _all() -> dict[str, dict[str, Any]]:
    return {p["id"]: p for p in load_profiles()["profiles"]}


PROFILE_IDS: tuple[str, ...] = tuple(_all())


def get_profile(profile_id: str) -> dict[str, Any]:
    """One profile by id; ``ValueError`` names the valid ids."""
    profiles = _all()
    if profile_id not in profiles:
        raise ValueError(f"unknown profile {profile_id!r}; choose one of {', '.join(profiles)}")
    return profiles[profile_id]
