"""Trial import from MLflow, Optuna, W&B/CSV exports and a Monte-Neo ledger."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from monte_neo.verify.ledger import Ledger
from monte_neo.verify.trials_import import count_trials, effective_n_trials, trials_row


def _mlruns(root: Path, experiments: dict[str, tuple[str, list[str]]]) -> Path:
    for exp_id, (name, stages) in experiments.items():
        d = root / exp_id
        d.mkdir(parents=True)
        (d / "meta.yaml").write_text(f"artifact_location: file:///x\nexperiment_id: '{exp_id}'\nname: {name}\n")
        for i, stage in enumerate(stages):
            r = d / f"run{i:03d}"
            (r / "metrics").mkdir(parents=True)
            (r / "meta.yaml").write_text(f"run_id: run{i:03d}\nlifecycle_stage: {stage}\nstatus: 3\n")
    (root / ".trash").mkdir(exist_ok=True)
    return root


def test_mlflow_files_counts_deleted_separately(tmp_path: Path) -> None:
    root = _mlruns(tmp_path / "mlruns", {"1": ("alpha", ["active"] * 3 + ["deleted"] * 2)})
    out = count_trials(f"mlflow:{root}")
    assert out["count"] == 5 and out["details"]["deleted"] == 2 and out["details"]["experiment"] == "alpha"


def test_mlflow_files_experiment_selection_and_ambiguity(tmp_path: Path) -> None:
    root = _mlruns(tmp_path / "mlruns", {"1": ("alpha", ["active"] * 3), "2": ("beta", ["active"] * 7)})
    with pytest.raises(ValueError, match="several experiments.*'alpha'.*'beta'"):
        count_trials(f"mlflow:{root}")
    assert count_trials(f"mlflow:{root}:beta")["count"] == 7
    assert count_trials(f"mlflow:{root}:1")["count"] == 3
    with pytest.raises(ValueError, match="not found"):
        count_trials(f"mlflow:{root}:gamma")


def test_mlflow_sqlite(tmp_path: Path) -> None:
    db = tmp_path / "mlflow.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE experiments (experiment_id INTEGER, name TEXT)")
    con.execute("CREATE TABLE runs (run_uuid TEXT, experiment_id INTEGER, lifecycle_stage TEXT)")
    con.executemany("INSERT INTO experiments VALUES (?, ?)", [(0, "Default"), (1, "x")])
    con.executemany("INSERT INTO runs VALUES (?, ?, ?)", [(f"r{i}", 1, "deleted" if i < 2 else "active") for i in range(6)] + [("z", 0, "active")])
    con.commit()
    con.close()
    out = count_trials(f"mlflow:sqlite:///{db}:x")
    assert out["count"] == 6 and out["details"]["deleted"] == 2
    with pytest.raises(ValueError, match="several experiments"):
        count_trials(f"mlflow:sqlite:///{db}")


def test_optuna_counts_all_states_and_is_read_only(tmp_path: Path) -> None:
    db = tmp_path / "study.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE studies (study_id INTEGER, study_name TEXT)")
    con.execute("CREATE TABLE trials (trial_id INTEGER, study_id INTEGER, state TEXT)")
    con.execute("INSERT INTO studies VALUES (1, 's1')")
    con.executemany("INSERT INTO trials VALUES (?, 1, ?)", [(i, s) for i, s in enumerate(["COMPLETE"] * 4 + ["PRUNED"] * 3 + ["FAIL"])])
    con.commit()
    con.close()
    before = db.read_bytes()
    out = count_trials(f"optuna:sqlite:///{db}")
    assert out["count"] == 8 and out["details"]["by_state"] == {"COMPLETE": 4, "PRUNED": 3, "FAIL": 1}
    assert db.read_bytes() == before
    con = sqlite3.connect(db)
    con.execute("INSERT INTO studies VALUES (2, 's2')")
    con.commit()
    con.close()
    with pytest.raises(ValueError, match="several studies.*'s1'.*'s2'"):
        count_trials(f"optuna:sqlite:///{db}")
    assert count_trials(f"optuna:sqlite:///{db}:s2")["count"] == 0


def test_wandb_and_csv(tmp_path: Path) -> None:
    f = tmp_path / "runs.csv"
    f.write_text("Name,State,lr\na,finished,0.1\nb,crashed,0.2\n\nc,finished,0.3\n")
    w = count_trials(f"wandb:{f}")
    assert w["count"] == 3 and w["details"]["by_state"] == {"finished": 2, "crashed": 1}
    assert count_trials(f"csv:{f}")["count"] == 3
    assert count_trials(str(f))["source"] == "csv"


def test_ledger_distinct_variants(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    ledger = Ledger(path)
    for v in ("a", "b", "a"):
        ledger.record(variant=v, data_id="d", sharpe=1.0, verdict="pass", certificate_id="c")
    out = count_trials(f"ledger:{path}")
    assert out["count"] == 2 and out["details"]["chain_ok"]


@pytest.mark.parametrize("spec", ["nope:thing", "something", "mlflow:/no/such/dir", "optuna:sqlite:////no/such.db", "csv:/no/such.csv", "ledger:/no/such", "wandb:", "optuna:/x"])
def test_bad_specs_raise_helpful_errors(spec: str) -> None:
    with pytest.raises(ValueError):
        count_trials(spec)


def test_unknown_prefix_message_lists_forms() -> None:
    with pytest.raises(ValueError, match="mlflow:.*optuna:.*wandb:"):
        count_trials("foo:bar")


def test_row_and_effective() -> None:
    imp = {"source": "mlflow", "location": "x", "count": 412, "details": {"experiment": "x"}}
    row = trials_row(imp, 12, None)
    assert row["id"] == "trials_imported" and row["status"] == "warn" and "declared as 12" in row["summary"] and "412" in row["summary"]
    assert trials_row(imp, 500, 450)["status"] == "pass"
    assert trials_row(imp, None, 100)["status"] == "warn"
    assert effective_n_trials(12, 30, 412) == 412
    assert effective_n_trials(None, None, None) == 1


def test_raytune_counts_trial_directories(tmp_path: Path) -> None:
    root = tmp_path / "exp"
    for i in range(4):
        (root / f"trainable_{i}").mkdir(parents=True)
        (root / f"trainable_{i}" / ("params.json" if i % 2 else "result.json")).write_text("{}")
    (root / "driver_artifacts").mkdir()
    out = count_trials(f"raytune:{root}")
    assert out["source"] == "raytune" and out["count"] == 4


def test_raytune_experiment_state_file(tmp_path: Path) -> None:
    import json

    root = tmp_path / "exp"
    root.mkdir()
    (root / "experiment_state-2026-01-01_00-00-00.json").write_text(json.dumps({"trial_data": [["a", "b"]] * 7}))
    assert count_trials(f"raytune:{root}")["count"] == 7


def test_raytune_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        count_trials(f"raytune:{tmp_path / 'missing'}")
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError, match="no Ray Tune trials"):
        count_trials(f"raytune:{tmp_path / 'empty'}")
