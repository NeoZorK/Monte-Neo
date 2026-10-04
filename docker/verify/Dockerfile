# Monte-Neo verifier image for checking strategy code you do not trust.
#
# The release is pinned by hash, so write the pin first (the version must be on PyPI):
#   python3 scripts/pin_release.py 0.51.0 > docker/verify/monte-neo.txt
#   docker build -t monte-neo-verify docker/verify
#
# Run it without network, with a read-only file system and resource limits
# (see docs/api/verify.md, "Security note").
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

ARG VERSION=""
# The engines are compiled at build time into /opt/numba. Docker keeps file times only to the
# second, and Numba rejects a cache whose source time changed, so the times are rounded first.
# Dependencies come from a hash-locked file, and so does the release itself: monte-neo.txt is written by
# scripts/build_docker_image.sh with the sha256 of every file PyPI holds for that version.
COPY requirements.txt monte-neo.txt /tmp/
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt \
 && pip install --no-cache-dir --require-hashes --no-deps -r /tmp/monte-neo.txt \
 && python -c "import monte_neo, os, pathlib; [os.utime(p, (int(p.stat().st_mtime),) * 2) for p in pathlib.Path(monte_neo.__file__).parent.rglob('*.py')]" \
 && NUMBA_CACHE_DIR=/opt/numba monte-neo verify --precompile \
 && chmod -R a+rX /opt/numba

# Each run copies the cache into its own /tmp: nothing a strategy writes survives the run.
ENV NUMBA_CACHE_DIR=/tmp/numba
ENTRYPOINT ["sh", "-c", "cp -r /opt/numba /tmp/numba 2>/dev/null; exec \"$@\"", "--"]
CMD ["monte-neo", "verify", "--help"]
USER nobody
