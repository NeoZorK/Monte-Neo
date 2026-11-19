"""Survivorship bias in a universe or basket, priced when the missing names are declared.

A universe built from today's listings contains only names that survived. The names that were delisted, collapsed or
dropped are missing, and with them their losses. Without a list of them the bias cannot be measured, so the check does
**not** pass silently: it warns, and the Alpha Readiness Level is capped (see ``readiness.CEILINGS``).

With a declared list of missing symbols ``m`` (``delisted``) next to ``n`` symbols in the data, an equal-weight
holding of the full universe returns ``(n * R + m * D) / (n + m)`` where ``R`` is the data's equal-weight buy-and-hold
return and ``D`` the assumed total return of a missing name (``delist_return``). The strategy's overstatement is
approximated as ``m / (n + m) * exposure * (R - D)`` with ``exposure`` its average gross long weight in a missing
name's place: a rough estimate that assumes it would have held the missing names like the rest.

``D = -0.30`` follows Shumway (1997), "The delisting bias in CRSP data", Journal of Finance 52(1), for performance-related
delistings in equities (Shumway and Warther 1999 find about -0.55 for NASDAQ). Delisted crypto tokens usually lose far
more: pass your own per-symbol ``delist_return``. This is an estimate; the real remedy is the missing price history.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from monte_neo.verify.checks import check

DEFAULT_DELIST_RETURN = -0.30
BIAS_WARN = 0.25  # share of the strategy's return that the missing names would remove


def parse_delisted(delisted: Any, default: float = DEFAULT_DELIST_RETURN) -> list[tuple[str, float]]:
    """Normalise ``delisted`` to ``[(symbol, assumed total return)]``.

    Accepts a list of symbols, a list of ``(symbol, return)`` pairs, or a table with ``symbol`` and optional
    ``delist_return``.

    Raises:
        ValueError: A return below -100 %, a table without a ``symbol`` column, or a duplicate symbol.
    """
    if delisted is None:
        return []
    if isinstance(delisted, pd.DataFrame):
        if "symbol" not in delisted.columns:
            raise ValueError("the delisted table needs a symbol column (and optionally delist_return)")
        col = delisted["delist_return"] if "delist_return" in delisted.columns else pd.Series(default, index=delisted.index)
        items = list(zip(delisted["symbol"].astype(str), col.fillna(default).astype(float), strict=True))
    else:
        items = [(str(x[0]), float(x[1])) if isinstance(x, (list, tuple)) else (str(x), float(default)) for x in delisted]
    if any(d < -1.0 for _, d in items):
        raise ValueError("a delist_return cannot be below -100%")
    if len({s for s, _ in items}) != len(items):
        raise ValueError("duplicate symbols in the delisted list")
    return items


def survivorship_bias_row(
    base: dict[str, Any], *, delisted: list[tuple[str, float]] | None, n_symbols: int, bench_return: float,
    total_return: float, exposure: float,
) -> dict[str, Any]:
    """Row ``survivorship``.

    Args:
        base: The structural ``survivorship`` row (symbols that stop trading inside the data).
        delisted: Declared missing symbols with assumed returns; ``None`` means nothing declared, ``[]`` means
            "there were none".
        n_symbols: Symbols present in the data.
        bench_return: Equal-weight buy-and-hold total return of the data (``R``).
        total_return: The strategy's total return.
        exposure: Its average gross long weight (0..1).

    Returns:
        ``skip`` for one symbol; ``warn`` (ceiling on ARL) when nothing is declared and no symbol ever stopped trading;
        ``pass`` when symbols stop inside the data, or when the declared list leaves the result intact;
        ``warn`` when the declared names would remove at least 25 % of the return; ``fail`` when they would remove all of it.
    """
    det = dict(base.get("details", {}))
    if base["status"] == "skip":
        return base
    if det.get("exante_rule_required"):  # carry baskets: only a recomputed composition rule decides, never a declared list
        return base
    if delisted is None:
        if base["status"] == "pass":  # delistings are already inside the data
            return base
        return check("survivorship", "integrity", "warn",
                     "no list of delisted or dropped symbols was given and none stops trading in the data: the universe may be "
                     "today's survivors, so the result is capped at ARL 4 until the missing names are added or declared (delisted=...)", det)
    m = len(delisted)
    det.update(declared_missing=m, declared=[s for s, _ in delisted][:20])
    if m == 0:
        return check("survivorship", "integrity", "pass", "declared: no symbol was delisted or dropped from this universe", det)
    mean_d = sum(d for _, d in delisted) / m
    share = m / (n_symbols + m)
    over = share * max(exposure, 0.0) * (bench_return - mean_d)
    adjusted = total_return - over
    det.update(mean_delist_return=mean_d, missing_share=share, overstatement=over, adjusted_total_return=adjusted)
    text = (f"{m} declared missing names ({share:.0%} of the full universe, assumed return {mean_d:+.0%}) would lower the "
            f"strategy's total return from {total_return:+.1%} to about {adjusted:+.1%}")
    if total_return > 0.0 and adjusted <= 0.0:
        return check("survivorship", "integrity", "fail", "survivorship removes the profit: " + text, det)
    if total_return > 0.0 and over >= BIAS_WARN * total_return:
        return check("survivorship", "integrity", "warn", "survivorship inflates the result: " + text, det)
    return check("survivorship", "integrity", "pass", text, det)


__all__ = ["BIAS_WARN", "DEFAULT_DELIST_RETURN", "parse_delisted", "survivorship_bias_row"]
