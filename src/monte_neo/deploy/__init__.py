"""``monte-neo deploy``: run a verified strategy as a forward record on the Binance spot DEMO testnet.

The package keeps an append-only, hash-chained evidence journal, two virtual books replayed from it (paper at mainnet
prices with a cost model, and testnet fills), a static dashboard, RFC 3161 anchors and a report with a manifest.
Standard library only at runtime. Demo execution is not live trading and nothing here is investment advice.
"""

from __future__ import annotations

__all__ = ["account", "anchor", "binance", "certify", "dashboard", "eligibility", "journal", "keys", "metrics", "plugin", "report", "runner"]
