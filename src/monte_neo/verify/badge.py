"""A "verified by Monte-Neo" badge: a shields.io endpoint file built from a certificate.

Publish the JSON somewhere with a public URL (a gist, GitHub Pages, the repository itself) and point
``https://img.shields.io/endpoint?url=...`` at it. The badge shows the verdict and the certificate id.
"""

from __future__ import annotations

from typing import Any

COLORS = {
    "PASS": "brightgreen",
    "PASS_WITH_WARNINGS": "yellow",
    "NEEDS_MORE_EVIDENCE": "orange",
    "REJECT": "red",
}
LABELS = {
    "PASS": "pass",
    "PASS_WITH_WARNINGS": "pass with warnings",
    "NEEDS_MORE_EVIDENCE": "needs more evidence",
    "REJECT": "reject",
}


def badge_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Shields.io endpoint JSON (``schemaVersion`` 1) for a certificate."""
    verdict = str(report.get("verdict", ""))
    cert_id = str(report.get("certificate_id", ""))[:8]
    text = LABELS.get(verdict, "unknown")
    return {
        "schemaVersion": 1,
        "label": "Monte-Neo",
        "message": f"{text} · {cert_id}" if cert_id else text,
        "color": COLORS.get(verdict, "lightgrey"),
        "namedLogo": "checkmarx" if verdict.startswith("PASS") else None,
    }


def badge_markdown(url: str) -> str:
    """README snippet for a badge whose endpoint JSON is published at ``url``."""
    return f"[![Monte-Neo](https://img.shields.io/endpoint?url={url})](https://neozork.github.io/Monte-Neo/verify/)"


__all__ = ["badge_markdown", "badge_payload"]
