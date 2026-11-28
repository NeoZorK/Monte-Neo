#!/bin/bash
# Reproduce the ARL calibration.  Usage: ./run.sh setup | replicate | start | status | stop | aggregate
# Needs: git, uv (https://docs.astral.sh/uv/), about 12 GB of free disk. Every run is resumable: start it again.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${ARL_WORK:-$HOME/MonteNeoData/arl_confirm}"
TAG=v0.57.0
PYVER=3.13.16
BARS_SHA=de57183c5361ea7e68e0dd195712e1780f3f2e41867a74eed98723aa94c6f348
COMMIT=cd88c80066df9baf658e39aeeb5d753c979c9f09
export MONTE_NEO_RC="$WORK/monte-neo"
export ARL_BARS="${ARL_BARS:-$HOME/MonteNeoData/rates/bars_1d.parquet}"
JOBS="${JOBS:-8}"
N="${N:-350000}"
SEED="${SEED:-20261128}"   # base seed of the confirmatory run; change only to test the software
PY="$MONTE_NEO_RC/.venv/bin/python"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1

check_code() {
  [ "$(git -C "$MONTE_NEO_RC" rev-parse HEAD)" = "$COMMIT" ] || { echo "wrong commit in $MONTE_NEO_RC"; exit 1; }
  [ -z "$(git -C "$MONTE_NEO_RC" status --porcelain --untracked-files=no)" ] || { echo "checkout is modified"; exit 1; }
  [ -f "$ARL_BARS" ] || { echo "bars not found: $ARL_BARS (see README.md)"; exit 1; }
  if [ "${ARL_ANY_BARS:-0}" != 1 ]; then   # ARL_ANY_BARS=1: your own bars; real-data results will then differ
    [ "$(shasum -a 256 "$ARL_BARS" | cut -d' ' -f1)" = "$BARS_SHA" ] || { echo "bars hash mismatch"; exit 1; }
  fi
  (cd "$HERE" && shasum -a 256 -c SHA256SUMS >/dev/null) || { echo "deposit files differ from SHA256SUMS"; exit 1; }
  [ "$("$PY" -c 'import platform;print(platform.python_version())')" = "$PYVER" ] || { echo "Python $PYVER required"; exit 1; }
}
calib() { # arm zoo_seeds base_seed outdir args...
  local arm=$1 zoo=$2 seed=$3 out=$4; shift 4
  ARL_ARM=$arm ARL_ZOO_SEEDS=$zoo ARL_BASE_SEED=$seed ARL_CALIB_OUT="$out" nice -n 5 "$PY" -I "$HERE/calib.py" "$@"
}
case "${1:-status}" in
  setup)
    mkdir -p "$WORK"
    [ -d "$MONTE_NEO_RC/.git" ] || git clone --quiet --branch $TAG https://github.com/NeoZorK/Monte-Neo "$MONTE_NEO_RC"
    (cd "$MONTE_NEO_RC" && uv sync --frozen --python $PYVER --quiet)
    check_code
    shasum -a 256 "$ARL_BARS" "$HERE/calib.py" "$HERE/analyze.py" "$HERE/run.sh"
    "$PY" -c 'import sys,platform,numpy,pandas;print(sys.version.split()[0],platform.platform(),"numpy",numpy.__version__,"pandas",pandas.__version__)' ;;
  replicate)  # the first ${N_REP:-2000} development cases (final rules); compare with the published per-case results
    check_code
    calib silent mod1000 20261119 "$WORK/replicate" run --jobs "$JOBS" --n-cases "${N_REP:-2000}" ;;
  night)      # confirmatory run: both arms and the software check, in this terminal
    check_code
    export TMPDIR="$WORK/tmp"; mkdir -p "$TMPDIR"   # one temporary trial ledger per case; removed at the end
    for pass in "" --retry-errors; do   # the second pass retries failed cases once with the same seed
      calib parity full "$SEED" "$WORK/parity" run --jobs "$JOBS" --n-cases "$N" $pass
      calib silent full "$SEED" "$WORK/silent" run --jobs "$JOBS" --n-cases "$N" --asymmetric-only $pass
      calib silent full "$SEED" "$WORK/silent_check" run --jobs "$JOBS" --n-cases "${N_CHECK:-3500}" $pass
    done
    rm -rf "$WORK/tmp"
    echo "CONFIRMATORY RUN COMPLETE" ;;
  start)      # same, detached and protected against sleep; needs the DOI of the published pre-registration
    check_code
    [ -n "${PREREG_DOI:-}" ] || [ -f "$WORK/prereg.txt" ] || { echo "publish the pre-registration first, then: PREREG_DOI=10.5281/zenodo.N $0 start"; exit 1; }
    [ -f "$WORK/prereg.txt" ] || echo "pre-registration $PREREG_DOI; first start $(date -u +%Y-%m-%dT%H:%M:%SZ); SHA256SUMS $(shasum -a 256 "$HERE/SHA256SUMS" | cut -d' ' -f1)" > "$WORK/prereg.txt"
    cat "$WORK/prereg.txt"
    if screen -list | grep -q '\.arl_confirm'; then echo "already running"; exit 0; fi
    screen -dmS arl_confirm bash -c "caffeinate -ims '$HERE/run.sh' night 2>&1 | tee -a '$WORK/night.out'"
    sleep 3; echo "started in screen 'arl_confirm'. Status: $0 status" ;;
  status)
    screen -list | grep arl_confirm || echo "(not running)"
    for d in parity silent silent_check; do [ -f "$WORK/$d/calib.log" ] && { echo "== $d"; tail -n 1 "$WORK/$d/calib.log"; }; done
    grep -c 'CONFIRMATORY RUN COMPLETE' "$WORK/night.out" 2>/dev/null | sed 's/^/complete markers: /' || true ;;
  stop) screen -S arl_confirm -X quit || echo "not running"
        for d in parity silent silent_check; do f="$WORK/$d/run.pid"; [ -f "$f" ] && { pkill -P "$(cat "$f")" 2>/dev/null || true; kill "$(cat "$f")" 2>/dev/null || true; rm -f "$f"; }; done ;;
  aggregate) calib parity full "$SEED" "$WORK/parity" aggregate; calib silent full "$SEED" "$WORK/silent" aggregate ;;
  *) echo "usage: $0 setup|replicate|start|status|stop|aggregate"; exit 1 ;;
esac
