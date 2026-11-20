"""Load the Hall of Fame store, classify entries, rank them and keep the monthly history.

Layout under ``hall_of_fame/``: ``entries/<id>.json`` (``hall-entry/1``), ``certificates/<id>.json`` (the full
``strategy-verdict/1`` certificate of the entry), ``maintainer_keys.json`` and ``history.jsonl`` (one monthly snapshot per table).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from monte_neo.hall.entry import check_entry, summarize

Item = dict[str, Any]


def load_keys(root: Path) -> dict[str, str]:
    """Trusted maintainer keys: key id -> ``ed25519:<base64>`` (empty when the file is absent)."""
    path = root / "maintainer_keys.json"
    if not path.exists():
        return {}
    return {k["key_id"]: k["public_key"] for k in json.loads(path.read_text(encoding="utf-8"))["keys"]}


def load_items(root: Path, rules: dict[str, Any]) -> list[Item]:
    """Every entry under ``root/entries`` with its certificate, its summary and the list of errors (empty when valid)."""
    keys, items = load_keys(root), []
    for path in sorted((root / "entries").glob("*.json")):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            cert_path = root / "certificates" / path.name
            cert = json.loads(cert_path.read_text(encoding="utf-8")) if cert_path.exists() else None
            errs = check_entry(entry, cert, rules, keys)
            if entry.get("id") != path.stem:
                errs.append("id must equal the file name")
        except (OSError, ValueError, AttributeError) as exc:
            entry, cert, errs = {"id": path.stem}, None, [f"unreadable entry: {exc}"]
        items.append({"entry": entry, "summary": summarize(cert) if cert else {}, "errors": errs, "path": str(path)})
    return items


def sort_key(item: Item) -> tuple[Any, ...]:
    """Order of the table: ARL, depth, Deflated Sharpe (none ranks last), certificate date, id. Return is not an input."""
    s = item["summary"]
    dsr = s["deflated_sharpe"]
    dsr = dsr if isinstance(dsr, (int, float)) and math.isfinite(dsr) else float("-inf")
    return (-s["arl"], -s["depth"], -dsr, s["date"], item["entry"]["id"])


def classify(items: list[Item], rules: dict[str, Any]) -> dict[str, Any]:
    """Split valid items into ``ranked``, ``self_reported`` and ``excluded`` (with a reason); invalid ones go to ``errors``."""
    out: dict[str, Any] = {"errors": [i for i in items if i["errors"]], "ranked": [], "self_reported": [], "excluded": []}
    seen: dict[str, str] = {}
    per_month: dict[tuple[str, str], int] = {}
    cap = rules["limits"]["entries_per_author_per_month"]
    for it in sorted((i for i in items if not i["errors"]), key=lambda i: (i["entry"]["submitted_at"], i["entry"]["id"])):
        e, s = it["entry"], it["summary"]
        slot = (e["author"], e["submitted_at"][:7])
        per_month[slot] = per_month.get(slot, 0) + 1
        fps = [f"{k}:{s['data_sha256']}:{s[k]}" for k in ("signals_sha256", "source_sha256") if s[k]]
        twin = next((seen[f] for f in fps if f in seen), None)
        reason = None
        if per_month[slot] > cap:
            reason = f"more than {cap} entries by this author in {slot[1]}"
        elif twin:
            reason = f"same strategy as {twin} (same data and signal or source hash)"
        elif s["verdict"] in rules["score"]["excluded_verdicts"]:
            reason = f"verdict {s['verdict']} is never ranked"
        if reason:
            out["excluded"].append((it, reason))
            continue
        seen.update({f: e["id"] for f in fps})
        out["self_reported" if not rules["tiers"][e["tier"]]["ranked"] else "ranked"].append(it)
    out["ranked"].sort(key=sort_key)
    return out


def _group(item: Item) -> tuple[str, str]:
    return (item["entry"]["hall_rules_version"], item["entry"]["arl_rules_version"])


def tables(ranked: list[Item], rules: dict[str, Any]) -> dict[str, list[Item]]:
    """Top-N lists of the current rules: ``overall`` and one per category (only entries of the current rules versions)."""
    cur = [i for i in ranked if _group(i) == (rules["version"], rules["arl_rules_version"])]
    out = {"overall": cur[: rules["top_n"]]}
    out.update({c: [i for i in cur if i["entry"]["category"] == c][: rules["top_n"]] for c in rules["categories"]})
    return out


def archived(ranked: list[Item], rules: dict[str, Any]) -> dict[tuple[str, str], list[Item]]:
    """Ranked entries of older rules versions, grouped by (hall rules, ARL rules): archived tables, never mixed with the current one."""
    out: dict[tuple[str, str], list[Item]] = {}
    for i in ranked:
        if _group(i) != (rules["version"], rules["arl_rules_version"]):
            out.setdefault(_group(i), []).append(i)
    return out


def read_history(path: Path) -> list[dict[str, Any]]:
    """Snapshots from ``history.jsonl`` (empty when absent)."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_history(history: list[dict[str, Any]], month: str, rules: dict[str, Any], current: dict[str, list[Item]]) -> list[dict[str, Any]]:
    """History with this month's snapshots (one per table) replaced by the current standings, ordered by month and table."""
    keep = [h for h in history if not (h["month"] == month and h["rules"] == rules["version"])]
    new = [{"month": month, "rules": rules["version"], "scope": s, "ranking": [i["entry"]["id"] for i in rows]} for s, rows in current.items()]
    return sorted(keep + new, key=lambda h: (h["month"], h["rules"], h["scope"]))


def history_text(history: list[dict[str, Any]]) -> str:
    """``history.jsonl`` content."""
    return "".join(json.dumps(h, sort_keys=True) + "\n" for h in history)


def runs(history: list[dict[str, Any]], rules: dict[str, Any], scope: str, by_rank: bool) -> dict[str, list[dict[str, Any]]]:
    """Consecutive-snapshot runs per entry in one table: the same rank (``by_rank``) or just presence in the table.

    Each run has ``key`` (rank or 0), ``start`` and ``end`` months and ``current`` (it reaches the latest snapshot).
    """
    snaps = [h for h in history if h["rules"] == rules["version"] and h["scope"] == scope]
    out: dict[str, list[dict[str, Any]]] = {}
    for idx, h in enumerate(snaps):
        for rank, eid in enumerate(h["ranking"], 1):
            key, lst = (rank if by_rank else 0), out.setdefault(eid, [])
            if lst and lst[-1]["idx"] == idx - 1 and lst[-1]["key"] == key:
                lst[-1].update(end=h["month"], idx=idx)
            else:
                lst.append({"key": key, "start": h["month"], "end": h["month"], "idx": idx})
    for lst in out.values():
        for r in lst:
            r["current"] = r["idx"] == len(snaps) - 1
    return out


__all__ = ["archived", "classify", "history_text", "load_items", "load_keys", "read_history", "runs", "sort_key", "tables", "update_history"]
