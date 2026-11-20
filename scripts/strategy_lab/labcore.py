"""Strategy Lab core: data splits, strategy registry, one function per stage. No trading, no keys, no network.

Time is cut into discovery (< 2021-01-01, data from 2017-08), validation (2021-01-01 .. 2024-12-31: bull 2021, bear 2022, recovery 2023-24)
and a sealed holdout (>= 2025-01-01). Round 1 used validation 2023-24 only; its results are archived in results_round1/.
The holdout is only read by ``stage_holdout`` and only for a candidate frozen in a git commit (see freeze.py).
"""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HOME_OVERRIDE = os.environ.get("STRATEGY_LAB_HOME")  # set only by lab.py --dry-run/--self-test: everything goes to a scratch folder
LAB = Path(HOME_OVERRIDE) if HOME_OVERRIDE else ROOT / "strategy_lab"
WORK, RES = LAB / "work", LAB / "results"
DATA, STRATS = LAB / "data" / "processed", ROOT / "examples" / "strategies"
VAL_START, HOLD_START = pd.Timestamp("2021-01-01"), pd.Timestamp("2025-01-01")
COMMISSION_BPS, SLIPPAGE_BPS, PPY = 10, 5, 365
AUM_QUOTE = 50_000  # planned capital in USDT for the market-impact and participation checks of the alpha path
SLICES = {"disc": VAL_START, "pre": HOLD_START, "full": None}  # pre = discovery + validation (no holdout)
IDEA_AUTHOR = "Claude Sonnet 5.5"
PROCESS_AUTHOR = "Rostyslav Shcherbyna"
LAB_LEDGER = WORK / "ledger.jsonl"
FUND_FRAC = 0.0  # reserved


