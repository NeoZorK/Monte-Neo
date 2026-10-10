"""The one "not investment advice" text that every report, certificate, CLI run and MCP answer carries.

Keep the wording here only: reports, the CLI, the MCP server, the docs footer and the tests read these constants,
so the text cannot drift between outputs.
"""

from __future__ import annotations

SHORT = (
    "Not investment advice: a research example, not a call to trade or a promise of profit. "
    "Simulated results do not predict future returns."
)

FULL = (
    "Not investment advice. Monte-Neo is a research and verification tool. Its reports, examples and reference "
    "strategies illustrate a method; they are not a recommendation, an offer or a call to buy, sell or trade any "
    "instrument, and not a promise of profit. Simulated and past results do not predict future returns. Trading can "
    "lose money, including more than the initial capital when leverage is used. Decisions and their consequences are "
    "yours; consult a licensed adviser if you need advice."
)

# What the verifier measures, said before the advice notice in certificates.
SCOPE = "Checks backtest methodology (look-ahead, costs, selection bias), not future profit."

# The same, for alpha reports: they judge a score and its portfolio, not a backtest.
ALPHA_SCOPE = "Checks whether a score predicts returns and whether its portfolio can be traded, not future profit."

# HTML footer: small but readable (12 px, muted colour with at least 4.5:1 contrast in both themes, printed too).
HTML_CSS = (
    ".disclaimer{font-size:12px;line-height:1.4;color:var(--mute);border-top:1px solid var(--line);"
    "margin-top:28px;padding-top:10px}@media print{.disclaimer{color:#444}}"
)


def html_footer() -> str:
    """The full notice as an HTML paragraph with the ``disclaimer`` class (style: :data:`HTML_CSS`).

    Returns:
        ``<p class='disclaimer'>...</p>`` (the text is a constant without markup characters).
    """
    return f"<p class='disclaimer'>{FULL}</p>"


__all__ = ["ALPHA_SCOPE", "FULL", "HTML_CSS", "SCOPE", "SHORT", "html_footer"]
