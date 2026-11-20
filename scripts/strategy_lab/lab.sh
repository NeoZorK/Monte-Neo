#!/usr/bin/env bash
# One command for the Strategy Lab. Pins the Python version (numba does not support 3.15, and `uv run` otherwise picks
# the newest interpreter), checks the tools first and gives readable errors.
#
#   scripts/strategy_lab/lab.sh                 interactive screen (live table, ETA, keys)
#   scripts/strategy_lab/lab.sh bg              background run with a log (survives closing the terminal)
#   scripts/strategy_lab/lab.sh status          progress table, ETA and the last log lines (read-only)
#   scripts/strategy_lab/lab.sh dry-run         whole pass on synthetic stubs (checks the tooling, writes no results)
#   scripts/strategy_lab/lab.sh self-test       dry-run plus kill -9 / resume checks
# Extra arguments go to lab.py, e.g.  lab.sh bg --jobs 1 --threads 1
# LAB_PYTHON=3.13 lab.sh ...   overrides the interpreter (default 3.12). Not investment advice.
set -u
cd "$(dirname "$0")/../.." || exit 1
PYV="${LAB_PYTHON:-3.12}"
command -v uv >/dev/null 2>&1 || { echo "uv is not installed: https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1; }
RUN=(uv run --python "$PYV" python)
mkdir -p strategy_lab/logs
cmd="${1:-run}"; [ $# -gt 0 ] && shift
case "$cmd" in
run)        exec "${RUN[@]}" scripts/strategy_lab/lab.py "$@" ;;
bg)         nohup caffeinate -is "${RUN[@]}" scripts/strategy_lab/lab.py --plain --exit-when-done "$@" > strategy_lab/logs/lab_bg.out 2>&1 &
            echo "started in background (pid $!). Status:  scripts/strategy_lab/lab.sh status"
            echo "Log:     tail -f strategy_lab/logs/lab_bg.out" ;;
status)     "${RUN[@]}" scripts/strategy_lab/run_all.py --status 2>&1 | tail -30
            echo "--- last log lines"; tail -5 strategy_lab/logs/lab_bg.out 2>/dev/null | cut -c1-200
            pgrep -f "strategy_lab/lab.py" >/dev/null && echo "lab.py: RUNNING" || echo "lab.py: not running" ;;
dry-run)    exec "${RUN[@]}" scripts/strategy_lab/lab.py --dry-run --plain "$@" ;;
self-test)  exec "${RUN[@]}" scripts/strategy_lab/lab.py --self-test "$@" ;;
*)          sed -n '2,11p' "$0"; exit 2 ;;
esac
