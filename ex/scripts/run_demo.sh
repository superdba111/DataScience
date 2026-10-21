#!/usr/bin/env bash
# Demonstrates the required sequence: batch_01 -> batch_02 -> batch_02 replay.
# Usage: scripts/run_demo.sh            (from the project root)
set -euo pipefail
cd "$(dirname "$0")/.."

STATE_DIR=out
OUT=output
rm -rf "$STATE_DIR"            # 1. start from an empty state location
mkdir -p "$STATE_DIR" "$OUT"

echo "== step 1: batch_01 on empty state"
python3 -m market_pulse.pipeline --state "$STATE_DIR/state.db" --batch batch_01 \
  --report-out "$OUT/hourly_after_batch_01.csv" \
  --latest-out "$OUT/latest_after_batch_01.csv" \
  --summary-out "$OUT/run_summary_batch_01.json" > /dev/null

echo "== step 2: batch_02 against existing state"
python3 -m market_pulse.pipeline --state "$STATE_DIR/state.db" --batch batch_02 \
  --report-out "$OUT/hourly_after_batch_02.csv" \
  --latest-out "$OUT/latest_after_batch_02.csv" \
  --summary-out "$OUT/run_summary_batch_02.json" > /dev/null

echo "== step 3: batch_02 replay (no reset)"
python3 -m market_pulse.pipeline --state "$STATE_DIR/state.db" --batch batch_02 \
  --report-out "$STATE_DIR/hourly_after_batch_02_replay.csv" \
  --latest-out "$STATE_DIR/latest_after_batch_02_replay.csv" \
  --summary-out "$OUT/run_summary_batch_02_replay.json" > /dev/null

echo "== replay check"
diff -q "$OUT/hourly_after_batch_02.csv" "$STATE_DIR/hourly_after_batch_02_replay.csv"
diff -q "$OUT/latest_after_batch_02.csv" "$STATE_DIR/latest_after_batch_02_replay.csv"
echo "replay left hourly results and latest-price dataset unchanged"

for f in batch_01 batch_02 batch_02_replay; do
  python3 - "$OUT/run_summary_$f.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
dq = s["data_quality"]
print(f"{s['batch_directory']:9s} run={s['run_status']:9s} report={dq['report_status']:10s} "
      f"rows={s['row_counts']} latest={s['state']['latest_price_rows']} "
      f"publishable={dq['hours_with_publishable_difference']}/{dq['hourly_rows']}")
PY
done
