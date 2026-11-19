"""Text and SVG output of the Hall of Fame: tables, medal badges. Pure functions of data, no file access."""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape

from monte_neo.disclaimer import SHORT
from monte_neo.hall.ranking import Item

MEDAL_ICON = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}
MEDAL_COLOR = {"gold": ("#f7d774", "#c9981a"), "silver": ("#eef1f4", "#9aa3ad"), "bronze": ("#e3a76b", "#9a5b24")}
RAW_URL = "https://raw.githubusercontent.com/NeoZorK/Monte-Neo/main/hall_of_fame/badges/"
HEAD = "| Rank | Strategy | Author | Category | ARL / depth | Deflated Sharpe | Tier | Holds this rank | Certificate SHA-256 |"


def medal_of(rank: int, rules: dict[str, Any]) -> str | None:
    """``gold`` / ``silver`` / ``bronze`` for a medal rank, else ``None``."""
    return next((m for m, n in rules["medals"].items() if n == rank), None)


def badge_name(item: Item, scope: str, medal: str) -> str:
    """File name of a medal badge."""
    return f"{item['entry']['id']}--{scope}--{medal}.svg"


def _cut(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def row(item: Item, rank: int, rules: dict[str, Any], holds: str) -> str:
    """One table row (every value comes from the entry or the certificate)."""
    e, s = item["entry"], item["summary"]
    medal = medal_of(rank, rules)
    dsr = "n/a" if s["deflated_sharpe"] is None else f"{s['deflated_sharpe']:.3f}"
    arl = f"ARL {s['arl']}, depth {s['depth']}/4" + (" (provisional)" if s["provisional"] else "")
    tier = f"{e['tier']} {rules['tiers'][e['tier']]['name']}"
    return (f"| {MEDAL_ICON[medal] + ' ' if medal else ''}{rank} | {e['strategy']} | {e['author']} | {e['category']} | {arl} | {dsr} | "
            f"{tier} | {holds} | `{e['certificate_sha256'][:16]}…` |")


def table(rows: list[Item], rules: dict[str, Any], scope: str, holds: dict[tuple[str, str], str]) -> str:
    """A ranked table with its disclaimer; a hint when empty."""
    if not rows:
        return f"_No ranked entries yet._\n\n{SHORT}"
    lines = [HEAD, "|---|---|---|---|---|---|---|---|---|"]
    lines += [row(it, n, rules, holds.get((scope, it["entry"]["id"]), "—")) for n, it in enumerate(rows, 1)]
    return "\n".join(lines) + f"\n\n{SHORT}"


def plain_table(rows: list[Item], rules: dict[str, Any]) -> str:
    """Table for entries that are not ranked (self-reported, archived): no rank, no medal."""
    if not rows:
        return "_None._"
    lines = [HEAD.replace("| Rank ", "| # ").replace("Holds this rank", "Submitted"), "|---|---|---|---|---|---|---|---|---|"]
    lines += [row(it, n, {**rules, "medals": {}}, it["entry"]["submitted_at"]) for n, it in enumerate(rows, 1)]
    return "\n".join(lines) + f"\n\n{SHORT}"


def badge_svg(item: Item, rank: int, scope: str, medal: str, holds: str) -> str:
    """A medal badge (SVG) with the SHA-256 of the certificate; texts are escaped."""
    e, s = item["entry"], item["summary"]
    light, dark = MEDAL_COLOR[medal]
    sha = e["certificate_sha256"]
    title = f"Monte-Neo Hall of Fame {medal} ({scope}): {e['strategy']} by {e['author']}, certificate SHA-256 {sha}"
    t = [escape(_cut(x, n)) for x, n in ((e["strategy"], 34), (e["author"], 44), (f"ARL {s['arl']}, depth {s['depth']}/4" + (" - provisional" if s["provisional"] else ""), 44))]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="420" height="190" viewBox="0 0 420 190" role="img" aria-label="{escape(title, {'"': '&quot;'})}">
<title>{escape(title)}</title><desc>Evidence rating, not investment advice. Holds this rank: {escape(holds)}. Rules {escape(e['hall_rules_version'])}, ARL {escape(str(e['arl_rules_version']))}.</desc>
<defs><linearGradient id="m" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{light}"/><stop offset="1" stop-color="{dark}"/></linearGradient></defs>
<rect width="420" height="190" rx="14" fill="#141922" stroke="{dark}" stroke-width="2"/>
<path d="M46 14 L70 70 L94 14 Z" fill="{dark}"/>
<circle cx="70" cy="86" r="40" fill="url(#m)" stroke="{light}" stroke-width="3"/>
<text x="70" y="99" text-anchor="middle" font-family="Georgia,serif" font-size="38" font-weight="700" fill="#141922">{rank}</text>
<text x="70" y="146" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="12" font-weight="700" fill="{light}">{medal.upper()} · {escape(_cut(scope, 14)).upper()}</text>
<g font-family="Helvetica,Arial,sans-serif" fill="#e8ecf2">
<text x="132" y="32" font-size="11" font-weight="700" fill="{light}" letter-spacing="1">MONTE-NEO HALL OF FAME</text>
<text x="132" y="58" font-size="17" font-weight="700">{t[0]}</text>
<text x="132" y="78" font-size="12">{t[1]}</text>
<text x="132" y="98" font-size="12">{t[2]}</text>
<text x="132" y="116" font-size="11" fill="#b9c2cf">Holds this rank: {escape(holds)}</text>
<text x="132" y="136" font-size="9" font-family="Menlo,Consolas,monospace" fill="#b9c2cf">SHA-256 {sha[:32]}</text>
<text x="132" y="148" font-size="9" font-family="Menlo,Consolas,monospace" fill="#b9c2cf">{sha[32:]}</text>
<text x="20" y="176" font-size="10" fill="#b9c2cf">Evidence rating, not investment advice. Simulated results do not predict future returns.</text></g>
</svg>
"""


def embed_snippets(winners: list[tuple[Item, str, str]]) -> str:
    """Markdown snippets (one per medal) that a winner can paste into their own README."""
    if not winners:
        return "_No medals yet._"
    out = []
    for item, scope, medal in winners:
        e = item["entry"]
        out.append(f"**{MEDAL_ICON[medal]} {e['strategy']} ({scope})**\n\n```markdown\n![Monte-Neo Hall of Fame {medal}, {scope}]({RAW_URL}{badge_name(item, scope, medal)})\n```")
    return "\n\n".join(out)


__all__ = ["badge_name", "badge_svg", "embed_snippets", "medal_of", "plain_table", "row", "table"]
