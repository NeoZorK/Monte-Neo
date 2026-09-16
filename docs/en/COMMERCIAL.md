# Monte-Neo — commercial notes

Monte-Neo’s **public core** is **MIT open source** on GitHub:
https://github.com/NeoZorK/Monte-Neo

## Product (public)

Fast local research for trading strategies on Apple Silicon:

- Fee-aware next-bar research economics (Metal / Numba; MLX optional)
- Monte Carlo research helpers
- Paper OMS lane (validation semantics, not a production-bot claim)

Install: `pip install monte-neo` (when published) or `pip install "monte-neo[apple]"` on Apple Silicon.

## What stays commercial / private

Separate from the MIT tree (do not mix into public releases):

- Private bake-off harnesses and peer comparisons
- Studio-only research notebooks and proprietary strategies
- Paid support, custom integration, OEM / white-label engagements

## Licensing tiers (services, not a second license for the MIT core)

1. **OSS / MIT** — use, fork, ship the public package freely
2. **Support & consulting** — written agreement
3. **OEM / white-label** — custom packaging under a commercial contract

## Native Metal extension

```bash
uv sync --extra apple
uv run bash scripts/build_native.sh
```

See [METAL_NATIVE_BUILD.md](../METAL_NATIVE_BUILD.md).
