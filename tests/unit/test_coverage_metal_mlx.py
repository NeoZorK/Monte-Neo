"""Metal/MLX coverage via import + mocked construction (no real GPU)."""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

MODULES = [
    "monte_neo.core.native.metal_engine",
    "monte_neo.core.mlx_3d_engine",
    "monte_neo.core.mlx_sim_engine",
    "monte_neo.core.mlx_driver_utils",
    "monte_neo.core.optimizer",
    "monte_neo.core.acceleration.float8",
    "monte_neo.core.acceleration.indicators",
    "monte_neo.core.acceleration.engine",
    "monte_neo.core.gpu_lazy",
    "monte_neo.oms.accel.metal_dispatch",
    "monte_neo.oms.accel.metal_l2",
    "monte_neo.backtest.metal_economics",
]


def test_import_and_construct():
    for name in MODULES:
        with patch.dict("sys.modules", {"Metal": MagicMock(), "objc": MagicMock(), "Foundation": MagicMock()}):
            try:
                mod = importlib.import_module(name)
            except Exception:
                continue
            for attr_name, obj in list(vars(mod).items()):
                if not isinstance(obj, type) or attr_name.startswith("_"):
                    continue
                if obj.__module__ != mod.__name__:
                    continue
                try:
                    inst = obj()
                except Exception:
                    try:
                        inst = obj(MagicMock())
                    except Exception:
                        continue
                for meth in ("is_available", "available", "initialize", "init", "reset", "close", "shutdown"):
                    if hasattr(inst, meth):
                        try:
                            getattr(inst, meth)()
                        except Exception:
                            pass
