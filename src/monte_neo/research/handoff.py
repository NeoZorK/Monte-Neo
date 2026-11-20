"""Hand the champion of a search to the rest of Monte-Neo: a validation dossier and a Hall of Fame entry, both from its certificate."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from monte_neo.research.project import ResearchProject


def handoff(project: ResearchProject, *, dossier_dir: str | Path | None = None, hall_dir: str | Path | None = None, author: str | None = None,
            name: str | None = None, category: str | None = None, tier: str = "C", framework: str = "generic") -> dict[str, Any]:
    """Write the dossier and/or the Hall entry of the frozen candidate (its certificate must exist: ``research certify``).

    Raises:
        ValueError: Nothing frozen, no certificate yet, the Hall entry lacks author, name or category, or the Hall refuses the entry.
    """
    fz = next(iter(project._entries("freeze")), None)
    if fz is None:
        raise ValueError("nothing is frozen: only a frozen champion is handed over")
    cert = project.certificate_of(fz["candidate"])
    if cert is None:
        raise ValueError("the champion has no certificate yet: run `research certify` first")
    out: dict[str, Any] = {"candidate": fz["candidate"], "certificate_id": cert.get("certificate_id")}
    if dossier_dir is not None:
        from monte_neo.dossier.build import build_dossier, write_dossier

        d = build_dossier(cert, framework=framework, meta={"name": name or project.name, "developer": author, "scope": "honest research project " + project.name, "tier": tier},
                          holdout=project.holdout_evidence())
        out["dossier"] = str(write_dossier(d, cert, dossier_dir))
    if hall_dir is not None:
        from monte_neo.hall.entry import certificate_sha256, check_entry, make_entry
        from monte_neo.hall.rules import load_rules

        if not (author and name and category):
            raise ValueError("a Hall entry needs author, name and category")
        rules = load_rules()
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        entry = make_entry(cert, author=author, strategy=name, category=category, tier=tier, submitted_at=date, rules=rules)
        errs = check_entry(entry, cert, rules, {}, draft=True)
        if errs:
            raise ValueError("; ".join(errs))
        root = Path(hall_dir)
        for sub, doc in (("entries", entry), ("certificates", cert)):
            (root / sub).mkdir(parents=True, exist_ok=True)
            (root / sub / f"{entry['id']}.json").write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
        out["hall"] = {"entry": entry["id"], "dir": str(root), "certificate_sha256": certificate_sha256(cert)}
    if dossier_dir is None and hall_dir is None:
        raise ValueError("give dossier_dir and/or hall_dir")
    return out


__all__ = ["handoff"]
