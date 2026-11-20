#!/bin/sh
# Restart run_all.py until it exits cleanly (after a crash, a kill or a reboot start this script again). Usage:
#   nohup sh scripts/strategy_lab/watchdog.sh --stages prepare,discovery,validation --jobs 2 > strategy_lab/logs/watchdog.out 2>&1 &
cd "$(dirname "$0")/../.." || exit 1
mkdir -p strategy_lab/logs
n=0
until python scripts/strategy_lab/run_all.py "$@"; do
  n=$((n+1)); echo "$(date -u +%FT%TZ) run_all failed (attempt $n); retry in 60 s"
  [ "$n" -ge 20 ] && { echo "too many failures"; exit 1; }
  sleep 60
done
