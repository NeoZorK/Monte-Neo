# Platforms and Python versions

Status vocabulary: **verified locally** (run by a maintainer, result recorded), **prepared** (script or CI job exists, never run
for that cell), **not supported**. "Verified in CI" appears here only after the first green run of the `portable`,
`windows-smoke` and `docker-linux` jobs in `.github/workflows/ci.yml`; until then those cells are "prepared".

| OS | Python 3.11 | 3.12 | 3.13 | 3.14 | 3.15 (beta-supported) |
|---|---|---|---|---|---|
| macOS arm64 (macos-15 in CI) | verified locally | verified locally | verified locally* | verified locally | verified locally |
| Linux (ubuntu-latest, Docker) | prepared (CI) | verified locally (Docker, 3.14 image: 2973 passed) | prepared (CI) | verified locally (Docker) | prepared (CI) |
| Windows 11 | prepared (CI, `scripts/win_smoke.ps1`) | prepared | prepared | prepared | prepared |
| Intel macOS | not supported (no CI, wheel-only dependencies) | | | | |

\* macOS runs used the full suite with all extras (3481 passed, 70 skipped on 3.11, 3.12, 3.14, and 3.15 after the lock refresh below);
the first 3.13 run had two timeouts under heavy machine load (the same tests pass alone). Older measurements were taken
before the lock refresh; the 3.11 to 3.14 cells are not re-run since.

Windows is not in the package classifiers until a real Windows run passes. A best-effort Wine run (Windows build of Python
3.12 in a linux/amd64 container) installed the wheel and ran `--version`, key generation, file locks and MCP setup, but
imports and `verify --demo` crashed under the emulation layer, so it proves nothing about Windows and was abandoned.
Windows containers cannot run on a Mac. GitHub dropped the `macos-14` runner image; the macOS jobs use `macos-15`.

Python 3.15 needed newer pins for the Apple and ML extras (`mlx` 0.32, `scikit-learn` 1.9.1, `scipy` 1.18, `statsmodels` 0.15,
`matplotlib` 3.11); `uv.lock` carries them.

## What needs nothing from Apple

`monte-neo verify`, the CLI and the MCP server use NumPy, pandas, Numba (optional: plain-Python fallback) and Rich.
MLX and Metal live behind the `apple` extra and are imported only on demand.

## Docker (headless)

```bash
docker build -f docker/Dockerfile -t monte-neo .
docker run --rm monte-neo verify --help
docker compose -f docker/docker-compose.yml --profile headless run --rm verify --help
```

## Windows smoke (when the Windows host is available)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\win_smoke.ps1
```

## Python 3.15 and Numba

Numba before 0.68 refuses to install on Python 3.15 (its build stops with "only versions >=3.10,<3.15"). The project
therefore requires `numba>=0.68` on 3.15 and `uv.lock` pins 0.68.1 with a prebuilt wheel, so nothing is compiled during
`uv sync`. If Numba is ever missing (an unsupported interpreter, `--no-deps`), the engines run as plain Python with
identical results and the verifier prints a slow-path hint. Measured on macOS arm64 / Python 3.15.2:
`monte-neo verify --demo-quotes` takes about 2.8 s with Numba (warm cache) and about 3.8 s without it; small inputs hide
the gap, which grows with the number of bars and trials (`docs/api/verify.md` quotes about 100x for a single large backtest).
