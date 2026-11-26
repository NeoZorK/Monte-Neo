"""Virtual books replayed from the journal: the paper book (mainnet prices, modelled costs) and the testnet book (real fills).

Both start from the capital of the ``start`` entry and change only through ``paper_fill`` / ``fill`` entries (and, on a
perpetual-futures venue, ``funding`` entries for that book), so every
number is derived from the journal and can be recomputed by anyone who has it. Testnet balance resets by Binance do not
touch the virtual testnet book.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def replay(entries: Iterable[dict[str, Any]], book: str) -> dict[str, Any]:
    """Cash, positions and the NAV history of ``book`` (``paper`` or ``testnet``)."""
    kind = "paper_fill" if book == "paper" else "fill"
    cash, start, fees = 0.0, None, 0.0
    pos: dict[str, float] = {}
    marks: list[dict[str, Any]] = []
    for e in entries:
        b = e["body"]
        if e["kind"] == "start":
            start, cash = b, float(b["capital"])
        elif e["kind"] == kind:
            sign = 1.0 if b["side"] == "BUY" else -1.0
            pos[b["symbol"]] = pos.get(b["symbol"], 0.0) + sign * float(b["qty"])
            cash -= sign * float(b["qty"]) * float(b["price"]) + float(b["fee_usdt"])
            fees += float(b["fee_usdt"])
        elif e["kind"] == "funding" and b.get("book") == book:
            cash += float(b["amount_usdt"])
        elif e["kind"] == "mark":
            px = b["prices"]
            nav_now = cash + sum(q * px[s] for s, q in pos.items() if s in px)
            marks.append({"day": b["day"], "nav": nav_now, "prices": px})
    return {"book": book, "start": start, "cash": cash, "positions": pos, "fees": fees, "marks": marks}


def nav(acc: dict[str, Any], prices: dict[str, float]) -> float:
    return float(acc["cash"] + sum(q * prices[s] for s, q in acc["positions"].items() if s in prices))


def daily_returns(marks: list[dict[str, Any]]) -> list[float]:
    return [b["nav"] / a["nav"] - 1.0 if a["nav"] else 0.0 for a, b in zip(marks, marks[1:], strict=False)]