def report_dir(name: str) -> Path:
    """Where report.md goes: next to the strategy normally, in the scratch folder for dry runs (never touch the repo)."""
    d = LAB / "reports" / name if HOME_OVERRIDE else STRATS / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def names() -> list[str]:
    return sorted(p.parent.name for p in STRATS.glob("*/strategy.py"))


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(f"lab_{name}", STRATS / name / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def combos(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(grid)
    return [dict(zip(keys, v)) for v in itertools.product(*grid.values())]


def lab_trials() -> int:
    """Every variant the Lab declares anywhere (all grids of all ideas): the n_trials of the final certificates."""
    return sum(len(combos(load_module(n).META["grid"])) for n in names())


def total_trials() -> int:
    """n_trials of every certificate that spans the whole Lab: all crypto variants of all rounds plus the pre-registered ETF grid points."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from etf_ideas import etf_trials

    return lab_trials() + etf_trials()


def load_etf_panel(upto: str, sealed: bool = False):
    """(adjusted close, close) of the ETF track up to a date; 2021+ only with sealed=True (frozen candidate). Crypto loaders are untouched."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import etf_data

    return etf_data.load_panel(upto, sealed=sealed)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


WIDE = Path(os.environ.get("LAB_DATA_DIR") or LAB / "data_wide") / "processed"  # the wide (rounds 4+) archive; set LAB_DATA_DIR to move it to a disk


def load_series(kind: str, sym: str, cut: pd.Timestamp | None) -> pd.DataFrame | None:
    p = DATA / f"{kind}_{sym}_1d.parquet"
    if not p.exists():
        p = WIDE / f"{kind}_{sym}_1d.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
    return df if cut is None else df[df["timestamp"] < cut].reset_index(drop=True)


def panel(meta: dict[str, Any], cut: pd.Timestamp | None) -> dict[str, dict[str, pd.DataFrame]]:
    return {k: {s: d for s in syms if (d := load_series(k, s, cut)) is not None} for k, syms in meta["data"].items()}


MNDIR = WORK / "mn"  # cwd of the CLI: .monte-neo/registrations.jsonl and oracle.jsonl live here (git-ignored)


def mn(*args: str, cwd: Path | None = None, threads: int = 1, timeout: int = 3600) -> subprocess.CompletedProcess:
    """Run the monte-neo CLI in a subprocess with limited threads (exit codes 1-2 are verdicts, not failures)."""
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
           **{k: str(threads) for k in ("OMP_NUM_THREADS", "NUMBA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}}
    MNDIR.mkdir(parents=True, exist_ok=True)
    return subprocess.run([sys.executable, "-c", "from monte_neo.cli.entry import main; main()", *args],
                          capture_output=True, text=True, env=env, cwd=cwd or MNDIR, timeout=timeout)


def work(name: str) -> Path:
    d = WORK / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def prepare(name: str) -> dict[str, Any]:
    """Write the three data slices of one idea. The sealed slice is written too but only stage_holdout passes it on."""
    mod = load_module(name)
    meta, w = mod.META, work(name)
    info: dict[str, Any] = {}
    for tag, cut in SLICES.items():
        if meta["kind"] == "verify":
            df = load_series("spot", meta["asset"].split("_")[1], cut)
            df.to_parquet(w / f"ohlcv_{tag}.parquet")
            info[tag] = {"bars": len(df), "first": str(df.timestamp.iloc[0].date()), "last": str(df.timestamp.iloc[-1].date())}
        elif meta["kind"] == "alpha":
            pan = {s: d for s in meta["universe"] if (d := load_series("spot", s, cut)) is not None and len(d) > 0}
            long = pd.concat([d.assign(symbol=s) for s, d in pan.items()])[["timestamp", "symbol", "close", "volume"]]
            long.to_parquet(w / f"universe_{tag}.parquet")
            sc = mod.scores(pan, **{k: v for k, v in meta["params"].items() if k != "horizon"})
            # coins with no bars in this slice and NaN scores carry no information (pandas 3 stack keeps NaN rows)
            sc = sc[sc["symbol"].isin(pan) & sc["score"].notna()]
            sc.to_parquet(w / f"scores_{tag}.parquet")
            listed = [(s, load_series("spot", s, None)["timestamp"].iloc[0].date().isoformat()) for s in meta["universe"] if s in pan]  # listing dates
            pd.DataFrame(listed, columns=["symbol", "start"]).assign(end="2100-01-01").to_csv(w / f"membership_{tag}.csv", index=False)
            info[tag] = {"rows": len(long), "symbols": len(pan)}
        else:
            r = mod.returns(panel(meta, cut), **meta["params"])
            r.index = pd.to_datetime(r.index).tz_localize(None) if r.index.tz is not None else r.index
            r.rename_axis("date").to_csv(w / f"returns_{tag}.csv", header=["return"])
            info[tag] = {"bars": len(r)}
    return info


def _read(p: Path) -> dict[str, Any]:
    return json.loads(Path(p).read_text())


def summarize(cert: dict[str, Any], alpha: dict[str, Any] | None = None) -> dict[str, Any]:
    from monte_neo.readiness import readiness

    rd = readiness(certificate=cert or None, alpha=alpha)
    rep = alpha or cert
    m = rep.get("metrics", {}) or {}
    return {"verdict": rep.get("verdict"), "certificate_id": rep.get("certificate_id"), "arl": rd["level"], "arl_depth": rd.get("depth"), "arl_headline": rd.get("headline"), "arl_provisional": rd.get("provisional"),
            "arl_summary": rd.get("summary"),
            "sharpe": m.get("sharpe_annualized", m.get("sharpe")), "deflated_sharpe": m.get("deflated_sharpe", m.get("dsr")),
            "ic_t_stat": m.get("ic_t_stat"), "mean_ic": m.get("mean_ic"), "total_return": m.get("total_return"),
            "max_drawdown": m.get("max_drawdown"), "bars": m.get("bars"), "timing_p": m.get("timing_p_value"),
            "benchmark_sharpe": m.get("benchmark_sharpe_annualized"), "benchmark_total_return": m.get("benchmark_total_return"),
            "checks": [{"id": c["id"], "status": c["status"], "summary": c.get("summary", "")} for c in rep.get("checks", [])],
            "reasons": rep.get("reasons", [])[:8]}


def add_input_evidence(rep: dict[str, Any], meta: dict[str, Any]) -> list[str]:
    """A returns-only certificate has no price data, so `data_integrity` is "not run" and the ARL falls to 0 by construction.
    Run the same integrity check on the OHLCV the return series was built from and add its row to the evidence (in memory; the
    certificate file is untouched). Honest: it says the INPUT prices are clean, nothing more."""
    from monte_neo.verify.checks import data_integrity

    if any(c["id"] == "data_integrity" and c["status"] != "skip" for c in rep.get("checks", [])):
        return []
    worst, found = "pass", []
    for kind in ("spot", "perp"):
        for sym in meta["data"].get(kind, []):
            d = load_series(kind, sym, HOLD_START)
            if d is None:
                continue
            row = data_integrity({k: d[k].to_numpy(float) for k in ("open", "high", "low", "close")}, d["timestamp"])
            if row["status"] != "pass":
                worst = row["status"]
                found.append(f"{kind}_{sym}: {row['summary']}")
    rep.setdefault("checks", []).append({"id": "data_integrity", "category": "integrity", "status": worst, "details": {"scope": "input prices of the return series"},
                                         "summary": "input prices are clean" if not found else "; ".join(found[:3])})
    return ["data_integrity"]


def run_verify(name: str, tag: str, n_trials: int, extra: list[str], threads: int, label: str, html: bool = True) -> dict[str, Any]:
    """Verify one idea on one slice; return the compact record. Certificates stay in strategy_lab/work (git-ignored)."""
    mod = load_module(name)
    meta, w = mod.META, work(name)
    out, cert_p = w / f"{label}.cert.json", w / f"{label}.cert.json"
    base = ["--commission-bps", str(COMMISSION_BPS), "--slippage-bps", str(SLIPPAGE_BPS), "--periods-per-year", str(PPY)]
    alpha_p = None
    if meta["kind"] == "verify":
        args = ["verify", "--ohlcv", str(w / f"ohlcv_{tag}.parquet"), "--strategy", str(STRATS / name / "strategy.py"), *base,
                "--n-trials", str(n_trials), "--ledger", str(LAB_LEDGER), "--out", str(out), *extra]
        if html:
            args += ["--html", str(w / f"{label}.html")]
    elif meta["kind"] == "returns":
        args = ["verify", "--returns", str(w / f"returns_{tag}.csv"), "--n-strategies", str(n_trials), "--periods-per-year", str(PPY), "--out", str(out), *extra]
    else:
        alpha_p = w / f"{label}.alpha.json"
        args = ["alpha", "--ohlcv", str(w / f"universe_{tag}.parquet"), "--scores", str(w / f"scores_{tag}.parquet"), "--horizon", str(meta["horizon"]),
                "--n-trials", str(n_trials), "--out", str(alpha_p), "--aum", str(AUM_QUOTE),
                "--membership", str(w / f"membership_{tag}.csv"), *extra]
    r = mn(*args, threads=threads)
    target = alpha_p or out
    if not target.exists():
        raise RuntimeError(f"monte-neo produced no report (exit {r.returncode}): {r.stderr[-600:] or r.stdout[-600:]}")
    rep = _read(target)
    added = add_input_evidence(rep, meta) if meta["kind"] == "returns" else []
    rec = summarize(None, rep) if alpha_p else summarize(rep)
    if added:
        rec["evidence_added"] = added
        rec["arl_scope"] = ("returns-only evidence: the Lab added data_integrity of the input prices; signal-level checks (ic, timing, placebo) cannot run on a "
                            "return series, so the ARL is capped by construction and is not comparable with signal certificates")
    rec.update(slice=tag, n_trials=n_trials, exit_code=r.returncode, report_sha256=sha256_file(target))
    return rec


def load_version() -> str:
    from monte_neo import __version__

    return __version__
