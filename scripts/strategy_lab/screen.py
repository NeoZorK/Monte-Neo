"""Wide honest search (rounds 4+): free screening on DISCOVERY only, then promotion in committed batches.

    screen.py run                 screen every variant of the signal grammar on discovery (resumable; every variant goes to the hash-chained ledger)
    screen.py select --batch N    pick <= 10 decorrelated candidates from discovery results, write strategy_lab/batches/batchN.json + examples/strategies/r4_bN_*
    screen.py fetchval --batch N  download the validation months, ONLY if batchN.json is committed unmodified (pre-registration)
    screen.py report --batch N    after lab.py: White reality check over the batch, cost of the search, gate table

Validation and holdout are physically unreachable from `run`/`select`: the panel loader cuts every series at VAL_START in code.
Not investment advice. Nothing here trades.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

import labcore as lc
import numpy as np
import pandas as pd

sys.path.insert(0, str(lc.STRATS / "_common"))
import signals  # noqa: E402
from binance_costs import side_frac  # noqa: E402

LEDGER = lc.ROOT / "strategy_lab" / "ledgers" / "screen_ledger.jsonl"
BATCHES = lc.ROOT / "strategy_lab" / "batches"
SPLIT_A = pd.Timestamp("2019-07-01")  # discovery halves: A = 2017-08..2019-06, B = 2019-07..2020-12
MAX_VARIANTS, HORIZONS, TOPK = 3000, (3, 7, 14), (30, 60)


def assert_disc(close: pd.DataFrame, volume: pd.DataFrame) -> None:
    """Hard guard: no row at or after VAL_START may ever reach the screening."""
    for x in (close, volume):
        if len(x) and x.index.max() >= lc.VAL_START:
            raise RuntimeError(f"validation/holdout data reached the screening: {x.index.max().date()} >= {lc.VAL_START.date()}")


def panel_disc() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Close and volume of every coin, rows strictly BEFORE VAL_START. There is no parameter to ask for later data."""
    cache = lc.WORK / "screen_panel_disc.pkl"
    if cache.exists():
        c, v = pd.read_pickle(cache)
        assert_disc(c, v)
        return c, v
    cl, vo = {}, {}
    for d in (lc.DATA, lc.WIDE):
        for f in sorted(d.glob("spot_*_1d.parquet")):
            sym = f.name[5:-11]
            if sym in cl:
                continue
            x = lc.load_series("spot", sym, lc.VAL_START)
            if x is not None and len(x):
                s = x.drop_duplicates("timestamp").set_index("timestamp")
                cl[sym], vo[sym] = s["close"], s["volume"]
    close, volume = pd.DataFrame(cl).sort_index(), pd.DataFrame(vo).sort_index()
    assert_disc(close, volume)
    lc.WORK.mkdir(parents=True, exist_ok=True)
    pd.to_pickle((close, volume), cache)
    return close, volume


def variants() -> list[dict]:
    out = []
    for fam, grid in signals.FAMILIES.items():
        for vals in itertools.product(*grid.values()):
            for sign, h, k in itertools.product((1, -1), HORIZONS, TOPK):
                out.append({"family": fam, "params": dict(zip(grid, vals)), "sign": sign, "horizon": h, "top_k": k})
    for fam, grid in signals.FAMILIES_EXT.items():  # new families (appended after the frozen ones, so ledger order is kept)
        for vals in itertools.product(*grid.values()):
            for sign, h, k in itertools.product((1, -1), HORIZONS, TOPK):
                out.append({"family": fam, "params": dict(zip(grid, vals)), "sign": sign, "horizon": h, "top_k": k})
    for r in (2, 3):  # equal-weight composites of fixed canonical components, direction fixed by the literature (no sign flip)
        for names in itertools.combinations(signals.COMPONENTS, r):
            for h, k in itertools.product(HORIZONS, TOPK):
                out.append({"family": "comp_" + "".join(names), "params": {"parts": list(names)}, "sign": 1, "composite": [signals.COMPONENTS[n] for n in names],
                            "horizon": h, "top_k": k})
    assert len(out) <= MAX_VARIANTS and len({vid(v) for v in out}) == len(out)
    return out


def vid(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]


def costs(cols) -> pd.Series:
    return pd.Series({c: side_frac(c, "perp") for c in cols})


