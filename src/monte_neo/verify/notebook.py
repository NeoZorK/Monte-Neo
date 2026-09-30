"""Show a certificate as a report inside Jupyter, VS Code notebooks and other rich displays.

``verify_strategy`` and ``verify_grid`` return a :class:`Certificate`: a plain ``dict`` (so JSON dumps,
indexing and every existing caller work unchanged) that also draws itself as the HTML report in a notebook and prints as one summary line. The page is put
in a sandboxed ``iframe`` (``srcdoc``), so its styles never leak into the notebook and the notebook's
styles never leak into it.
"""

from __future__ import annotations

import html
from typing import Any

FRAME_HEIGHT = 1100


class Certificate(dict):  # type: ignore[type-arg]
    """A ``strategy-verdict/1`` certificate that renders as the HTML report in a notebook cell."""

    def __repr__(self) -> str:
        """A short line instead of a 50 KB dict; the data itself is still there (``report["checks"]``, ``dict(report)``)."""
        checks = self.get("checks")
        rows = checks if isinstance(checks, list) else []
        failed = sum(1 for c in rows if isinstance(c, dict) and c.get("status") == "fail")
        return f"<Certificate {self.get('verdict')} {self.get('certificate_id')}: {len(rows)} checks, {failed} failed>"

    def _repr_html_(self) -> str:
        from monte_neo.verify.report_html import render_html

        page = html.escape(render_html(dict(self)), quote=True)
        return (
            f'<iframe sandbox srcdoc="{page}" style="width:100%;height:{FRAME_HEIGHT}px;border:0" '
            'title="Monte-Neo verification report"></iframe>'
        )

    def save_html(self, path: str) -> str:
        """Write the report to ``path`` and return the path."""
        from monte_neo.verify.report_html import write_html

        return str(write_html(dict(self), path))


def show(report: dict[str, Any]) -> Certificate:
    """Wrap any certificate dict (for example one loaded from JSON) so a notebook cell draws it."""
    return report if isinstance(report, Certificate) else Certificate(report)


__all__ = ["Certificate", "show"]
