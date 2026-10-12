"""``validation-dossier/1``: one folder a model-risk committee, a validator or an auditor can read and rerun.

The dossier is built from a finished certificate (and, optionally, an alpha report and a live-monitoring report). It
adds what a committee asks for and a certificate does not say in words: purpose and scope, the assumptions, every
limitation, the environment, a clause-by-clause map to a framework, the exact command to reproduce, and blank sign-off
fields. It is evidence for a validation, not a statement of compliance.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from monte_neo import disclaimer
from monte_neo._version import __version__
from monte_neo.dossier.frameworks import framework_map
from monte_neo.readiness import readiness

DOSSIER_SCHEMA_ID = "validation-dossier/1"
PACKAGES = ("numpy", "pandas", "numba", "monte-neo")

# What no run of the verifier can establish; repeated in every dossier.
STANDING_LIMITS = (
    "The verifier tests the backtest's methodology on the data given; it does not forecast future returns.",
    "The economic rationale of the idea (why it should work) is a human judgement; the dossier gives evidence, not that judgement.",
    "Costs, fills and latency are models: queue position and partial fills are not modelled.",
    "A strategy that behaves differently when it detects a test can only be caught by the probes it does not detect.",
)


def environment() -> dict[str, Any]:
    """Python, platform and package versions of this run (for the reproduction section)."""
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return {"python": sys.version.split()[0], "platform": platform.platform(), "engine_version": __version__, "packages": versions}


def limitations(cert: dict[str, Any]) -> list[str]:
    """Every limitation of this certificate in plain words: skipped checks, assumptions, scope notes, standing limits."""
    out: list[str] = []
    model = (cert.get("reproducibility") or {}).get("model") or {}
    if model:
        fill = "next bar's open" if model.get("fill_policy", "next_bar_open") == "next_bar_open" else "next bar's close"
        out.append(f"Fills at the {fill}; commission {model.get('commission_bps')} bps and slippage {model.get('slippage_bps')} bps per side.")
    if cert.get("scope"):
        out.append(str(cert["scope"]))
    for item in (cert.get("assumptions") or {}).values() if isinstance(cert.get("assumptions"), dict) else []:
        out.append(str(item))
    for row in cert.get("checks", []):
        if row.get("status") == "skip":
            out.append(f"Not checked: {row['id']} ({row.get('summary', '')}).")
    out.extend(STANDING_LIMITS)
    return out


def reproduce_command(cert: dict[str, Any]) -> str:
    """The shell command that reruns the certificate (inputs named as placeholders)."""
    settings = (cert.get("reproducibility") or {}).get("settings") or {}
    if settings.get("kind") == "returns":
        return "monte-neo verify --returns RETURNS.csv --recheck certificate.json"
    cmd = "monte-neo verify --recheck certificate.json --ohlcv DATA.csv --strategy STRATEGY.py"
    if settings.get("events_sha256"):
        cmd += " --events EVENTS.csv"
    return cmd


def build_dossier(
    cert: dict[str, Any],
    *,
    framework: str = "generic",
    meta: dict[str, Any] | None = None,
    alpha: dict[str, Any] | None = None,
    live: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a ``validation-dossier/1`` from a certificate.

    Args:
        cert: A ``strategy-verdict/1`` certificate (signed or not).
        framework: ``generic``, ``sr11-7``, ``ss1-23`` or ``rts6``.
        meta: Free fields for the committee: ``name``, ``owner``, ``purpose``, ``scope``, ``developer``, ``tier``.
        alpha: An optional ``alpha-report/1`` for the same strategy's signal.
        live: An optional ``live-monitor/1`` report.

    Returns:
        The dossier dict; :func:`write_dossier` writes it as a folder.
    """
    info = {k: str(v) for k, v in (meta or {}).items() if v is not None}
    body = {
        "schema": DOSSIER_SCHEMA_ID,
        "certificate_id": cert.get("certificate_id"),
        "verdict": cert.get("verdict"),
        "meta": info,
        "summary": {
            "verdict": cert.get("verdict"),
            "reasons": cert.get("reasons", [])[:8],
            "next_actions": cert.get("next_actions", [])[:8],
            "metrics": cert.get("metrics", {}),
        },
        "checks": cert.get("checks", []),
        "framework": framework_map(cert, framework, live=live is not None),
        "readiness": readiness(certificate=cert, alpha=alpha, live=live),
        "limitations": limitations(cert),
        "reproduce": {"command": reproduce_command(cert), "reproducibility": cert.get("reproducibility", {})},
        "environment": environment(),
        "alpha": alpha,
        "live": live,
        "sign_off": [{"role": r, "name": "", "date": "", "signature": ""} for r in ("Model developer", "Independent validator", "Model owner")],
        "disclaimer": disclaimer.FULL,
    }
    digest = json.dumps({"c": cert.get("certificate_id"), "f": framework, "m": info, "a": (alpha or {}).get("verdict")}, sort_keys=True)
    body["dossier_id"] = hashlib.sha256(digest.encode()).hexdigest()[:16]
    body["generated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    return body


def write_dossier(dossier: dict[str, Any], cert: dict[str, Any], out_dir: str | Path, lite: bool = False) -> Path:
    """Write the folder: ``dossier.html``, ``dossier.json``, ``certificate.json``, ``environment.json``,
    ``REPRODUCE.md``, ``limitations.md`` (and ``dossier-lite.html`` with ``lite``). Returns the folder."""
    from monte_neo.dossier.html import render_dossier

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "dossier.json").write_text(json.dumps(dossier, indent=2, default=str), encoding="utf-8")
    (out / "certificate.json").write_text(json.dumps(cert, indent=2, default=str), encoding="utf-8")
    (out / "environment.json").write_text(json.dumps(dossier["environment"], indent=2), encoding="utf-8")
    (out / "dossier.html").write_text(render_dossier(dossier), encoding="utf-8")
    if lite:
        from monte_neo.dossier.lite import render_lite

        (out / "dossier-lite.html").write_text(render_lite(dossier), encoding="utf-8")
    (out / "limitations.md").write_text("# Limitations\n\n" + "\n".join(f"- {x}" for x in dossier["limitations"]) + "\n", encoding="utf-8")
    (out / "REPRODUCE.md").write_text(
        "# Reproduce\n\nWith the same data and strategy, and monte-neo "
        f"{dossier['environment']['engine_version']}:\n\n```bash\npip install 'monte-neo=={__version__.lstrip('v')}'\n"
        f"{dossier['reproduce']['command']}\n```\n\nExpected: `\"reproduced\": true` and certificate id "
        f"`{dossier['certificate_id']}`.\n", encoding="utf-8",
    )
    return out


__all__ = ["DOSSIER_SCHEMA_ID", "build_dossier", "environment", "limitations", "reproduce_command", "write_dossier"]
