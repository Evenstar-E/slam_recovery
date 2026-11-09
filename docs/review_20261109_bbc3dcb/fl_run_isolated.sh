#!/bin/bash
# FAST-LIVO2 replay on an isolated ROS master, with a per-run receipt directory.
#
# Same node/config/rate as the archived run (/tmp/fl_record.sh, /tmp/run43.sh), but:
#   * it never touches a global rosmaster and only kills process groups it started itself;
#   * every run writes /tmp/fl_run_<utc>_<pid>/ holding all logs, a pre-run identity snapshot
#     (script, input bag, configs, binary, and the ROS parameters as actually loaded), every
#     process exit code, and a post-run output check;
#   * success is decided by an explicit output check (bag exists, non-empty, parseable,
#     /aft_mapped_to_init count > 0, sane first/last stamp) AND by the recorder and node exits --
#     never by `stat` succeeding;
#   * if the receipt itself cannot be written, the run is a failure.
#
#   bash fl_run_isolated.sh <bag> <out> [rate] [drain] [--overwrite]
#
# The output path must not already exist unless --overwrite is passed.
#
# Test hook: FL_TEST_FAIL_AFTER_START=1 exits right after the node is up, so the cleanup trap is
# exercised with roscore + record + node all running (see test_fl_run_cleanup.sh).
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
CFG="${FL_CONFIG:-/home/R26534/FAST-LIVO2/config/m2dgr.yaml}"
CAM=/home/R26534/FAST-LIVO2/config/camera_m2dgr.yaml
PARAMS="$RUN_DIR/ros_params.yaml"
STATUS=FAIL
REASON="not finished"
TERMINATION="NOT_REACHED"
PLAY_EXIT=null; REC_EXIT=null; NODE_EXIT=null; RC_EXIT=null
RC=""; REC=""; NODE=""

sha() { if [ -f "$1" ]; then sha256sum "$1" | cut -d' ' -f1; else echo null; fi; }

# kill a whole process group (we start each with setsid, so PGID == PID); never a bare -
cleanup() {
  for pid in "$NODE" "$REC" "$RC"; do
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && kill -TERM -- "-$pid" 2>/dev/null
  done
  sleep 1
  for pid in "$NODE" "$REC" "$RC"; do
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && kill -KILL -- "-$pid" 2>/dev/null
  done
}

write_receipt() {
  env -u PYTHONPATH /usr/bin/python3 - "$RUN_DIR" "$STATUS" "$REASON" "$TERMINATION" \
      "$BAG" "$OUT" "$RATE" "$DRAIN" "$PLAY_EXIT" "$REC_EXIT" "$NODE_EXIT" \
      "$SELF" "$BIN" "$CFG" "$CAM" "$PARAMS" "$RC" "$REC" "$NODE" <<'PY'
import hashlib, json, os, subprocess, sys

(rd, status, reason, term, bag, out, rate, drain,
 play_x, rec_x, node_x, selfp, binp, cfg, cam, params,
 rc_pid, rec_pid, node_pid) = sys.argv[1:]

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

pre_path = os.path.join(rd, "pre_run.json")
pre = json.load(open(pre_path)) if os.path.exists(pre_path) else {}

# sources must not have changed while the run was in flight
changed = [k for k, v in (pre.get("sha256") or {}).items()
           if v is not None and sha(pre.get("paths", {}).get(k)) != v]

check = {}
check_path = os.path.join(rd, "output_check.json")
if os.path.exists(check_path):
    check = json.load(open(check_path))

rec = {
    "status": status,
    "status_reason": reason,
    "termination": term,
    "pre_run": pre,
    "sources_changed_during_run": changed,
    "config": {"primary": {"path": cfg, "sha256": sha(cfg), "override_env": os.environ.get("FL_CONFIG", "")},
               "camera": {"path": cam, "sha256": sha(cam)},
               "ros_params_dump": {"path": params, "sha256": sha(params)}},
    "host": {"binary": binp, "sha256": sha(binp),
             "source_revision": pre.get("host_revision")},
    "run": {"rate": float(rate), "drain_sec": float(drain),
            "master_uri": os.environ.get("ROS_MASTER_URI"), "run_dir": rd,
            "taskset_prefix": os.environ.get("FL_TASKSET", "")},
    "managed_pids": {"roscore": i(rc_pid), "record": i(rec_pid), "node": i(node_pid)},
    "process_exit": {"rosbag_play": i(play_x), "rosbag_record": i(rec_x),
                     "fastlivo_node": i(node_x)},
    "output": {"bag": out, **check},
}
with open(os.path.join(rd, "receipt.json"), "w") as fh:
    json.dump(rec, fh, indent=1)
print(json.dumps({"receipt": os.path.join(rd, "receipt.json"), "status": status,
                  "reason": reason, "messages": check.get("odometry_messages"),
                  "output_sha256": (check.get("sha256") or "")[:16],
                  "sources_changed": changed}))
PY
  return $?
}

