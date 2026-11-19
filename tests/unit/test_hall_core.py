"""Hall of Fame: rules, entry checks, ranking, history, build (no CLI)."""

from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from monte_neo.hall import build as hb
from monte_neo.hall import entry as he
from monte_neo.hall import ranking as hr
from monte_neo.hall import render as hrender
from monte_neo.hall import rules as hrules
from monte_neo.verify.signing import generate_keypair, sign_certificate

ROOT = Path(__file__).resolve().parents[2]
RULES = hrules.load_rules()


def fake_cert(arl: int = 3, depth: int = 1, dsr: float | None = 0.5, verdict: str = "NEEDS_MORE_EVIDENCE", data: str = "d1",
              sig: str | None = "s1", src: str | None = None, date: str = "2026-11-01", n_trials: Any = 5, ret: float = 1.0) -> dict[str, Any]:
    checks = [] if dsr is None else [{"id": "deflated_sharpe", "details": {"deflated_sharpe": dsr}}]
    return {"schema": "strategy-verdict/1", "verdict": verdict, "certificate_id": f"id-{data}-{sig}", "generated_at": f"{date}T00:00:00+00:00",
            "arl": {"level": arl, "depth": depth, "rules_version": "arl-rules/1", "provisional": True},
            "reproducibility": {"engine_version": "v0.54.0", "data_sha256": data, "signals_sha256": sig, "source_sha256": src, "n_trials": n_trials},
            "checks": checks, "metrics": {"total_return": ret}}


