#!/usr/bin/env bash
# Build the arXiv upload archive: main.tex and the PDF figures only (arXiv runs pdflatex itself).
# Usage: ./build_arxiv.sh   ->  build/phantom-mean-reversion-arxiv.tar.gz
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
if command -v pdflatex >/dev/null 2>&1; then
  (cd build && cp ../main.tex . && mkdir -p figures && cp ../figures/*.pdf figures/ \
    && pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null \
    && pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null \
    && echo "compiled: build/main.pdf ($(pdfinfo main.pdf 2>/dev/null | awk '/Pages/{print $2}') pages)" \
    && rm -f main.aux main.log main.out)
elif command -v tectonic >/dev/null 2>&1; then
  mkdir -p build/pdf && tectonic -X compile main.tex --outdir build/pdf && echo "compiled with tectonic: build/pdf/main.pdf"
else
  echo "no TeX engine found: skipping the test compile (arXiv compiles it; or use Overleaf)"
fi
tar -czf build/phantom-mean-reversion-arxiv.tar.gz main.tex figures/*.pdf
tar -tzf build/phantom-mean-reversion-arxiv.tar.gz
echo "wrote build/phantom-mean-reversion-arxiv.tar.gz"
