#!/usr/bin/env python3
"""Validate the catalog data and generate cards/, INDEX.md and TYPES.md.

Usage: python build_catalog.py   (needs PyYAML)
"""
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import lab_results  # noqa: E402

ROOT = Path(__file__).parent
DISC = "Not investment advice. Research and education only; past or hypothetical results do not guarantee future results."


def load(name):
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


# What can lose money in a hedged book, by type: the card's "Worst scenario" section (hedged never means risk-free).
WORST = {
    "stat_arb_pairs": ["the relationship breaks and the spread never returns", "both legs gap together in a crash while the hedge ratio is stale", "short borrow is recalled or its rate jumps"],
    "carry": ["the carry flips sign (funding, curve or rate) when it is most crowded", "the hedge leg's margin is called in a fast move"],
    "event_merger_arb": ["the deal breaks: the target falls back to its stand-alone price, many times the spread earned"],
    "convertible_arb": ["credit spreads widen and liquidity vanishes together (2005, 2008)", "short borrow on the stock is recalled"],
    "long_short_equity": ["the long and short books fall together in a deleveraging (August 2007 quant crisis)", "a short squeeze on a crowded short"],
    "market_making": ["adverse selection: the quotes fill only on the side that keeps moving", "a gap through the inventory limit"],
    "short_volatility": ["a volatility spike larger than any in the sample: years of premium lost in days", "margin calls force closing at the worst prices"],
    "crypto_specific": ["the venue halts withdrawals or fails", "a peg, a listing or a relationship that held in the sample breaks for good"],
    "factor_premia": ["the long and short legs reverse together in a factor crash (momentum 2009, value 2020)", "short borrow costs or recalls"],
    "trend_following": ["a sharp reversal after a long trend: the book is positioned the wrong way at the turn"],
}
NEUTRAL_STRUCT = {"MN", "BAS", "SPR", "OPT"}
EXT_CAP = 30
EXTENSIONS = [("MN-1", "strategies_mn.yaml", "market-neutral and arbitrage"),
              ("X-2", "strategies_x2.yaml", "coverage gaps: market making, order flow, machine learning, long volatility, "
                                            "portfolio construction, overlays, crypto events, and controls")]


def validate(strats, types, traps):
    errs = []
    tmap = {t["id"]: t for t in types}
    ids = [s["id"] for s in strats]
    if len(ids) != len(set(ids)):
        errs.append("duplicate strategy ids")
    main = [s for s in strats if not s.get("_ext")]
    ext = [s for s in strats if s.get("_ext")]
    if len(main) > 100:
        errs.append(f"catalog has {len(main)} > 100 entries")
    for label, _f, _w in EXTENSIONS:
        n = sum(1 for s in ext if s["_ext"] == label)
        if n > EXT_CAP:
            errs.append(f"extension {label} has {n} > {EXT_CAP} entries")
    for s in ext:
        if "structure" not in s:
            errs.append(f"{s['id']}: extension entries need structure")
        if s["_ext"] == "MN-1" and "worst" not in s:
            errs.append(f"{s['id']}: MN-1 entries need worst")
    for s in strats:
        if s["type"] not in tmap:
            errs.append(f"{s['id']}: unknown type {s['type']}")
        if s["tier"] not in ("A", "B", "C"):
            errs.append(f"{s['id']}: bad tier")
        for k in s["traps"]:
            if k not in traps:
                errs.append(f"{s['id']}: unknown trap {k}")
        for f in ("name", "source", "formula", "params", "data", "regime", "verification"):
            if f not in s:
                errs.append(f"{s['id']}: missing {f}")
    for t in types:
        for k in t["traps"]:
            if k not in traps:
                errs.append(f"type {t['id']}: unknown trap {k}")
    return errs


def write_cards(strats, tmap, traps):
    cards = ROOT / "cards"
    cards.mkdir(exist_ok=True)
    for old in cards.glob("*.md"):
        old.unlink()
    for s in strats:
        t = tmap[s["type"]]
        body = [f"# {s['name']}", "", f"> {DISC}", "",
                f"- **id:** `{s['id']}`",
                f"- **type:** [{t['name']}](../TYPES.md#{t['id']})",
                f"- **data tier:** {s['tier']} (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)",
                f"- **source:** {s['source']}",
                f"- **verification (2026-11-08):** {s['verification']}", "",
                "## Definition (frozen, from the source)", "", s["formula"], "",
                "Parameters (do not tune):", ""]
        body += [f"- `{k}` = {v}" for k, v in (s["params"] or {}).items()] or ["- none"]
        body += ["", f"**Data needed:** {', '.join(s['data'])}", "",
                 f"**Expected regime behaviour:** {s['regime']}", "", "## Known traps", ""]
        for k in dict.fromkeys(s["traps"] + t["traps"][:2]):
            body.append(f"- **{traps[k]['title']}** - {traps[k]['text']} Monte-Neo: {traps[k]['check']}.")
        body += ["", "## How to measure", "",
                 f"Metrics: {', '.join(t['measure']['metrics'])}.",
                 f"Benchmark: {t['measure']['benchmark']}.",
                 f"Horizon: {t['measure']['horizon']}.", "",
                 "## What Monte-Neo cannot verify", ""] + [f"- {c}" for c in t["cannot"]]
        if s.get("structure") in NEUTRAL_STRUCT or s["type"] in WORST and s["type"] not in ("trend_following", "factor_premia", "crypto_specific"):
            body += ["", "## Worst scenario (hedged is not risk-free)", ""]
            if s.get("worst"):
                body.append(f"- **This strategy:** {s['worst']}")
            body += [f"- {w}" for w in WORST.get(s["type"], [])]
            body += ["- Counterparty: a hedge does not protect the capital held at a venue that fails.", "",
                     "Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` "
                     "(measured losses, leg correlation in stress, and stated shocks with their formulas)."]
        (cards / f"{s['id']}.md").write_text("\n".join(body) + "\n", encoding="utf-8")


