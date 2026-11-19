#!/usr/bin/env bash
# Overnight honest search queue (no Claude needed). Runs inside `screen`, at background priority (taskpolicy -b + nice),
# so other work on this Mac keeps the CPU. Every step is idempotent: start it again after a crash or a reboot.
#
#   scripts/strategy_lab/night_search.sh start     start the queue in a detached screen session "montesearch"
#   scripts/strategy_lab/night_search.sh status    current step, ETA hints, last log lines, batch reports
#   scripts/strategy_lab/night_search.sh attach    watch it live (detach: Ctrl-A then D)
#   scripts/strategy_lab/night_search.sh stop      stop after the current command (progress is kept)
#   scripts/strategy_lab/night_search.sh dry       check tools and print the plan, change nothing
#
# Plan per batch N = 1..MAX_BATCH: select (discovery only) -> commit the batch (pre-registration) -> fetch validation
# months -> lab.py prepare/discovery/validation for the new candidates -> batch report (reality check, cost of search).
# The sealed holdout is NEVER opened here. Not investment advice; nothing trades.
set -u
cd "$(dirname "$0")/../.." || exit 1
ROOT=$(pwd)
PY="$ROOT/.venv/bin/python"
LOG="$ROOT/strategy_lab/logs/night_search.log"
STATE="$ROOT/strategy_lab/logs/night_search.state"
STOP="$ROOT/strategy_lab/logs/night_search.stop"
MAX_BATCH="${MAX_BATCH:-4}"
JOBS="${JOBS:-2}"; THREADS="${THREADS:-2}"
LOW=(nice -n 10 taskpolicy -b)
mkdir -p "$ROOT/strategy_lab/logs"

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
step() { echo "$*" > "$STATE"; log "STEP $*"; }
stopped() { [ -f "$STOP" ] && { log "stop file found: stopping cleanly"; rm -f "$STOP"; exit 0; }; }

check() {
  [ -x "$PY" ] || { echo "missing $PY"; return 1; }
  "$PY" -c "import pandas, numpy, monte_neo" 2>/dev/null || { echo "venv lacks pandas/numpy/monte_neo"; return 1; }
  command -v screen >/dev/null && command -v taskpolicy >/dev/null || { echo "screen/taskpolicy missing"; return 1; }
  [ -f scripts/strategy_lab/screen.py ] && [ -f scripts/strategy_lab/lab.py ] || { echo "lab scripts missing"; return 1; }
  echo "tools OK"
}

queue() {
  log "queue start (max batch $MAX_BATCH, jobs $JOBS, threads $THREADS, background priority)"
  if [ "${SKIP_WAIT:-0}" != 1 ]; then
    while pgrep -f "[f]etch_data.py" >/dev/null; do step "waiting for an earlier download to finish"; sleep 120; stopped; done
  fi
  for N in $(seq 1 "$MAX_BATCH"); do
    stopped
    B="strategy_lab/batches/batch$N.json"
    if [ ! -f "$B" ]; then
      step "batch $N: select candidates on discovery"
      "${LOW[@]}" "$PY" scripts/strategy_lab/screen.py select --batch "$N" >> "$LOG" 2>&1 || { log "select failed"; exit 1; }
      if ! grep -q '"id"' "$B"; then log "batch $N: no candidate passed the discovery filters; search ends"; break; fi
    fi
    if [ -n "$(git status --porcelain -- examples/strategies strategy_lab/results)" ]; then
      step "batch $N: commit generated reports of earlier batches (outputs, not inputs)"
      git add examples/strategies/*/report.md strategy_lab/results 2>/dev/null; git -c commit.gpgsign=false commit -q -m "Strategy Lab search: generated reports and results before batch $N validation" || true
    fi
    if [ -n "$(git status --porcelain -- "$B" examples/strategies/r4_b"$N"_*/strategy.py examples/strategies/r4_b"$N"_*/card.md)" ] || ! git ls-files --error-unmatch "$B" >/dev/null 2>&1; then
      step "batch $N: commit (pre-registration before validation is read)"
      git add "$B" examples/strategies/r4_b"$N"_* && git -c commit.gpgsign=false commit -q -m "Strategy Lab search: batch $N pre-registered (selected on discovery only)" || { log "commit failed"; exit 1; }
    fi
    stopped
    step "batch $N: fetch validation months (resumable)"
    "${LOW[@]}" "$PY" scripts/strategy_lab/screen.py fetchval --batch "$N" >> "$LOG" 2>&1 || { log "fetchval failed (rerun start to resume)"; exit 1; }
    stopped
    step "batch $N: lab.py prepare/discovery/validation"
    n=0
    until "${LOW[@]}" "$PY" scripts/strategy_lab/lab.py --plain --exit-when-done --jobs "$JOBS" --threads "$THREADS" --interval 300 >> "$LOG" 2>&1; do
      n=$((n+1)); [ "$n" -ge 5 ] && { log "lab.py failed 5 times"; exit 1; }; log "lab.py retry $n in 60 s"; sleep 60; stopped
    done
    step "batch $N: report"
    "${LOW[@]}" "$PY" scripts/strategy_lab/screen.py report --batch "$N" >> "$LOG" 2>&1 || log "report failed for batch $N"
  done
  step "done: see strategy_lab/results/batch*_report.md (holdout still sealed)"
}

case "${1:-}" in
dry)    check && echo "plan: batches 1..$MAX_BATCH; existing: $(ls strategy_lab/batches 2>/dev/null | tr '\n' ' ')"
        pgrep -fl "[f]etch_data.py" | cut -c1-120 || true
        screen -ls 2>/dev/null | grep montesearch || echo "queue not running" ;;
start)  check || exit 1
        screen -ls 2>/dev/null | grep -q montesearch && { echo "already running: $0 status"; exit 0; }
        rm -f "$STOP"; screen -dmS montesearch env SKIP_WAIT="${SKIP_WAIT:-0}" bash "$0" _queue
        echo "started in screen 'montesearch'. Status: $0 status   Live: $0 attach" ;;
_queue) queue ;;
status) screen -ls 2>/dev/null | grep -q montesearch && echo "queue: RUNNING" || echo "queue: not running"
        echo "step: $(cat "$STATE" 2>/dev/null)"; tail -6 "$LOG" 2>/dev/null | cut -c1-200
        ls strategy_lab/results/batch*_report.md 2>/dev/null; uptime ;;
attach) exec screen -r montesearch ;;
stop)   touch "$STOP"; echo "will stop after the current command" ;;
*)      sed -n '2,10p' "$0"; exit 2 ;;
esac