def net(sc: pd.DataFrame, ret: pd.DataFrame, beta: pd.DataFrame, h: int, mult: float = 1.0) -> pd.Series:
    """Dollar-neutral top/bottom third, rebalanced every h days, BTC beta hedged, net of per-coin Binance costs; earns from the next bar."""
    r = sc.rank(axis=1, pct=True)
    hi, lo = (r > 2 / 3).astype(float), (r <= 1 / 3).astype(float)
    w = (hi.div(hi.sum(axis=1).replace(0, np.nan), axis=0) * 0.5 - lo.div(lo.sum(axis=1).replace(0, np.nan), axis=0) * 0.5).fillna(0)
    hedge = -(w * beta.reindex_like(w).fillna(0)).sum(axis=1)
    w["BTCUSDT"] = w["BTCUSDT"] + hedge
    mask = pd.Series((np.arange(len(w)) % h) == 0, index=w.index)
    held = w.where(mask).ffill().fillna(0).shift(1).fillna(0)
    c = costs(held.columns) * mult
    return (held * ret.reindex(columns=held.columns).fillna(0)).sum(axis=1) - held.diff().abs().fillna(0).mul(c, axis=1).sum(axis=1)


def sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * np.sqrt(365)) if len(r) > 60 and r.std() > 0 else float("nan")


def alpha_t(r: pd.Series, b: pd.Series) -> float:
    b = b.reindex(r.index).fillna(0)
    beta = np.cov(r, b)[0, 1] / b.var() if b.var() > 0 else 0.0
    e = r - beta * b
    return float(e.mean() / (e.std() / np.sqrt(len(e)))) if e.std() > 0 else 0.0


def evaluate(spec: dict, close, volume, ret, beta, btc) -> dict:
    sc = signals.score(close, volume, spec)
    r1, r2 = net(sc, ret, beta, spec["horizon"]), net(sc, ret, beta, spec["horizon"], 2.0)
    start = sc.notna().any(axis=1).idxmax()
    r1, r2 = r1[r1.index >= start], r2[r2.index >= start]
    a, b = r1[r1.index < SPLIT_A], r1[r1.index >= SPLIT_A]
    return {"sharpe_all": sharpe(r1), "sharpe_A": sharpe(a), "sharpe_B": sharpe(b), "sharpe_x2": sharpe(r2), "alpha_t": alpha_t(r1, btc), "bars": len(r1),
            "ann_return": float(r1.mean() * 365)}


def last_hash() -> str:
    if not LEDGER.exists():
        return "genesis"
    return json.loads(LEDGER.read_text().strip().splitlines()[-1])["hash"]


def cmd_run(a) -> None:
    close, volume = panel_disc()
    ret = close.pct_change(fill_method=None)
    btc = ret["BTCUSDT"]
    beta = ret.rolling(90).cov(btc).div(btc.rolling(90).var(), axis=0).shift(1)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(x)["id"] for x in LEDGER.read_text().splitlines()} if LEDGER.exists() else set()
    todo = [v for v in variants() if vid(v) not in done]
    t0, prev = time.time(), last_hash()
    print(f"variants {len(variants())}, done {len(done)}, todo {len(todo)}; discovery panel {close.shape}, ends {close.index.max().date()}")
    with LEDGER.open("a") as f:
        for i, spec in enumerate(todo, 1):
            m = evaluate(spec, close, volume, ret, beta, btc)
            rec = {"id": vid(spec), "spec": spec, "metrics": m, "stage": "discovery", "prev": prev}
            prev = hashlib.sha256((prev + json.dumps(rec, sort_keys=True, default=str)).encode()).hexdigest()
            f.write(json.dumps({**rec, "hash": prev}, default=str) + "\n")
            f.flush()
            if i % 25 == 0:
                print(f"{i}/{len(todo)} ETA {(time.time() - t0) / i * (len(todo) - i):.0f}s", flush=True)


def rows() -> list[dict]:
    return [json.loads(x) for x in LEDGER.read_text().splitlines()]


