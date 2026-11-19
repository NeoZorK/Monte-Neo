#!/usr/bin/env bash
# Daily forward record (no trading, no keys). Idempotent: records every missing day up to yesterday (UTC), so a missed day is filled on the next run.
#   scripts/strategy_lab/forward_daily.sh once     one pass with retries (what launchd calls)
#   scripts/strategy_lab/forward_daily.sh loop     screen-friendly loop: a pass, then sleep until ~06:30 local the next day
#   scripts/strategy_lab/forward_daily.sh status   journal chain check and last day
set -u
cd "$(dirname "$0")/../.." || exit 1
PY="$(pwd)/.venv/bin/python"
LOG="$(pwd)/strategy_lab/forward/daily.log"
mkdir -p strategy_lab/forward
LOW=(nice -n 10 taskpolicy -b)
one() {
  for n in 1 2 3 4; do
    echo "$(date '+%F %T') pass (attempt $n)" >> "$LOG"
    "${LOW[@]}" "$PY" scripts/strategy_lab/forward_record.py run >> "$LOG" 2>&1 && return 0
    sleep $((n * 120))
  done
  echo "$(date '+%F %T') FAILED after 4 attempts" >> "$LOG"; return 1
}
case "${1:-once}" in
  once)   one ;;
  loop)   while true; do one; now=$(date +%s); next=$(date -v+1d -v6H -v30M -v0S +%s); sleep $((next - now)); done ;;
  status) "$PY" scripts/strategy_lab/forward_record.py status; tail -3 "$LOG" 2>/dev/null ;;
  *) sed -n '2,6p' "$0"; exit 2 ;;
esac
