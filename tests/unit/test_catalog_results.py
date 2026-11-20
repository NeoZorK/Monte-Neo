"""The catalog results are generated from Strategy Lab data and stay in step with it."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

CAT = Path(__file__).resolve().parents[2] / "docs" / "catalog"


def _load(name: str):
    sys.path.insert(0, str(CAT))
    spec = importlib.util.spec_from_file_location(name, CAT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generated_files_match_the_generator() -> None:
    lr = _load("lab_results")
    import yaml

    strats = yaml.safe_load((CAT / "strategies.yaml").read_text(encoding="utf-8"))
    assert (CAT / "RESULTS.md").read_text(encoding="utf-8") == lr.results_md(strats)
    assert (CAT / "WHAT_DID_NOT_WORK.md").read_text(encoding="utf-8") == lr.failures_md()


def test_every_row_is_marked_and_unverified_rows_say_so() -> None:
    lr = _load("lab_results")
    import yaml

    strats = yaml.safe_load((CAT / "strategies.yaml").read_text(encoding="utf-8"))
    rows = [ln for ln in lr.results_md(strats).splitlines() if ln.startswith("| [")]
    assert len(rows) == len(strats) == 100
    for ln in rows:
        assert lr.NOTE in ln or lr.NOT_VERIFIED in ln
    verified = lr.verified_by_catalog()
    assert set(verified) <= {s["id"] for s in strats} and len(verified) >= 5


def test_reasons_and_boundaries() -> None:
    lr = _load("lab_results")
    base = {"net_sharpe": 0.5, "sharpe_x2": 0.4, "dsr": 0.99, "alpha_t": 3.0, "beta_share": 0.0, "arl": 5, "n_trials": 10}
    assert lr.reasons(base) == ["no single reason is stored; see the report"]
    assert any("loses money" in r for r in lr.reasons({**base, "net_sharpe": -0.1}))
    assert any("doubled costs" in r for r in lr.reasons({**base, "sharpe_x2": -0.1}))
    assert any("Deflated" in r for r in lr.reasons({**base, "dsr": 0.94}))
    assert not any("Deflated" in r for r in lr.reasons({**base, "dsr": 0.95}))
    assert any("market beta" in r for r in lr.reasons({**base, "beta_share": 0.3}))
    assert any("ARL 3" in r for r in lr.reasons({**base, "arl": 3}))
    assert lr.index_cells("nope", {}) == (lr.NOT_VERIFIED, "-")


def test_failures_page_lists_only_rejected_or_weak() -> None:
    lr = _load("lab_results")
    page = lr.failures_md()
    assert "## Rejected (" in page and "REJECT" in page and "not investment advice" in page.lower()