def cmd_select(a) -> None:
    taken = {c["id"] for b in BATCHES.glob("batch*.json") for c in json.loads(b.read_text()).get("candidates", [])}  # skip helper files (score hashes)
    good = [r for r in rows() if r["id"] not in taken and all(np.isfinite(r["metrics"][k]) for k in ("sharpe_A", "sharpe_B", "sharpe_x2", "alpha_t"))
            and r["metrics"]["sharpe_A"] > 0 and r["metrics"]["sharpe_B"] > 0 and r["metrics"]["sharpe_x2"] > 0 and r["metrics"]["alpha_t"] >= 2.0]
    good.sort(key=lambda r: -min(r["metrics"]["sharpe_A"], r["metrics"]["sharpe_B"]))
    close, volume = panel_disc()
    ret = close.pct_change(fill_method=None)
    btc = ret["BTCUSDT"]
    beta = ret.rolling(90).cov(btc).div(btc.rolling(90).var(), axis=0).shift(1)
    picked, streams = [], []
    for r in good:
        s = net(signals.score(close, volume, r["spec"]), ret, beta, r["spec"]["horizon"])
        if all(abs(s.corr(o)) < 0.6 for o in streams):
            picked.append(r)
            streams.append(s)
        if len(picked) == 10:
            break
    n_tested = len(rows())
    batch = {"batch": a.batch, "created": time.strftime("%F"), "screened_variants": n_tested, "passed_filters": len(good), "ledger_head": last_hash(),
             "rule": "both discovery halves net Sharpe > 0, costs x2 Sharpe > 0, alpha t vs BTC >= 2, pairwise return corr < 0.6, max 10",
             "candidates": [{"id": r["id"], "spec": r["spec"], "discovery": r["metrics"]} for r in picked]}
    BATCHES.mkdir(parents=True, exist_ok=True)
    (BATCHES / f"batch{a.batch}.json").write_text(json.dumps(batch, indent=1, default=str))
    cm = json.loads((lc.STRATS / "_common" / "wide_universe.json").read_text()) if (lc.STRATS / "_common" / "wide_universe.json").exists() else None
    for k, c in enumerate(batch["candidates"], 1):
        d = lc.STRATS / f"r4_b{a.batch}_{k}_{c['id'][:6]}"
        d.mkdir(exist_ok=True)
        sp = c["spec"]
        (d / "strategy.py").write_text(f'''"""Strategy Lab search candidate {c["id"]} (batch {a.batch}). Not investment advice. Spec fixed by the committed batch file."""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_common"))
import signals  # noqa: E402

SPEC = {json.dumps(sp)}
META = {{"kind": "alpha", "round": 4, "title": "Search candidate {c["id"][:8]}: {sp["family"]} {json.dumps(sp["params"]).replace(chr(34), chr(39))} sign {sp["sign"]}, top {sp["top_k"]} liquid coins",
        "family": "search_{sp["family"]}", "universe": json.loads((Path(__file__).resolve().parents[1] / "_common" / "wide_universe.json").read_text()),
        "portfolio": "long_short", "hedge_btc": True, "params": {{}}, "grid": {{}}, "horizon": {sp["horizon"]}}}


def scores(panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    close = pd.DataFrame({{s: d.set_index("timestamp")["close"] for s, d in panel.items()}}).sort_index()
    volume = pd.DataFrame({{s: d.set_index("timestamp")["volume"] for s, d in panel.items()}}).sort_index()
    return signals.long_form(signals.score(close, volume, SPEC))
''')
        m = c["discovery"]
        (d / "card.md").write_text(f"""# Search candidate {c["id"][:8]} ({sp["family"]})

**Idea source:** systematic signal grammar (`_common/signals.py`), screened on discovery only (2017-08..2020); pre-registered in `strategy_lab/batches/batch{a.batch}.json` before validation was read. **Process and verification:** Rostyslav Shcherbyna.

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea
Family `{sp["family"]}`, parameters `{json.dumps(sp["params"])}`, sign {sp["sign"]:+d}; long the top third / short the bottom third of the {sp["top_k"]} most liquid coins (point in time), rebalanced every {sp["horizon"]} days, hedged to BTC beta.

## Why it might work
It was selected by discovery results, not by theory: net Sharpe A/B halves {m["sharpe_A"]:.2f}/{m["sharpe_B"]:.2f}, costs x2 {m["sharpe_x2"]:.2f}, alpha t vs BTC {m["alpha_t"]:.2f}. That is exactly why the validation count N includes every promoted candidate and a family test is run.

## Where it breaks
Selection bias from the screening; delisted coins are included only where data exist; short legs need perpetuals (funding not modelled); capacity depends on the liquid set.

## How it is tested
Validation 2021-2024 with n_trials = all Lab candidates of all rounds; holdout 2025+ sealed. See `report.md`.
""")
    print(f"batch{a.batch}: {len(picked)} candidates of {len(good)} that passed the filters ({n_tested} screened)")


