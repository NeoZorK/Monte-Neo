"""Scripts for real data: market downloads (parsers only, no network), the wild scan and the real-markets runner."""

from __future__ import annotations

import io
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
import fetch_market_data as fm  # noqa: E402
import wild_scan as ws  # noqa: E402

from monte_neo.backtest import synthetic_ohlcv  # noqa: E402

ROOT = Path(__file__).parents[2]


def _zip(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("BTCUSDT-1h-2024-01.csv", text)
    return buf.getvalue()


def test_binance_archives_in_milliseconds_microseconds_and_with_a_header() -> None:
    ms = "1704067200000,100,110,90,105,12.5,1704070799999,1,2,3,4,0\n1704070800000,105,111,101,108,8,1704074399999,1,2,3,4,0\n"
    rows = fm.parse_binance_zip(_zip(ms))
    assert rows[0] == ["2024-01-01 00:00:00+00:00", "100", "110", "90", "105", "12.5"] and rows[1][0] == "2024-01-01 01:00:00+00:00"
    us = "1735689600000000,100,110,90,105,12.5,1,1,2,3,4,0\n"
    assert fm.parse_binance_zip(_zip(us))[0][0] == "2025-01-01 00:00:00+00:00"
    assert len(fm.parse_binance_zip(_zip("open_time,open,high,low,close,volume\n" + ms))) == 2


def test_stooq_tables_and_error_pages_and_the_month_range(tmp_path: Path) -> None:
    rows = fm.parse_stooq("Date,Open,High,Low,Close,Volume\n2024-01-02,1,2,0.5,1.5,100\n2024-01-03,1.5,2,1,1.8,\n")
    assert rows[0] == ["2024-01-02", "1", "2", "0.5", "1.5", "100"]
    with pytest.raises(ValueError, match="did not return a table"):
        fm.parse_stooq("Exceeded the daily hits limit")
    assert fm.months("2023-11", "2024-02") == ["2023-11", "2023-12", "2024-01", "2024-02"]
    out = tmp_path / "d" / "x.csv"
    fm.write(rows, out)
    assert out.read_text().splitlines()[0] == "timestamp,open,high,low,close,volume"


def test_the_written_file_is_readable_by_the_verifier_and_the_doctor(tmp_path: Path) -> None:
    from monte_neo.verify import load_ohlcv
    from monte_neo.verify.doctor import diagnose

    df = synthetic_ohlcv(300, seed=1)
    rows = [[f"2024-01-{1 + i // 24:02d} {i % 24:02d}:00:00+00:00", str(o), str(h), str(lo), str(c), str(v)] for i, (o, h, lo, c, v) in enumerate(zip(df["open"], df["high"], df["low"], df["close"], df["volume"], strict=True)) if i < 24 * 28]
    path = tmp_path / "m.csv"
    fm.write(rows, path)
    assert len(load_ohlcv(path)) == len(rows) and diagnose(path)["status"] in ("ok", "warn")


def test_the_wild_scan_reports_only_aggregates(tmp_path: Path) -> None:
    repo = tmp_path / "secret-repo-name"
    repo.mkdir()
    (repo / "leaky_strat.py").write_text(
        "from freqtrade.strategy import IStrategy\n\n\nclass S(IStrategy):\n    def populate_indicators(self, dataframe, metadata):\n"
        "        dataframe['f'] = dataframe['close'].shift(-1)\n        return dataframe\n    def populate_entry_trend(self, dataframe, metadata):\n"
        "        dataframe.loc[dataframe['f'] > dataframe['close'], 'enter_long'] = 1\n        return dataframe\n", encoding="utf-8")
    (repo / "clean.py").write_text("import pandas as pd\n\n\ndef signal(df):\n    c = df['close']\n    return (c > c.rolling(20).mean()).astype(int)\n", encoding="utf-8")
    (repo / "notes.py").write_text("print('hello')\n", encoding="utf-8")
    (repo / "broken.py").write_text("def (:\n", encoding="utf-8")
    result = ws.scan([tmp_path])
    assert result["files"] == 2 and result["frameworks"] == {"freqtrade": 1, "plain pandas/numpy": 1}
    assert result["fail"] == {"freqtrade": 1} and result["rules"]["negative_shift"] == 1 and result["skipped"] == 1
    text = ws.render(result)
    assert "secret-repo-name" not in text and "leaky_strat" not in text and "shift(-1)" not in text and "Freqtrade".lower() in text.lower()


def test_the_wild_scan_cli_and_a_missing_directory(tmp_path: Path) -> None:
    (tmp_path / "s.py").write_text("def signal(df):\n    return df['close'].shift(-1)\n", encoding="utf-8")
    out = tmp_path / "r.md"
    ok = subprocess.run([sys.executable, str(ROOT / "scripts" / "wild_scan.py"), str(tmp_path), "--out", str(out), "--json", str(tmp_path / "r.json")], capture_output=True, text=True, check=False)
    assert ok.returncode == 0 and out.read_text().startswith("# Wild scan") and (tmp_path / "r.json").exists()
    bad = subprocess.run([sys.executable, str(ROOT / "scripts" / "wild_scan.py"), str(tmp_path / "nope")], capture_output=True, text=True, check=False)
    assert bad.returncode == 3


def test_the_real_markets_runner_writes_a_summary(tmp_path: Path) -> None:
    csv = tmp_path / "toy_1h.csv"
    df = synthetic_ohlcv(900, seed=3)
    df.to_csv(csv, index=False)
    run = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "real_markets_run.py"), "--out", str(tmp_path / "out"), "--budget", "60", "--null-runs", "3", "--evolve", "0", str(csv)],
        capture_output=True, text=True, check=False, cwd=ROOT,
    )
    assert run.returncode == 0, run.stderr
    summary = (tmp_path / "out" / "SUMMARY.md").read_text()
    assert "toy_1h" in summary and "ERROR" not in summary and (tmp_path / "out" / "toy_1h" / "result.json").exists()
