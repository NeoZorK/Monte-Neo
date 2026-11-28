"""Compute every calibration number of the ARL paper from per-case results.

Usage: python analyze.py LABEL=PATH [LABEL=PATH ...] [--out numbers.md]
PATH is a results.parquet, a results.csv or a run directory that holds one of them.
Optional: --overlay LABEL=BASE,TOP  builds a run in which the cases present in TOP replace those of BASE
(used for the "silent" arm: the parity run with its asymmetric cases replaced).
Intervals are Wilson 95 %.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

Z = 1.96
COLS = ["id", "i", "group", "population", "track", "kind", "arl_level", "truth_max_level", "years", "K", "sharpe", "edge", "caps",
        "seed", "blocked_level", "blocking_rule", "arl_depth", "rules_version", "base_seed", "arm"]


def load(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.is_dir():
        p = p / "results.parquet" if (p / "results.parquet").exists() else p / "results.csv"
    if p.suffix == ".parquet":
        import pyarrow.parquet as pq

        have = pq.ParquetFile(p).schema_arrow.names
        df = pd.read_parquet(p, columns=[c for c in COLS if c in have])
    else:
        df = pd.read_csv(p, usecols=lambda c: c in COLS, low_memory=False)
    for c in ("i", "arl_level", "truth_max_level", "years", "K", "sharpe", "edge", "seed", "blocked_level", "arl_depth", "base_seed"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if df["id"].duplicated().any():
        raise SystemExit(f"duplicate case ids in {p}")
    if df["arl_level"].isna().any():
        raise SystemExit(f"missing levels in {p}")
    return df


def rate(mask: pd.Series) -> str:
    n, k = len(mask), int(mask.sum())
    if n == 0:
        return "n/a"
    p = k / n
    d = 1 + Z * Z / n
    mid = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return f"{100 * p:.2f} % [{100 * max(0, mid - h):.2f}, {100 * min(1, mid + h):.2f}] ({k:,}/{n:,})"


def planted_x(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df.population == "C") & df.kind.str.match(r"planted_E\d")]


def asymmetric(df: pd.DataFrame) -> pd.Series:
    """Cases whose inputs differ between the parity and the silent arm."""
    return (df.kind == "hidden_trials") | df.kind.str.startswith("zoo_trap:")


def software_check(check: pd.DataFrame, parity: pd.DataFrame, silent: pd.DataFrame) -> list[str]:
    """P4: a full silent run of the first cases equals parity (symmetric cases) and silent (asymmetric cases)."""
    cols = ["arl_level", "arl_depth", "blocked_level", "blocking_rule", "caps"]
    out = ["\n## Software check (P4)"]
    for name, part, ref in (("symmetric cases against parity", check[~asymmetric(check)], parity),
                            ("asymmetric cases against silent", check[asymmetric(check)], silent)):
        r = ref.set_index("id").reindex(part.id)
        absent = int(r.arl_level.isna().sum())
        diff = (part.set_index("id")[cols].astype(str) != r[cols].astype(str)).any(axis=1)
        out.append(f"- {name}: {len(part):,} compared, {int(diff.sum())} differ, {absent} absent from the reference")
    return out


def real_series(cases: pd.DataFrame, manifest: pd.DataFrame) -> pd.Series:
    """Asset class of the series each real-data noise case drew: replays the generator's first two random draws."""
    m = manifest.sort_values("series_id")
    cls = m.set_index("series_id").asset_class
    out = []
    for seed, years in zip(cases.seed.astype(int), cases.years.astype(int)):
        rng = np.random.default_rng(seed)
        n = years * 365
        rng.standard_normal(n)
        ok = m.series_id[m.rows >= n].to_numpy()
        if len(ok) == 0:
            raise SystemExit(f"no series with {n} bars")
        out.append(cls.loc[int(rng.choice(ok))])
    return pd.Series(out, index=cases.index)


def real_report(df: pd.DataFrame, manifest: pd.DataFrame) -> list[str]:
    s = df[df.kind == "null_real"].copy()
    s["cls"] = real_series(s, manifest)
    out = ["\n### Noise on real bars by asset class\n| asset class | years | above level 3 |\n|---|---|---|"]
    for cls, g in s.groupby("cls"):
        out.append(f"| {cls} | all | {rate(g.arl_level > 3)} |")
        for y, h in g.groupby("years"):
            out.append(f"| {cls} | {int(y)} | {rate(h.arl_level > 3)} |")
    return out


