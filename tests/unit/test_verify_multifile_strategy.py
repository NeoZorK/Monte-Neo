"""A strategy split over several files (helper module, package, parameter file) imports and verifies everywhere."""

from __future__ import annotations

import sys

import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import verify_strategy
from monte_neo.verify.ingest import load_signal_fn


@pytest.fixture()
def project(tmp_path):
    folder = tmp_path / "my strategy"
    (folder / "pkg").mkdir(parents=True)
    (folder / "helper_mn_qa.py").write_text("def sma(x, n):\n    return x.rolling(n).mean()\n")
    (folder / "pkg" / "__init__.py").write_text("from .ind import ema\n")
    (folder / "pkg" / "ind.py").write_text("def ema(x, n):\n    return x.ewm(span=n, adjust=False).mean()\n")
    (folder / "params.json").write_text('{"fast": 12, "slow": 60}')
    (folder / "strat.py").write_text(
        "import json, os\n"
        "from helper_mn_qa import sma\n"
        "from pkg import ema\n"
        "P = json.load(open(os.path.join(os.path.dirname(__file__), 'params.json')))\n"
        "def signal(df):\n"
        "    return (ema(df['close'], P['fast']) > sma(df['close'], P['slow'])).astype(int)\n"
    )
    yield folder / "strat.py"
    sys.modules.pop("helper_mn_qa", None)
    sys.modules.pop("pkg", None)


def test_helper_modules_next_to_the_strategy_import(project) -> None:
    fn, _ = load_signal_fn(project)
    df = synthetic_ohlcv(400, seed=1)
    assert len(fn(df)) == 400


def test_the_strategy_folder_never_shadows_installed_modules(project, tmp_path) -> None:
    shadow = project.parent / "numpy.py"
    shadow.write_text("raise RuntimeError('shadowed')\n")
    load_signal_fn(project)
    import numpy

    assert hasattr(numpy, "ndarray")
    assert str(project.parent.resolve()) == sys.path[-1] or str(project.parent.resolve()) in sys.path
    assert sys.path.index(str(project.parent.resolve())) > 0


@pytest.mark.parametrize("options", [{}, {"jobs": 2}, {"isolate": True}, {"isolate": True, "jobs": 2, "timeout": 120}])
def test_multi_file_strategy_verifies_in_every_mode(project, options) -> None:
    df = synthetic_ohlcv(800, seed=2)
    report = verify_strategy(df, strategy=str(project), **options)
    statuses = {c["id"]: c["status"] for c in report["checks"]}
    assert statuses["determinism"] == "pass" and statuses["lookahead_truncation"] == "pass"
    assert statuses["external_data"] == "pass"
