"""Close remaining coverage miss for publish gate."""
from __future__ import annotations

from unittest.mock import MagicMock


def test_sequential_advice_generic_high_pass():
    from monte_neo.monte_carlo.sequential import SequentialMCRunner

    runner = SequentialMCRunner(MagicMock())
    advice = runner._generate_advice("custom_stage", 0.97, {})
    assert "high confidence" in advice.lower()
