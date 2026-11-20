"""Strategy Lab control script: atomic state, resume rules, auto plan, resumable download, single instance, safe stop."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "strategy_lab"
sys.path.insert(0, str(SCRIPTS))
import fetch_data as fd  # noqa: E402
import lab  # noqa: E402


def test_atomic_write_and_corrupt_read(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    lab.atomic_write(p, '{"a": 1}')
    assert lab.read_json(p, None) == {"a": 1}
    assert not list(tmp_path.glob("*.tmp"))
    p.write_text("{half a fi")  # what a power cut would leave behind without atomic replace
    assert lab.read_json(p, {"d": 1}) == {"d": 1}
    assert (tmp_path / "s.json.bad").exists()
    assert lab.read_json(tmp_path / "missing.json", 5) == 5


@pytest.mark.parametrize(("cores", "ram", "machine", "ideas", "jobs"), [(8, 16, "arm64", 10, 2), (8, 16, "x86_64", 10, 1), (2, 4, "arm64", 10, 1), (16, 64, "arm64", 1, 1)])
def test_auto_plan(cores: int, ram: float, machine: str, ideas: int, jobs: int) -> None:
    j, t, d = lab.auto_plan(cores, ram, machine, ideas)
    assert j == jobs
    assert 1 <= t <= 4
    assert d >= 1


def test_state_progress_eta_and_restart_rules() -> None:
    st = {"a": {"prepare": {"status": "done", "seconds": 4}, "discovery": {"status": "running"}}, "b": {"prepare": {"status": "error"}}}
    assert lab.count_done(st, ["a", "b"]) == (1, 6)
    assert lab.eta_seconds(st, ["a", "b"], 1) == 20.0
    assert lab.eta_seconds({}, ["a"], 1) is None
    fixed_state, n = lab.normalize_state(st)
    assert n == 2
    assert fixed_state["a"] == {"prepare": {"status": "done", "seconds": 4}}  # finished work is kept, the rest is pending again
    assert lab.bar(15, 30).startswith("[" + "#" * 15 + "-" * 15)


def test_fetch_resumes_and_redownloads_damaged_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", "1,2,3\n")
    good = buf.getvalue()
    calls: list[str] = []

    def fake_get(url: str, tries: int = 8):
        calls.append(url)
        return None if url.endswith(".CHECKSUM") else good

    monkeypatch.setattr(fd, "get", fake_get)
    r1 = fd.fetch_one("spot/a.zip", tmp_path, {})
    assert r1["status"] == "ok"
    n = len(calls)
    assert fd.fetch_one("spot/a.zip", tmp_path, {"spot/a.zip": r1["sha256"]})["status"] == "cached" and len(calls) == n  # no network
    (tmp_path / "spot" / "a.zip").write_bytes(good[:20])  # cut in the middle of a write
    assert fd.fetch_one("spot/a.zip", tmp_path, {})["status"] == "ok" and len(calls) > n
    (tmp_path / "spot" / "a.zip").write_bytes(good)  # valid zip but not the hash in the manifest
    assert fd.fetch_one("spot/a.zip", tmp_path, {"spot/a.zip": "0" * 64})["status"] == "ok"


def test_fetch_reports_network_down_instead_of_crashing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def down(url: str, tries: int = 8):
        raise RuntimeError("network is down")

    monkeypatch.setattr(fd, "get", down)
    assert fd.fetch_one("spot/b.zip", tmp_path, {})["status"] == "error"


def test_single_instance_and_safe_stop(tmp_path: Path) -> None:
    """Second lab.py is refused (flock); SIGTERM stops the first one cleanly (rc 130) without losing the state files."""
    cmd = [sys.executable, str(SCRIPTS / "lab.py"), "--dry-run", "--plain", "--no-auto", "--home", str(tmp_path / "home")]
    p1 = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        lock = tmp_path / "home" / "work" / "lab.lock"
        end = time.time() + 120
        while time.time() < end and not (lock.exists() and lock.read_text().strip()):
            time.sleep(0.3)
        assert lock.read_text().strip() == str(p1.pid)
        p2 = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        assert p2.returncode == 3
        assert "already running" in p2.stdout
        assert (tmp_path / "home" / "DRY_RUN").exists()  # marked as a dry run
        p1.terminate()
        assert p1.wait(timeout=60) == 130
        assert json.loads((tmp_path / "home" / "work" / "lab_state.json").read_text())["mode"] == "idle"
    finally:
        if p1.poll() is None:
            os.kill(p1.pid, 9)


def test_dry_run_refuses_the_real_lab_folder() -> None:
    r = subprocess.run([sys.executable, str(SCRIPTS / "lab.py"), "--dry-run", "--home", str(SCRIPTS.parents[1] / "strategy_lab")], capture_output=True, text=True, timeout=120)
    assert r.returncode != 0
    assert "must not use the real" in r.stderr