def cmd_fetchval(a) -> None:
    f = BATCHES / f"batch{a.batch}.json"
    rel = str(f.relative_to(lc.ROOT))
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], capture_output=True, cwd=lc.ROOT).returncode == 0
    clean = subprocess.run(["git", "status", "--porcelain", "--", rel, "examples/strategies"], capture_output=True, text=True, cwd=lc.ROOT).stdout.strip() == ""
    if not (tracked and clean):
        raise SystemExit("REFUSED: commit batch file and the candidate folders first (pre-registration before validation is read)")
    avail = json.loads((lc.ROOT / "strategy_lab" / "logs" / "wide_months.json").read_text())
    syms = ",".join(sorted(avail))
    r = subprocess.run([sys.executable, str(Path(__file__).parent / "fetch_data.py"), "--root", str(lc.WIDE.parent), "--start", "2021-01", "--end", "2024-12", "--threads", "12",
                        "--perp", "", "--months-file", str(lc.ROOT / "strategy_lab" / "logs" / "wide_months.json"), "--spot", syms])
    raise SystemExit(r.returncode)


def reality_check(m: np.ndarray, n_boot: int = 2000, block: int = 10, seed: int = 0) -> float:
    """White (2000) reality check p-value: is the best candidate's mean better than zero after accounting for the search? Stationary bootstrap."""
    rng = np.random.default_rng(seed)
    k, t = m.shape
    obs = np.sqrt(t) * m.mean(axis=1).max()
    c = m - m.mean(axis=1, keepdims=True)
    cnt = 0
    for _ in range(n_boot):
        idx = np.empty(t, dtype=int)
        pos = rng.integers(t)
        for i in range(t):
            pos = rng.integers(t) if rng.random() < 1 / block else (pos + 1) % t
            idx[i] = pos
        cnt += np.sqrt(t) * c[:, idx].mean(axis=1).max() >= obs
    return (cnt + 1) / (n_boot + 1)


def expected_max_sharpe(n: int, t_years: float) -> float:
    """False Strategy Theorem (Bailey and Lopez de Prado 2014): expected best annual Sharpe among n zero-skill strategies."""
    from statistics import NormalDist

    g, nd = 0.5772156649, NormalDist()
    return float(np.sqrt(1.0 / t_years) * ((1 - g) * nd.inv_cdf(1 - 1 / n) + g * nd.inv_cdf(1 - 1 / (n * np.e)))) if n > 1 else 0.0


def cmd_report(a) -> None:
    b = json.loads((BATCHES / f"batch{a.batch}.json").read_text())
    names = [d.name for d in sorted(lc.STRATS.glob(f"r4_b{a.batch}_*"))]
    series, lines = [], []
    n_all = lc.lab_trials()
    for nm in names:
        s = lc.RES / nm / "validation.json"
        if not s.exists():
            continue
        v = json.loads(s.read_text())
        e = v.get("economics", {}).get("validation", {})
        net_ = None
        import labecon
        r = labecon.net_returns(nm, lc.HOLD_START)
        if r is not None:
            r.index = pd.to_datetime(r.index).tz_localize(None) if r.index.tz is not None else r.index
            series.append(r[r.index >= lc.VAL_START])
        lines.append(f"| {nm} | {v['verdict']} | {v.get('arl_headline', v['arl'])} | {e.get('sharpe')} | {v['economics'].get('cost_x2_sharpe_validation')} | {e.get('alpha_t_vs_btc')} | {e.get('beta_share')} | {e.get('deflated_sharpe')} |")
    out = [f"# Batch {a.batch}: validation report (holdout sealed)", "", "Not investment advice.", "",
           f"n_trials on validation = all Lab candidates = **{n_all}**. Screened on discovery: {b['screened_variants']} variants (ledger head `{b['ledger_head'][:12]}`).", ""]
    if series:
        m = pd.concat(series, axis=1).dropna().to_numpy().T
        t_years = m.shape[1] / 365
        out += [f"White reality check over the {m.shape[0]} candidates (stationary bootstrap, 2000 draws): p = **{reality_check(m):.3f}** (SPA of Hansen is not in Monte-Neo: see MONTE_NEO_GAPS.md).",
                f"Cost of the search: expected best annual Sharpe of {n_all} zero-skill strategies over {t_years:.1f} years = **{expected_max_sharpe(n_all, t_years):.2f}**; "
                f"for the {b['screened_variants']} discovery variants (3.5 years) = {expected_max_sharpe(b['screened_variants'], 3.5):.2f}.", ""]
    out += ["| Candidate | Verdict | ARL / depth | Net Sharpe | Costs x2 | Alpha t vs BTC | Beta share | DSR |", "|---|---|---|---|---|---|---|---|"] + lines
    (lc.RES / f"batch{a.batch}_report.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "select", "fetchval", "report"])
    ap.add_argument("--batch", type=int, default=1)
    a = ap.parse_args()
    {"run": cmd_run, "select": cmd_select, "fetchval": cmd_fetchval, "report": cmd_report}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
