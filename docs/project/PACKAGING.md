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


## GitHub Pages

Docs site: https://neozork.github.io/Monte-Neo/ (MkDocs Material).

- Config: `mkdocs.yml`
- Workflow: `.github/workflows/docs.yml` (deploys on push to `main` when `docs/` changes)
- Enable once: GitHub → Settings → Pages → Source **GitHub Actions**
- Home page source is `docs/INDEX.md` (kept for maintenance tests). On Linux MkDocs emits `site/INDEX/index.html`; the workflow copies it to `site/index.html` so the site root is not a soft 404.

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
