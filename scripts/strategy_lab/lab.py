"""Strategy Lab: ONE entry point to run, watch and control the whole pipeline (data -> prepare -> discovery -> validation).

    uv run python scripts/strategy_lab/lab.py                       # interactive screen (keys at the bottom)
    nohup uv run python scripts/strategy_lab/lab.py --plain > strategy_lab/logs/lab.out 2>&1 &   # nohup / ssh, no TTY needed
    uv run python scripts/strategy_lab/lab.py --dry-run             # whole pass on tiny synthetic stubs (scratch folder, never results/)
    uv run python scripts/strategy_lab/lab.py --self-test           # dry-run + kill -9 resume checks; exit code 0 = all good

Keys: r run/continue  p pause/resume  x safe stop  f retry failed  a analyze  l longer log  h holdout (confirmation)  q quit.
Ctrl-C = safe stop: the child gets SIGTERM, progress lives in atomic files, the next start continues. The holdout is never
started automatically: only key h, only a candidate frozen in a git commit, only after typing the confirmation phrase.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import platform
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
PIPE = ["prepare", "discovery", "validation"]
MAX_ATTEMPTS = 20
KEYS = "[r]un [p]ause [x]stop [f]retry-failed [a]nalyze [l]og [h]oldout [q]uit"


# ------------------------------------------------------------------ small helpers (pure, unit-tested)
def atomic_write(path: Path, text: str) -> None:
    """Write a file so that a power cut leaves either the old or the new content, never half of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_json(path: Path, default):
    """Tolerant read: a missing or corrupt file gives the default (a corrupt one is kept aside as .bad)."""
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default
    except (ValueError, OSError):
        with contextlib.suppress(OSError):
            os.replace(path, path.with_name(path.name + ".bad"))
        return default


