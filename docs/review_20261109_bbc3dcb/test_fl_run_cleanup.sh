#!/bin/bash
# Does the cleanup trap actually kill what the runner started, and does the harness assert it?
#
# FL_TEST_FAIL_AFTER_START=1 makes the runner exit right after the node is up -- with roscore,
# rosbag record and fastlivo_mapping all running, which is the state a later `set -e` failure used
# to leave behind.  This test FAILS (non-zero) if any check below does not hold; it never ends on
# a successful `rm`.
#
#   * the runner exits 3
#   * the ROS master port is closed afterwards (roscore and its children are gone)
#   * every PID the runner recorded as managed is gone
#   * the receipt says FAIL, with a reason and a termination label
set -uo pipefail
HERE=$(dirname "$(readlink -f "$0")")
BAG=/tmp/fastlivo/hall01_inj43_15s.bag
OUT=/tmp/fl_cleanup_test_out_$$.bag
LOG=/tmp/fl_cleanup_test_$$.log
FAILED=0

fail() { echo "ASSERT FAILED: $*" >&2; FAILED=1; }

rm -f "$OUT"
FL_TEST_FAIL_AFTER_START=1 bash "$HERE/fl_run_isolated.sh" "$BAG" "$OUT" 1.0 1 > "$LOG" 2>&1
RC=$?
echo "runner exit=$RC (expect 3)"
[ "$RC" -eq 3 ] || fail "runner exit $RC, expected 3"

RUN_DIR=$(grep -o '/tmp/fl_run_[^ ]*' "$LOG" | head -1)
PORT=$(grep -o '127\.0\.0\.1:[0-9]*' "$LOG" | head -1 | cut -d: -f2)
echo "run_dir=$RUN_DIR master_port=$PORT"
[ -n "$RUN_DIR" ] || fail "no run directory was created"
[ -n "$PORT" ] || fail "no master port was logged"

if [ -n "$PORT" ]; then
  /usr/bin/python3 - "$PORT" <<'PY' || fail "ROS master port still open"
import socket, sys
s = socket.socket(); s.settimeout(2.0)
try:
    s.connect(("127.0.0.1", int(sys.argv[1])))
    print("port", sys.argv[1], "STILL OPEN")
    sys.exit(1)
except Exception:
    print("port", sys.argv[1], "closed")
    sys.exit(0)
finally:
    s.close()
PY
fi

if [ -n "$RUN_DIR" ] && [ -f "$RUN_DIR/receipt.json" ]; then
  /usr/bin/python3 - "$RUN_DIR/receipt.json" <<'PY' || fail "receipt assertions failed"
import json, os, sys
d = json.load(open(sys.argv[1]))
print("receipt:", json.dumps({"status": d["status"], "reason": d["status_reason"],
                              "termination": d["termination"],
                              "managed_pids": d.get("managed_pids")}))
bad = []
if d["status"] != "FAIL":
    bad.append(f"status={d['status']}")
if not d.get("status_reason"):
    bad.append("no status_reason")
if d.get("termination") in (None, "NOT_REACHED"):
    bad.append(f"termination={d.get('termination')}")
for name, pid in (d.get("managed_pids") or {}).items():
    if pid is None:
        continue
    try:
        os.kill(pid, 0)
        bad.append(f"{name} pid {pid} still alive")
    except ProcessLookupError:
        pass
    except PermissionError:
        bad.append(f"{name} pid {pid} exists but is not ours")
if bad:
    print("receipt problems:", bad)
    sys.exit(1)
print("receipt assertions: status FAIL, reason present, all managed PIDs gone")
PY
else
  fail "no receipt written for the failed run"
fi

rm -f "$OUT"
if [ "$FAILED" -ne 0 ]; then
  echo "CLEANUP TEST FAILED"
  exit 1
fi
echo "CLEANUP TEST PASSED"
exit 0
