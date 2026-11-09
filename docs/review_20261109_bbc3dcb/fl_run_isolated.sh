#!/bin/bash
# FAST-LIVO2 replay on an isolated ROS master, with a per-run receipt directory.
#
# Same node/config/rate as the archived run (/tmp/fl_record.sh, /tmp/run43.sh), but:
#   * it never touches a global rosmaster and only kills PIDs it started itself;
#   * every run writes its own directory /tmp/fl_run_<utc>_<pid>/ with all logs, the identity of
#     what it consumed (input bag, both configs, binary, this script), the ROS parameters as
#     actually loaded, every process exit code, and the output hash + message coverage;
#   * a failure at any step exits non-zero and still leaves a receipt, instead of ending on a
#     `stat` that succeeds no matter what happened.
#
#   bash fl_run_isolated.sh <bag> <out> [rate] [drain] [--overwrite]
#
# The output path must not already exist unless --overwrite is passed: silently replacing a
# previous run's bag is exactly how a receipt stops being evidence.
#
# Test hook: FL_TEST_FAIL_AFTER_START=1 exits right after the node starts, so the cleanup trap can
# be exercised (see test_fl_run_cleanup.sh).
set -uo pipefail

BAG="${1:-}"; OUT="${2:-}"; RATE="${3:-0.5}"; DRAIN="${4:-150}"
OVERWRITE=0
for a in "$@"; do [ "$a" = "--overwrite" ] && OVERWRITE=1; done

if [ -z "$BAG" ] || [ -z "$OUT" ]; then
  echo "usage: $0 <bag> <out> [rate] [drain] [--overwrite]" >&2
  exit 2
fi
if [ ! -f "$BAG" ]; then echo "FAIL: input bag missing: $BAG" >&2; exit 2; fi
if [ -e "$OUT" ] && [ "$OVERWRITE" -ne 1 ]; then
  echo "FAIL: output exists: $OUT (pass --overwrite to replace it)" >&2
  exit 2
fi

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)_$$"
RUN_DIR="/tmp/fl_run_${RUN_ID}"
mkdir -p "$RUN_DIR"
echo "run_dir=$RUN_DIR"
printf '%s\n' "$0 $*" > "$RUN_DIR/command.txt"

SELF=$(readlink -f "$0")
BIN=/home/R26534/fast_livo2_ws/devel/lib/fast_livo/fastlivo_mapping
CFG=/home/R26534/FAST-LIVO2/config/m2dgr.yaml
CAM=/home/R26534/FAST-LIVO2/config/camera_m2dgr.yaml
PARAMS="$RUN_DIR/ros_params.yaml"
STATUS=FAIL
PLAY_EXIT=null; REC_EXIT=null; NODE_EXIT=null
RC=""; REC=""; NODE=""

sha() { if [ -f "$1" ]; then sha256sum "$1" | cut -d' ' -f1; else echo null; fi; }

cleanup() {
  local code=$?
  # reverse start order: node, record, roscore; only PIDs this script started
  for pid in "$NODE" "$REC" "$RC"; do
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && kill -TERM "$pid" 2>/dev/null
  done
  sleep 1
  for pid in "$NODE" "$REC" "$RC"; do
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
  done
  return $code
}

