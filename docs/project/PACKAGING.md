# Packaging & PyPI (free only)

## What PyPI is for this project

[PyPI](https://pypi.org) is the public Python package index. Publishing `monte-neo`
there lets strangers run:

```bash
pip install monte-neo
# Apple Silicon Metal/MLX:
pip install "monte-neo[apple]"
```

GitHub Releases and `pip install git+https://…` remain free forever; PyPI is
**discoverability + one-command install**, not a paywall.

## Fit for Monte-Neo

Yes. MIT library with a clear research-bar job on macOS. Numba CPU paths work more
broadly; Metal/MLX are an **`[apple]` extra** so Linux/CI wheels still install.

## Not yet (checklist before first upload)

- [x] README / FAQ / non-goals
- [x] `project.urls`, classifiers, keywords
- [x] Hatch PEP 440 version (leading `v` stripped for the wheel)
- [x] Optional `[apple]` extras (mlx, pyobjc)
- [x] `python -m build` + install wheel in a clean venv on Mac (with and without `[apple]`; Linux CI wheel install still recommended)
- [x] TestPyPI dry-run (`twine upload --repository testpypi`) — 0.15.1
- [x] Trusted Publishing (OIDC) on GitHub → pypi.org (workflow `publish.yml`; publisher active on PyPI + TestPyPI for NeoZorK/Monte-Neo env `pypi`)
- [x] Name claim `monte-neo` still free on PyPI (checked 2026-09-16)
- [x] Explicit “first publish” OK from maintainer — 0.15.1 on PyPI

## Free channels only

| Channel | Cost | Role |
|---------|------|------|
| PyPI | Free for public OSS | Primary install (when ready) |
| TestPyPI | Free | Rehearsal |
| GitHub Releases | Free | Source + notes (already used) |
| GitHub Packages | Free for public | Optional mirror — **not** primary for Python |
| `git+https` install | Free | Until PyPI |

No paid private indexes.

## Local build smoke

```bash
uv sync --extra apple --group dev
uv run python -m build
uv run --with 'twine>=6' --with 'packaging>=24.2' twine check dist/*
```

Note: wheels may declare Metadata-Version 2.5; use `packaging>=24.2` with twine.


## Import without `[apple]`

Base install must import without MLX/Metal. Acceleration modules use `from __future__ import annotations` so `mx.array` annotations are not evaluated when `mlx` is absent. Metal C++ extension absence is logged at `debug`, not warning.

## Wheel contents smoke

After `python -m build`, confirm the wheel includes ``monte_neo/data/``.
A root ``data/`` gitignore pattern historically dropped that package from Hatch builds.
Use ``/data/`` (repo-root only) in ``.gitignore``.

```bash
unzip -l dist/*.whl | grep monte_neo/data/
python -c "from monte_neo.data.sampler import DataSampler; print(DataSampler)"
```


## First published

- **0.15.1** on TestPyPI: https://test.pypi.org/project/monte-neo/0.15.1/
- **0.15.1** on PyPI: https://pypi.org/project/monte-neo/0.15.1/
- **0.16.0** / **0.17.0** on PyPI: https://pypi.org/project/monte-neo/
- Prefer PyPI for users; TestPyPI only with `--no-deps` wheel download (see Installation)


## GitHub Pages

Docs site: https://neozork.github.io/Monte-Neo/ (MkDocs Material).

- Config: `mkdocs.yml`
- Workflow: `.github/workflows/docs.yml` (deploys on push to `main` when `docs/` changes)
- Enable once: GitHub → Settings → Pages → Source **GitHub Actions**
- Home page source is `docs/index.md` (MkDocs site root). Docs file map is `docs/docs-map.md` (maintenance tests). The old sed/copy-home steps in `docs.yml` are now a no-op (no `site/home/`); remove them when a token with `workflow` scope can push workflow edits.

## Trusted Publishing (OIDC)

Workflow: `.github/workflows/publish.yml` (on GitHub Release).

On https://pypi.org/manage/account/publishing/ add a pending publisher:

| Field | Value |
|-------|--------|
| PyPI Project | `monte-neo` |
| Owner | `NeoZorK` |
| Repository | `Monte-Neo` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

Create a GitHub Environment named `pypi` (optional protection rules). After the first OIDC upload, long-lived API tokens can be rotated away.


## Extras matrix (v0.16+)

| Extra | Contents |
|-------|----------|
| *(default)* | Research-core: numpy, pandas, pyarrow, numba, rich, CLI |
| `apple` | MLX + PyObjC Metal/Cocoa (**darwin only** markers) |
| `plot` | matplotlib / seaborn / mplfinance / plotext / pillow |
| `data` | binance-connector (downloader / websocket) |
| `ml` | lightgbm, sklearn, statsmodels, scipy, ta |
| `server` | fastapi, uvicorn, redis, psycopg2-binary |
| `full` | Explicit kitchen-sink list (local parity with pre-0.16 installs) |
| `dev` | pytest stack + plot + data (test suite) |

Plot / exchange helpers lazy-import and raise a clear “install monte-neo[…]” error if missing.
