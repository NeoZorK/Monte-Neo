"""Every label in the tables is checked by an oracle that does not use the verifier."""

from __future__ import annotations

import pytest
from mechanisms import HONEST, LEAKS
from zoo_lib import dataset, oracle_causal

DF = dataset()


def _row(row: tuple) -> tuple:
    return row[0], row[2], row[3], tuple(row[4]) if len(row) > 4 else ()


@pytest.mark.parametrize("row", LEAKS, ids=lambda r: r[0])
def test_leak_labels(row: tuple) -> None:
    name, expr, rule, pre = _row(row)
    assert not oracle_causal(expr, rule, pre, DF), f"{name} is labelled a leak but its positions are causal"


@pytest.mark.parametrize("row", HONEST, ids=lambda r: r[0])
def test_honest_labels(row: tuple) -> None:
    name, expr, rule, pre = _row(row)
    assert oracle_causal(expr, rule, pre, DF), f"{name} is labelled honest but its positions change with later bars"


def test_names_are_unique() -> None:
    names = [r[0] for r in LEAKS + HONEST]
    assert len(names) == len(set(names))