def report(df: pd.DataFrame) -> list[str]:
    out: list[str] = []
    a, b = df[df.population == "A"], df[df.population == "B"]
    cv = df[(df.population == "C") & (df.track == "V")]
    cx = planted_x(df)
    fp = lambda s: s.arl_level > s.truth_max_level  # noqa: E731
    out.append(f"cases: {len(df):,} (A {len(a):,}, B {len(b):,}, C {(df.population == 'C').sum():,}); distinct (kind, seed): "
               f"{len(df[['kind', 'seed']].drop_duplicates()):,}")
    out.append("\n### Headline\n| measure | value |\n|---|---|")

    def row(name: str, mask: pd.Series) -> None:
        out.append(f"| {name} | {rate(mask)} |")

    row("False promotion, A (traps)", fp(a))
    row("False promotion, B (noise)", fp(b))
    row("B on random walks and noise scores", fp(b[b.kind != "null_real"]))
    row("B on real market bars", fp(b[b.kind == "null_real"]))
    h = a[a.kind == "hidden_trials"]
    row("Hidden-trials trap at level 4 or above", h.arl_level >= 4)
    r = a[a.kind == "regime_decay"]
    row("Regime-decay trap above its maximum", fp(r))
    c = a[a.kind == "cost_omission"]
    row("Cost-omission trap above its maximum", fp(c))
    row("Planted single-asset edge, level 3 or above", cv.arl_level >= 3)
    row("Planted single-asset edge, level 4 or above", cv.arl_level >= 4)
    row("Planted single-asset edge, level 5 or above", cv.arl_level >= 5)
    row("Planted single-asset edge, level 6 or above", cv.arl_level >= 6)
    row("Planted cross-sectional edge E1-E4, level 3 or above", cx.arl_level >= 3)
    row("Planted cross-sectional edge E1-E4, level 6 or above", cx.arl_level >= 6)
    out.append("\n### False promotion by trap type\n| trap | max level | above maximum |\n|---|---|---|")
    for kind, s in a.groupby("kind"):
        out.append(f"| {kind} | {int(s.truth_max_level.iloc[0])} | {rate(fp(s))} |")
    out.append("\n### Honest twins of the cross-sectional traps\n| twin | level 6 or above |\n|---|---|")
    for kind, s in df[df.kind.str.startswith("zoo_twin:")].groupby("kind"):
        out.append(f"| {kind} | {rate(s.arl_level >= 6)} |")
    out.append("\n### Noise by data and K\n| data | K | above level 3 |\n|---|---|---|")
    for (kind, k), s in b.groupby(["kind", "K"]):
        out.append(f"| {kind} | {int(k)} | {rate(fp(s))} |")
    out.append("\n### Regime-decay by sample length\n| years | above maximum |\n|---|---|")
    for y, s in r.groupby("years"):
        out.append(f"| {int(y)} | {rate(fp(s))} |")
    for level in (3, 6):
        out.append(f"\n### Single-asset power, level {level} or above\n| Sharpe | years | rate |\n|---|---|---|")
        for (sh, y), s in cv.groupby(["sharpe", "years"]):
            out.append(f"| {sh} | {int(y)} | {rate(s.arl_level >= level)} |")
    out.append("\n### Cross-sectional power by edge\n| edge | level 3 or above | level 6 or above |\n|---|---|---|")
    for kind, s in cx.groupby("kind"):
        out.append(f"| {kind} | {rate(s.arl_level >= 3)} | {rate(s.arl_level >= 6)} |")
    zoo = a[a.kind.str.startswith("zoo_trap:")]
    out.append("\n### Evidence ceilings\n| measure | value |\n|---|---|")
    row("Hidden-trials cases capped by missing trial evidence", h.caps.fillna("").str.contains("trial_evidence"))
    if "blocking_rule" in df.columns:
        only = zoo[(zoo.blocked_level == 5) & (zoo.blocking_rule == "universe_lookahead")]
        out.append(f"| Cross-sectional traps stopped at level 5 by the universe check alone | {len(only):,}/{len(zoo):,} |")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("runs", nargs="*", help="LABEL=PATH")
    ap.add_argument("--overlay", action="append", default=[], help="LABEL=BASE,TOP")
    ap.add_argument("--out", default=None)
    ap.add_argument("--expect", type=int, default=None, help="number of cases every run should hold")
    ap.add_argument("--check", default=None, help="CHECK_RUN_PATH,PARITY_LABEL,SILENT_LABEL")
    ap.add_argument("--manifest", default=str(Path(__file__).with_name("bars_manifest.csv")))
    a = ap.parse_args()
    manifest = pd.read_csv(a.manifest)
    notes: dict[str, str] = {}
    runs: dict[str, pd.DataFrame] = {}
    for item in a.runs:
        label, path = item.split("=", 1)
        runs[label] = load(path)
    for item in a.overlay:
        label, pair = item.split("=", 1)
        base, top = (load(x) for x in pair.split(","))
        if not asymmetric(top).all():
            raise SystemExit("overlay: TOP holds cases whose inputs do not differ between arms")
        need = asymmetric(base)
        missing = len(set(base.id[need]) - set(top.id))
        notes[label] = f"asymmetric cases of BASE missing from TOP: {missing}"
        runs[label] = pd.concat([base[~need], top], ignore_index=True)  # never fall back to a BASE result
    lines = ["# ARL calibration numbers"]
    for label, df in runs.items():
        lines += [f"\n## {label}"]
        if a.expect:
            lines.append(f"cases expected {a.expect:,}, present {len(df):,}, missing {a.expect - len(df):,}")
        if label in notes:
            lines.append(notes[label])
        lines += report(df) + real_report(df, manifest)
    if a.check:
        path, par, sil = a.check.split(",")
        lines += software_check(load(path), runs[par], runs[sil])
    text = "\n".join(lines) + "\n"
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
