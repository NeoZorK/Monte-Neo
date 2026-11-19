#!/usr/bin/env bash
# Run the full test suite on several Python versions, one at a time, under nice.
# Usage: scripts/py_matrix.sh [--no-resume] [versions...]   (default: 3.11 3.12 3.13 3.14 3.15)
# Output: $OUT/summary.txt (one line per version), $OUT/pytest-<ver>.log, $OUT/sync-<ver>.log
# Resumable: a version already listed in summary.txt is skipped. Status: cat $OUT/summary.txt
set -u
cd "$(dirname "$0")/.."
OUT="${OUT:-${TMPDIR:-/tmp}/py_matrix}"; mkdir -p "$OUT"
[ "${1:-}" = "--no-resume" ] && { shift; rm -f "$OUT/summary.txt"; }
VERS=("$@"); [ ${#VERS[@]} -eq 0 ] && VERS=(3.11 3.12 3.13 3.14 3.15)
for v in "${VERS[@]}"; do
  grep -q "^$v " "$OUT/summary.txt" 2>/dev/null && continue
  start=$(date +%s)
  export UV_PROJECT_ENVIRONMENT="$OUT/venv$v"
  if ! nice -n 10 uv sync --python "$v" --all-extras --group dev > "$OUT/sync-$v.log" 2>&1; then
    echo "$v SYNC-FAILED secs=$(( $(date +%s)-start )) (see sync-$v.log)" >> "$OUT/summary.txt"; continue
  fi
  nice -n 10 uv run --no-sync --python "$v" pytest tests -n auto -W ignore -q --no-header -p no:cacheprovider > "$OUT/pytest-$v.log" 2>&1
  rc=$?
  echo "$v exit=$rc secs=$(( $(date +%s)-start )) $(tail -1 "$OUT/pytest-$v.log" | tr -d '=')" >> "$OUT/summary.txt"
done
echo DONE >> "$OUT/summary.txt"
