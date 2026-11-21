#!/bin/bash
# Launcher for `monte-neo deploy`: start | status | stop | serve | logs.   Runs in screen sessions, survives logout; resumable.
#   scripts/deploy_loop.sh start            daily loop: record every missing day, anchor the head, rebuild the dashboard
#   scripts/deploy_loop.sh serve [PORT]     read-only dashboard (default 127.0.0.1:8787; DEPLOY_HOST=0.0.0.0 for the LAN)
#   scripts/deploy_loop.sh status           loop state, journal check, last metrics
#   scripts/deploy_loop.sh stop             stop the loop and the server (the journal is never touched)
#   scripts/deploy_loop.sh logs             tail of the loop log
# The run must exist: monte-neo deploy init --strategy ... --certificate ...   (same --var and --run as below).
# Settings (environment): DEPLOY_RUN (default "default"), DEPLOY_VAR (default ./var), DEPLOY_CMD (default "monte-neo"),
#   DEPLOY_HOST. Testnet keys: MONTE_NEO_TESTNET_KEY / MONTE_NEO_TESTNET_SECRET from the environment, else from the macOS
#   Keychain (security add-generic-password -s monte_neo_testnet_key -a monte-neo -w '<key>'; same for monte_neo_testnet_secret).
#   Never put keys in a file. The next run is at 00:10 UTC (the daily bar has closed); a failure retries in one hour.
set -u
RUN=${DEPLOY_RUN:-default}
VAR=${DEPLOY_VAR:-$(pwd)/var}
CMD=${DEPLOY_CMD:-monte-neo}
HOST=${DEPLOY_HOST:-127.0.0.1}
LOG="$VAR/$RUN/loop.log"
mkdir -p "$VAR/$RUN"
ARGS="--var $VAR --run $RUN"

keys() {
  [ -n "${MONTE_NEO_TESTNET_KEY:-}" ] || MONTE_NEO_TESTNET_KEY=$(security find-generic-password -s monte_neo_testnet_key -w 2>/dev/null || true)
  [ -n "${MONTE_NEO_TESTNET_SECRET:-}" ] || MONTE_NEO_TESTNET_SECRET=$(security find-generic-password -s monte_neo_testnet_secret -w 2>/dev/null || true)
  export MONTE_NEO_TESTNET_KEY MONTE_NEO_TESTNET_SECRET
}

loop() {
  while true; do
    keys
    if $CMD deploy run $ARGS >>"$LOG" 2>&1; then
      $CMD deploy anchor $ARGS >>"$LOG" 2>&1 || echo "$(date -u +%FT%TZ) anchor failed (retry next cycle)" >>"$LOG"
      $CMD deploy dashboard $ARGS >>"$LOG" 2>&1
      now=$(date -u +%s); next=$(( (now / 86400 + 1) * 86400 + 600 )); wait=$(( next - now ))
      echo "$(date -u +%FT%TZ) ok; next run in $((wait / 60)) min" >>"$LOG"
    else
      echo "$(date -u +%FT%TZ) run failed; retry in 60 min" >>"$LOG"; wait=3600
    fi
    sleep "$wait"
  done
}

case "${1:-status}" in
  start) command -v screen >/dev/null || { echo "screen is needed (brew install screen)"; exit 1; }
         screen -list | grep -q "\.deploy_loop_$RUN" && { echo "already running"; exit 0; }
         screen -dmS "deploy_loop_$RUN" bash -c "$(declare -f keys loop); RUN='$RUN' CMD='$CMD' LOG='$LOG' ARGS='$ARGS' loop"
         echo "started deploy_loop_$RUN; log: $LOG" ;;
  serve) command -v screen >/dev/null || { echo "screen is needed (brew install screen)"; exit 1; }
         screen -list | grep -q "\.deploy_web_$RUN" && { echo "already serving"; exit 0; }
         screen -dmS "deploy_web_$RUN" bash -c "$CMD deploy serve $ARGS --host '$HOST' --port ${2:-8787}"
         echo "dashboard: http://$HOST:${2:-8787}/" ;;
  status) screen -list | grep -E "deploy_(loop|web)_$RUN" || echo "(not running)"
          tail -n 3 "$LOG" 2>/dev/null
          $CMD deploy status $ARGS | python3 -c "import json,sys;d=json.load(sys.stdin);s=d['summary'];print('journal ok:', d['journal']['ok'], '|', d['journal']['entries'], 'entries');print('days', s['days'], '| NAV', s['paper_nav'], '| killed', s['killed'])" ;;
  stop) screen -S "deploy_loop_$RUN" -X quit 2>/dev/null; screen -S "deploy_web_$RUN" -X quit 2>/dev/null; echo "stopped" ;;
  logs) tail -n 40 "$LOG" ;;
  *) echo "usage: $0 start|serve [PORT]|status|stop|logs"; exit 1 ;;
esac
