#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_vgain_sweep.sh [--plan-only] [--mode run] [--run-mode cosmics] [--log-dir DIR]
# Runs pds-run once per config in configs/vst/*vgain*.json

PLAN_ONLY=""
MODE="run"
RUN_MODE="cosmics"
LOG_DIR="vgain_logs"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan-only) PLAN_ONLY="--plan-only"; shift ;;
    --mode) MODE="$2"; shift 2 ;;
    --run-mode) RUN_MODE="$2"; shift 2 ;;
    --log-dir) LOG_DIR="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

mkdir -p "$LOG_DIR"

for cfg in configs/vst/*vgain*.json; do
  [ -f "$cfg" ] || continue
  base=$(basename "$cfg")
  log="$LOG_DIR/${base%.json}.log"
  echo "Running $cfg -> $log"
  cmd=(pds-run "$MODE" --conf "$cfg")
  if [[ "$MODE" == "run" ]]; then
    cmd+=(--mode "$RUN_MODE")
  fi
  if [[ -n "$PLAN_ONLY" ]]; then
    cmd+=("$PLAN_ONLY")
  fi
  "${cmd[@]}" | tee "$log"
done

echo "Done. Logs in $LOG_DIR"