write_receipt() {
  env -u PYTHONPATH /usr/bin/python3 - "$RUN_DIR" "$STATUS" "$BAG" "$OUT" "$RATE" "$DRAIN" \
      "$PLAY_EXIT" "$REC_EXIT" "$NODE_EXIT" "$SELF" "$BIN" "$CFG" "$CAM" "$PARAMS" <<'PY'
import hashlib, json, os, subprocess, sys
(rd, status, bag, out, rate, drain, play_x, rec_x, node_x, selfp, binp, cfg, cam, params) = sys.argv[1:]

def sha(p):
    if not p or not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()

def i(x):
    try:
        return int(x)
    except Exception:
        return None

msgs = start = end = None
first_stamp = last_stamp = None
try:
    from rosbags.rosbag1 import Reader
    if os.path.exists(out) and os.path.getsize(out) > 0:
        from rosbags.typesys import Stores, get_typestore
        ts_store = get_typestore(Stores.ROS1_NOETIC)
        with Reader(out) as r:
            msgs = next((c.msgcount for c in r.connections
                         if c.topic == "/aft_mapped_to_init"), 0)
            for conn, t, raw in r.messages():
                m = ts_store.deserialize_ros1(raw, conn.msgtype)
                s = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
                if first_stamp is None:
                    first_stamp = s
                last_stamp = s
            start = r.start_time / 1e9 if r.start_time else None
            end = r.end_time / 1e9 if r.end_time else None
except Exception as e:
    print("receipt: could not read output bag:", e, file=sys.stderr)

ok_output = (os.path.exists(out) and os.path.getsize(out) > 0 and (msgs or 0) > 0)
rec = {
    "status": status if ok_output else "FAIL",
    "status_reason": None if ok_output else "output bag missing, empty, or no /aft_mapped_to_init",
    "runner": {"path": selfp, "sha256": sha(selfp)},
    "input": {"bag": bag, "sha256": sha(bag),
              "bytes": os.path.getsize(bag) if os.path.exists(bag) else None},
    "config": {"m2dgr": {"path": cfg, "sha256": sha(cfg)},
               "camera": {"path": cam, "sha256": sha(cam)},
               "ros_params_dump": {"path": params, "sha256": sha(params)}},
    "host": {"binary": binp, "sha256": sha(binp),
             "source_revision": subprocess.run(
                 ["git", "-C", "/home/R26534/fast_livo2_ws/src/FAST-LIVO2", "rev-parse", "HEAD"],
                 capture_output=True, text=True).stdout.strip() or None},
    "run": {"rate": float(rate), "drain_sec": float(drain),
            "master_uri": os.environ.get("ROS_MASTER_URI"),
            "run_dir": rd},
    "process_exit": {"rosbag_play": i(play_x), "rosbag_record": i(rec_x),
                     "fastlivo_node": i(node_x)},
    "output": {"bag": out, "sha256": sha(out),
               "bytes": os.path.getsize(out) if os.path.exists(out) else 0,
               "odometry_messages": msgs, "first_stamp_sec": first_stamp,
               "last_stamp_sec": last_stamp,
               "bag_start_sec": start, "bag_end_sec": end},
}
with open(os.path.join(rd, "receipt.json"), "w") as fh:
    json.dump(rec, fh, indent=1)
print(json.dumps({"receipt": os.path.join(rd, "receipt.json"), "status": rec["status"],
                  "messages": msgs, "output_sha256": (rec["output"]["sha256"] or "")[:16]}))
PY
}

on_exit() {
  rc=$?
  cleanup
  write_receipt
  exit $rc
}
trap on_exit EXIT   # INT/TERM exit by default and still fire this

set +u          # the ROS setup scripts reference unset variables
source /home/R26534/mm/ros/setup.bash
source /home/R26534/fast_livo2_ws/devel/setup.bash
set -u
export ROS_HOME="$RUN_DIR/ros_home"
mkdir -p "$ROS_HOME"
PORT=$(/usr/bin/python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
export ROS_MASTER_URI="http://127.0.0.1:$PORT"
export ROS_HOSTNAME=127.0.0.1
echo "master=$ROS_MASTER_URI bag=$BAG out=$OUT rate=$RATE drain=$DRAIN"

roscore -p "$PORT" > "$RUN_DIR/roscore.log" 2>&1 &
RC=$!
READY=0
for i in $(seq 1 60); do
  if rosnode list >/dev/null 2>&1; then READY=1; break; fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  echo "FAIL: ros master not ready after 60 s (port $PORT)" >&2
  exit 1
fi

rosparam load "$CFG" / || { echo "FAIL: could not load $CFG" >&2; exit 1; }
rosparam load "$CAM" /laserMapping || { echo "FAIL: could not load $CAM" >&2; exit 1; }
rosparam dump "$PARAMS" / || { echo "FAIL: could not dump parameters" >&2; exit 1; }

rosbag record -O "$OUT" /aft_mapped_to_init > "$RUN_DIR/record.log" 2>&1 &
REC=$!
sleep 2
rosrun fast_livo fastlivo_mapping > "$RUN_DIR/node.log" 2>&1 &
NODE=$!
sleep 3

if [ ! -x "$BIN" ] || ! kill -0 "$NODE" 2>/dev/null; then
  echo "FAIL: node did not start" >&2
  exit 1
fi

if [ "${FL_TEST_FAIL_AFTER_START:-0}" = "1" ]; then
  echo "FAIL: FL_TEST_FAIL_AFTER_START (cleanup test)" >&2
  exit 3
fi

rosbag play "$BAG" -r "$RATE" > "$RUN_DIR/play.log" 2>&1
PLAY_EXIT=$?
if [ "$PLAY_EXIT" -ne 0 ]; then echo "FAIL: rosbag play exited $PLAY_EXIT" >&2; exit 1; fi
if ! kill -0 "$NODE" 2>/dev/null; then echo "FAIL: node died during play" >&2; exit 1; fi

echo "play exit=$PLAY_EXIT, draining ${DRAIN}s"
sleep "$DRAIN"

kill -INT "$REC" 2>/dev/null
for i in $(seq 1 30); do kill -0 "$REC" 2>/dev/null || break; sleep 1; done
wait "$REC" 2>/dev/null; REC_EXIT=$?
sleep 2
kill -9 "$NODE" 2>/dev/null
wait "$NODE" 2>/dev/null; NODE_EXIT=$?
kill -9 "$RC" 2>/dev/null
RC=""

if [ ! -s "$OUT" ]; then
  echo "FAIL: output bag missing or empty" >&2
  exit 1
fi
STATUS=OK
exit 0
