"""Honest indicator search: the search counts its own trials and is tested against its own luck.

1. Candidates are random causal trees (``dsl``); the last ``lockbox`` share of the data is never seen by the search.
2. Every candidate's net return series on the search window gives its Sharpe. The *effective* number of independent
   trials is the number of clusters of highly correlated candidates: it is the ``n_trials`` of the final certificate.
3. **Search null.** The identical candidate list is evaluated on surrogates of the market (the same bars in random
   order). The best Sharpe over the whole list on each surrogate is what pure luck
   delivers for this search; the real best Sharpe must beat it (an empirical p-value of the *procedure*).
4. White's Reality Check and Hansen's SPA run on one representative per cluster.
5. The lockbox is opened once, for the winner only.
6. Canaries: leaky expressions go through the same causality gate as every candidate; if one passes, the run stops.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.discover import dsl
from monte_neo.verify.reality import reality_check
from monte_neo.verify.stats import infer_periods_per_year

TOP_K = 10
MIN_ACTIVE = 0.5  # share of bars with a position for a candidate to count
GATE_POINTS = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


@dataclass(frozen=True)
class Config:
    budget: int = 2000
    seed: int = 1
    null_runs: int = 39
    lockbox: float = 0.2
    cost_bps: float = 5.0  # per side, commission and slippage together
    side: str = "long_short"
    alpha: float = 0.05
    lockbox_alpha: float = 0.10
    max_depth: int = 3
    cluster_corr: float = 0.8
    rc_samples: int = 300
    periods_per_year: float | None = None


def _positions(f: pd.Series, m: int, side: str, memo: dict[str, pd.Series], k: str) -> np.ndarray:
    mk = f"ma|{k}|{m}"
    if mk not in memo:
        memo[mk] = f.rolling(m).mean()
    base = memo[mk]
    ok = f.notna().to_numpy() & base.notna().to_numpy()
    above = (f.to_numpy() > base.to_numpy()) & ok
    if side == "long_flat":
        return above.astype(np.float64)
    return np.where(ok, np.where(above, 1.0, -1.0), 0.0)


def _net(pos: np.ndarray, ret: np.ndarray, cost: float) -> np.ndarray:
    """Net return of bar t+1 for the position decided at the close of t, costs charged on the change."""
    change = np.abs(np.diff(pos, prepend=0.0))
    return pos[:-1] * ret[1:] - cost * change[:-1]


def _sharpe(net: np.ndarray, ppy: float, flat: float = -np.inf) -> float:
    """Annualized Sharpe; a series that never moves (a candidate that never trades) gets ``flat`` and never wins."""
    sd = float(np.std(net, ddof=1)) if net.size > 1 else 0.0
    return float(np.mean(net) / sd * np.sqrt(ppy)) if sd > 1e-15 else flat


def _evaluate_all(cands: list[tuple[dsl.Node, int]], df: pd.DataFrame, cfg: Config, ppy: float, warm: int) -> tuple[np.ndarray, np.ndarray]:
    """(net return matrix, Sharpe vector) of every candidate on ``df``, skipping ``warm`` bars."""
    env = dsl.environment(df)
    memo: dict[str, pd.Series] = {}
    ret = np.nan_to_num(env["ret"].to_numpy(), nan=0.0)
    cost = cfg.cost_bps / 1e4
    mat = np.empty((len(cands), len(df) - 1 - warm))
    for i, (tree, m) in enumerate(cands):
        k = dsl.key(tree)
        f = dsl.evaluate(tree, env, memo)
        pos = _positions(f, m, cfg.side, memo, k)
        mat[i] = _net(pos, ret, cost)[warm:]
        if np.mean(pos[warm:] != 0) < MIN_ACTIVE or np.count_nonzero(np.diff(pos[warm:])) < 4:
            mat[i] = 0.0  # mostly undefined or hardly trading: not a candidate (flat series have Sharpe -inf)
    sharpes = np.array([_sharpe(row, ppy) for row in mat])
    return mat, sharpes


def surrogate(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """A market with the same bars (shapes, volatility, volume) in random order: any serial structure is destroyed.

    Bars are permuted, not resampled in blocks: a block bootstrap keeps the structure inside a block, which is
    exactly what a momentum or reversal indicator feeds on, and the search would find it in the "null" too.
    """
    c = df["close"].to_numpy(dtype=np.float64)
    prev = np.r_[c[0], c[:-1]]
    shape = {k: df[k].to_numpy(dtype=np.float64) / prev for k in ("open", "high", "low", "close")}
    idx = np.r_[0, 1 + rng.permutation(len(df) - 1)]  # the first bar has no previous close and stays in place
    path = c[0] * np.cumprod(shape["close"][idx])
    before = np.r_[c[0], path[:-1]]
    out = df.copy()
    for k in ("open", "high", "low", "close"):
        out[k] = before * shape[k][idx]
    out["high"] = out[["open", "high", "low", "close"]].max(axis=1)
    out["low"] = out[["open", "high", "low", "close"]].min(axis=1)
    if "volume" in out.columns:
        out["volume"] = df["volume"].to_numpy()[idx]
    return out


def _clusters(mat: np.ndarray, sharpes: np.ndarray, threshold: float) -> list[int]:
    """Greedy clusters of correlated return series, best Sharpe first; the indices of the cluster representatives."""
    std = mat.std(axis=1)
    live = np.flatnonzero(std > 1e-15)
    if live.size == 0:
        return []
    z = (mat[live] - mat[live].mean(axis=1, keepdims=True)) / std[live][:, None]
    order = np.argsort(-sharpes[live])
    free = np.ones(live.size, dtype=bool)
    reps: list[int] = []
    for pos in order:
        if not free[pos]:
            continue
        reps.append(int(live[pos]))
        corr = z[free] @ z[pos] / z.shape[1]
        members = np.flatnonzero(free)[corr >= threshold]
        free[members] = False
        free[pos] = False
    return reps


def _block_p(returns: np.ndarray, seed: int, samples: int = 1000) -> float:
    """One-sided p-value that the mean return is not above zero (circular block bootstrap of the centred returns)."""
    n = returns.size
    if n < 20 or returns.std() < 1e-15:
        return 1.0
    length = max(2, int(round(n ** (1 / 3))))
    rng = np.random.default_rng(seed)
    centred = returns - returns.mean()
    starts = rng.integers(0, n, size=(samples, n // length + 1))
    idx = ((starts[:, :, None] + np.arange(length)[None, None, :]) % n).reshape(samples, -1)[:, :n]
    means = centred[idx].mean(axis=1)
    return float((1.0 + np.sum(means >= returns.mean())) / (samples + 1.0))


def causality_gate(source: str, df: pd.DataFrame) -> bool:
    """True when the positions at bars <= t do not change when the bars after t are removed."""
    scope: dict[str, Any] = {"__name__": "discover_gate"}
    exec(compile(source, "<discover>", "exec"), scope)  # noqa: S102  # nosec B102 - generated from a tree or from the canary list below
    fn = scope["signal"]
    full = np.asarray(fn(df.copy()), dtype=float)
    n = len(df)
    for share in GATE_POINTS:
        t = int(n * share) | 1
        head = np.asarray(fn(df.iloc[: t + 1].reset_index(drop=True).copy()), dtype=float)
        if not np.array_equal(head, full[: t + 1]):
            return False
    return True


CANARIES = (
    'df["close"].shift(-5)', 'df["close"].rolling(20, center=True, min_periods=1).mean() - df["close"]', 'df["close"].pct_change(-3)',
    'df["close"].rank(pct=True)', 'df["close"].where(np.arange(len(df)) % 5 == 0).bfill()', 'df["close"].shift(-20) - df["close"]',
    'df["high"].shift(-2) - df["close"]', 'df["close"].clip(upper=df["close"].quantile(0.8))',
    'df["close"].diff(-4)',
)


def _canary_source(expr: str) -> str:
    return (
        "import numpy as np\nimport pandas as pd\n\n\ndef signal(df):\n"
        f"    f = pd.Series({expr}, index=df.index)\n"
        "    return pd.Series(np.where(f > f.rolling(10).mean(), 1, -1), index=df.index).where(f.notna(), 0).to_numpy()\n"
    )


def selftest(df: pd.DataFrame, cands: list[tuple[dsl.Node, int]], cfg: Config, rng: np.random.Generator) -> dict[str, Any]:
    """Every canary must be rejected and a sample of genuine candidates must pass; otherwise the run is not trustworthy."""
    window = df.iloc[: min(len(df), 600)].reset_index(drop=True)
    rejected = sum(not causality_gate(_canary_source(e), window) for e in CANARIES)
    picks = rng.choice(len(cands), size=min(20, len(cands)), replace=False) if cands else []
    genuine = sum(causality_gate(dsl.strategy_source(cands[i][0], cands[i][1], cfg.side), window) for i in picks)
    out = {"canaries": len(CANARIES), "canaries_rejected": int(rejected), "genuine_checked": len(picks), "genuine_causal": int(genuine)}
    if rejected != len(CANARIES):
        raise RuntimeError(f"the causality gate let a leaky canary through: {out}")
    if genuine != len(picks):
        raise RuntimeError(f"the causality gate rejected genuine candidates: {out}")
    return out


def discover(df: pd.DataFrame, config: Config | None = None) -> dict[str, Any]:
    """Run an honest search on ``df`` (a price table) and return the result, the source of the winner and the journal."""
    cfg = config or Config()
    if not 0.05 <= cfg.lockbox <= 0.5:
        raise ValueError(f"lockbox must be between 0.05 and 0.5, got {cfg.lockbox}")
    if cfg.side not in ("long_short", "long_flat"):
        raise ValueError(f"side must be long_short or long_flat, got {cfg.side!r}")
    data = df.reset_index(drop=True)
    n = len(data)
    if n < 400:
        raise ValueError(f"need at least 400 bars, got {n}")
    ppy = float(cfg.periods_per_year or (infer_periods_per_year(data["timestamp"]) if "timestamp" in data.columns else 252.0))
    split = int(n * (1.0 - cfg.lockbox))
    search = data.iloc[:split].reset_index(drop=True)
    warm = 130  # longest window plus the rule window
    rng = np.random.default_rng(cfg.seed)
    cands = dsl.make(rng, cfg.budget, cfg.max_depth, tuple(c for c in dsl.COLUMNS if c != "volume" or "volume" in data.columns))
    if not cands:
        raise RuntimeError("no candidates could be generated")
    check = selftest(search, cands, cfg, np.random.default_rng(cfg.seed + 1))

    mat, sharpes = _evaluate_all(cands, search, cfg, ppy, warm)
    # The winner is picked by train-then-validate (never by the lockbox): the top candidates on the first part of
    # the search window compete on its last part. The search null below tests the whole search, not this pick.
    cut = int(mat.shape[1] * 0.65)
    train = np.array([_sharpe(row[:cut], ppy) for row in mat])
    top = np.argsort(-train)[: min(TOP_K, len(cands))]
    valid = {int(i): _sharpe(mat[i, cut:], ppy) for i in top}
    best_i = max(valid, key=lambda i: valid[i])
    if not np.isfinite(valid[best_i]):
        raise RuntimeError("no candidate trades in the search window: raise the budget or give the data more bars")
    selection = {"top_k": len(top), "train_sharpe": round(float(train[best_i]), 4), "validation_sharpe": round(float(valid[best_i]), 4)}
    reps = _clusters(mat, sharpes, cfg.cluster_corr)
    n_eff = max(1, len(reps))
    rc = reality_check(mat[reps], samples=cfg.rc_samples) if len(reps) >= 2 else {}

    null_best = []
    null_rng = np.random.default_rng(cfg.seed + 2)
    for _ in range(int(cfg.null_runs)):
        _, s = _evaluate_all(cands, surrogate(search, null_rng), cfg, ppy, warm)
        null_best.append(float(np.max(s)))
    obs = float(np.max(sharpes))  # the statistic of the search: the best Sharpe anywhere in the list
    p_null = (1.0 + sum(b >= obs for b in null_best)) / (len(null_best) + 1.0) if null_best else None

    tree, m = cands[best_i]
    source = dsl.strategy_source(tree, m, cfg.side)
    # The lockbox is opened once, for the winner only.
    env = dsl.environment(data)
    k = dsl.key(tree)
    pos = _positions(dsl.evaluate(tree, env, {}), m, cfg.side, {}, k)
    net_all = _net(pos, np.nan_to_num(env["ret"].to_numpy(), nan=0.0), cfg.cost_bps / 1e4)
    box = net_all[split:]
    lock_sharpe = _sharpe(box, ppy, flat=0.0)
    lock_p = _block_p(box, cfg.seed + 3)

    cert = _certify(data, source, cfg, n_eff, ppy)
    reasons = []
    if p_null is None or p_null > cfg.alpha:
        reasons.append(f"the best Sharpe of the search ({obs:.2f}) is not above what the same search finds on shuffled markets (p = {p_null})")
    if rc and rc["p_spa"] > cfg.alpha:
        reasons.append(f"Hansen's SPA does not reject luck (p = {rc['p_spa']})")
    if lock_sharpe <= 0 or lock_p > cfg.lockbox_alpha:
        reasons.append(f"the lockbox does not confirm it (Sharpe {lock_sharpe:.2f}, p = {lock_p:.3f})")
    if cert["verdict"] == "REJECT":
        reasons.append(f"the verifier rejects the winner: {cert['reasons'][0] if cert['reasons'] else 'see the certificate'}")
    journal = [{"key": dsl.key(t), "rule_window": mm, "sharpe": round(float(s), 4)} for (t, mm), s in zip(cands, sharpes, strict=True)]
    journal_text = "\n".join(json.dumps(j, sort_keys=True) for j in journal) + "\n"
    return {
        "found": not reasons,
        "reasons": reasons,
        "best": {**dsl.describe(tree), "rule_window": m, "side": cfg.side, "source": source},
        "search": {
            "candidates": len(cands), "effective_trials": n_eff, "search_bars": split, "lockbox_bars": n - split,
            "best_sharpe": round(obs, 4), "selection": selection, "null_best_sharpe": _quantiles(null_best), "null_runs": len(null_best),
            "p_search_null": None if p_null is None else round(p_null, 4),
            "p_reality_check": rc.get("p_reality_check"), "p_spa": rc.get("p_spa"),
            "periods_per_year": ppy,
        },
        "lockbox": {"opened": 1, "sharpe": round(lock_sharpe, 4), "p": round(lock_p, 4), "bars": int(box.size)},
        "certificate": cert,
        "selftest": check,
        "config": asdict(cfg),
        "journal_sha256": hashlib.sha256(journal_text.encode()).hexdigest(),
        "journal": journal_text,
    }


def _certify(data: pd.DataFrame, source: str, cfg: Config, n_eff: int, ppy: float) -> dict[str, Any]:
    """The certificate of the winner on the whole table, deflated by the *effective* number of trials."""
    from monte_neo.verify import model_from_costs, verify_strategy

    scope: dict[str, Any] = {"__name__": "discover_winner"}
    exec(compile(source, "<discover>", "exec"), scope)  # noqa: S102  # nosec B102 - generated from a tree
    model = model_from_costs(
        commission_bps=cfg.cost_bps / 2, slippage_bps=cfg.cost_bps / 2, side_mode=cfg.side, warmup_bars=130, n_bars=len(data)
    )
    return verify_strategy(data, signal_fn=scope["signal"], source=source, model=model, n_trials=n_eff, periods_per_year=ppy)


def _quantiles(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    a = np.asarray(values)
    return {"median": round(float(np.median(a)), 4), "q95": round(float(np.quantile(a, 0.95)), 4), "max": round(float(a.max()), 4)}


__all__ = ["CANARIES", "Config", "causality_gate", "discover", "selftest", "surrogate"]
