#!/bin/bash
# Does the cleanup trap actually kill what the runner started?
#
# FL_TEST_FAIL_AFTER_START=1 makes the runner exit right after the node is up, i.e. with roscore,
# rosbag record and fastlivo_mapping all running -- the state a later `set -e` failure used to
# leave behind.  Afterwards the master port must be closed and the receipt must say FAIL.
set -uo pipefail
HERE=$(dirname "$(readlink -f "$0")")
BAG=/tmp/fastlivo/hall01_inj43_15s.bag
OUT=/tmp/fl_cleanup_test_out_$$.bag
LOG=/tmp/fl_cleanup_test_$$.log
rm -f "$OUT"

FL_TEST_FAIL_AFTER_START=1 bash "$HERE/fl_run_isolated.sh" "$BAG" "$OUT" 1.0 1 > "$LOG" 2>&1
RC=$?
echo "runner exit=$RC (expect 3)"

RUN_DIR=$(grep -o '/tmp/fl_run_[^ ]*' "$LOG" | head -1)
PORT=$(grep -o '127\.0\.0\.1:[0-9]*' "$LOG" | head -1 | cut -d: -f2)
echo "run_dir=$RUN_DIR master_port=$PORT"

/usr/bin/python3 - "$PORT" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket(); s.settimeout(2.0)
try:
    s.connect(("127.0.0.1", port))
    print("PORT_STILL_OPEN: cleanup FAILED (rosmaster survived)")
except Exception:
    print("port closed: rosmaster was cleaned up")
finally:
    s.close()
PY

if [ -n "$RUN_DIR" ] && [ -f "$RUN_DIR/receipt.json" ]; then
  /usr/bin/python3 - "$RUN_DIR/receipt.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print("receipt status =", d["status"], "| process_exit =", d["process_exit"])
print("logs:", ", ".join(sorted(p for p in __import__("os").listdir(__import__("os").path.dirname(sys.argv[1])))))
PY
else
  echo "FAIL: no receipt written for the failed run"
fi
rm -f "$OUT"