def auto_plan(cores: int, ram_gb: float, machine: str, n_ideas: int) -> tuple[int, int, int]:
    """(jobs, threads per job, download threads). Old Intel Mac with HDD -> one job; M1 16 GB -> two jobs."""
    by_ram = max(1, int((ram_gb - 4) // 3))
    jobs = max(1, min(n_ideas, cores // 4 or 1, by_ram))
    old_intel = machine in ("x86_64", "i386")
    if old_intel:
        jobs = 1
    threads = max(1, min(4, cores // (jobs * 2)))
    return jobs, threads, 2 if old_intel else 4


def count_done(state: dict, names: list[str]) -> tuple[int, int]:
    done = sum(1 for n in names for s in PIPE if state.get(n, {}).get(s, {}).get("status") == "done")
    return done, len(names) * len(PIPE)


def eta_seconds(state: dict, names: list[str], jobs: int) -> float | None:
    secs = [state[n][s]["seconds"] for n in names for s in PIPE if state.get(n, {}).get(s, {}).get("status") == "done" and "seconds" in state[n][s]]
    done, total = count_done(state, names)
    return None if not secs else (total - done) * (sum(secs) / len(secs)) / max(jobs, 1)


def normalize_state(state: dict) -> tuple[dict, int]:
    """Before a (re)start a stage that was 'running' or ended in 'error' is simply pending again."""
    fixed = 0
    for n in state:
        for s in list(state[n]):
            if state[n][s].get("status") in ("running", "error"):
                del state[n][s]
                fixed += 1
    return state, fixed


def bar(done: int, total: int, width: int = 30) -> str:
    k = width * done // max(total, 1)
    return "[" + "#" * k + "-" * (width - k) + f"] {done}/{total}"


def hms(sec: float | None) -> str:
    return "?" if sec is None else f"{int(sec // 3600):d}:{int(sec % 3600 // 60):02d}:{int(sec % 60):02d}"


def tail(path: Path, n: int) -> list[str]:
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 16384))
            return f.read().decode(errors="replace").replace("\r", "\n").splitlines()[-n:]
    except OSError:
        return []


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
    except Exception:  # noqa: BLE001 - monitoring must never stop the run
        return ""


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Adopted:
    """A child left running by a previous lab.py that died (kill -9, closed terminal): keep watching it instead of killing good work."""

    def __init__(self, pid: int):
        self.pid = pid

    def poll(self):
        return None if pid_alive(self.pid) else 0

    def wait(self):
        while pid_alive(self.pid):
            time.sleep(0.2)


def make_stubs(home: Path) -> None:
    """Tiny synthetic daily series for every symbol: ONLY for checking the control logic, never real data."""
    import zlib

    import fetch_data as fd
    import numpy as np
    import pandas as pd

    out = home / "data" / "processed"
    out.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range("2017-08-17", "2026-06-30", freq="1D", tz="UTC")
    for kind, syms in (("spot", fd.SPOT), ("perp", fd.PERP), ("fund", fd.PERP)):
        for s in syms:
            rng = np.random.default_rng(zlib.crc32(f"{kind}{s}".encode()))
            if kind == "fund":
                df = pd.DataFrame({"timestamp": idx, "funding": 0.0003 + rng.normal(0, 0.0002, len(idx))})
            else:
                c = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.03, len(idx))))
                o = np.r_[c[0], c[:-1]]
                df = pd.DataFrame({"timestamp": idx, "open": o, "high": np.maximum(o, c) * 1.01, "low": np.minimum(o, c) * 0.99, "close": c,
                                   "volume": rng.uniform(1e3, 2e3, len(idx))})
            df.to_parquet(out / f"{kind}_{s}_1d.parquet")
    atomic_write(home / "data" / "manifest.json", json.dumps({"stub": True, "complete": True, "series": {"stub": 1}}))


# ------------------------------------------------------------------ the lab
class Lab:
    def __init__(self, a: argparse.Namespace):
        import labcore as lc
        import run_all as ra

        self.lc, self.ra, self.a = lc, ra, a
        self.dry = bool(a.dry_run or a.self_test)
        self.home = lc.LAB
        self.names = lc.names()
        self.lab_p = lc.WORK / "lab_state.json"
        self.logs = lc.LAB / "logs"
        self.mode, self.child, self.kind = "idle", None, ""
        self.attempts, self.retry_at, self.launch_done = 0, 0.0, 0
        self.t0, self.quit, self.sig = time.time(), False, 0
        self.stop_deadline = 0.0
        self.log_lines = 6
        self.cores = os.cpu_count() or 1
        self.ram_total = self._ram_total()
        jobs, thr, dl = auto_plan(self.cores, self.ram_total, platform.machine(), len(self.names))
        self.jobs, self.threads, self.dl = a.jobs or jobs, a.threads or thr, a.download_threads or dl
        self._res: dict = {}
        self._res_t = 0.0
        self.final_printed = False

    # ---- files / logging
    def log(self, msg: str) -> None:
        self.logs.mkdir(parents=True, exist_ok=True)
        with (self.logs / "lab.log").open("a") as f:
            f.write(f"{time.strftime('%F %T')} {msg}\n")

    def lab_state(self) -> dict:
        return read_json(self.lab_p, {"attempts": 0, "runtime": 0.0})

    def save_lab(self) -> None:
        st = self.lab_state()
        st.update({"attempts": self.attempts, "mode": self.mode, "updated": time.strftime("%F %T")})
        atomic_write(self.lab_p, json.dumps(st, indent=1))

    def state(self) -> dict:
        return read_json(self.ra.STATE, {})

    def data_ready(self) -> bool:
        m = read_json(self.home / "data" / "manifest.json", {})
        import fetch_data as fd

        proc = self.home / "data" / "processed"
        need = [f"{k}_{s}_1d.parquet" for k, syms in (("spot", fd.SPOT), ("perp", fd.PERP), ("fund", fd.PERP)) for s in syms]
        # round 2 needs history from 2017-08 and every listed series: an older 2019+ download is NOT enough
        return bool(m.get("complete")) and (m.get("stub") or str(m.get("range", ["9"])[0]) <= "2017-08") and all((proc / n).exists() for n in need)

    def pipeline_done(self) -> bool:
        d, t = count_done(self.state(), self.names)
        return d == t

    # ---- process control
    def _ram_total(self) -> float:
        try:
            if sys.platform == "darwin":
                return int(sh(["sysctl", "-n", "hw.memsize"]).strip()) / 2**30
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
        except Exception:  # noqa: BLE001
            return 16.0

    def adopt_orphans(self) -> None:
        """A previous lab.py that died hard leaves its child running (own session): keep supervising that child."""
        pf = self.lc.WORK / "child.pid"
        info = read_json(pf, {})
        pid = info.get("pid")
        cmd = sh(["ps", "-p", str(pid), "-o", "command="]) if pid else ""
        if pid and pid_alive(pid) and (not cmd.strip() or re.search(r"run_all|fetch_data", cmd)):  # no ps available -> trust the pid file
            self.log(f"orphan child {pid} ({info.get('kind')}) from a previous session: adopted, waiting for it")
            self.child, self.kind, self.mode = Adopted(pid), info.get("kind", "pipeline"), "running"
            self.launch_done = count_done(self.state(), self.names)[0]
        else:
            pf.unlink(missing_ok=True)

    @staticmethod
    def terminate(pid: int, wait: float = 20) -> None:
        for sig in (signal.SIGCONT, signal.SIGTERM):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pid, sig)
        end = time.time() + wait
        while time.time() < end and pid_alive(pid):
            time.sleep(0.3)
        if pid_alive(pid):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pid, signal.SIGKILL)

    def command(self) -> tuple[str, list[str]] | None:
        if not self.data_ready():
            return "data", [sys.executable, str(HERE / "fetch_data.py"), "--threads", str(self.dl)]
        if not self.pipeline_done():
            return "pipeline", [sys.executable, str(HERE / "run_all.py"), "--stages", ",".join(PIPE), "--jobs", str(self.jobs),
                                "--threads", str(self.threads)]
        return None

    def start_child(self) -> None:
        cmd = self.command()
        if cmd is None:
            self.mode = "done"
            return
        self.kind, argv = cmd
        st, fixed = normalize_state(self.state())
        if fixed:
            atomic_write(self.ra.STATE, json.dumps(st, indent=1))
        self.launch_done = count_done(st, self.names)[0]
        self.logs.mkdir(parents=True, exist_ok=True)
        out = (self.logs / "lab_child.log").open("a")
        out.write(f"\n=== {time.strftime('%F %T')} {self.kind} attempt {self.attempts + 1} ===\n")
        out.flush()
        self.child = subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, cwd=REPO)
        atomic_write(self.lc.WORK / "child.pid", json.dumps({"pid": self.child.pid, "kind": self.kind}))
        self.mode = "running"
        self.log(f"started {self.kind} pid={self.child.pid} jobs={self.jobs} threads={self.threads}")

    def poll(self) -> None:
        now = time.time()
        if self.mode == "running" and self.child:
            rc = self.child.poll()
            if rc is None:
                return
            self.child = None
            (self.lc.WORK / "child.pid").unlink(missing_ok=True)
            progress = count_done(self.state(), self.names)[0] > self.launch_done or (self.kind == "data" and rc == 0)
            self.log(f"{self.kind} exited rc={rc} progress={progress}")
            if rc == 0:
                self.attempts = 0
                if self.command():
                    self.start_child()
                else:
                    self.mode = "done"
            else:
                self.attempts = 0 if progress else self.attempts + 1
                if self.attempts >= MAX_ATTEMPTS:
                    self.mode = "failed"
                else:
                    self.mode, self.retry_at = "retry", now + min(60, 5 * 2 ** self.attempts)
            self.save_lab()
        elif self.mode == "retry" and now >= self.retry_at:
            self.start_child()
        elif self.mode == "stopping" and self.child:
            if self.child.poll() is not None or now > self.stop_deadline:
                if self.child.poll() is None:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(self.child.pid, signal.SIGKILL)
                    self.child.wait()
                self.child = None
                (self.lc.WORK / "child.pid").unlink(missing_ok=True)
                self.mode = "idle"
                self.log("safe stop done")
                self.save_lab()

    # ---- user actions
    def act_run(self) -> None:
        if self.mode in ("idle", "failed", "done", "retry"):
            self.attempts = 0
            self.start_child()
            self.save_lab()

    def act_pause(self) -> None:
        if self.mode == "running" and self.child:
            os.killpg(self.child.pid, signal.SIGSTOP)
            self.mode = "paused"
            self.log("paused")
        elif self.mode == "paused" and self.child:
            os.killpg(self.child.pid, signal.SIGCONT)
            self.mode = "running"
            self.log("resumed")

    def act_stop(self) -> None:
        if self.child and self.mode in ("running", "paused"):
            for sig in (signal.SIGCONT, signal.SIGTERM):
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(self.child.pid, sig)
            self.mode, self.stop_deadline = "stopping", time.time() + 25
            self.log("safe stop requested")
        elif self.mode == "retry":
            self.mode = "idle"

    def act_retry_failed(self) -> None:
        if self.child:
            return
        st, fixed = normalize_state(self.state())
        atomic_write(self.ra.STATE, json.dumps(st, indent=1))
        self.log(f"retry failed: {fixed} stage(s) reset")
        self.act_run()

    def act_analyze(self) -> str:
        r = subprocess.run([sys.executable, str(HERE / "analyze.py")], capture_output=True, text=True, timeout=300, cwd=REPO)
        self.log(f"analyze rc={r.returncode} {r.stdout.strip()[-200:]} {r.stderr.strip()[-300:]}")
        return (r.stdout + r.stderr).strip()

    def act_holdout(self, plain: bool) -> None:
        """Only here, never automatic: a candidate frozen in a git commit, an explicit typed confirmation."""
        if self.dry or plain:
            print("holdout: not available in dry-run or plain mode")
            return
        if not self.pipeline_done():
            print("holdout: finish validation for all ideas first")
            return
        import labstages as ls

        ok = []
        for n in self.names:
            if (self.lc.RES / n / "holdout_opening.json").exists():
                print(f"  {n}: holdout already opened (one-shot)")
                continue
            try:
                ls.frozen_ok(n)
                ok.append(n)
                print(f"  {n}: frozen and committed")
            except Exception as e:  # noqa: BLE001
                print(f"  {n}: {str(e)[:110]}")
        if not ok:
            print("No frozen candidate. Choose ONE: python scripts/strategy_lab/freeze.py NAME ; git commit ; then key h.")
            return
        name = input("Candidate to open the sealed holdout for (empty = cancel): ").strip()
        if name not in ok:
            print("cancelled")
            return
        if input(f"The holdout can be opened ONCE and cannot be tuned afterwards. Type exactly: OPEN HOLDOUT {name}\n> ").strip() != f"OPEN HOLDOUT {name}":
            print("cancelled")
            return
        self.log(f"HOLDOUT opened for {name} by menu")
        r = subprocess.run([sys.executable, str(HERE / "run_all.py"), "--stages", "holdout", "--only", name, "--jobs", "1", "--threads", str(self.threads)], cwd=REPO)
        print(f"run_all rc={r.returncode}\n{self.act_analyze()}\nCommit strategy_lab/results and examples/strategies/{name}/report.md as the reviewed case.")

    def shutdown(self) -> None:
        if self.child and self.child.poll() is None:
            self.act_stop()
            while self.mode == "stopping":
                self.poll()
                time.sleep(0.3)
        self.save_lab()

    # ---- monitoring and screen
    def resources(self) -> dict:
        if time.time() - self._res_t < 5 and self._res:
            return self._res
        r: dict = {"warn": []}
        free = self.ra.free_gb()
        r["ram"] = f"RAM free {free:.1f}/{self.ram_total:.0f} GB"
        r["cpu"] = f"load {os.getloadavg()[0]:.1f}/{self.cores}"
        du = shutil.disk_usage(self.home if self.home.exists() else REPO)
        r["disk"] = f"disk free {du.free / 2**30:.0f} GB"
        if du.free < 5 * 2**30:
            r["warn"].append(f"LOW DISK: {du.free / 2**30:.1f} GB free")
        if free < 1.5:
            r["warn"].append(f"LOW RAM: {free:.1f} GB free, run_all waits for memory")
        pw = "power n/a"
        if sys.platform == "darwin":
            b = sh(["pmset", "-g", "batt"])
            m = re.search(r"drawing from '([^']+)'", b)
            p = re.search(r"(\d+)%", b)
            if m:
                pw = m.group(1) + (f" {p.group(1)}%" if p else "")
                if "Battery" in m.group(1) and p and int(p.group(1)) < 25:
                    r["warn"].append("ON BATTERY < 25%: connect power")
            t = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", sh(["pmset", "-g", "therm"]))
            r["therm"] = f"CPU limit {t.group(1)}%" if t else "no thermal limit"
            if t and int(t.group(1)) < 100:
                r["warn"].append(f"THERMAL THROTTLING: CPU at {t.group(1)}% (temperature itself needs sudo)")
        r["power"] = pw
        self._res, self._res_t = r, time.time()
        return r

    @staticmethod
    def _since(v: dict) -> float:
        try:
            return datetime.fromisoformat(v["since"]).timestamp()
        except (KeyError, ValueError):
            return time.time()

    def cell(self, st: dict, n: str, s: str, color: bool) -> str:
        v = st.get(n, {}).get(s, {})
        k = v.get("status")
        txt = {"done": f"ok {str(v.get('verdict') or '')[:10]}".strip(), "running": f"RUN {int(time.time() - self._since(v))}s",
               "error": "ERROR"}.get(k, "-")
        c = {"done": "32", "running": "33", "error": "31"}.get(k)
        return f"\x1b[{c}m{txt:<15}\x1b[0m" if color and c else f"{txt:<15}"

    def render(self, color: bool, full: bool = True) -> str:
        st = self.state()
        done, total = count_done(st, self.names)
        res = self.resources()
        eta = eta_seconds(st, self.names, self.jobs)
        run = self.lab_state().get("runtime", 0.0) + (time.time() - self.t0)
        out = []
        if self.dry:
            out.append(f"*** DRY-RUN: synthetic stub data, results are NOT real and go to {self.home} (never to results/) ***")
        phase = self.kind or ("data" if not self.data_ready() else "pipeline")
        extra = f" retry in {max(0, int(self.retry_at - time.time()))}s (attempt {self.attempts}/{MAX_ATTEMPTS})" if self.mode == "retry" else ""
        out.append(f"Strategy Lab | mode: {self.mode.upper()}{extra} | phase: {phase} | jobs={self.jobs} threads={self.threads} | up {hms(run)}")
        if not self.data_ready():
            pr = read_json(self.home / "data" / "progress.json", {})
            d, t = pr.get("done", 0), pr.get("total", 0)
            e = (time.time() - pr["t0"]) / d * (t - d) if d and "t0" in pr else None
            out.append(f"data     {bar(d, t)}  ETA {hms(e)}  {pr.get('stat', '')}")
        clock = f" (about {time.strftime('%H:%M', time.localtime(time.time() + eta))})" if eta else ""
        out.append(f"pipeline {bar(done, total)}  ETA {hms(eta)}{clock}")
        out.append(f"{res['ram']} | {res['cpu']} | {res['disk']} | {res.get('power', '')} | {res.get('therm', '')}")
        out += [("\x1b[1;31m" if color else "") + "WARNING: " + w + ("\x1b[0m" if color else "") for w in res["warn"]]
        if full:
            out.append(f"{'idea':<24}" + "".join(f"{s:<15}" for s in PIPE) + "holdout")
            for n in self.names:
                ho = "OPENED" if (self.lc.RES / n / "holdout_opening.json").exists() else "sealed"
                out.append(f"{n:<24}" + "".join(self.cell(st, n, s, color) for s in PIPE) + ho)
        k = self.log_lines
        for src in (self.logs / "run_all.log", self.logs / "lab.log"):
            out += ["  | " + x for x in tail(src, k // 2 if k < 12 else k)]
        return "\n".join(out)

    def final_text(self) -> str:
        sm = read_json(self.lc.RES / "summary.json", {})
        rows = [f"  {r['name']:<24}{r['verdict']:<22}ARL {r['arl']}  {str(r['certificate_id'])[:16]}" for r in sm.get("strategies", [])]
        head = "ALL STAGES UP TO VALIDATION ARE FINISHED." + ("  (DRY-RUN: nothing here is real)" if self.dry else "")
        hint = ("The holdout is SEALED. Choose ONE candidate: python scripts/strategy_lab/freeze.py NAME ; git commit ; "
                "then run lab.py, key h, and type the confirmation.") if not self.dry else "Dry-run complete: the control logic works."
        return "\n".join([head, *rows, hint])

    # ---- main loop
    def run(self) -> int:
        plain = self.a.plain or not (sys.stdin.isatty() and sys.stdout.isatty())
        self.lc.WORK.mkdir(parents=True, exist_ok=True)
        lockf = (self.lc.WORK / "lab.lock").open("a+")
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("another lab.py is already running for this folder (flock); only one instance is allowed")
            return 3
        lockf.seek(0)
        lockf.truncate()
        lockf.write(str(os.getpid()))
        lockf.flush()
        self.adopt_orphans()
        if self.dry and not self.data_ready():
            make_stubs(self.home)
        for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):  # SIGHUP: the terminal window was closed
            signal.signal(s, lambda n, _f: setattr(self, "sig", n))
        fd, old = None, None
        if not plain:
            import termios
            import tty

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        try:
            self.log(f"lab started plain={plain} dry={self.dry} jobs={self.jobs} threads={self.threads} home={self.home}")
            if not self.a.no_auto and not self.child:
                self.act_run()
            last_print, last_done = 0.0, -1
            while True:
                if self.sig:
                    if self.quit:  # second Ctrl-C / SIGTERM while stopping: hurry up
                        self.shutdown()
                        return 130
                    self.quit, self.sig = True, 0
                    self.act_stop()
                if self.quit and not self.child:
                    return 130
                self.poll()
                if self.mode == "done" and not self.final_printed:
                    self.final_printed = True
                    note = self.act_analyze()
                    self.log("all stages finished")
                    if plain:
                        print(self.render(False) + "\n" + note + "\n" + self.final_text(), flush=True)
                        return 0
                    sys.stdout.write("\x1b[H\x1b[J" + self.render(True) + "\n\n" + self.final_text() + "\n" + KEYS + "\n")
                    if self.a.exit_when_done:
                        return 0
                if self.mode == "failed" and plain:
                    print(self.render(False) + f"\nFAILED after {MAX_ATTEMPTS} attempts without progress; see strategy_lab/logs", flush=True)
                    return 1
                now = time.time()
                if plain:
                    d = count_done(self.state(), self.names)[0]
                    if now - last_print >= self.a.interval or d != last_done:
                        print(f"--- {time.strftime('%F %T')}\n" + self.render(False, full=d != last_done or now - last_print >= 300), flush=True)
                        last_print, last_done = now, d
                    time.sleep(1)
                    continue
                if self.mode != "done":
                    try:
                        sys.stdout.write("\x1b[H\x1b[J" + self.render(True) + "\n\n" + KEYS + "\n")
                        sys.stdout.flush()
                    except OSError:  # the terminal is gone (window closed, ssh dropped): stop safely, progress is on disk
                        self.sig = signal.SIGHUP
                        continue
                if select.select([sys.stdin], [], [], 1.0)[0]:
                    raw = os.read(fd, 1)
                    if not raw:  # EOF on the terminal
                        self.sig = signal.SIGHUP
                        continue
                    k = raw.decode(errors="ignore").lower()
                    if k == "r":
                        self.act_run()
                    elif k == "p":
                        self.act_pause()
                    elif k == "x":
                        self.act_stop()
                    elif k == "f":
                        self.act_retry_failed()
                    elif k == "a":
                        self.act_analyze()
                    elif k == "l":
                        self.log_lines = 24 if self.log_lines < 12 else 6
                    elif k == "q":
                        self.quit = True
                        self.act_stop()
                    elif k == "h":
                        import termios
                        import tty

                        termios.tcsetattr(fd, termios.TCSADRAIN, old)
                        try:
                            self.act_holdout(plain)
                            input("\nEnter to return... ")
                        finally:
                            tty.setcbreak(fd)
        finally:
            if old is not None:
                import termios

                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            self.save_lab()
            fcntl.flock(lockf, fcntl.LOCK_UN)


def self_test() -> int:
    """Control-logic checks: pure helpers, then a dry pass with kill -9 of the child and of lab.py itself, then resume."""
    fails: list[str] = []

    def check(name: str, ok: bool) -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}", flush=True)
        if not ok:
            fails.append(name)

    with tempfile.TemporaryDirectory(prefix="lab_selftest_") as td:
        p = Path(td) / "x.json"
        atomic_write(p, '{"a": 1}')
        check("atomic write", read_json(p, None) == {"a": 1} and not list(Path(td).glob("*.tmp")))
        p.write_text("{broken")
        check("corrupt json -> default, kept as .bad", read_json(p, {"d": 1}) == {"d": 1} and p.with_name("x.json.bad").exists())
    check("auto_plan M1 16GB", auto_plan(8, 16, "arm64", 10)[:2] == (2, 2))
    check("auto_plan 2014 Intel 16GB", auto_plan(8, 16, "x86_64", 10)[0] == 1)
    check("auto_plan tiny box", auto_plan(2, 4, "arm64", 10)[:2] == (1, 1))
    st = {"a": {"prepare": {"status": "done", "seconds": 4}, "discovery": {"status": "running"}}, "b": {"prepare": {"status": "error"}}}
    check("count_done", count_done(st, ["a", "b"]) == (1, 6))
    check("eta uses mean duration", eta_seconds(st, ["a", "b"], 1) == 20.0)
    ns, fixed = normalize_state(st)
    check("normalize: running/error -> pending", fixed == 2 and "discovery" not in ns["a"] and ns["b"] == {})

    home = Path(tempfile.mkdtemp(prefix="lab_selftest_home_"))
    base = [sys.executable, str(HERE / "lab.py"), "--plain", "--dry-run", "--home", str(home), "--interval", "5", "--jobs", "1", "--threads", "1"]
    state_p = home / "work" / "state.json"

    def done_now() -> int:
        s = read_json(state_p, {})
        return sum(1 for n in s for v in s[n].values() if v.get("status") == "done")

    def wait_for(n: int, proc: subprocess.Popen, limit: float = 300) -> bool:
        end = time.time() + limit
        while time.time() < end and done_now() < n and proc.poll() is None:
            time.sleep(0.5)
        return done_now() >= n

    p1 = subprocess.Popen(base, stdout=open(home / "selftest.out", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    check("dry pass starts and makes progress", wait_for(2, p1))
    cp = read_json(home / "work" / "child.pid", {})
    if cp.get("pid"):
        os.kill(cp["pid"], signal.SIGKILL)  # the child dies in the middle of a stage
        time.sleep(1)
    check("watchdog survives kill -9 of the child", wait_for(done_now() + 2, p1) and p1.poll() is None)
    n_before = done_now()
    p1.kill()  # lab.py itself dies hard (power cut): the orphan child is left running
    p1.wait()
    time.sleep(1)
    cp = read_json(home / "work" / "child.pid", {})
    orphan = bool(cp.get("pid") and pid_alive(cp["pid"]))
    print(f"  info  orphan child still running after kill -9 of lab.py: {orphan}")
    p2 = subprocess.Popen(base, stdout=open(home / "selftest2.out", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    try:
        rc = p2.wait(timeout=900)
    except subprocess.TimeoutExpired:
        p2.kill()
        rc = -9
    check("resume after kill -9 of lab.py finishes with rc 0", rc == 0)
    s = read_json(state_p, {})
    names = [d.name for d in (REPO / "examples" / "strategies").iterdir() if (d / "strategy.py").exists()]
    check("every idea x stage is done, none lost", all(s.get(n, {}).get(st_, {}).get("status") == "done" for n in names for st_ in PIPE))
    check("progress was kept (not restarted from zero)", n_before >= 4)
    check("results are only in the scratch folder", (home / "results" / "summary.json").exists())
    check("orphan was adopted by the new lab.py", not orphan or "adopted" in (home / "logs" / "lab.log").read_text())
    check("no orphan child left", not (cp.get("pid") and pid_alive(cp["pid"])))
    print(f"scratch folder: {home}")
    if not fails:
        shutil.rmtree(home, ignore_errors=True)
    print("SELF-TEST " + ("FAILED: " + ", ".join(fails) if fails else "PASSED"))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plain", action="store_true", help="no TTY screen: timestamped text lines (nohup, ssh)")
    ap.add_argument("--interval", type=int, default=30, help="plain mode: seconds between status prints")
    ap.add_argument("--dry-run", action="store_true", help="full pass on synthetic stubs in a scratch folder")
    ap.add_argument("--self-test", action="store_true", help="dry-run with kill -9 and resume checks")
    ap.add_argument("--home", type=Path, help="scratch folder for dry-run")
    ap.add_argument("--jobs", type=int, help="ideas in parallel (default: auto by RAM and cores)")
    ap.add_argument("--threads", type=int, help="threads per job (default: auto)")
    ap.add_argument("--download-threads", type=int)
    ap.add_argument("--no-auto", action="store_true", help="do not start work until key r")
    ap.add_argument("--exit-when-done", action="store_true", help="interactive mode: exit after the final summary")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.dry_run:
        home = (a.home or Path(tempfile.mkdtemp(prefix="strategy_lab_dry_"))).resolve()
        real = REPO / "strategy_lab"
        if home == real or real in home.parents:
            sys.exit("dry-run must not use the real strategy_lab folder")
        home.mkdir(parents=True, exist_ok=True)
        (home / "DRY_RUN").write_text("synthetic data; results are not real\n")
        os.environ["STRATEGY_LAB_HOME"] = str(home)
    elif a.home:
        sys.exit("--home is only for --dry-run")
    return Lab(a).run()


if __name__ == "__main__":
    raise SystemExit(main())
