# Monte-Neo verifier image for checking strategy code you do not trust.
#
#   docker build -t monte-neo-verify docker/verify                      # latest release
#   docker build -t monte-neo-verify --build-arg VERSION=0.36.0 docker/verify
#
# Run it without network, with a read-only file system and resource limits
# (see docs/api/verify.md, "Security note").
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

ARG VERSION=""
# The engines are compiled at build time into /opt/numba. Docker keeps file times only to the
# second, and Numba rejects a cache whose source time changed, so the times are rounded first.
# Dependencies come from a hash-locked file; only monte-neo itself is resolved from the index.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt \
 && pip install --no-cache-dir --no-deps "monte-neo${VERSION:+==$VERSION}" \
 && python -c "import monte_neo, os, pathlib; [os.utime(p, (int(p.stat().st_mtime),) * 2) for p in pathlib.Path(monte_neo.__file__).parent.rglob('*.py')]" \
 && NUMBA_CACHE_DIR=/opt/numba monte-neo verify --precompile \
 && chmod -R a+rX /opt/numba

# Each run copies the cache into its own /tmp: nothing a strategy writes survives the run.
ENV NUMBA_CACHE_DIR=/tmp/numba
ENTRYPOINT ["sh", "-c", "cp -r /opt/numba /tmp/numba 2>/dev/null; exec \"$@\"", "--"]
CMD ["monte-neo", "verify", "--help"]
USER nobody
