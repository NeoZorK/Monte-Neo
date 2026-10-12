"""Jupyter cell magic ``%%verify``: verify the strategy written in the cell.

Load it with ``%load_ext monte_neo.verify.magic`` and write::

    %%verify --ohlcv data.csv --n-trials 20 --commission-bps 5
    def signal(df):
        ...

The cell body (``signal(df)``, or ``fit`` / ``predict``) is written to a temporary file and checked with
:func:`monte_neo.verify.verify_strategy`; the returned certificate draws itself as the HTML report. IPython is not a
dependency: this module imports without it.
"""

from __future__ import annotations

import argparse
import os
import shlex
import tempfile
from typing import Any


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="%%verify", add_help=False)
    parser.add_argument("--ohlcv", required=True, help="OHLCV file (csv or parquet)")
    parser.add_argument("--n-trials", type=int, default=None, help="how many variants were tried")
    parser.add_argument("--commission-bps", type=float, default=None)
    parser.add_argument("--slippage-bps", type=float, default=None)
    return parser


def verify_cell(line: str, cell: str) -> Any:
    """Run ``verify_strategy`` on the strategy source in ``cell`` with the options in ``line``.

    Args:
        line: Magic arguments: ``--ohlcv`` (required), ``--n-trials``, ``--commission-bps``, ``--slippage-bps``.
        cell: Python source defining ``signal(df)`` or ``fit`` / ``predict``.

    Returns:
        The :class:`~monte_neo.verify.notebook.Certificate` (renders as the HTML report in a notebook).

    Raises:
        ValueError: On missing or unknown arguments or an empty cell.
    """
    from monte_neo.verify import verify_strategy
    from monte_neo.verify.notebook import Certificate

    try:
        args = _parser().parse_args(shlex.split(line))
    except SystemExit as exc:
        raise ValueError("usage: %%verify --ohlcv data.csv [--n-trials N] [--commission-bps X] [--slippage-bps X]") from exc
    if not cell.strip():
        raise ValueError("the cell is empty: write signal(df) (or fit / predict) below the %%verify line")
    model = None
    if args.commission_bps is not None or args.slippage_bps is not None:
        from monte_neo.backtest.model import ExecutionModel

        base = ExecutionModel(side_mode="long_short")
        model = ExecutionModel(
            side_mode="long_short",
            commission_bps=base.commission_bps if args.commission_bps is None else args.commission_bps,
            slippage_bps=base.slippage_bps if args.slippage_bps is None else args.slippage_bps,
        )
    handle, path = tempfile.mkstemp(suffix=".py", prefix="verify_cell_")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(cell if cell.endswith("\n") else cell + "\n")
        report = verify_strategy(args.ohlcv, strategy=path, n_trials=args.n_trials, model=model)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return report if isinstance(report, Certificate) else Certificate(report)


def load_ipython_extension(ipython: Any) -> None:
    """Register the ``%%verify`` cell magic (called by ``%load_ext monte_neo.verify.magic``)."""
    ipython.register_magic_function(verify_cell, magic_kind="cell", magic_name="verify")


__all__ = ["load_ipython_extension", "verify_cell"]