on_exit() {
  rc=$?
  cleanup
  if ! write_receipt; then
    echo "FAIL: could not write the receipt" >&2
    [ "$rc" -eq 0 ] && rc=1
  fi
  # a FAIL receipt can never accompany a zero exit
  [ "$STATUS" = "OK" ] || { [ "$rc" -eq 0 ] && rc=1; }
  exit $rc
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

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

# ---- pre-run identity snapshot -----------------------------------------------------------
REV=$(git -C /home/R26534/fast_livo2_ws/src/FAST-LIVO2 rev-parse HEAD 2>/dev/null || echo null)
env -u PYTHONPATH /usr/bin/python3 - "$RUN_DIR" "$SELF" "$BAG" "$CFG" "$CAM" "$BIN" "$REV" <<'PY'
import hashlib, json, os, sys
rd, selfp, bag, cfg, cam, binp, rev = sys.argv[1:]

def sha(p):
    if not p or not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()

paths = {"script": selfp, "input_bag": bag, "config_m2dgr": cfg, "config_camera": cam,
         "host_binary": binp}
pre = {"paths": paths, "sha256": {k: sha(v) for k, v in paths.items()},
       "host_revision": rev, "captured": "BEFORE_LAUNCH",
       "sizes": {k: (os.path.getsize(v) if os.path.exists(v) else None)
                 for k, v in paths.items()}}
json.dump(pre, open(os.path.join(rd, "pre_run.json"), "w"), indent=1)
print("pre-run snapshot:", json.dumps(pre["sha256"]))
PY

# ---- launch ------------------------------------------------------------------------------
setsid roscore -p "$PORT" > "$RUN_DIR/roscore.log" 2>&1 &
RC=$!
READY=0
for i in $(seq 1 60); do
  if rosnode list >/dev/null 2>&1; then READY=1; break; fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  STATUS=FAIL; REASON="ros master not ready after 60 s (port $PORT)"
  echo "FAIL: $REASON" >&2; exit 1
fi

rosparam load "$CFG" / || { STATUS=FAIL; REASON="could not load $CFG"; exit 1; }
rosparam load "$CAM" /laserMapping || { STATUS=FAIL; REASON="could not load $CAM"; exit 1; }
rosparam dump "$PARAMS" / || { STATUS=FAIL; REASON="could not dump ROS parameters"; exit 1; }

setsid rosbag record -O "$OUT" /aft_mapped_to_init > "$RUN_DIR/record.log" 2>&1 &
REC=$!
sleep 2
setsid ${FL_TASKSET:-} rosrun fast_livo fastlivo_mapping > "$RUN_DIR/node.log" 2>&1 &
NODE=$!
sleep 3

if [ ! -x "$BIN" ]; then STATUS=FAIL; REASON="host binary missing: $BIN"; exit 1; fi
if ! kill -0 "$NODE" 2>/dev/null; then STATUS=FAIL; REASON="node did not start"; exit 1; fi

if [ "${FL_TEST_FAIL_AFTER_START:-0}" = "1" ]; then
  STATUS=FAIL; REASON="FL_TEST_FAIL_AFTER_START (cleanup test)"; TERMINATION="PLANNED_TEST_ABORT"
  echo "FAIL: $REASON" >&2; exit 3
fi

rosbag play "$BAG" -r "$RATE" > "$RUN_DIR/play.log" 2>&1
PLAY_EXIT=$?
if [ "$PLAY_EXIT" -ne 0 ]; then
  STATUS=FAIL; REASON="rosbag play exited $PLAY_EXIT"; TERMINATION="UNEXPECTED_PLAY_EXIT"; exit 1
fi
if ! kill -0 "$NODE" 2>/dev/null; then
  STATUS=FAIL; REASON="node died during play"; TERMINATION="UNEXPECTED_NODE_DEATH"
  wait "$NODE" 2>/dev/null; NODE_EXIT=$?
  exit 1
fi

echo "play exit=$PLAY_EXIT, draining ${DRAIN}s"
sleep "$DRAIN"

# the host must still be alive at the end of the drain, or the output is truncated
if ! kill -0 "$NODE" 2>/dev/null; then
  STATUS=FAIL; REASON="node died during drain"; TERMINATION="UNEXPECTED_NODE_DEATH"
  wait "$NODE" 2>/dev/null; NODE_EXIT=$?
  exit 1
fi

kill -INT -- "-$REC" 2>/dev/null
for i in $(seq 1 30); do kill -0 "$REC" 2>/dev/null || break; sleep 1; done
wait "$REC" 2>/dev/null; REC_EXIT=$?
sleep 2
kill -KILL -- "-$NODE" 2>/dev/null
wait "$NODE" 2>/dev/null; NODE_EXIT=$?
TERMINATION="PLANNED_KILL_AFTER_DRAIN"
kill -KILL -- "-$RC" 2>/dev/null
wait "$RC" 2>/dev/null; RC_EXIT=$?
RC=""

if [ "$REC_EXIT" -ne 0 ]; then
  STATUS=FAIL; REASON="rosbag record exited $REC_EXIT"; exit 1
fi

# ---- output check decides success ---------------------------------------------------------
if ! env -u PYTHONPATH /usr/bin/python3 - "$OUT" "$RUN_DIR/output_check.json" <<'PY'
import hashlib, json, math, os, sys
out, dst = sys.argv[1], sys.argv[2]
res = {"bag": out, "exists": os.path.exists(out),
       "bytes": os.path.getsize(out) if os.path.exists(out) else 0}
ok = True
if not res["exists"] or res["bytes"] == 0:
    ok = False
    res["error"] = "missing or empty"
else:
    h = hashlib.sha256()
    with open(out, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 22), b""):
            h.update(c)
    res["sha256"] = h.hexdigest()
    try:
        from rosbags.rosbag1 import Reader
        from rosbags.typesys import Stores, get_typestore
        store = get_typestore(Stores.ROS1_NOETIC)
        with Reader(out) as r:
            res["odometry_messages"] = next(
                (c.msgcount for c in r.connections if c.topic == "/aft_mapped_to_init"), 0)
            first = last = None
            for conn, _t, raw in r.messages():
                m = store.deserialize_ros1(raw, conn.msgtype)
                s = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
                first = s if first is None else first
                last = s
            res["first_stamp_sec"] = first
            res["last_stamp_sec"] = last
            res["duration_sec"] = (last - first) if (first is not None and last is not None) else None
            res["bag_start_sec"] = r.start_time / 1e9 if r.start_time else None
            res["bag_end_sec"] = r.end_time / 1e9 if r.end_time else None
        if (res.get("odometry_messages") or 0) <= 0:
            ok = False; res["error"] = "no /aft_mapped_to_init messages"
        elif first is None or last is None or not (math.isfinite(first) and math.isfinite(last)):
            ok = False; res["error"] = "stamps missing or non-finite"
        elif last < first:
            ok = False; res["error"] = "stamps not monotonic"
        elif last - first > 3600:
            ok = False; res["error"] = "stamp span implausible"
    except Exception as e:
        ok = False; res["error"] = f"unparseable bag: {e}"
res["verdict"] = "OK" if ok else "FAIL"
json.dump(res, open(dst, "w"), indent=1)
print(json.dumps(res))
sys.exit(0 if ok else 1)
PY
then
  STATUS=FAIL; REASON="output check failed (see output_check.json)"
  echo "FAIL: output check failed" >&2
  exit 1
fi

STATUS=OK; REASON="completed"
exit 0
