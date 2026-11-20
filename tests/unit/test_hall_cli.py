"""``monte-neo hall``: build, submit and attest, with real certificates and real rechecks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli import hall_cmd
from monte_neo.cli.entry import main as entry_main
from monte_neo.hall import entry as he
from monte_neo.verify import verify_strategy
from monte_neo.verify.signing import generate_keypair

SMA = "def signal(df, fast=10, slow=40):\n    c = df['close']\n    return (c.rolling(fast).mean() > c.rolling(slow).mean()).astype(int)\n"
AUTHOR = ["--author", "Ann", "--category", "trend"]


@pytest.fixture(scope="module")
def lab(tmp_path_factory: pytest.TempPathFactory) -> dict:
    d = tmp_path_factory.mktemp("lab")
    df = synthetic_ohlcv(1500, seed=2)
    (d / "s.py").write_text(SMA)
    df.to_parquet(d / "data.parquet")
    other = synthetic_ohlcv(900, seed=5)
    other.to_parquet(d / "other.parquet")
    cert = verify_strategy(df, strategy=str(d / "s.py"), n_trials=1)
    (d / "cert.json").write_text(json.dumps(cert))
    (d / "reject.json").write_text(json.dumps({**cert, "verdict": "REJECT"}))
    return {"dir": d, "key": generate_keypair(d / "m")}


def run(*argv: str) -> int:
    return hall_cmd.main(list(argv))


def a(lab: dict, name: str = "data.parquet") -> list[str]:
    d = lab["dir"]
    return ["--ohlcv", str(d / name), "--strategy-file", str(d / "s.py")]


def readme(tmp_path: Path) -> Path:
    p = tmp_path / "README.md"
    p.write_text("<!-- hall:top10:start -->\n<!-- hall:top10:end -->\n")
    return p


def test_submit_tier_a_reproduces_and_prepares_files(lab: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = lab["dir"]
    out, root = tmp_path / "out", tmp_path / "root"
    code = run("submit", str(d / "cert.json"), *AUTHOR, "--name", "SMA demo", "--tier", "A", "--code-url", "https://example.com/r", *a(lab),
               "--out", str(out), "--root", str(root), "--date", "2026-11-10")
    text = capsys.readouterr().out
    assert code == 0 and "Not investment advice" in text and "pull request" in text
    entry = json.loads(next((out / "entries").glob("*.json")).read_text())
    assert entry["recheck"]["reproduced"] is True and entry["tier"] == "A"
    cert = json.loads(next((out / "certificates").glob("*.json")).read_text())
    assert he.check_entry(entry, cert, hall_cmd.load_rules(), {}) == []


def test_submit_refusals(lab: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = lab["dir"]
    base = ["submit", str(d / "cert.json"), *AUTHOR, "--name", "S", "--out", str(tmp_path / "o"), "--root", str(tmp_path / "r"), "--date", "2026-11-10"]
    assert run(*base, "--tier", "A", "--code-url", "https://x.io/r") == 3 and "--ohlcv" in capsys.readouterr().err  # no data to recheck
    assert run(*base, "--tier", "A", "--code-url", "https://x.io/r", *a(lab, "other.parquet")) == 3  # does not reproduce
    assert run(*base, "--tier", "A", *a(lab)) == 3 and "code_url" in capsys.readouterr().err
    rej = ["submit", str(d / "reject.json"), *AUTHOR, "--name", "S", "--tier", "C", "--out", str(tmp_path / "o"), "--root", str(tmp_path / "r")]
    assert run(*rej) == 3 and "never ranked" in capsys.readouterr().err
    assert run("submit", str(d / "missing.json"), *AUTHOR, "--name", "S", "--tier", "C") == 3
    assert run("submit") == 3 and run("nonsense") == 3 and run("--help") == 0
    assert not (tmp_path / "o").exists()


def test_tier_b_flow_attest_build_and_duplicates(lab: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d, key = lab["dir"], lab["key"]
    out, root, rd, docs = tmp_path / "out", tmp_path / "hall_of_fame", readme(tmp_path), tmp_path / "docs" / "hall.md"
    assert run("submit", str(d / "cert.json"), *AUTHOR, "--name", "Private SMA", "--tier", "B", "--out", str(out), "--root", str(root), "--date", "2026-11-10") == 0
    assert "privately" in capsys.readouterr().out
    draft = next((out / "entries").glob("*.json"))
    cert = d / "cert.json"
    att = ["attest", str(draft), "--cert", str(cert), "--key", key["private_key"], "--root", str(root), "--date", "2026-11-10"]
    assert run(*att, *a(lab, "other.parquet")) == 3 and "not reproduced" in capsys.readouterr().err
    assert run(*att) == 3 and "--ohlcv" in capsys.readouterr().err
    assert not root.exists()
    forged = [x if x != str(cert) else str(d / "reject.json") for x in att]
    assert run(*forged, *a(lab)) == 3 and "SHA-256" in capsys.readouterr().err
    # the key is trusted only after the maintainer lists it
    root.mkdir(exist_ok=True)
    (root / "maintainer_keys.json").write_text(json.dumps({"keys": [{"key_id": key["key_id"], "public_key": Path(key["public_key"]).read_text().strip()}]}))
    assert run(*att, *a(lab)) == 0
    signed = json.loads(next((root / "entries").glob("*.json")).read_text())
    assert signed["recheck"]["by"] == "maintainer" and signed["signature"]["key_id"] == key["key_id"]
    build = ["build", "--root", str(root), "--readme", str(rd), "--docs", str(docs), "--guide", str(tmp_path / "none.md"), "--month", "2026-11"]
    assert run(*build, "--check") == 1 and "out of date" in capsys.readouterr().out
    assert run(*build) == 0
    # The current table ranks only certificates computed with its ARL rules version; one computed with newer rules is kept
    # in a separate table, without a medal, until the maintainer starts a new table (docs/guides/hall-of-fame.md).
    from monte_neo.arl_rules import load_rules
    from monte_neo.hall.rules import load_rules as hall_rules

    same = load_rules()["version"] == hall_rules()["arl_rules_version"]
    assert "Private SMA" in rd.read_text() if same else any("Private SMA" in f.read_text() for f in root.rglob("*.md"))
    assert run(*build, "--check") == 0 and "up to date" in capsys.readouterr().out
    # the same strategy under another name is refused at submit time, and attesting it again is refused too
    dup = ["submit", str(d / "cert.json"), *AUTHOR, "--name", "Renamed", "--tier", "B", "--out", str(tmp_path / "o2"), "--root", str(root), "--date", "2026-11-11"]
    assert run(*dup) == 3 and "same strategy" in capsys.readouterr().err
    # tampering with the entry breaks the build
    path = next((root / "entries").glob("*.json"))
    path.write_text(json.dumps({**signed, "author": "Eve"}))
    assert run(*build) == 3 and "does not match" in capsys.readouterr().err
    # only tier B drafts are attested
    tier_c = json.loads(draft.read_text()) | {"tier": "C"}
    draft.write_text(json.dumps(tier_c))
    assert run(*att, *a(lab)) == 3 and "only tier B" in capsys.readouterr().err


def test_build_defaults_month_and_syncs_the_guide(lab: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, rd, docs, guide = tmp_path / "root", readme(tmp_path), tmp_path / "hall.md", tmp_path / "g.md"
    root.mkdir()
    guide.write_text("<!-- hall:score:start -->\nold\n<!-- hall:score:end -->\n")
    args = ["build", "--root", str(root), "--readme", str(rd), "--docs", str(docs), "--guide", str(guide)]
    assert run(*args) == 0 and "ARL level" in guide.read_text()
    assert run(*args, "--check") == 0  # the month comes from the history just written
    assert run("build", "--root", str(root), "--readme", str(rd), "--docs", str(docs), "--guide", str(guide), "--check", "--month", "2030-01") == 1
    monkeypatch.setattr(sys, "argv", ["monte-neo", "hall", "--help"])
    assert entry_main() == 0


def test_entry_point_lists_the_command(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["monte-neo", "--help"])
    entry_main()
    assert "hall " in capsys.readouterr().out
