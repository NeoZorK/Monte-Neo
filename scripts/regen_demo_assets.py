#!/usr/bin/env python3
"""Regenerate docs/assets/demo_sma_sweep.png and demo_memory_plan.png.

Uses Metal when available. Refuses to write if SMA sweep returns are flat/zero.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from monte_neo.backtest import (
    ExecutionModel,
    export_sma_sweep,
    export_single,
    plan_research_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets"


def _ohlc(n: int = 50_000, seed: int = 42):
    rng = np.random.default_rng(seed)
    ret = 0.00008 + 0.008 * rng.standard_normal(n)
    ret[10_000:20_000] -= 0.00015
    ret[30_000:40_000] += 0.00012
    close = 100.0 * np.exp(np.cumsum(ret))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1.0 + 0.0005 * rng.random(n))
    low = np.minimum(open_, close) * (1.0 - 0.0005 * rng.random(n))
    return open_, high, low, close


def regen_sma_sweep(device: str = "metal") -> Path:
    open_, high, low, close = _ohlc()
    n = len(close)
    model = ExecutionModel(commission_bps=2.0, slippage_bps=2.0, warmup_bars=50)
    out = export_sma_sweep(
        open_, high, low, close, combos=16, model=model, device=device
    )
    if not out.get("ok"):
        raise RuntimeError(f"export_sma_sweep failed: {out}")
    rows = list(out["metrics"]["rows"])
    returns = np.asarray([r["total_return"] for r in rows], dtype=float)
    labels = [f"{r['fast']}/{r['slow']}" for r in rows]
    if np.allclose(returns, 0.0) or float(np.nanstd(returns)) < 1e-6:
        raise RuntimeError("refusing to publish flat/zero total_return chart")

    best = max(rows, key=lambda r: r["total_return"])
    fast, slow = int(best["fast"]), int(best["slow"])

    def sma(x, w):
        y = np.empty_like(x)
        y[: w - 1] = np.nan
        csum = np.cumsum(x, dtype=np.float64)
        y[w - 1 :] = (csum[w - 1 :] - np.concatenate([[0.0], csum[:-w]])) / w
        return y

    sf, ss = sma(close, fast), sma(close, slow)
    sig = np.zeros(n, dtype=np.int8)
    valid = ~(np.isnan(sf) | np.isnan(ss))
    sig[valid & (sf > ss)] = 1
    sig[valid & (sf < ss)] = -1
    ex = export_single(
        open_, high, low, close, sig, model=model, include_equity=True, equity_stride=100
    )
    eq = np.asarray(ex["equity"], dtype=float)
    eq_t = np.arange(len(eq)) * int(ex.get("equity_stride") or 100)

    fig, axes = plt.subplots(
        2, 1, figsize=(10, 7.2), gridspec_kw={"height_ratios": [1.15, 1]}, constrained_layout=True
    )
    ax = axes[0]
    colors = ["#2a9d8f" if v >= 0 else "#e76f51" for v in returns]
    ax.bar(np.arange(len(returns)), returns, color=colors, width=0.82, edgecolor="none")
    ax.axhline(0.0, color="#333", lw=0.8, alpha=0.7)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("total_return")
    ax.set_title(
        f"Monte-Neo export_sma_sweep · device={out['device']} · n=50k · combos=16"
    )
    ax.grid(True, axis="y", alpha=0.25)
    best_i = int(np.argmax(returns))
    ax.annotate(
        f"best {labels[best_i]}\n{returns[best_i]:+.3f}",
        xy=(best_i, returns[best_i]),
        xytext=(best_i + 1.5, returns[best_i]),
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color="#264653"),
        color="#264653",
    )
    axes[1].plot(eq_t, eq, color="#264653", lw=1.4)
    axes[1].set_title(
        f"Best combo equity (fast={fast}, slow={slow}) · stride={ex.get('equity_stride')}"
    )
    axes[1].set_xlabel("bar")
    axes[1].set_ylabel("equity")
    axes[1].grid(True, alpha=0.25)

    path = OUT / "demo_sma_sweep.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def regen_memory_plan() -> Path:
    sizes = [50_000, 100_000, 500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000]
    host, metal, labels_n = [], [], []
    label_map = {
        50_000: "50k",
        100_000: "100k",
        500_000: "500k",
        1_000_000: "1M",
        2_000_000: "2M",
        5_000_000: "5M",
        10_000_000: "10M",
    }
    for nb in sizes:
        p = plan_research_bytes(n_bars=nb, n_combos=16)
        host.append(p["bytes_peak_est"] / (1024**3))
        metal.append(p["metal_shared_bytes_est"] / (1024**3))
        labels_n.append(label_map[nb])
    last = plan_research_bytes(n_bars=sizes[-1], n_combos=16)
    budget_host = last["bytes_budget"] / (1024**3)
    budget_metal = last["metal_shared_bytes_budget"] / (1024**3)

    fig, ax = plt.subplots(figsize=(10, 5.2), constrained_layout=True)
    x = np.arange(len(sizes))
    ax.plot(x, host, "o-", color="#1d3557", label="host peak est (GiB)", lw=2)
    ax.plot(x, metal, "s--", color="#e9c46a", label="Metal shared est (GiB)", lw=2)
    ax.axhline(budget_host, color="#2a9d8f", ls=":", lw=1.6, label="host soft budget")
    ax.axhline(budget_metal, color="#f4a261", ls=":", lw=1.6, label="Metal shared budget")
    ax.set_xticks(x)
    ax.set_xticklabels(labels_n)
    ax.set_ylabel("GiB")
    ax.set_xlabel("n_bars")
    ax.set_title("plan_research_bytes · 16 combos · 16GB-class gate")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.annotate(
        f"{host[0]:.3f} GiB",
        xy=(0, host[0]),
        xytext=(0.4, host[0] + 0.35),
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color="#1d3557"),
    )
    path = OUT / "demo_memory_plan.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p1 = regen_sma_sweep("metal")
    p2 = regen_memory_plan()
    print("wrote", p1)
    print("wrote", p2)


if __name__ == "__main__":
    main()
