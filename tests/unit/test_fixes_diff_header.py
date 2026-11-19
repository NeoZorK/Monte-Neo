from __future__ import annotations

from monte_neo.verify.fixes import suggest_fixes

SRC = "def signal(df):\n    return df.close.shift(-1) > df.close\n"


def test_diff_header_uses_the_given_file_name() -> None:
    out = suggest_fixes(SRC, filename="my_rule.py")
    assert out["changes"]
    assert "--- my_rule.py" in out["diff"] and "+++ my_rule.causal.py" in out["diff"]


def test_diff_header_default_is_unchanged() -> None:
    out = suggest_fixes(SRC)
    assert out["changes"]
    assert "--- strategy.py" in out["diff"]
