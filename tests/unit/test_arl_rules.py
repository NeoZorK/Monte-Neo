"""The ARL rules file is the single source of truth: the loader, the generated docs, the authorship, the readiness link."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from monte_neo import arl_rules
from monte_neo import readiness as readiness_mod
from monte_neo.arl_rules import (
    describe_requirement,
    load_rules,
    markdown_caps,
    markdown_depth,
    markdown_honesty,
    markdown_levels,
    page_in_sync,
    sync_page,
    validate,
)

ROOT = Path(__file__).resolve().parents[2]
AUTHORSHIP = ("The Alpha Readiness Level (ARL) was devised by Rostyslav Shcherbyna, author of Monte-Neo; it is modelled on the idea "
              "of a technology readiness level and is a Monte-Neo scale, not an industry standard.")


def test_rules_file_is_valid_and_provisional() -> None:
    r = load_rules()
    assert r["schema"] == r["version"] == "arl-rules/2" and r["status"] == "provisional"
    assert [lv["level"] for lv in r["levels"]] == list(range(1, 10))
    assert load_rules("arl-rules/2") is r
    assert [c["id"] for c in r["depth"]["criteria"]] == ["D1", "D2", "D3", "D4"] and r["depth"]["max"] == 4
    for n in range(1, 10):
        assert set(r["depth"]["levels"][str(n)]) == {"D1", "D2", "D3", "D4"}


def test_unknown_version_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown ARL rules version"):
        load_rules("arl-rules/99")


def test_validate_rejects_broken_files() -> None:
    good = load_rules()
    bad = copy.deepcopy(good)
    del bad["honesty"]
    with pytest.raises(ValueError, match="lack"):
        validate(bad)
    bad = copy.deepcopy(good)
    bad["status"] = "draft"
    with pytest.raises(ValueError, match="provisional or frozen"):
        validate(bad)
    bad = copy.deepcopy(good)
    bad["levels"].pop()
    with pytest.raises(ValueError, match="numbered 1..9"):
        validate(bad)
    bad = copy.deepcopy(good)
    del bad["depth"]["levels"]["3"]["D4"]
    with pytest.raises(ValueError, match="level 3 needs"):
        validate(bad)
    bad = copy.deepcopy(good)
    bad["depth"]["levels"]["2"]["D1"]["needs"] = ""
    with pytest.raises(ValueError, match="text and needs"):
        validate(bad)
    bad = copy.deepcopy(good)
    bad["depth"]["levels"]["2"]["D1"]["rule"] = {"type": "all", "of": [{"type": "magic"}]}
    with pytest.raises(ValueError, match="unknown rule type"):
        validate(bad)


def test_authorship_is_published_verbatim() -> None:
    assert load_rules()["authorship"] == AUTHORSHIP
    for page in ("README.md", "docs/guides/dossier-readiness-monitor.md", "docs/guides/arl.md"):
        assert AUTHORSHIP in (ROOT / page).read_text(encoding="utf-8"), page
    assert AUTHORSHIP in (readiness_mod.__doc__ or "").replace("\n", " ").replace("  ", " ")


def test_docs_equal_the_rules_file() -> None:
    for page in ("docs/guides/arl.md", "docs/guides/dossier-readiness-monitor.md"):
        assert page_in_sync(ROOT / page), f"{page} is out of sync with arl_rules_v2.json: run monte-neo readiness --sync-docs {page}"


def test_a_changed_threshold_makes_the_docs_stale() -> None:
    page = (ROOT / "docs/guides/arl.md").read_text(encoding="utf-8")
    changed = copy.deepcopy(load_rules())
    changed["depth"]["levels"]["3"]["D3"]["text"] = "at least 500 closed trades"
    assert sync_page(page, changed) != page and "at least 500 closed trades" in sync_page(page, changed)
    assert sync_page(page) == page


def test_sync_page_unknown_block() -> None:
    with pytest.raises(ValueError, match="unknown ARL block"):
        sync_page("<!-- arl:nope:start -->\n<!-- arl:nope:end -->")
    assert sync_page("no markers") == "no markers"


def test_generated_blocks_cover_the_rules() -> None:
    r = load_rules()
    md = markdown_levels() + markdown_depth() + markdown_honesty() + markdown_caps()
    for lv in r["levels"]:
        assert lv["name"] in md
    assert describe_requirement(r["levels"][3]["requirements"]) == "`ic` + `signal_placebo` or `timing_significance`; `selection_adjusted_sharpe`"
    assert "caps the level at 1" in markdown_caps() and "paper, testnet, simulated" in markdown_caps()
    assert markdown_honesty().startswith("1. ")


def _thresholds(rule: dict) -> list[float]:
    out = [rule[k] for k in ("value", "max", "min_t") if isinstance(rule.get(k), (int, float))]
    for sub in rule.get("of", []):
        out += _thresholds(sub)
    return out


def test_every_numeric_threshold_appears_in_its_documented_text() -> None:
    """A threshold changed in the rule but not in its text (or the reverse) is a red test."""
    for n, crits in load_rules()["depth"]["levels"].items():
        for cid, c in crits.items():
            numbers = {float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.?\d*", c["text"])}
            for t in _thresholds(c["rule"]) if "custody" not in c["text"] else []:  # a presence flag, not a threshold
                candidates = {t, round(t * 100, 6)} | ({5.0, 6.0} if abs(t - 5 / 6) < 1e-9 else set()) | ({6.0} if t == 182 else set())  # 182 days = 6 months
                assert numbers & candidates, f"level {n} {cid}: threshold {t} is not in the text {c['text']!r}"


def test_readiness_reads_only_the_rules_file(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = {"checks": [{"id": "data_integrity", "status": "pass", "category": "integrity"}, {"id": "lookahead_truncation", "status": "pass", "category": "lookahead"},
                       {"id": "net_profitability", "status": "pass", "category": "economics"}, {"id": "cost_margin", "status": "pass", "category": "economics"}]}
    assert readiness_mod.readiness(rows)["level"] == 3
    changed = copy.deepcopy(load_rules())
    changed["levels"][2]["requirements"] = [[[["market_impact", "OK"]]]]  # level 3 now needs a different check
    monkeypatch.setattr(readiness_mod, "load_rules", lambda version=None: changed)
    assert readiness_mod.readiness(rows)["level"] == 2
    assert readiness_mod.LEVELS[3][0] == "It earns after costs" and readiness_mod.CEILINGS["survivorship"][0] == 4


def test_rules_file_json_is_what_load_returns() -> None:
    assert json.loads(arl_rules.RULES_FILE.read_text(encoding="utf-8")) == load_rules()


def test_citation_file_is_untouched() -> None:
    import subprocess

    # A release may bump version and date-released; everything else (authors, title, licence) stays as on main.
    out = subprocess.run(["git", "show", "github/main:CITATION.cff"], cwd=ROOT, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        pytest.skip("github/main is not available")

    def stable(text: str) -> list[str]:
        return [ln for ln in text.splitlines() if not ln.startswith(("version:", "date-released:"))]

    assert stable((ROOT / "CITATION.cff").read_text(encoding="utf-8")) == stable(out.stdout)
