"""Run one zoo case through the verifier and say what it concluded."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
from mechanisms import HONEST, LEAKS
from zoo_lib import DISGUISES, build, compile_signal, dataset

from monte_neo.verify import verify_strategy

DYNAMIC = ("lookahead_truncation", "lookahead_perturbation")
ACCUSATION = (*DYNAMIC, "repaint_history", "external_data", "lookahead_static_lint", "implausible_accuracy", "data_independence", "determinism")
KNOWN_GAPS_FILE = Path(__file__).with_name("known_gaps.json")
DF = dataset()


def cases(level: str = "lite") -> list[tuple[str, str, str, bool, tuple]]:
    """(case id, mechanism id, disguise, leaks, row) for the chosen level (lite = direct form only)."""
    forms = ("direct",) if level == "lite" else DISGUISES
    out = []
    for leaks, table in ((True, LEAKS), (False, HONEST)):
        for row in table:
            for form in forms:
                out.append((f"{row[0]}/{form}", row[0], form, leaks, row))
    return out


def run_case(row: tuple, disguise: str) -> dict:
    expr, rule, pre = row[2], row[3], tuple(row[4]) if len(row) > 4 else ()
    source = build(expr, rule, disguise, pre)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = verify_strategy(DF, signal_fn=compile_signal(source), source=source)
    status = {c["id"]: c["status"] for c in report["checks"]}
    return {
        "verdict": report["verdict"],
        "dynamic": any(status.get(i) == "fail" for i in DYNAMIC),
        "lint": status.get("lookahead_static_lint") in ("warn", "fail"),
        "accused": [i for i in ACCUSATION if status.get(i) == "fail"],
    }


def known_gaps() -> dict[str, str]:
    return json.loads(KNOWN_GAPS_FILE.read_text(encoding="utf-8")) if KNOWN_GAPS_FILE.exists() else {}


def outcome_ok(leaks: bool, result: dict) -> bool:
    return result["dynamic"] if leaks else not result["accused"]


__all__ = ["ACCUSATION", "DYNAMIC", "cases", "known_gaps", "outcome_ok", "run_case"]
_ = np
