#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_vgain_sweep.sh [--plan-only] [--mode thr-scan] [--log-dir DIR]
# Runs pds-run thr-scan once per config in configs/vst/*vgain*.json

PLAN_ONLY=""
MODE="run"
LOG_DIR="vgain_logs"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan-only) PLAN_ONLY="--plan-only"; shift ;;
    --mode) MODE="$2"; shift 2 ;;
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
  pds-run "$MODE" "$cfg" $PLAN_ONLY | tee "$log"
done

echo "Done. Logs in $LOG_DIR"
