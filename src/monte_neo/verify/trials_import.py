"""Honest ``n_trials`` imported from experiment trackers on disk (offline, no network, no keys).

The Deflated Sharpe needs the number of variants tried. Researchers already log every run in a
tracker, so the count is read from its files instead of being declared. Supported specs:

* ``mlflow:<mlruns dir>[:<experiment>]`` or ``mlflow:sqlite:///<db>[:<experiment>]``
* ``optuna:sqlite:///<db>[:<study>]``
* ``wandb:<export.csv>``, ``csv:<file.csv>`` (or a bare ``*.csv`` path)
* ``ledger:<path>``: distinct variants in a Monte-Neo ledger

Deleted runs were still tried: they are counted and reported separately.
"""

from __future__ import annotations

import csv
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from monte_neo.verify.checks import check


def _result(source: str, location: str, count: int, details: dict[str, Any]) -> dict[str, Any]:
    return {"source": source, "location": location, "count": int(count), "details": details}


def _split_name(rest: str) -> tuple[str, str | None]:
    """Split ``<path>[:<name>]``; a path that exists as a whole has no name part."""
    if Path(rest).exists() or ":" not in rest:
        return rest, None
    path, name = rest.rsplit(":", 1)
    return path, (name or None)


def _sqlite_ro(rest: str) -> tuple[sqlite3.Connection, str, str | None]:
    """Open ``sqlite:///<db>[:<name>]`` read-only; returns (connection, db path, name)."""
    body = rest[len("sqlite:///"):]
    path, name = _split_name(body)
    if not Path(path).is_file():
        raise ValueError(f"sqlite database not found: {path}")
    conn = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)
    return conn, path, name


def _meta(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        if ":" in line and not line.startswith((" ", "-", "#")):
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip().strip("'\"")
    return out


def _pick(options: dict[str, str], wanted: str | None, what: str, where: str) -> str:
    """Pick an id from ``{id: name}`` by id or name; error with the list when ambiguous or unknown."""
    plural = "studies" if what == "study" else f"{what}s"
    listing = ", ".join(f"{name!r} (id {key})" for key, name in sorted(options.items()))
    if not options:
        raise ValueError(f"no {what} found in {where}")
    if wanted is None:
        if len(options) == 1:
            return next(iter(options))
        raise ValueError(f"several {plural} in {where}, name one (append ':<name>'): {listing}")
    for key, name in options.items():
        if wanted in (key, name):
            return key
    raise ValueError(f"{what} {wanted!r} not found in {where}; available: {listing}")


def _mlflow_files(root: Path, wanted: str | None) -> dict[str, Any]:
    if not root.is_dir():
        raise ValueError(f"MLflow directory not found: {root}")
    exps = {}
    for d in root.iterdir():
        if d.is_dir() and (d / "meta.yaml").is_file() and not d.name.startswith("."):
            exps[d.name] = _meta(d / "meta.yaml").get("name", d.name)
    exp_id = _pick(exps, wanted, "experiment", str(root))
    stages: Counter[str] = Counter()
    for run in (root / exp_id).iterdir():
        if run.is_dir() and (run / "meta.yaml").is_file():
            stages[_meta(run / "meta.yaml").get("lifecycle_stage", "active")] += 1
    return _result("mlflow", str(root), sum(stages.values()),
                   {"experiment": exps[exp_id], "experiment_id": exp_id, "deleted": stages.get("deleted", 0), "by_stage": dict(stages)})


def _mlflow_sqlite(rest: str) -> dict[str, Any]:
    conn, path, wanted = _sqlite_ro(rest)
    with closing(conn):
        try:
            exps = {str(i): str(n) for i, n in conn.execute("SELECT experiment_id, name FROM experiments")}
            exp_id = _pick(exps, wanted, "experiment", path)
            rows = conn.execute("SELECT lifecycle_stage, COUNT(*) FROM runs WHERE experiment_id = ? GROUP BY lifecycle_stage", (int(exp_id),)).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"{path} is not an MLflow tracking database: {exc}") from exc
    stages = {str(s): int(n) for s, n in rows}
    return _result("mlflow", path, sum(stages.values()),
                   {"experiment": exps[exp_id], "experiment_id": exp_id, "deleted": stages.get("deleted", 0), "by_stage": stages})


def _optuna(rest: str) -> dict[str, Any]:
    if not rest.startswith("sqlite:///"):
        raise ValueError("optuna spec must look like optuna:sqlite:///path/study.db[:<study name>]")
    conn, path, wanted = _sqlite_ro(rest)
    with closing(conn):
        try:
            studies = {str(i): str(n) for i, n in conn.execute("SELECT study_id, study_name FROM studies")}
            sid = _pick(studies, wanted, "study", path)
            rows = conn.execute("SELECT state, COUNT(*) FROM trials WHERE study_id = ? GROUP BY state", (int(sid),)).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"{path} is not an Optuna storage database: {exc}") from exc
    states = {str(s): int(n) for s, n in rows}
    return _result("optuna", path, sum(states.values()), {"study": studies[sid], "by_state": states})


