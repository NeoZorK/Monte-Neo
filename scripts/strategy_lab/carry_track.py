"""Delta-neutral funding carry track (long spot / short USD-M perpetual) on the data already in the Lab.

Not investment advice. Nothing trades; no keys. Holdout (>= 2025-01-01) is cut at load time and never read.
Stages: `disc` (2020 only), `val` (2021-2024), `both`. Variants and the selection rule live in strategy_lab/batches/carry_prereg.json
and were committed before `val` was ever run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labcore as lc  # noqa: E402
import labecon  # noqa: E402

sys.path.insert(0, str(lc.STRATS / "_common"))
from binance_costs import side_frac  # noqa: E402

CUT = lc.HOLD_START  # hard cut: nothing at or after 2025-01-01 is ever loaded
SYMS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOGEUSDT", "DOTUSDT", "AVAXUSDT", "ATOMUSDT", "SOLUSDT"]
MARGIN = 0.50          # perp margin, share of notional (2x max leverage); the first guess 0.25 gave 79 liquidations, see the addendum in carry_prereg.json
CAP_COST = 0.05        # opportunity cost of deployed capital, per year (conservative: charged also when bills paid ~0)
PRE = lc.ROOT / "strategy_lab" / "batches" / "carry_prereg.json"
OUT = lc.WORK / "carry"

VARIANTS = {  # frozen in carry_prereg.json
    "A_fast_daily":   dict(L=7,  enter=0.0003, exit=0.0001,  R=1, cap=1 / 6, topk=None, syms=SYMS),
    "B_weekly":       dict(L=14, enter=0.0003, exit=0.0001,  R=7, cap=1 / 6, topk=None, syms=SYMS),
    "C_very_fast":    dict(L=3,  enter=0.0004, exit=0.00015, R=1, cap=1 / 6, topk=None, syms=SYMS),
    "D_top4_weekly":  dict(L=14, enter=0.0003, exit=0.0001,  R=7, cap=0.25,  topk=4,    syms=SYMS),
    "E_btc_eth_slow": dict(L=30, enter=0.0002, exit=0.00005, R=7, cap=0.5,   topk=None, syms=["BTCUSDT", "ETHUSDT"]),
}


def load() -> dict[str, pd.DataFrame]:
    """Aligned daily panels (index = date), all cut before the holdout."""
    out: dict[str, dict[str, pd.Series]] = {k: {} for k in ("S", "P", "F", "VS", "VP", "PH")}
    for s in SYMS:
        sp, pp, fu = (lc.load_series(k, s, CUT) for k in ("spot", "perp", "fund"))
        if sp is None or pp is None or fu is None:
            continue
        sp, pp, fu = sp.set_index("timestamp"), pp.set_index("timestamp"), fu.set_index("timestamp")
        out["S"][s], out["P"][s], out["F"][s] = sp["close"], pp["close"], fu["funding"]
        # the perp day-high is used only for the liquidation test; a high more than 10% above both open and close is treated as a bad tick (ETH 2020-03-13: +203%)
        out["VS"][s], out["VP"][s] = sp["volume"] * sp["close"], pp["volume"] * pp["close"]
        out["PH"][s] = np.minimum(pp["high"], np.maximum(pp["open"], pp["close"]) * 1.10)
    df = {k: pd.DataFrame(v).sort_index() for k, v in out.items()}
    idx = df["S"].index[df["S"].index >= "2019-12-01"]  # funding history starts 2020-01
    assert idx.max() < CUT
    return {k: v.reindex(idx) for k, v in df.items()}


MAINT, TOPUP, LIQ_FEE = 0.04, 0.30, 0.01  # liquidation ratio, top-up trigger (restores MARGIN), liquidation fee (share of notional)


def simulate(d: dict[str, pd.DataFrame], v: dict, phase: int = 0, cost_mult: float = 1.0, cap_cost: float = CAP_COST):
    """Unit-based simulation with an explicit perp margin account (v2 of the accounting, see carry_prereg.json addendum).
    Per coin: u units long spot (fully paid) and u units short perp; margin account M (MARGIN x perp notional at entry).
    Daily: M += u*(P[t-1]-P[t]) + u*mean(P)*funding. If M/(u*P) < TOPUP at the close, spot is sold to restore MARGIN (both legs cut, costs paid).
    If the perp day-high takes the ratio below 4% the position is liquidated (loss at the high, 1% fee), then flat until the next decision.
    Trades cost fee+spread per leg. Capital cost on deployed capital. Equity = cash + sum(u*S + M)."""
    syms = [s for s in v["syms"] if s in d["S"].columns]
    S, P, F, H = d["S"][syms], d["P"][syms], d["F"][syms], d["PH"][syms]
    mL = F.rolling(v["L"], min_periods=v["L"]).mean()
    avail = S.notna() & P.notna() & F.notna() & mL.notna()
    fs = np.array([side_frac(s, "spot", cost_mult) for s in syms])
    fp = np.array([side_frac(s, "perp", cost_mult) for s in syms])
    n, k = len(S), len(syms)
    Sv, Pv, Hv, Fv, Mv, Av = (np.nan_to_num(S.to_numpy()), np.nan_to_num(P.to_numpy()), np.nan_to_num(H.to_numpy()), F.fillna(0).to_numpy(), mL.to_numpy(), avail.to_numpy())
    u, M = np.zeros(k), np.zeros(k)
    cash, E_prev = 1.0, 1.0
    ret, tcost, eq, liq = np.zeros(n), np.zeros(n), np.ones(n), np.zeros(n)
    wts, uh = np.zeros((n, k)), np.zeros((n, k))
    for t in range(1, n):
        on = u > 0
        if on.any():
            cash -= cap_cost / 365 * float((u * Sv[t - 1] + M)[on].sum())  # opportunity cost of deployed capital
            M0 = M.copy()
            M[on] += (u * (Pv[t - 1] - Pv[t]))[on] + (u * 0.5 * (Pv[t] + Pv[t - 1]) * Fv[t])[on]
            # liquidation at the day's high
            ratio_hi = (M0 + u * (Pv[t - 1] - Hv[t])) / np.maximum(u * Hv[t], 1e-12)
            lq = on & (ratio_hi < MAINT) & (Hv[t] > 0)
            for i in np.where(lq)[0]:
                M[i] = M0[i] + u[i] * (Pv[t - 1, i] - Hv[t, i]) - LIQ_FEE * u[i] * Hv[t, i]  # loss marked at the high, not the close
                tc = u[i] * Sv[t, i] * fs[i]
                cash += u[i] * Sv[t, i] - tc + M[i]
                tcost[t] += tc
                u[i], M[i], liq[t] = 0.0, 0.0, liq[t] + 1
            on = u > 0
            # top-up: restore margin to 25% by selling spot and cutting both legs
            ratio = M / np.maximum(u * Pv[t], 1e-12)
            for i in np.where(on & (ratio < TOPUP))[0]:
                un = (M[i] + u[i] * Sv[t, i]) / (Sv[t, i] + MARGIN * Pv[t, i])
                du = u[i] - un
                tc = du * (Sv[t, i] * fs[i] + Pv[t, i] * fp[i])
                M[i] = MARGIN * un * Pv[t, i] - tc
                u[i] = un
                tcost[t] += tc
        if (t - phase) % v["R"] == 0:  # decide at the close of t, trade at the close of t, earn from t+1
            held = u > 0
            keep = held & Av[t] & (Mv[t] > v["exit"])
            want = ~held & Av[t] & (Mv[t] > v["enter"])
            if v["topk"]:
                rank = pd.Series(np.where(Av[t], Mv[t], -np.inf)).rank(ascending=False, method="first").to_numpy()
                keep &= rank <= v["topk"] + 1
                want &= rank <= v["topk"]
            for i in np.where(held & ~keep)[0]:  # exit: sell spot, buy back perp
                tc = u[i] * (Sv[t, i] * fs[i] + Pv[t, i] * fp[i])
                cash += u[i] * Sv[t, i] + M[i] - tc
                tcost[t] += tc
                u[i], M[i] = 0.0, 0.0
            E_now = cash + float((u * Sv[t] + M).sum())
            for i in np.where(want)[0]:  # entry with up to cap * equity
                tgt = min(v["cap"] * E_now, cash)
                if tgt <= 1e-9:
                    continue
                un = tgt / (Sv[t, i] + MARGIN * Pv[t, i])
                tc = un * (Sv[t, i] * fs[i] + Pv[t, i] * fp[i])
                u[i], M[i] = un, MARGIN * un * Pv[t, i]
                cash -= un * Sv[t, i] + M[i] + tc  # spot + margin + entry costs
                tcost[t] += tc
        E = cash + float((u * Sv[t] + M).sum())
        ret[t], eq[t] = E / E_prev - 1, E
        E_prev = E
        wts[t] = (u * Sv[t] + M) / max(E, 1e-12)
        uh[t] = u
    idx = S.index
    return pd.Series(ret, index=idx, name="return"), pd.DataFrame(wts, index=idx, columns=syms), pd.Series(tcost, index=idx) / pd.Series(eq, index=idx).shift(1).fillna(1.0), pd.Series(liq, index=idx), pd.DataFrame(uh, index=idx, columns=syms)


def sharpe(r: pd.Series):
    r = r.dropna()
    return float(r.mean() / r.std() * np.sqrt(365)) if len(r) > 30 and r.std() > 0 else float("nan")


def capacity(d, w: pd.DataFrame, ret_idx, part: float = 0.01):
    """AUM (USDT) at which a typical held position would be `part` of the trailing-30d median daily USD volume of the thinner market.
    Reported as the 10th percentile over held coin-days (a conservative, not a worst-case, number)."""
    adv = pd.concat([d["VS"][w.columns].rolling(30).median(), d["VP"][w.columns].rolling(30).median()]).groupby(level=0).min().reindex(w.index)
    ratio = (part * adv / (w / (1 + MARGIN)).where(w > 0.01)).loc[ret_idx].stack()
    return float(ratio.quantile(0.10)) if len(ratio) else float("nan")


def n_trials_lab() -> dict:
    """Variants declared anywhere in the Lab: grids of all strategy files (parsed by text if a file does not import), the screening ledger, and this track."""
    total, broken = 0, 0
    for p in sorted(lc.STRATS.glob("*/strategy.py")):
        try:
            total += len(lc.combos(lc.load_module(p.parent.name).META["grid"]))
        except Exception:
            broken += 1
            m = re.search(r'"grid":\s*(\{[^}]*\})', p.read_text())
            total += max(1, int(np.prod([len(x) for x in json.loads(m.group(1)).values()])) if m and m.group(1) != "{}" else 1)
    scr = sum(1 for _ in open(lc.LAB / "ledgers" / "screen_ledger.jsonl")) if (lc.LAB / "ledgers" / "screen_ledger.jsonl").exists() else 0
    return {"strategy_files_grid_points": total, "files_parsed_by_text": broken, "screen_ledger": scr, "carry_track": 45}


def metrics(r: pd.Series, btc: pd.Series, n_trials: int) -> dict:
    return labecon.metrics(r, btc, n_trials)


def run(stage: str, only: list[str] | None = None) -> dict:
    d = load()
    btc = d["S"]["BTCUSDT"].pct_change()
    nt = n_trials_lab()
    ntr = sum(nt.values())
    res: dict = {"n_trials": ntr, "n_trials_parts": nt, "variants": {}}
    sl = {"disc": (None, lc.VAL_START), "val": (lc.VAL_START, CUT)}
    for name, v in VARIANTS.items():
        if only and name not in only:
            continue
        rec: dict = {}
        for tag, (a, b) in sl.items():
            if stage not in (tag, "both"):
                continue
            dd = d if tag == "val" else {k: x[x.index < b] for k, x in d.items()}  # disc: nothing from 2021 on is even loaded into the sim
            base, w, tc, lq, _ = simulate(dd, v)
            x2 = simulate(dd, v, cost_mult=2.0)[0]
            zero_cap = simulate(dd, v, cap_cost=0.0)[0]
            phases = {ph: simulate(dd, v, phase=ph)[0] for ph in range(v["R"])}
            cut = lambda r: r[(r.index >= a) if a is not None else slice(None)][lambda z: (z.index < b)]  # noqa: E731
            cut = (lambda r, a=a, b=b: r[((r.index >= a) if a is not None else True) & (r.index < b)])
            sel = cut(base)
            first_trade = sel[sel != 0].index.min()
            sel = sel[sel.index >= first_trade] if pd.notna(first_trade) else sel
            m = metrics(sel, btc, ntr)
            ph_sh = {ph: sharpe(cut(r).loc[sel.index[0]:]) for ph, r in phases.items()}
            worst_ph = min(ph_sh, key=lambda k: ph_sh[k])
            wm = metrics(cut(phases[worst_ph]).loc[sel.index[0]:], btc, ntr)
            by_year = {str(y): {"sharpe": round(sharpe(g), 2), "return": round(float((1 + g).prod() - 1), 4)} for y, g in sel.groupby(sel.index.year)}
            rec[tag] = {"first_trade": str(sel.index[0].date()), **m, "sharpe_cost_x2": round(sharpe(cut(x2).loc[sel.index[0]:]), 3),
                        "sharpe_capital_cost_0": round(sharpe(cut(zero_cap).loc[sel.index[0]:]), 3),
                        "ann_return": round(float(sel.mean() * 365), 4), "phase_sharpes": {str(k): round(x, 3) for k, x in ph_sh.items()},
                        "worst_phase": int(worst_ph), "worst_phase_dsr": wm.get("deflated_sharpe"), "worst_phase_sharpe": wm.get("sharpe"),
                        "liquidations": int(cut(lq).sum()), "by_year": by_year, "avg_deployed": round(float(cut(w).sum(axis=1).mean()), 3),
                        "turnover_cost_per_year": round(float(cut(tc).sum() / max(len(sel) / 365, 1e-9)), 4),
                        "capacity_usdt_p10": round(capacity(d, w, sel.index)) if tag == "val" else None}
            if tag == "val":
                rec[tag]["_series"] = sel
        res["variants"][name] = rec
    return res, d, btc


def tails(d, btc, series: dict[str, pd.Series]) -> dict:
    wins = {"2020-03 crash": ("2020-03-08", "2020-03-20"), "2021-05 crash": ("2021-05-10", "2021-05-25"), "2022-05 LUNA": ("2022-05-05", "2022-05-16"),
            "2022-11 FTX": ("2022-11-06", "2022-11-17")}
    ph_move = (d["PH"] / d["P"].shift(1) - 1).max(axis=1)
    out = {}
    for n, r in series.items():
        out[n] = {}
        for k, (a, b) in wins.items():
            g = r[a:b]
            out[n][k] = None if g.empty else {"cum_return": round(float((1 + g).prod() - 1), 4), "worst_day": round(float(g.min()), 4)}
    out["_max_one_day_perp_rally_any_coin"] = {k: round(float(ph_move[a:b].max()), 3) for k, (a, b) in wins.items()}
    return out


def hac_t(r: pd.Series, lags: int = 10) -> float:
    """t-statistic of the mean daily return with Newey-West (Bartlett) standard error."""
    x = r.to_numpy(float) - r.mean()
    n = len(x)
    v = float((x * x).sum() / n)
    for L in range(1, lags + 1):
        v += 2 * (1 - L / (lags + 1)) * float((x[L:] * x[:-L]).sum() / n)
    return float(r.mean() / np.sqrt(v / n))


def final(name: str) -> dict:
    """Extra checks for the selected variant: plateau grid, margin sensitivity, HAC t, ARL via the verifier (returns and legs paths)."""
    global MARGIN, TOPUP
    d = load()
    btc = d["S"]["BTCUSDT"].pct_change()
    v = VARIANTS[name]
    out: dict = {"variant": name}
    sel = lambda r: r[(r.index >= lc.VAL_START) & (r.index < CUT)]  # noqa: E731
    grid = {}
    for fl in (0.5, 1, 2):
        for fe in (0.67, 1, 1.5):
            vv = {**v, "L": max(2, int(round(v["L"] * fl))), "enter": v["enter"] * fe, "exit": v["exit"] * fe}
            r = sel(simulate(d, vv)[0])
            r2 = sel(simulate(d, vv, cost_mult=2.0)[0])
            grid[f"L={vv['L']},enter={vv['enter']:.5f}"] = {"sharpe": round(sharpe(r), 2), "sharpe_x2": round(sharpe(r2), 2), "ann_return": round(float(r.mean() * 365), 4)}
    out["plateau"] = grid
    sens = {}
    for m, tu in ((0.25, 0.12), (0.5, 0.30), (1.0, 0.60)):
        MARGIN, TOPUP = m, tu
        r, w, _, lq, _ = simulate(d, v)
        sens[f"margin={m}"] = {"sharpe": round(sharpe(sel(r)), 2), "ann_return": round(float(sel(r).mean() * 365), 4), "liquidations": int(sel(lq).sum())}
    MARGIN, TOPUP = 0.50, 0.30
    out["margin_sensitivity"] = sens
    r, w, tc, lq, uh = simulate(d, v)
    rv = sel(r)
    rv = rv[rv.index >= rv[rv != 0].index.min()]
    out["hac_t_mean_return"] = round(hac_t(rv), 2)
    out["naive_t_mean_return"] = round(float(rv.mean() / rv.std() * np.sqrt(len(rv))), 2)
    out["first_half_sharpe"], out["second_half_sharpe"] = round(sharpe(rv[: len(rv) // 2]), 2), round(sharpe(rv[len(rv) // 2:]), 2)
    out["worst_30d_return"] = round(float(rv.rolling(30).sum().min()), 4)
    out["worst_year"] = min(((str(y), round(float((1 + g).prod() - 1), 4)) for y, g in rv.groupby(rv.index.year)), key=lambda z: z[1])
    # verifier: returns path (+ benchmark BTC), n_trials = all Lab variants
    ntr = sum(n_trials_lab().values())
    W = OUT / "verify"
    W.mkdir(parents=True, exist_ok=True)
    rv.rename_axis("date").to_csv(W / "returns_val.csv", header=["return"])
    btc[rv.index].rename_axis("date").to_csv(W / "btc_val.csv", header=["return"])
    meta = {"data": {"spot": [s for s in v["syms"]], "perp": [s for s in v["syms"]]}}
    args = ["verify", "--returns", str(W / "returns_val.csv"), "--n-strategies", str(ntr), "--periods-per-year", "365", "--benchmark", str(W / "btc_val.csv"),
            "--out", str(W / "cert_returns.json")]
    rr = lc.mn(*args, cwd=W)
    rep = json.loads((W / "cert_returns.json").read_text())
    lc.add_input_evidence(rep, meta)
    out["arl_returns_path"] = lc.summarize(rep)
    out["arl_returns_path"]["exit_code"] = rr.returncode
    # verifier: legs path (spot long, perp short, funding as a third leg whose 'price' is the cumulative funding index)
    legs = pd.DataFrame(index=rv.index)
    prev = r.index.get_indexer(rv.index) - 1
    E = (1 + r).cumprod().shift(1).fillna(1.0)
    gross = sel(simulate(d, v, cap_cost=0.0)[0]).reindex(rv.index)  # the legs carry no capital cost: compare with the return before it
    legs["reported_return"] = gross
    cols = []
    for sym in v["syms"]:
        S_, P_, F_ = d["S"][sym], d["P"][sym], d["F"][sym].fillna(0)
        u_ = uh[sym].shift(1).fillna(0)
        base_ = pd.Series(1.0, index=S_.index)
        legs[f"px_spot{sym}"], legs[f"px_perp{sym}"], legs[f"px_fund{sym}"] = S_.reindex(rv.index), P_.reindex(rv.index), (1 + F_).cumprod().reindex(rv.index)
        legs[f"qty_spot{sym}"] = (u_ * S_.shift(1) / E).reindex(rv.index)
        legs[f"qty_perp{sym}"] = (-u_ * P_.shift(1) / E).reindex(rv.index)
        legs[f"qty_fund{sym}"] = (u_ * P_.shift(1) / E).reindex(rv.index)
    legs = legs.fillna(0.0).rename_axis("date")
    legs.to_csv(W / "legs_val.csv")
    rl = lc.mn("verify", "--legs", str(W / "legs_val.csv"), "--legs-pnl", "simple", "--legs-tol", "0.10", "--legs-fixed-out", str(W / "legs_fixed.csv"),
               "--periods-per-year", "365", "--out", str(W / "cert_legs.json"), cwd=W)
    try:
        rep2 = json.loads((W / "cert_legs.json").read_text())
        out["arl_legs_path"] = lc.summarize(rep2)
        out["arl_legs_path"]["exit_code"] = rl.returncode
        out["arl_legs_path"]["note"] = "reported_return = strategy return before the 5% capital cost (legs hold no cash leg); trade costs stay in"
    except Exception as e:  # noqa: BLE001
        out["arl_legs_path"] = {"error": str(e), "stdout": rl.stdout[-800:], "stderr": rl.stderr[-800:]}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["disc", "val", "both", "final"], default="disc")
    ap.add_argument("--variant", default="E_btc_eth_slow")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.stage == "final":
        Path(OUT / "result_final.json").write_text(json.dumps(final(a.variant), indent=1, default=str))
        sys.exit(0)
    res, d, btc = run(a.stage, a.only)
    series = {n: r["val"].pop("_series") for n, r in res["variants"].items() if "val" in r}
    if series:
        res["tails"] = tails(d, btc, series)
        pd.DataFrame(series).to_csv(OUT / "val_returns.csv")
    OUT.mkdir(parents=True, exist_ok=True)
    Path(a.out or OUT / f"result_{a.stage}.json").write_text(json.dumps(res, indent=1, default=str))
    for n, r in res["variants"].items():
        for tag, m in r.items():
            print(n, tag, {k: m.get(k) for k in ("first_trade", "bars", "sharpe", "sharpe_cost_x2", "sharpe_capital_cost_0", "max_drawdown", "ann_return", "corr_btc", "beta_btc", "alpha_t_vs_btc", "deflated_sharpe", "worst_phase_dsr", "avg_deployed", "turnover_cost_per_year")})
