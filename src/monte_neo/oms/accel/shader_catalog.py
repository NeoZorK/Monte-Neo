"""Catalog of OMS Metal shader sources shipped with the package."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

_SHADER_NAMES = (
    "oms_bar_match.metal",
    "oms_l2_walk.metal",
)


def shader_dir() -> Path:
    return Path(__file__).resolve().parent / "shaders"


def list_shaders() -> list[str]:
    return list(_SHADER_NAMES)


def load_shader_source(name: str) -> str:
    if name not in _SHADER_NAMES:
        raise KeyError(f"unknown shader: {name}")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    path = shader_dir() / name
    if not path.is_file():
        # package resource fallback
        try:  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            ref = resources.files("monte_neo.oms.accel.shaders").joinpath(name)  # pragma: no cover  # defensive / unreachable after unit mocks on CI
            return ref.read_text(encoding="utf-8")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
        except Exception as exc:  # pragma: no cover
            raise FileNotFoundError(path) from exc
    return path.read_text(encoding="utf-8")


def work_checklist_shaders() -> dict[str, bool]:
    d = shader_dir()
    return {name: (d / name).is_file() for name in _SHADER_NAMES}