def _csv(source: str, path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.is_file():
        raise ValueError(f"CSV file not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = [r for r in csv.reader(handle) if any(c.strip() for c in r)]
    if not rows:
        raise ValueError(f"CSV file is empty: {path}")
    header, body = rows[0], rows[1:]
    details: dict[str, Any] = {"columns": len(header)}
    state_col = next((i for i, h in enumerate(header) if h.strip().lower() == "state"), None)
    if source == "wandb" and state_col is not None:
        details["by_state"] = dict(Counter((r[state_col] if state_col < len(r) else "").strip() for r in body))
    return _result(source, str(path), len(body), details)


def _ledger(path_str: str) -> dict[str, Any]:
    from monte_neo.verify.ledger import Ledger

    path = Path(path_str)
    if not path.is_file():
        raise ValueError(f"ledger not found: {path}")
    ledger = Ledger(path)
    entries = ledger.entries()
    variants = {e["variant"] for e in entries if e.get("variant")}
    return _result("ledger", str(path), len(variants), {"entries": len(entries), "chain_ok": ledger.check()["ok"]})


def count_trials(spec: str) -> dict[str, Any]:
    """Count the variants tried, as recorded by an experiment tracker.

    Args:
        spec: ``mlflow:...``, ``optuna:sqlite:///...``, ``wandb:file.csv``, ``csv:file.csv``,
            a bare ``*.csv`` path or ``ledger:path``.

    Returns:
        ``{"source", "location", "count", "details"}``.

    Raises:
        ValueError: On a bad spec, a missing path, or an ambiguous experiment/study.
    """
    spec = spec.strip()
    kind, sep, rest = spec.partition(":")
    kind = kind.lower()
    if not sep or kind not in {"mlflow", "optuna", "wandb", "csv", "ledger"}:
        if spec.lower().endswith(".csv"):
            return _csv("csv", spec)
        raise ValueError(f"unknown --trials-from spec {spec!r}: use mlflow:<mlruns>[:<experiment>], mlflow:sqlite:///<db>[:<experiment>], "
                         "optuna:sqlite:///<db>[:<study>], wandb:<export.csv>, csv:<file.csv> or ledger:<path>")
    if not rest:
        raise ValueError(f"empty location in {spec!r}")
    if kind == "mlflow":
        if rest.startswith("sqlite:///"):
            return _mlflow_sqlite(rest)
        path, name = _split_name(rest)
        return _mlflow_files(Path(path), name)
    if kind == "optuna":
        return _optuna(rest)
    if kind == "ledger":
        return _ledger(rest)
    return _csv(kind, rest)


def effective_n_trials(declared: int | None, counted: int | None, imported: int | None) -> int:
    """Largest of the declared, ledger-counted and imported numbers of trials (at least 1)."""
    return max([1] + [int(v) for v in (declared, counted, imported) if v is not None])


def trials_row(imported: dict[str, Any], declared: int | None, counted: int | None) -> dict[str, Any]:
    """Check row ``trials_imported``: the tracker count against the declared and counted ones."""
    n = imported["count"]
    label = imported["source"]
    exp = imported.get("details", {}).get("experiment") or imported.get("details", {}).get("study")
    what = f"{label} {exp!r}" if exp else label
    details = {**imported, "declared": declared, "counted": counted}
    if declared is not None and declared < n:
        return check("trials_imported", "statistics", "warn",
                     f"n_trials was declared as {declared} but {what} has {n} runs: the larger number is used", details)
    if counted is not None and counted < n:
        return check("trials_imported", "statistics", "warn",
                     f"the ledger counts {counted} variants but {what} has {n} runs: the larger number is used", details)
    return check("trials_imported", "statistics", "pass", f"{n} run(s) imported from {what}; declared and counted numbers cover it", details)


def trials_for_verify(spec: str, declared: int | None) -> tuple[int, dict[str, Any]]:
    """The ``n_trials`` to verify with and the ``trials_imported`` row, for the CLI and the MCP server.

    The row is context only (``info``): the larger count is already in ``n_trials``, which the certificate hashes,
    and a recheck has no tracker to read, so the row must not move the verdict.
    """
    imported = count_trials(spec)
    row = trials_row(imported, declared, None)
    row["status"] = "info"
    return effective_n_trials(declared, None, imported["count"]), row


__all__ = ["count_trials", "effective_n_trials", "trials_for_verify", "trials_row"]
