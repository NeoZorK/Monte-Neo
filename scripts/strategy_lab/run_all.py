"""Run the Strategy Lab stages for all ideas, resumable after a crash or a power cut.

    python scripts/strategy_lab/run_all.py --stages prepare,discovery,validation --jobs 2
    python scripts/strategy_lab/run_all.py --stages holdout --only NAME      # only frozen+committed candidates
    python scripts/strategy_lab/run_all.py --status                          # table, no work

State lives in strategy_lab/work/state.json (written atomically); finished stages are skipped, a stage that was running when
the process died is redone. Log: strategy_lab/logs/run_all.log. Stop with Ctrl-C or kill: nothing is corrupted.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import labcore as lc
from labstages import STAGES, now

ORDER = ["prepare", "discovery", "validation", "holdout"]
STATE, LOG, LOCK = lc.WORK / "state.json", lc.LAB / "logs" / "run_all.log", lc.WORK / "run_all.lock"


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{now()} {msg}\n")


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


_LOCK = threading.Lock()


def save_state(st: dict) -> None:
    with _LOCK:  # worker threads share one state dict; write atomically so a power cut never leaves half a file
        lc.WORK.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, indent=1))
        os.replace(tmp, STATE)


def free_gb() -> float:
    """Free + inactive RAM in GB (macOS vm_stat, Linux /proc/meminfo); 99 if unknown."""
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
            page = int(out.split("page size of")[1].split()[0])
            val = {l.split(":")[0]: int(l.split(":")[1].strip(" .\n")) for l in out.splitlines()[1:] if ":" in l}
            return (val["Pages free"] + val["Pages inactive"]) * page / 2**30
        for l in open("/proc/meminfo"):
            if l.startswith("MemAvailable"):
                return int(l.split()[1]) / 2**20
    except Exception:  # noqa: BLE001 - monitoring must never stop the run
        pass
    return 99.0


def take_lock() -> None:
    lc.WORK.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            os.kill(int(LOCK.read_text()), 0)
            sys.exit(f"another run_all.py is running (pid {LOCK.read_text()}); remove {LOCK} if it is stale")
        except (ProcessLookupError, ValueError):
            pass  # stale lock from a killed run
    LOCK.write_text(str(os.getpid()))


def status(names: list[str], st: dict) -> None:
    print(f"{'idea':<24}" + "".join(f"{s:<13}" for s in ORDER))
    for n in names:
        print(f"{n:<24}" + "".join(f"{st.get(n, {}).get(s, {}).get('status', '-'):<13}" for s in ORDER))


def run_one(name: str, stage: str, threads: int, min_free: float) -> dict:
    while free_gb() < min_free:  # RAM guard: wait instead of swapping
        log(f"wait: free RAM {free_gb():.1f} GB < {min_free} GB ({name}/{stage})")
        time.sleep(20)
    t0 = time.time()
    (lc.RES / name).mkdir(parents=True, exist_ok=True)
    rec = STAGES[stage](name, threads)
    rec["finished_at"], rec["seconds"] = now(), round(time.time() - t0, 1)
    tmp = lc.RES / name / f"{stage}.tmp"
    tmp.write_text(json.dumps(rec, indent=1, default=str))
    os.replace(tmp, lc.RES / name / f"{stage}.json")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stages", default="prepare,discovery,validation")
    ap.add_argument("--only", help="comma separated idea names")
    ap.add_argument("--jobs", type=int, default=2, help="ideas processed in parallel (default 2)")
    ap.add_argument("--threads", type=int, default=2, help="BLAS/numba threads per job (default 2)")
    ap.add_argument("--min-free-gb", type=float, default=2.0, help="wait while free RAM is below this (default 2)")
    ap.add_argument("--redo", action="store_true", help="redo finished stages (never allowed for holdout)")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    names = [n for n in lc.names() if not a.only or n in a.only.split(",")]
    st = load_state()
    if a.status:
        status(names, st)
        return 0
    stages = a.stages.split(",")
    if "holdout" in stages and a.redo:
        sys.exit("the holdout is never redone")
    take_lock()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    for n in st:  # a stage 'running' belongs to a dead process
        for s, v in st[n].items():
            if v.get("status") == "running":
                v["status"] = "pending"
    todo = {n: [s for s in stages if a.redo or st.get(n, {}).get(s, {}).get("status") != "done"] for n in names}
    total, done, t0, errors = sum(len(v) for v in todo.values()), 0, time.time(), []
    log(f"start stages={stages} ideas={len(names)} todo={total} jobs={a.jobs}")

    def worker(n: str) -> tuple[str, list[str]]:
        for s in todo[n]:
            st.setdefault(n, {})[s] = {"status": "running", "since": now()}
            save_state(st)
            try:
                rec = run_one(n, s, a.threads, a.min_free_gb)
                st[n][s] = {"status": "done", "at": rec["finished_at"], "seconds": rec["seconds"], "verdict": rec.get("verdict")}
                log(f"done {n}/{s} {rec['seconds']}s verdict={rec.get('verdict')}")
            except BaseException as e:  # noqa: BLE001 - record and move on to the next idea
                st[n][s] = {"status": "error", "error": repr(e)[:300]}
                log(f"ERROR {n}/{s}: {traceback.format_exc()[-800:]}")
                save_state(st)
                return n, [f"{s}: {e!r}"[:200]]
            save_state(st)
        return n, []

    try:
        with ThreadPoolExecutor(a.jobs) as ex:
            futs = {ex.submit(worker, n): n for n in names if todo[n]}
            for f in as_completed(futs):
                n, errs = f.result()
                errors += [f"{n} {e}" for e in errs]
                done += len(todo[n])
                el = time.time() - t0
                eta = el / max(done, 1) * (total - done)
                bar = "#" * (30 * done // max(total, 1))
                eta_t = time.strftime("%H:%M", time.localtime(time.time() + eta))
                print(f"\r[{bar:<30}] {done}/{total} stages  elapsed {el:5.0f}s  ETA {eta:5.0f}s (about {eta_t})", end="", flush=True)
    finally:
        save_state(st)
        LOCK.unlink(missing_ok=True)
    print()
    status(names, st)
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
