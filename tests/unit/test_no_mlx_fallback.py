"""Without MLX the MLX indicator wrappers raise ImportError, so callers fall back to the CPU path."""

import pytest

from monte_neo.core.acceleration import indicators as acc


def test_mlx_wrappers_raise_import_error_without_mlx(monkeypatch):
    monkeypatch.setattr(acc, "mx", None)
    with pytest.raises(ImportError):
        acc.MLXSMA(5)
    with pytest.raises(ImportError):
        acc.MLXSMACrossStrategy(5, 20)


def test_sma_indicator_reports_no_mlx_representation(monkeypatch):
    from monte_neo.indicators.sma import SMAIndicator

    monkeypatch.setattr(acc, "mx", None)
    assert SMAIndicator().to_mlx_representation() is None
