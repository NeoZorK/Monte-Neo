# Monte-Neo — commercial model (internal)

**Private repository.** Not open source. GitHub distribution removed.

## Product

Monte-Neo is a Monte Carlo indicator generator framework with MLX screening,
Numba metrics, and Metal GPU acceleration on Apple Silicon.

## Distribution

- NeoZorK gitserver: `/Users/rostsh/git-server/NeoZorK/Monte-Neo.git`
- LAN: `ssh://rost@2014/Users/rost/git-server/NeoZorK/Monte-Neo.git`

## Licensing tiers

1. Internal NeoZorK R&D
2. Commercial license (written agreement)
3. OEM / white-label indicator generator

## Vendoring into QWC_WAVE2

No pip dependency. Vendored snippets only with gitserver path and commit hash
in docstrings.

## Native build

```bash
uv sync
uv run bash scripts/build_native.sh
```

See [METAL_NATIVE_BUILD.md](../METAL_NATIVE_BUILD.md).
