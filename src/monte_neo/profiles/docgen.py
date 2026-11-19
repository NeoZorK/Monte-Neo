"""Markdown generated from the profile rules file (``scripts/gen_profiles_doc.py`` writes it into the guide)."""

from __future__ import annotations

from monte_neo.profiles.registry import load_profiles

START, END = "<!-- profiles:start -->", "<!-- profiles:end -->"


def markdown_profiles() -> str:
    """One section per profile: summary, benchmark, required checks, metrics, not-assessed items, traps and controls."""
    out: list[str] = []
    for p in load_profiles()["profiles"]:
        out += [f"### `{p['id']}`: {p['title']}", "", p["summary"], "", f"- **Benchmark:** {p['benchmark']}",
                f"- **Required checks:** {', '.join(f'`{c}`' for c in p['required_checks'])}"]
        if p.get("recommended_checks"):
            out.append(f"- **Recommended checks:** {', '.join(f'`{c}`' for c in p['recommended_checks'])}")
        out.append(f"- **Metrics to read:** {', '.join(p['metrics_focus'])}")
        out += ["", "| Not assessed | Why |", "|---|---|"] + [f"| {n['what']} | {n['why']} |" for n in p["not_assessed"]]
        out += ["", "| Trap | What it does | Expected |", "|---|---|---|"]
        out += [f"| `{t['id']}` | {t['description']} | {_expect(t['expect'])} |" for t in p["traps"]]
        out += ["", "| Honest control | What it is | Expected |", "|---|---|---|"]
        out += [f"| `{c['id']}` | {c['description']} | {_expect(c['expect'])} |" for c in p["controls"]]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _expect(e: dict) -> str:
    parts = []
    if "check" in e:
        parts.append(f"`{e['check']}` is {e['status']}")
    if "verdict" in e:
        parts.append(f"verdict {e['verdict']}")
    if "verdict_not" in e:
        parts.append(f"verdict is not {e['verdict_not']}")
    if "any_check_fails_in" in e:
        parts.append(f"a {e['any_check_fails_in']} check fails")
    if "no_check_fails_in" in e:
        parts.append(f"no {e['no_check_fails_in']} check fails")
    if "checks_not_failing" in e:
        parts.append("none fails: " + ", ".join(f"`{c}`" for c in e["checks_not_failing"]))
    if "all_skipped" in e:
        parts.append("not assessed: " + ", ".join(f"`{c}`" for c in e["all_skipped"]))
    return "; ".join(parts)
