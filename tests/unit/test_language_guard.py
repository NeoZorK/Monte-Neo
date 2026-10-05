"""scripts/check_english_only.py: Cyrillic text and private files are refused, English passes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import check_english_only as guard  # noqa: E402

RU = "\u041f\u0440\u0438\u0432\u0435\u0442"  # a Russian word, written with escapes so that this file stays English


def test_text_checks() -> None:
    assert guard.check_text("pr", "Fix the docs link") == []
    assert guard.check_text("pr", f"line one\nFix {RU}") == ["pr:2: Cyrillic text"]
    assert guard.main(["--text", "Add a guide"]) == 0
    assert guard.main(["--text", "Add a guide", "--text", RU]) == 1


def test_paths_and_private_dirs() -> None:
    assert guard.check_paths(["src/a.py", "docs/guides/x.md"]) == []
    assert any("private" in m for m in guard.check_paths(["docs/internal/plan.md"]))
    assert any("private" in m for m in guard.check_paths(["scripts/internal/x.py", "tests/internal/t.py"]))
    assert any("file name" in m for m in guard.check_paths([f"docs/{RU}.md"]))


def test_files_binary_and_text(tmp_path: Path) -> None:
    text = tmp_path / "a.md"
    text.write_text(f"ok\n{RU}\n", encoding="utf-8")
    assert guard.check_file(str(text)) == [f"{text}:2: Cyrillic text"]
    image = tmp_path / "a.png"
    image.write_bytes(RU.encode("utf-8"))
    assert guard.check_file(str(image)) == []  # an image is not text
    blob = tmp_path / "a.bin"
    blob.write_bytes(b"\0" + RU.encode("utf-8"))
    assert guard.check_file(str(blob)) == []
    assert guard.check_file(str(tmp_path / "missing.md")) == []


def test_whole_repository_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603, S607

    git("init", "-q")
    (tmp_path / "ok.py").write_text("print('hello')\n", encoding="utf-8")
    git("add", "ok.py")
    monkeypatch.chdir(tmp_path)
    assert guard.main([]) == 0
    (tmp_path / "bad.md").write_text(f"{RU}\n", encoding="utf-8")
    git("add", "bad.md")
    assert guard.main([]) == 1
    assert "bad.md:1: Cyrillic text" in capsys.readouterr().out
