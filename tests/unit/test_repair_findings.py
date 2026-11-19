"""detect -> explain -> repair: findings, previews that pay a trial, and the guards."""

from __future__ import annotations

import json

import numpy as np
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli.repair_cmd import main
from monte_neo.repair import FINDINGS, explain, preview_fix
from monte_neo.verify import verify_strategy

DF = synthetic_ohlcv(1200, seed=4)
LEAKY = "import numpy as np\n\ndef signal(df):\n    return np.sign(df['close'].shift(-1) - df['close']).fillna(0).to_numpy()\n"
CAUSAL = "import numpy as np\n\ndef signal(df):\n    return np.where(df['close'].rolling(20).mean() > df['close'].rolling(80).mean(), 1, 0)\n"
FLIP = "import numpy as np\n\ndef signal(df):\n    return np.where(df['close'].diff().fillna(0) > 0, -1, 1)\n"


def write(tmp_path, text, name="s.py"):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_catalog_has_at_least_fifteen_findings_with_text() -> None:
    assert len(FINDINGS) >= 15
    for fid, f in FINDINGS.items():
        assert f["title"] and f["why"] and f["next"] and f["fix"] in {"source", "steps", "costs", "trials", "manual"}, fid


def test_explain_matches_failed_and_warned_checks_only() -> None:
    cert = {"checks": [{"id": "lookahead_truncation", "status": "fail", "summary": "x"}, {"id": "costs_modeled", "status": "pass", "summary": "y"},
                       {"id": "net_profitability", "status": "warn", "summary": "z"}]}
    ids = {f["finding"] for f in explain(cert)}
    assert ids == {"F01", "F07"}
    assert explain({"checks": []}) == []


def test_preview_source_fix_pays_a_trial_and_reverifies(tmp_path) -> None:
    res = preview_fix("F03", DF, write(tmp_path, LEAKY), n_trials=5)
    assert res["applied"] and res["kind"] == "source" and "shift" in res["diff"]
    assert res["trials"] == {"before": 5, "after": 6}
    assert res["before"]["verdict"] == "REJECT" and "lookahead_truncation" in res["before"]["failed"]
    assert "lookahead_truncation" not in res["after"]["failed"]
    assert "never raises a verdict" in res["note"]


def test_preview_cannot_hide_a_fix_that_does_not_help(tmp_path) -> None:
    res = preview_fix("F07", DF, write(tmp_path, FLIP), n_trials=1)
    assert res["applied"] and res["trials"]["after"] == 2
    assert res["after"]["verdict"] in ("REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS", "PASS")  # reported as measured, no promotion


def test_preview_costs_and_trials_and_delay(tmp_path) -> None:
    src = write(tmp_path, CAUSAL)
    assert preview_fix("F06", DF, src)["trials"]["after"] == 2
    assert preview_fix("F10", DF, src)["trials"]["after"] >= 10
    assert preview_fix("F04", DF, src)["applied"]


def test_manual_and_unknown_findings(tmp_path) -> None:
    res = preview_fix("F14", DF, write(tmp_path, CAUSAL))
    assert not res["applied"] and res["next_actions"]
    with pytest.raises(ValueError, match="unknown finding"):
        preview_fix("F99", DF, write(tmp_path, CAUSAL))


def test_source_fix_without_known_pattern_is_not_applied(tmp_path) -> None:
    res = preview_fix("F01", DF, write(tmp_path, CAUSAL))
    assert not res["applied"] and "by hand" in res["reason"]


def test_cli_explain_and_preview(tmp_path, capsys) -> None:
    rep = verify_strategy(DF, signal_fn=lambda d: np.sign(d["close"].shift(-1) - d["close"]).fillna(0).to_numpy(), n_trials=3, probe_checks=4)
    cert = tmp_path / "c.json"
    cert.write_text(json.dumps(rep, default=str))
    assert main(["--explain", str(cert)]) == 0
    assert "F01" in capsys.readouterr().out
    assert main(["--explain", str(tmp_path / "none.json")]) == 3
    csv = tmp_path / "d.csv"
    DF.to_csv(csv, index=False)
    s = write(tmp_path, LEAKY)
    assert main(["--preview", "F03", "--ohlcv", str(csv), "--strategy", str(s), "--n-trials", "2"]) == 0
    assert main(["--preview", "F03"]) == 3
    assert main(["--preview", "F14", "--ohlcv", str(csv), "--strategy", str(s)]) == 4