@pytest.fixture(scope="module")
def key(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return generate_keypair(tmp_path_factory.mktemp("k") / "m")


def keys_file(root: Path, k: dict[str, str]) -> None:
    (root / "maintainer_keys.json").write_text(json.dumps({"keys": [{"key_id": k["key_id"], "public_key": Path(k["public_key"]).read_text().strip(), "owner": "t"}]}))


def add(root: Path, cert: dict[str, Any], k: dict[str, str] | None = None, tier: str = "A", author: str = "Ann", name: str = "Alpha",
        cat: str = "trend", date: str = "2026-11-01", rules: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = he.make_entry(cert, author=author, strategy=name, category=cat, tier=tier, submitted_at=date, rules=rules or RULES,
                          code_url="https://example.com/x" if tier == "A" else None, idea_credit="idea" if tier == "A" else None,
                          recheck={"reproduced": True, "engine_version": "v0.54.0", "by": "maintainer"} if tier != "C" else None)
    if tier == "B":
        assert k
        entry = he.attest(entry, k["private_key"])
    for sub, doc in (("entries", entry), ("certificates", cert)):
        (root / sub).mkdir(parents=True, exist_ok=True)
        (root / sub / f"{entry['id']}.json").write_text(json.dumps(doc))
    return entry


def items(root: Path) -> list[hr.Item]:
    return hr.load_items(root, RULES)


# ---- rules ----

def test_rules_valid_and_guide_in_sync() -> None:
    assert RULES["version"] == "hall-of-fame/1" and RULES["status"] == "provisional"
    page = (ROOT / "docs/guides/hall-of-fame.md").read_text(encoding="utf-8")
    assert hrules.sync_page(page) == page
    assert "ARL level" in hrules.markdown_score() and "`REJECT`" in hrules.markdown_score()
    assert "| C | self-reported | no |" in hrules.markdown_tiers()
    assert "At most 3 entries" in hrules.markdown_limits() and hrules.markdown_honesty().startswith("1. ")


def test_rules_validation_and_unknown_block() -> None:
    def broken(edit: Any) -> dict[str, Any]:
        r = copy.deepcopy(RULES)
        edit(r)
        return r

    cases = (
        (lambda r: r.pop("tiers"), "lack"),
        (lambda r: [t.update(ranked=False) for t in r["tiers"].values()], "ranked tier"),
        (lambda r: r["medals"].update(gold=5), "medals"),
    )
    for edit, msg in cases:
        with pytest.raises(ValueError, match=msg):
            hrules.validate(broken(edit))
    with pytest.raises(ValueError, match="unknown Hall of Fame block"):
        hrules.sync_page("<!-- hall:nope:start -->\n<!-- hall:nope:end -->")
    assert hrules.sync_page("plain") == "plain"


# ---- entry ----

def test_hash_is_canonical_and_summary_reads_the_certificate() -> None:
    a = fake_cert()
    b = json.loads(json.dumps(a, sort_keys=True, indent=4))
    assert he.certificate_sha256(a) == he.certificate_sha256(b)
    assert he.certificate_sha256({**a, "verdict": "PASS"}) != he.certificate_sha256(a)
    s = he.summarize(a)
    assert (s["arl"], s["depth"], s["deflated_sharpe"], s["n_trials"], s["date"]) == (3, 1, 0.5, 5, "2026-11-01")
    assert he.summarize({})["date"] == "" and he.slug("!!!") == "strategy"


def test_valid_entries_per_tier(tmp_path: Path, key: dict[str, str]) -> None:
    keys_file(tmp_path, key)
    for tier in "ABC":
        e = add(tmp_path, fake_cert(sig=tier), key, tier=tier, name=f"s{tier}")
        assert he.check_entry(e, fake_cert(sig=tier), RULES, hr.load_keys(tmp_path)) == []


def test_entry_field_errors() -> None:
    c = fake_cert()
    e = he.make_entry(c, author="Ann", strategy="S", category="trend", tier="C", submitted_at="2026-11-01", rules=RULES)
    chk = lambda **kw: he.check_entry({**e, **kw}, c, RULES, {})  # noqa: E731
    assert chk() == []
    assert he.check_entry({"id": "x"}, c, RULES, {})[0].startswith("missing fields")
    assert any("author" in x for x in chk(author="a|b"))
    assert any("author" in x for x in chk(author="x" * 81))
    assert any("YYYY-MM-DD" in x for x in chk(submitted_at="2026-1-1"))
    assert any("https" in x for x in chk(code_url="http://x.io/a"))
    assert any("schema" in x for x in chk(schema="other"))
    assert any("tier" in x for x in chk(tier="Z"))
    assert any("category" in x for x in chk(category="moonshot"))
    assert any("missing" in x for x in he.check_entry(e, None, RULES, {}))


def test_certificate_tampering_and_requirements(key: dict[str, str]) -> None:
    c = fake_cert()
    e = he.make_entry(c, author="Ann", strategy="S", category="trend", tier="C", submitted_at="2026-11-01", rules=RULES)
    assert any("SHA-256" in x for x in he.check_entry(e, {**c, "verdict": "PASS"}, RULES, {}))
    for cert, text in ((fake_cert(n_trials=None), "n_trials"), (fake_cert(n_trials=0), "n_trials"), (fake_cert(n_trials=True), "n_trials")):
        e2 = he.make_entry(cert, author="Ann", strategy="S", category="trend", tier="C", submitted_at="2026-11-01", rules=RULES)
        assert any(text in x for x in he.check_entry(e2, cert, RULES, {}))
    old = {**fake_cert(), "arl": None}
    e3 = he.make_entry(old, author="Ann", strategy="S", category="trend", tier="C", submitted_at="2026-11-01", rules=RULES)
    assert any("ARL block" in x for x in he.check_entry(e3, old, RULES, {}))
    other = fake_cert()
    other["arl"]["rules_version"] = "arl-rules/2"
    assert any("differ" in x for x in he.check_entry({**e, "certificate_sha256": he.certificate_sha256(other)}, other, RULES, {}))
    bad = {**c, "schema": "x"}
    e4 = he.make_entry(bad, author="Ann", strategy="S", category="trend", tier="C", submitted_at="2026-11-01", rules=RULES)
    assert any("strategy-verdict/1" in x for x in he.check_entry(e4, bad, RULES, {}))
    signed = sign_certificate(c, key["private_key"])
    es = he.make_entry(signed, author="Ann", strategy="S", category="trend", tier="C", submitted_at="2026-11-01", rules=RULES)
    assert he.check_entry(es, signed, RULES, {}) == []
    forged = {**signed, "verdict": "PASS"}
    ef = {**es, "certificate_sha256": he.certificate_sha256(forged)}
    assert any("signature is not valid" in x for x in he.check_entry(ef, forged, RULES, {}))


def test_tier_requirements_and_attestation(tmp_path: Path, key: dict[str, str]) -> None:
    c = fake_cert()
    mk = lambda tier, **kw: he.make_entry(c, author="Ann", strategy="S", category="trend", tier=tier, submitted_at="2026-11-01", rules=RULES, **kw)  # noqa: E731
    a = mk("A")
    errs = he.check_entry(a, c, RULES, {})
    assert any("recheck" in x for x in errs) and any("code_url" in x for x in errs)
    failed = mk("A", code_url="https://x.io/a", recheck={"reproduced": False})
    assert any("recheck" in x for x in he.check_entry(failed, c, RULES, {}))
    b = mk("B", recheck={"reproduced": True})
    assert he.check_entry(b, c, RULES, {}, draft=True) == []
    assert any("not signed" in x for x in he.check_entry(b, c, RULES, {}))
    good = he.attest(b, key["private_key"])
    pub = Path(key["public_key"]).read_text().strip()
    trusted = {key["key_id"]: pub}
    assert he.check_entry(good, c, RULES, trusted) == []
    assert any("not in maintainer_keys" in x for x in he.check_entry(good, c, RULES, {}))
    assert any("does not match" in x for x in he.check_entry({**good, "author": "Eve"}, c, RULES, trusted))
    bad_sig = {**good, "signature": {**good["signature"], "value": "AAAA"}}
    assert any("does not match" in x for x in he.check_entry(bad_sig, c, RULES, trusted))
    assert any("does not match" in x for x in he.check_entry({**good, "signature": {"public_key": 5}}, c, RULES, trusted))


# ---- ranking ----

def test_order_is_evidence_not_return(tmp_path: Path, key: dict[str, str]) -> None:
    keys_file(tmp_path, key)
    add(tmp_path, fake_cert(arl=3, depth=3, dsr=0.9, sig="a", ret=500.0), name="rich")
    add(tmp_path, fake_cert(arl=4, depth=0, dsr=0.1, sig="b", ret=-0.5), name="sound")
    add(tmp_path, fake_cert(arl=3, depth=3, dsr=0.95, sig="c"), name="deeper-dsr")
    cls = hr.classify(items(tmp_path), RULES)
    assert [i["entry"]["strategy"] for i in cls["ranked"]] == ["sound", "deeper-dsr", "rich"]


def test_ties_dates_and_missing_dsr(tmp_path: Path) -> None:
    add(tmp_path, fake_cert(dsr=None, sig="a", date="2026-10-01"), name="nodsr", date="2026-10-02")
    add(tmp_path, fake_cert(dsr=0.0, sig="b", date="2026-10-05"), name="late", date="2026-10-06")
    add(tmp_path, fake_cert(dsr=0.0, sig="c", date="2026-10-03"), name="early", date="2026-10-06")
    order = [i["entry"]["strategy"] for i in hr.classify(items(tmp_path), RULES)["ranked"]]
    assert order == ["early", "late", "nodsr"]


def test_exclusions(tmp_path: Path) -> None:
    add(tmp_path, fake_cert(verdict="REJECT", sig="r"), name="rejected")
    add(tmp_path, fake_cert(sig="ok"), name="orig", date="2026-11-01")
    add(tmp_path, fake_cert(sig="ok", arl=4), name="clone", date="2026-11-02")  # same data and signals, other name
    add(tmp_path, fake_cert(sig="x", src="code1", data="d2"), name="srcA", date="2026-11-03", author="Cy")
    add(tmp_path, fake_cert(sig="y", src="code1", data="d2"), name="srcB", date="2026-11-03", author="Bob")
    add(tmp_path, fake_cert(sig="self"), tier="C", name="selfrep", author="Bob")
    cls = hr.classify(items(tmp_path), RULES)
    why = {i["entry"]["strategy"]: w for i, w in cls["excluded"]}
    assert "REJECT" in why["rejected"] and "same strategy as" in why["clone"] and "same strategy as" in why["srcB"]
    assert [i["entry"]["strategy"] for i in cls["self_reported"]] == ["selfrep"]
    assert {i["entry"]["strategy"] for i in cls["ranked"]} == {"orig", "srcA"}
    assert hr.tables(cls["ranked"], RULES)["overall"] and all(i["entry"]["tier"] != "C" for i in cls["ranked"])


def test_author_limit_per_month(tmp_path: Path) -> None:
    for n in range(4):
        add(tmp_path, fake_cert(sig=f"s{n}"), name=f"n{n}", date=f"2026-11-0{n + 1}")
    add(tmp_path, fake_cert(sig="dec"), name="dec", date="2026-12-01")
    cls = hr.classify(items(tmp_path), RULES)
    assert [w for _, w in cls["excluded"]] == ["more than 3 entries by this author in 2026-11"]
    assert len(cls["ranked"]) == 4


def test_invalid_items_are_reported(tmp_path: Path) -> None:
    e = add(tmp_path, fake_cert(sig="a"))
    (tmp_path / "certificates" / f"{e['id']}.json").write_text(json.dumps(fake_cert(sig="other")))  # changed certificate
    add(tmp_path, fake_cert(sig="b"), name="moved")
    (tmp_path / "entries" / "wrong-name.json").write_text((tmp_path / "entries" / next(p.name for p in (tmp_path / "entries").iterdir() if "moved" in p.name)).read_text())
    (tmp_path / "entries" / "broken.json").write_text("{not json")
    (tmp_path / "entries" / "list.json").write_text("[]")
    cls = hr.classify(items(tmp_path), RULES)
    msgs = " | ".join(x for i in cls["errors"] for x in i["errors"])
    assert len(cls["errors"]) == 4 and "SHA-256" in msgs and "id must equal the file name" in msgs and "unreadable entry" in msgs


def test_tables_top_n_categories_and_archive(tmp_path: Path) -> None:
    for n in range(4):
        add(tmp_path, fake_cert(arl=3 + n, sig=f"s{n}"), name=f"n{n}", cat="trend" if n < 3 else "carry", author=f"A{n}")
    old = copy.deepcopy(RULES)
    old["version"] = "hall-of-fame/0"
    add(tmp_path, fake_cert(arl=9, sig="old"), name="oldrules", author="Zed", rules=old)
    cls = hr.classify(items(tmp_path), RULES)
    small = {**RULES, "top_n": 2}
    tabs = hr.tables(cls["ranked"], small)
    assert len(tabs["overall"]) == 2 and len(tabs["trend"]) == 2 and len(tabs["carry"]) == 1 and tabs["pairs"] == []
    assert "oldrules" not in [i["entry"]["strategy"] for i in tabs["overall"]]
    arch = hr.archived(cls["ranked"], RULES)
    assert list(arch) == [("hall-of-fame/0", "arl-rules/1")]


def test_history_and_runs() -> None:
    mk = lambda ids: {"overall": [{"entry": {"id": i}} for i in ids]}  # noqa: E731
    h = hr.update_history([], "2026-11", RULES, mk(["a", "b"]))
    h = hr.update_history(h, "2026-12", RULES, mk(["a", "b"]))
    h = hr.update_history(h, "2027-01", RULES, mk(["b", "a", "c"]))
    h = hr.update_history(h, "2027-01", RULES, mk(["b", "a"]))  # same month: replaced, not duplicated
    assert [x["month"] for x in h] == ["2026-11", "2026-12", "2027-01"]
    r = hr.runs(h, RULES, "overall", by_rank=True)
    assert r["a"][0] == {"key": 1, "start": "2026-11", "end": "2026-12", "idx": 1, "current": False}
    assert r["a"][1]["key"] == 2 and r["a"][1]["current"] and r["b"][1]["start"] == "2027-01" and "c" not in r
    presence = hr.runs(h, RULES, "overall", by_rank=False)
    assert len(presence["a"]) == 1 and presence["a"][0]["end"] == "2027-01"
    assert hr.history_text(h).count("\n") == 3


def test_read_history_and_keys(tmp_path: Path) -> None:
    assert hr.read_history(tmp_path / "none.jsonl") == [] and hr.load_keys(tmp_path) == {}
    (tmp_path / "h.jsonl").write_text('{"a": 1}\n\n{"a": 2}\n')
    assert hr.read_history(tmp_path / "h.jsonl") == [{"a": 1}, {"a": 2}]


# ---- render and build ----

def setup_repo(tmp_path: Path, key: dict[str, str]) -> tuple[Path, Path, Path]:
    root = tmp_path / "hall_of_fame"
    root.mkdir()
    keys_file(root, key)
    readme, docs = tmp_path / "README.md", tmp_path / "hall.md"
    readme.write_text("# R\n<!-- hall:top10:start -->\nold\n<!-- hall:top10:end -->\nend\n")
    return root, readme, docs


def test_build_writes_checks_and_follows_history(tmp_path: Path, key: dict[str, str]) -> None:
    root, readme, docs = setup_repo(tmp_path, key)
    add(root, fake_cert(arl=4, sig="a"), key, tier="B", name="Gold one", author="Ann")
    add(root, fake_cert(arl=3, sig="b"), name="Silver", author="Bob")
    add(root, fake_cert(sig="c"), tier="C", name="Selfie", author="Cy")
    add(root, fake_cert(verdict="REJECT", sig="d"), name="Bad", author="Di")
    res = hb.build(root, readme, docs, "2026-11")
    assert res.errors == []
    changed = hb.write(res)
    assert readme in changed and hb.stale(hb.build(root, readme, docs, "2026-11")) == []
    text = readme.read_text()
    assert "🥇 1 | Gold one" in text and "end\n" in text and text.count("Not investment advice") >= 2 and "Selfie" not in text
    page = docs.read_text()
    assert "## Self-reported" in page and "Selfie" in page and "verdict REJECT is never ranked" in page and "raw.githubusercontent.com" in page
    badges = sorted(p.name for p in (root / "badges").glob("*.svg"))
    assert len(badges) == 4  # overall + trend, gold and silver
    svg = (root / "badges" / badges[0]).read_text()
    tree = ET.fromstring(svg)
    assert tree.tag.endswith("svg") and he.certificate_sha256(fake_cert(arl=4, sig="a")) in svg and "not investment advice" in svg
    # a later month with a new leader: the old leader moves to silver and the history shows spans
    add(root, fake_cert(arl=5, sig="e"), name="New leader", author="Ed", date="2026-12-01")
    hb.write(hb.build(root, readme, docs, "2026-12"))
    page = docs.read_text()
    assert "- gold in `overall`: Gold one (Ann), 2026-11 – 2026-11" in page
    # an obsolete badge is removed
    stale_badge = root / "badges" / "zzz.svg"
    stale_badge.write_text("<svg/>")
    res = hb.build(root, readme, docs, "2026-12")
    assert stale_badge in hb.stale(res) and stale_badge in res.obsolete
    hb.write(res)
    assert not stale_badge.exists()


def test_build_refuses_bad_input(tmp_path: Path, key: dict[str, str]) -> None:
    root, readme, docs = setup_repo(tmp_path, key)
    with pytest.raises(ValueError, match="YYYY-MM"):
        hb.build(root, readme, docs, "2026-13")
    readme.write_text("no markers")
    assert any("markers" in e for e in hb.build(root, readme, docs, "2026-11").errors)
    e = add(root, fake_cert(sig="a"))
    (root / "certificates" / f"{e['id']}.json").write_text(json.dumps(fake_cert(sig="forged")))
    assert any("SHA-256" in x for x in hb.build(root, readme, docs, "2026-11").errors)


def test_old_rules_are_archived_not_rewritten(tmp_path: Path, key: dict[str, str]) -> None:
    root, readme, docs = setup_repo(tmp_path, key)
    old = copy.deepcopy(RULES)
    old["version"] = "hall-of-fame/0"
    add(root, fake_cert(arl=8, sig="o"), name="Old timer", rules=old)
    res = hb.build(root, readme, docs, "2026-11")
    hb.write(res)
    arch = root / "archive" / "hall-of-fame-0__arl-rules-1.md"
    assert "Old timer" in arch.read_text() and "no medals" in arch.read_text() and "Not investment advice" in arch.read_text()
    assert "Old timer" not in readme.read_text() and "archive/hall-of-fame-0__arl-rules-1.md" in docs.read_text()


def test_render_helpers_and_empty_tables() -> None:
    assert hrender.medal_of(1, RULES) == "gold" and hrender.medal_of(9, RULES) is None
    assert "No ranked entries" in hrender.table([], RULES, "overall", {}) and hrender.plain_table([], RULES) == "_None._"
    assert hrender.embed_snippets([]) == "_No medals yet._"
    assert hrender._cut("x" * 50, 10) == "x" * 9 + "…"


def test_sync_guide(tmp_path: Path) -> None:
    g = tmp_path / "g.md"
    g.write_text("<!-- hall:score:start -->\nstale\n<!-- hall:score:end -->\n")
    assert hb.sync_guide(g) is True and hb.sync_guide(g) is False


def test_the_repository_hall_is_consistent() -> None:
    root = ROOT / "hall_of_fame"
    hist = hr.read_history(root / "history.jsonl")
    res = hb.build(root, ROOT / "README.md", ROOT / "docs/hall-of-fame.md", max(h["month"] for h in hist))
    assert res.errors == [] and hb.stale(res) == [], "run `monte-neo hall build`"
    its = hr.load_items(root, RULES)
    assert 3 <= len(its) <= 5 and all(i["errors"] == [] for i in its)
    for i in its:  # the seeds are examples: low ARL, provisional rules, not self-reported, never a return claim
        assert i["summary"]["arl"] <= 4 and i["summary"]["provisional"] is True and i["entry"]["tier"] == "B"
        assert i["entry"]["author"] == "Rostyslav Shcherbyna (process), idea: Claude Sonnet 5.5"
