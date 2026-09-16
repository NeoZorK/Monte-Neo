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
- [x] `python -m build` + install wheel in a clean venv on Mac (Linux CI wheel install still recommended)
- [ ] TestPyPI dry-run (`twine upload --repository testpypi`)
- [ ] Trusted Publishing (OIDC) on GitHub → pypi.org
- [ ] Name claim `monte-neo` still free on PyPI
- [ ] Explicit “first publish” OK from maintainer

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

## Wheel contents smoke

After `python -m build`, confirm the wheel includes ``monte_neo/data/``.
A root ``data/`` gitignore pattern historically dropped that package from Hatch builds.
Use ``/data/`` (repo-root only) in ``.gitignore``.

```bash
unzip -l dist/*.whl | grep monte_neo/data/
python -c "from monte_neo.data.sampler import DataSampler; print(DataSampler)"
```
