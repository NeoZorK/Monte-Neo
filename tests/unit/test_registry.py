"""``monte-neo registry``: list, show, import with hash and ledger checks, try, and the deploy command (offline)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from monte_neo.cli import registry_cmd
from monte_neo.cli.entry import main as entry_main
from monte_neo.registry import RegistryError, client, trial

CODE = "def signal(df):\n    return [1.0] * len(df)\n\n\ndef target_weights(closes_by_symbol):\n    return {'BTCUSDT': 1.0}\n"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _w(root: Path, rel: str, text: str) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return _sha(text)


def _chain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prev = "0" * 64
    for n, r in enumerate(rows):
        r.update({"v": 1, "seq": n, "ts": "2026-11-21T00:00:00Z", "prev": prev})
        r["hash"] = _sha(json.dumps(r, sort_keys=True))
        prev = r["hash"]
    return rows


def make_registry(root: Path, *, in_ledger: bool = True, importable: bool = True) -> Path:
    spec = {"catalog_id": "T-001", "code": {}, "data": {"symbols": ["BTCUSDT"], "start": "2024-01-01", "end": "2024-03-31"},
            "try": {"verify": {"n_trials": 7, "fee_bps": 10, "slippage_bps": 5}},
            "deploy": {"binance_spot_testnet": True, "rebalance": "daily", "symbols": ["BTCUSDT"]}}
    code_sha = _w(root, "strategies/T-001/strategy.py", CODE)
    spec["code"] = {"path": "strategies/T-001/strategy.py", "sha256": code_sha}
    spec_sha = _w(root, "specs/T-001.spec.json", json.dumps(spec))
    record = {"evaluation": {"verifier": "monte-neo", "verifier_version": "0.54.0", "verdict": "NEEDS_MORE_EVIDENCE", "arl_level": 4, "certificate_id": "abc123",
                             "metrics": {"sharpe_full_pre_holdout": 1.3},
                             "gate": {"name": "Lab gate", "criteria": "ARL >= 6", "passed": False, "why": "ARL 4, 22 trades"}}}
    rec_sha = _w(root, "records/T-001.json", json.dumps(record))
    sources = [{"id": "records/T-001.json", "sha256": rec_sha}, {"id": "strategies/T-001/strategy.py", "sha256": code_sha}]
    rows = [{"type": "freeze", "body": {}}, {"type": "record", "body": {"sources": sources if in_ledger else [{"id": "x", "sha256": "0" * 64}]}}]
    ledger = _chain(rows)
    (root / "ledger").mkdir()
    (root / "ledger" / "ledger.jsonl").write_text("\n".join(json.dumps(r) for r in ledger) + "\n", encoding="utf-8")
    entry: dict[str, Any] = {
        "id": "T-001", "name": "Test strategy", "asset_class": "crypto", "verdict": "NEEDS_MORE_EVIDENCE", "arl": 4, "gate_passed": False,
        "importable": importable, "summary": "A test record.", "signal": "test", "ledger_status": "NEGATIVE_RESULT_UNDER_PROTOCOL",
        "deploy": {"binance_spot_testnet": True, "rebalance": "daily", "symbols": ["BTCUSDT"]} if importable else {"binance_spot_testnet": False, "why": "no public code in this record"},
        "files": {"code": {"path": "strategies/T-001/strategy.py", "sha256": code_sha}, "record": {"path": "records/T-001.json", "sha256": rec_sha},
                  "spec": {"path": "specs/T-001.spec.json", "sha256": spec_sha}},
    }
    index = {"schema": "registry-index/1", "ledger_head": ledger[-1]["hash"], "records": [entry]}
    (root / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return root


@pytest.fixture()
def reg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_registry(tmp_path / "registry")
    monkeypatch.setenv("MONTE_NEO_REGISTRY", str(root))
    monkeypatch.chdir(tmp_path)
    return root


def test_list_and_json(reg: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert registry_cmd.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "T-001" in out and "NEEDS_MORE_EVIDENCE" in out and "deployable" in out
    assert registry_cmd.main(["list", "--deployable", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["records"][0]["id"] == "T-001"


def test_show(reg: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert registry_cmd.main(["show", "T-001"]) == 0
    out = capsys.readouterr().out
    assert "ARL 4" in out and "ARL >= 6" in out and "22 trades" in out and "monte-neo registry import T-001" in out
    assert registry_cmd.main(["show", "NOPE"]) == 3


def test_import_happy_path(reg: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert registry_cmd.main(["import", "T-001"]) == 0
    d = tmp_path / "strategies" / "T-001"
    assert (d / "strategy.py").read_text() == CODE
    prov = json.loads((d / "provenance.json").read_text())
    assert prov["ledger"]["seq"] == 1 and prov["files"]["strategy.py"]["sha256"] == _sha(CODE)
    assert {"spec.json", "record.json", "README.md"} <= {p.name for p in d.iterdir()}
    assert "registry try T-001" in (d / "README.md").read_text() and "--mode dry" in (d / "README.md").read_text()


def test_tampered_code_refused(reg: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (reg / "strategies/T-001/strategy.py").write_text(CODE + "# changed\n")
    assert registry_cmd.main(["import", "T-001", "--dir", str(tmp_path / "x")]) == 3
    assert "SHA-256 mismatch" in capsys.readouterr().err
    assert not (tmp_path / "x").exists()


def test_record_not_in_ledger_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("MONTE_NEO_REGISTRY", str(make_registry(tmp_path / "r", in_ledger=False)))
    assert registry_cmd.main(["import", "T-001", "--dir", str(tmp_path / "x")]) == 3
    assert "not in the ledger" in capsys.readouterr().err


def test_ledger_head_mismatch_refused(reg: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    idx = json.loads((reg / "index.json").read_text())
    idx["ledger_head"] = "f" * 64
    (reg / "index.json").write_text(json.dumps(idx))
    assert registry_cmd.main(["import", "T-001", "--dir", str(tmp_path / "x")]) == 3
    assert "head mismatch" in capsys.readouterr().err


def test_not_importable_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("MONTE_NEO_REGISTRY", str(make_registry(tmp_path / "r", importable=False)))
    assert registry_cmd.main(["import", "T-001", "--dir", str(tmp_path / "x")]) == 3
    assert "no public code in this record" in capsys.readouterr().err


def test_unreachable_registry_exit_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("MONTE_NEO_REGISTRY", str(tmp_path / "missing"))
    assert registry_cmd.main(["list"]) == 2


def _bars(start_ms: int, end_ms: int) -> list[list[Any]]:
    out, t, px = [], start_ms, 100.0
    while t <= end_ms:
        px *= 1.002
        out.append([t, str(px), str(px * 1.01), str(px * 0.99), str(px), "10", t + 86_399_999])
        t += 86_400_000
    return out


def test_try_prints_table_and_deploy_command(reg: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: dict[str, Any] = {}
    monkeypatch.setattr(trial, "fetch_klines", lambda sym, a, b: calls.setdefault("sym", sym) and _bars(a, b))

    def fake_verify(csv: Path, strategy: Path, n: int, fee: float, slip: float) -> dict[str, Any]:
        calls["args"] = (csv.name, strategy.name, n, fee, slip)
        return {"verdict": "NEEDS_MORE_EVIDENCE", "certificate_id": "mine42", "arl": {"level": 3}, "metrics": {"sharpe_annualized": 1.25}}

    monkeypatch.setattr(trial, "run_verify", fake_verify)
    d = tmp_path / "s"
    assert registry_cmd.main(["try", "T-001", "--dir", str(d)]) == 0
    out = capsys.readouterr().out
    assert calls["sym"] == "BTCUSDT" and calls["args"][2:] == (7, 10.0, 5.0)
    assert "abc123" in out and "mine42" in out and "1.25" in out and "engine version" in out
    assert f"monte-neo deploy init --strategy {d}/strategy.py --certificate {d}/certificate.json --symbols BTCUSDT --rebalance daily --mode dry" in out
    assert json.loads((d / "certificate.json").read_text())["certificate_id"] == "mine42"
    csv = next((d / "data").glob("*.csv"))
    assert csv.read_text().splitlines()[0] == "timestamp,open,high,low,close,volume"
    calls.clear()
    assert registry_cmd.main(["try", "T-001", "--dir", str(d)]) == 0  # cached CSV: no second download
    assert "sym" not in calls


def test_try_multi_symbol_not_supported(reg: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert registry_cmd.main(["import", "T-001", "--dir", str(tmp_path / "m")]) == 0
    p = tmp_path / "m" / "spec.json"
    spec = json.loads(p.read_text())
    spec["data"]["symbols"] = ["BTCUSDT", "ETHUSDT"]
    p.write_text(json.dumps(spec))
    assert registry_cmd.main(["try", "T-001", "--dir", str(tmp_path / "m")]) == 2
    assert "not supported yet" in capsys.readouterr().err


def test_try_refuses_changed_code(reg: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert registry_cmd.main(["import", "T-001", "--dir", str(tmp_path / "c")]) == 0
    with (tmp_path / "c" / "strategy.py").open("a") as f:
        f.write("# edited\n")
    assert registry_cmd.main(["try", "T-001", "--dir", str(tmp_path / "c")]) == 3


def test_entry_dispatch_and_help(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["monte-neo", "--help"])
    assert entry_main() == 0
    assert "registry" in capsys.readouterr().out


def test_unsafe_path_and_non_https(tmp_path: Path) -> None:
    with pytest.raises(RegistryError):
        client.read_file(str(tmp_path), "../etc/passwd")
    with pytest.raises(RegistryError):
        client.http_get("http://example.com/index.json")


def test_lint_allows_latest_bar_in_target_weights_only() -> None:
    from monte_neo.verify.lint import lint_source

    live = "def target_weights(c):\n    return {'A': float(c['A'].iloc[-1] > 0)}\n"
    assert not [f for f in lint_source(live)["findings"] if f["rule"] == "last_row"]
    sig = "def signal(df):\n    return df['close'].iloc[-1]\n"
    assert [f for f in lint_source(sig)["findings"] if f["rule"] == "last_row"]
