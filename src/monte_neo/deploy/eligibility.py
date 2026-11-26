"""Who may deploy: a Monte-Neo certificate whose verdict is not REJECT, and settings the machinery supports.

Supported: Binance spot (long-only, no leverage) and Binance USD-M perpetual futures (long and short, gross exposure up
to 2), daily or weekly rebalance, target ``local``. Everything else is refused with a message.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

VERDICTS = ("PASS", "PASS_WITH_WARNINGS", "NEEDS_MORE_EVIDENCE", "REJECT")
TARGETS_UNAVAILABLE = ("ssh", "aws", "gcp")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,12}USDT$")


class EligibilityError(ValueError):
    """The strategy or the settings cannot be deployed."""


def file_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _text_sha256(path: Path | str) -> str:
    """Hash as Monte-Neo computes it for ``source_sha256`` (the decoded source, re-encoded as UTF-8)."""
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def check_certificate(cert_path: Path | str, strategy_path: Path | str) -> dict[str, Any]:
    """Validate the certificate and return what the start entry records: ``{"certificate": {...}, "warnings": [...]}``."""
    p = Path(cert_path)
    try:
        raw = p.read_bytes()
        cert = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise EligibilityError(f"cannot read the certificate {p}: {exc}") from exc
    if not isinstance(cert, dict) or cert.get("verdict") not in VERDICTS or not cert.get("certificate_id"):
        raise EligibilityError(f"{p.name} is not a Monte-Neo certificate (needs verdict and certificate_id)")
    verdict = cert["verdict"]
    if verdict == "REJECT":
        raise EligibilityError(f"the certificate {cert['certificate_id']} has verdict REJECT: a rejected strategy is not deployed. Fix the strategy and verify again.")
    warnings: list[str] = []
    if verdict == "NEEDS_MORE_EVIDENCE":
        warnings.append("certificate verdict is NEEDS_MORE_EVIDENCE: the forward record is part of the evidence, not a confirmation")
    repro = cert.get("reproducibility") or {}
    src = repro.get("source_sha256")
    if src:
        if src not in (file_sha256(strategy_path), _text_sha256(strategy_path)):
            raise EligibilityError("the strategy file does not match the certificate: its SHA-256 differs from the certificate's source hash. Verify this exact file.")
    else:
        warnings.append("the certificate has no source hash: it was not proven that it was issued for this strategy file")
    arl = cert.get("arl") or {}
    return {
        "certificate": {"id": cert["certificate_id"], "verdict": verdict, "arl": arl.get("level"), "arl_headline": arl.get("headline"),
                        "n_trials": repro.get("n_trials"), "source_sha256": src, "file_sha256": hashlib.sha256(raw).hexdigest()},
        "warnings": warnings,
    }


def parse_weekday(text: str) -> int:
    t = str(text).strip().lower()
    for i, name in enumerate(WEEKDAYS):
        if t in (name, name[:3], str(i)):
            return i
    raise EligibilityError(f"unknown weekday {text!r}: use monday ... sunday")


def check_settings(*, market: str = "spot", leverage: float = 1.0, long_only: bool = True, rebalance: str = "weekly", mode: str = "testnet",
                   capital: float = 10_000.0, symbols: list[str] | None = None, fee_bps: float = 10.0, slippage_bps: float = 5.0,
                   kill_drawdown: float = -0.15) -> None:
    """Refuse every setting the machinery does not support. ``leverage`` is the gross exposure limit (sum of |weights|)."""
    from monte_neo.deploy.connectors import BY_MARKET

    if market not in BY_MARKET:
        raise EligibilityError(f"market must be one of {', '.join(sorted(BY_MARKET))} (got {market!r}); no margin or options")
    v = BY_MARKET[market]
    if not v.short and leverage != 1.0:
        raise EligibilityError("leverage is not supported on spot: weights are shares of capital, at most 1 in total")
    if not 0 < leverage <= v.max_gross:
        raise EligibilityError(f"leverage (gross exposure limit) must be above 0 and at most {v.max_gross:g} on {v.id}")
    if not long_only and not v.short:
        raise EligibilityError("short positions need a venue that allows them: use --market usdm (USD-M futures testnet)")
    if rebalance not in ("daily", "weekly"):
        raise EligibilityError(f"rebalance must be daily or weekly (got {rebalance!r}); intraday rebalancing is not supported")
    if mode not in ("testnet", "paper", "dry"):
        raise EligibilityError(f"mode must be testnet, paper or dry (got {mode!r})")
    if not capital > 0:
        raise EligibilityError("capital must be positive")
    if not symbols:
        raise EligibilityError("give at least one symbol, for example BTCUSDT,ETHUSDT")
    bad = [s for s in symbols if not SYMBOL_RE.match(s)]
    if bad or len(set(symbols)) != len(symbols):
        raise EligibilityError(f"symbols must be unique spot pairs quoted in USDT, such as BTCUSDT (got {symbols})")
    if fee_bps < 0 or slippage_bps < 0:
        raise EligibilityError("fee-bps and slippage-bps cannot be negative")
    if not -1.0 < kill_drawdown < 0.0:
        raise EligibilityError("kill-drawdown must be a negative fraction between -1 and 0, for example -0.15")