def write_index(strats):
    ext = [s for s in strats if s.get("_ext")]
    strats = [s for s in strats if not s.get("_ext")]
    cnt = Counter(s["tier"] for s in strats)
    idx = ["# Strategy catalog index", "", f"> {DISC}", "",
           f"{len(strats)} strategies. Tier A: {cnt['A']}, tier B: {cnt['B']}, tier C: {cnt['C']}. "
           "Generated by `build_catalog.py`; edit the YAML, not this file.", "",
           "Verified results, with every metric: [RESULTS.md](RESULTS.md). Failures: [WHAT_DID_NOT_WORK.md](WHAT_DID_NOT_WORK.md). "
           "ARL / depth and net Sharpe are validation only, holdout sealed, provisional rules, not investment advice.", "",
           "| id | name | type | tier | source | definition check | ARL / depth | net Sharpe |", "|---|---|---|---|---|---|---|---|"]
    found = lab_results.verified_by_catalog()
    for s in strats:
        arl, sh = lab_results.index_cells(s["id"], found)
        idx.append(f"| [{s['id']}](cards/{s['id']}.md) | {s['name']} | {s['type']} | {s['tier']} | {s['source']} | {s['verification'].split(':')[0]} | {arl} | {sh} |")
    for label, fname, what in EXTENSIONS:
        part = [s for s in ext if s["_ext"] == label]
        idx += ["", f"## Extension {label}: {what}", "",
                f"{len(part)} strategies from `{fname}`. Extensions are verified with n_trials = {100 + len(ext)} (the 100 above "
                "plus every extension entry). Hedged cards have a worst-scenario section: hedged is not risk-free.", "",
                "| id | name | type | structure | tier | source | ARL / depth | net Sharpe |", "|---|---|---|---|---|---|---|---|"]
        for s in part:
            arl, sh = lab_results.index_cells(s["id"], found)
            idx.append(f"| [{s['id']}](cards/{s['id']}.md) | {s['name']} | {s['type']} | {s['structure']} | {s['tier']} | {s['source']} | {arl} | {sh} |")
    (ROOT / "INDEX.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    return cnt


def write_types(strats, types, traps):
    tp = ["# Strategy and benchmark types", "", f"> {DISC}", "",
          "Generated from `types.yaml`. Check names marked PLAN are proposed in "
          "[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).", ""]
    for t in types:
        n = sum(1 for s in strats if s["type"] == t["id"])
        tp += [f'<a id="{t["id"]}"></a>', f"## {t['name']}", "",
               f"*Family: {t['family']}. Catalog entries: {n}.*", "", t["what"], "",
               "**How it is measured**", "",
               f"- Metrics: {', '.join(t['measure']['metrics'])}",
               f"- Benchmark: {t['measure']['benchmark']}",
               f"- Horizon: {t['measure']['horizon']}", "", "**Typical traps**", ""]
        tp += [f"- {traps[k]['title']}: {traps[k]['text']}" for k in t["traps"]]
        tp += ["", f"**Monte-Neo checks to apply:** {', '.join(t['checks'])}", "",
               f"**Data needed:** {', '.join(t['data'])}", "", "**Monte-Neo cannot verify:**", ""]
        tp += [f"- {c}" for c in t["cannot"]]
        tp += ["", f"**Key references:** {t['refs']}", ""]
    (ROOT / "TYPES.md").write_text("\n".join(tp) + "\n", encoding="utf-8")


def write_results(strats):
    strats = [s for s in strats if not s.get("_ext")]
    (ROOT / "RESULTS.md").write_text(lab_results.results_md(strats), encoding="utf-8")
    (ROOT / "WHAT_DID_NOT_WORK.md").write_text(lab_results.failures_md(), encoding="utf-8")


def main() -> int:
    traps, types, strats = load("traps.yaml"), load("types.yaml"), load("strategies.yaml")
    for label, fname, _what in EXTENSIONS:
        strats += [{**s, "_ext": label} for s in load(fname)]
    errs = validate(strats, types, traps)
    if errs:
        print("\n".join(errs))
        return 1
    tmap = {t["id"]: t for t in types}
    write_cards(strats, tmap, traps)
    cnt = write_index(strats)
    write_types(strats, types, traps)
    write_results(strats)
    unused = [t["id"] for t in types if not any(s["type"] == t["id"] for s in strats)]
    print(f"ok: {len(strats)} strategies, {len(types)} types, tiers {dict(cnt)}, types without entries: {unused}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
