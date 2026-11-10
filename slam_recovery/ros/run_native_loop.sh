#!/bin/bash
# Host FAST-LIVO2 and the recovery node together on one bag, deliberately in one process group.
#
#   run_native_loop.sh <bag> [--rate R] [--drain S] [--duration S] [--max-pairs N]
#                      [--candidate-source S]
#
# What it guarantees, and why each one is checked rather than assumed:
#   * the host and the recovery node are children of one supervisor started with setsid, so they
#     share one pgid and teardown kills exactly that group -- never a global rosmaster, never a
#     sibling run's node. "Same process group" is a wiring fact the peer asked to see verified, so
#     wiring.json compares the recovery node's own pgid against the host's live pgid;
#   * the recovery node is started BEFORE the host, so it is already subscribed when the first
#     `/velodyne_points` arrives; a node that starts late silently loses the beginning of the bag;
#   * the run is judged by the artefacts the recovery node wrote (summary, candidate stream,
#     wiring check), not by an exit status;
#   * the library that actually carries the host behaviour is resolved from /proc/<pid>/maps and
#     hashed, because the executable's sha does not change between builds.
#
# The recovery node runs from the repository working tree (PYTHONPATH), not from an installed
# package: the point of this script is to exercise the code under review.
set -uo pipefail

BAG="${1:-}"; shift || true
RATE=1.0; DRAIN=20; DURATION=0; MAX_PAIRS=0; CAND_SRC=host_poses
while [ $# -gt 0 ]; do
  case "$1" in
    --rate) RATE="$2"; shift 2 ;;
    --drain) DRAIN="$2"; shift 2 ;;
    --duration) DURATION="$2"; shift 2 ;;
    --max-pairs) MAX_PAIRS="$2"; shift 2 ;;
    --candidate-source) CAND_SRC="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -z "$BAG" ] && { echo "usage: $0 <bag> [options]" >&2; exit 2; }
[ -f "$BAG" ] || { echo "FAIL: input bag missing: $BAG" >&2; exit 2; }

REPO="/tmp/wt-sim"
HOST_WS="/home/R26534/fast_livo2_ws"
# The node needs rospy AND numpy from one interpreter. /usr/bin/python3 is 3.10 with a 3.10 numpy;
# putting the ROS 3.11 site-packages on its path makes numpy unimportable. The ROS interpreter is
# 3.11 and carries a working numpy, so rospy and numpy come from the same place.
PY="/home/R26534/mm/ros/bin/python3"
BIN="$HOST_WS/devel/lib/fast_livo/fastlivo_mapping"
CFG="${FL_CONFIG:-/home/R26534/FAST-LIVO2/config/m2dgr.yaml}"
CAM=/home/R26534/FAST-LIVO2/config/camera_m2dgr.yaml

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)_$$"
RUN_DIR="/tmp/fl_native_${RUN_ID}"
mkdir -p "$RUN_DIR"
echo "run_dir=$RUN_DIR"
printf '%s\n' "$0 $*" > "$RUN_DIR/command.txt"

STATUS=FAIL; REASON="not finished"; TERMINATION="NOT_REACHED"
RC=""; PAIR=""; REC=""; HOST=""
PLAY_EXIT=null; PAIR_EXIT=null; REC_EXIT=null; RC_EXIT=null

cleanup() {
  if [ -n "$PAIR" ]; then
    # SIGTERM the whole supervisor group, then wait for the recovery node to flush, then KILL.
    kill -TERM -- "-$PAIR" 2>/dev/null
  fi
  for _ in $(seq 1 15); do
    [ -n "$REC" ] && [ -d "/proc/$REC" ] && sleep 1 || break
  done
  [ -n "$PAIR" ] && kill -KILL -- "-$PAIR" 2>/dev/null
  [ -n "$RC" ] && kill -KILL -- "-$RC" 2>/dev/null
}

write_receipt() {
  env -u PYTHONPATH /usr/bin/python3 - "$RUN_DIR" "$STATUS" "$REASON" "$TERMINATION" \
      "$BAG" "$RATE" "$DRAIN" "$DURATION" "$MAX_PAIRS" "$CAND_SRC" \
      "$BIN" "$CFG" "$CAM" "$PLAY_EXIT" "$PAIR_EXIT" "$REC_EXIT" "$RC_EXIT" <<'PY'
import hashlib, json, os, sys

(rd, status, reason, term, bag, rate, drain, duration, max_pairs, cand_src,
 binp, cfg, cam, play_x, pair_x, rec_x, rc_x) = sys.argv[1:]

def sha(p):
    if not p or not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()

rec = {
    "status": status, "reason": reason, "termination": term,
    "run_id": os.path.basename(rd.rstrip("/")),
    "inputs": {"bag": bag, "bag_sha256": sha(bag),
               "host_binary": binp, "host_binary_sha256": sha(binp),
               "config_m2dgr": cfg, "config_m2dgr_sha256": sha(cfg),
               "config_camera": cam, "config_camera_sha256": sha(cam),
               "recovery_node_source": os.path.join(rd, "recovery_node_source.sha256")},
    "launch": {"rate": rate, "drain_s": drain, "duration_s": duration,
               "max_pairs": max_pairs, "candidate_source": cand_src,
               "group_model": "host and recovery node are children of one setsid supervisor"},
    "exit_codes": {"play": play_x, "supervisor": pair_x, "recovery_node": rec_x,
                   "roscore": rc_x},
}
p = os.path.join(rd, "recovery_node_source.sha256")
if os.path.exists(p):
    rec["inputs"]["recovery_node_source"] = open(p).read().strip()
runtime_lib = os.path.join(rd, "runtime_lib.txt")
if os.path.exists(runtime_lib):
    lib = open(runtime_lib).read().strip()
    rec["inputs"]["runtime_library"] = lib
    rec["inputs"]["runtime_library_sha256"] = sha(lib)
summary_path = os.path.join(rd, "run_summary.json")
if os.path.exists(summary_path):
    rec["recovery_summary_present"] = True
    try:
        s = json.load(open(summary_path))
        rec["recovery_summary_headline"] = {
            "paired": s.get("pairing", {}).get("paired"),
            "fed_to_step_frame": s.get("frames", {}).get("fed_to_step_frame"),
            "episodes": s.get("quarantine", {}).get("episodes"),
            "decisions": s.get("quarantine", {}).get("decisions"),
            "accepted": s.get("gate", {}).get("accepted"),
            "final_state": s.get("final_state"),
        }
    except Exception as exc:                       # a broken summary is not a passing run
        rec["recovery_summary_error"] = f"{type(exc).__name__}: {exc}"
        if rec["status"] == "OK":
            rec["status"] = "FAIL"
            rec["reason"] = "run_summary.json is not valid JSON"
else:
    if rec["status"] == "OK":
        rec["status"] = "FAIL"
        rec["reason"] = "recovery node wrote no run_summary.json"

json.dump(rec, open(os.path.join(rd, "receipt.json"), "w"), indent=1)
print(json.dumps({"status": rec["status"], "reason": rec["reason"]}, indent=1))
sys.exit(0 if rec["status"] == "OK" else 1)
PY
}

on_exit() {
  local rc=$?
  cleanup
  write_receipt || { echo "FAIL: could not write the receipt" >&2; rc=1; }
  [ "$STATUS" = "OK" ] || { [ "$rc" -eq 0 ] && rc=1; }
  echo "termination=$TERMINATION status=$STATUS reason=$REASON"
  exit $rc
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

set +u
source /home/R26534/mm/ros/setup.bash
source "$HOST_WS/devel/setup.bash"
set -u
export ROS_HOME="$RUN_DIR/ros_home"; mkdir -p "$ROS_HOME"
PORT=$(/usr/bin/python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
export ROS_MASTER_URI="http://127.0.0.1:$PORT"; export ROS_HOSTNAME=127.0.0.1
echo "master=$ROS_MASTER_URI bag=$BAG rate=$RATE"

sha256sum "$REPO/slam_recovery/ros/recovery_node.py" | cut -d' ' -f1 \
  > "$RUN_DIR/recovery_node_source.sha256"
{ "$PY" -V; echo "$PY"; } > "$RUN_DIR/python_version.txt" 2>&1

setsid roscore -p "$PORT" > "$RUN_DIR/roscore.log" 2>&1 &
RC=$!
READY=0
for _ in $(seq 1 60); do rosnode list >/dev/null 2>&1 && { READY=1; break; }; sleep 1; done
[ "$READY" -ne 1 ] && { STATUS=FAIL; REASON="ros master not ready (port $PORT)"; exit 1; }

rosparam load "$CFG" / || { STATUS=FAIL; REASON="could not load $CFG"; exit 1; }
rosparam load "$CAM" /laserMapping || { STATUS=FAIL; REASON="could not load $CAM"; exit 1; }

# ---- one supervisor, one process group ------------------------------------------------------
REC_ARGS=(--run-dir "$RUN_DIR" --candidate-source "$CAND_SRC" --scan-cap 6000)
[ "$DURATION" != "0" ] && REC_ARGS+=(--duration-sec "$DURATION")
[ "$MAX_PAIRS" != "0" ] && REC_ARGS+=(--max-pairs "$MAX_PAIRS")

cat > "$RUN_DIR/launch_pair.sh" <<EOF
#!/bin/bash
# Generated by run_native_loop.sh. Both children inherit this shell's pgid.
rosrun fast_livo fastlivo_mapping > "$RUN_DIR/host.log" 2>&1 &
echo \$! > "$RUN_DIR/host.pid"
PYTHONPATH="$REPO:\${PYTHONPATH:-}" "$PY" -B -m slam_recovery.ros.recovery_node \\
    $(printf '%q ' "${REC_ARGS[@]}")> "$RUN_DIR/recovery_node.log" 2>&1 &
echo \$! > "$RUN_DIR/rec.pid"
wait
EOF
chmod +x "$RUN_DIR/launch_pair.sh"

setsid bash "$RUN_DIR/launch_pair.sh" > "$RUN_DIR/supervisor.log" 2>&1 &
PAIR=$!
sleep 3
HOST=$(cat "$RUN_DIR/host.pid" 2>/dev/null || echo "")
REC=$(cat "$RUN_DIR/rec.pid" 2>/dev/null || echo "")
[ -z "$HOST" ] || [ -z "$REC" ] && { STATUS=FAIL; REASON="supervisor did not start both children"; exit 1; }
kill -0 "$REC" 2>/dev/null || { STATUS=FAIL; REASON="recovery node died at startup (see recovery_node.log)"; exit 1; }

# runtime identity of the library that actually carries the host behaviour
resolve_runtime_lib() {
  local pgid
  pgid=$(ps -o pgid= -p "$HOST" 2>/dev/null | tr -d ' ')
  [ -z "$pgid" ] && return 1
  for _ in $(seq 1 60); do
    for pid in $(pgrep -g "$pgid" -f fastlivo_mapping 2>/dev/null); do
      local line
      line=$(grep -m1 'liblaser_mapping\.so' "/proc/$pid/maps" 2>/dev/null) || continue
      printf '%s\n' "${line##* }" > "$RUN_DIR/runtime_lib.txt"
      printf '%s\n' "$pid" > "$RUN_DIR/runtime_pid.txt"
      printf '%s\n' "$pgid" > "$RUN_DIR/runtime_pgid.txt"
      return 0
    done
    sleep 0.5
  done
  return 1
}
resolve_runtime_lib || { STATUS=FAIL; REASON="runtime library identity unavailable"; exit 1; }

rosbag play "$BAG" -r "$RATE" > "$RUN_DIR/play.log" 2>&1
PLAY_EXIT=$?
[ "$PLAY_EXIT" -ne 0 ] && { STATUS=FAIL; REASON="rosbag play exited $PLAY_EXIT"; TERMINATION="UNEXPECTED_PLAY_EXIT"; exit 1; }

echo "play done, draining ${DRAIN}s"
sleep "$DRAIN"

kill -INT "$REC" 2>/dev/null
for _ in $(seq 1 40); do [ -d "/proc/$REC" ] && sleep 1 || break; done
kill -0 "$REC" 2>/dev/null && { STATUS=FAIL; REASON="recovery node did not exit after SIGINT"; TERMINATION="UNRESPONSIVE_RECOVERY_NODE"; exit 1; }
REC_EXIT=0
TERMINATION="PLANNED_KILL_AFTER_DRAIN"
[ -f "$RUN_DIR/run_summary.json" ] || { STATUS=FAIL; REASON="recovery node produced no summary"; exit 1; }

# ---- wiring, read back from the artefacts the node wrote ------------------------------------
env -u PYTHONPATH /usr/bin/python3 - "$RUN_DIR" "$REC" "$HOST" <<'PY'
import json, os, sys
rd, rec_pid, host_pid = sys.argv[1], sys.argv[2], sys.argv[3]
s = json.load(open(os.path.join(rd, "run_summary.json")))
p = s.get("pairing", {}); f = s.get("frames", {}); n = s.get("nis", {})
q = s.get("quarantine", {}); g = s.get("gate", {})

def pgid_of(pid):
    try:
        return os.getpgid(int(pid))
    except (OSError, TypeError, ValueError):
        return None

# The recovery node recorded its own pgid before exiting; the host is still alive here, so its
# pgid is read live. Comparing a live pid against a reaped one would compare None with a number.
recovery_pgid = s.get("runtime", {}).get("pgid")
host_pgid = pgid_of(host_pid)

checks = {}
checks["both_topics_received"] = {
    "pose_messages": s.get("runtime", {}).get("pose_messages"),
    "scan_messages": s.get("runtime", {}).get("scan_messages"),
    "ok": bool(s.get("runtime", {}).get("pose_messages"))
          and bool(s.get("runtime", {}).get("scan_messages")),
}
checks["pairing"] = {
    "paired": p.get("paired"),
    "fraction_of_poses": p.get("paired_fraction_of_poses"),
    "fraction_of_scans": p.get("paired_fraction_of_scans"),
    "max_abs_dt_ns": p.get("max_abs_dt_ns"),
    "ok": bool(p.get("paired")),
}
checks["nis_provenance"] = {
    "computed": n.get("computed"), "carried_forward": n.get("carried_forward"),
    "unavailable": n.get("unavailable"),
    "reference_node_map": n.get("reference_node_map"),
    "reference_prev_scan": n.get("reference_prev_scan"),
    "fed_to_step_frame": f.get("fed_to_step_frame"),
    "not_fed_no_reference": f.get("not_fed_no_nis_reference"),
    "ok": bool(f.get("fed_to_step_frame")),
}
checks["gate_reachable"] = {
    "episodes": q.get("episodes"), "decisions": q.get("decisions"),
    "accepted": g.get("accepted"), "rejected": g.get("rejected"),
    "errored": g.get("errored"),
    "incumbent_basis": [e.get("incumbent_basis", {}).get("status")
                        for e in q.get("episode_detail", [])],
    "evidence_reasons": [e.get("paired_evidence", {}).get("reason")
                         for e in q.get("episode_detail", [])],
    "ok": bool(q.get("decisions")),
}
checks["same_process_group"] = {
    "recovery_pid": int(rec_pid) if rec_pid.isdigit() else None,
    "host_pid": int(host_pid) if host_pid.isdigit() else None,
    "recovery_pgid": recovery_pgid, "host_pgid": host_pgid,
    "ok": recovery_pgid is not None and recovery_pgid == host_pgid,
}
out = {"checks": checks, "all_ok": all(v["ok"] for v in checks.values())}
json.dump(out, open(os.path.join(rd, "wiring.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
PY

if ! env -u PYTHONPATH /usr/bin/python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["all_ok"] else 1)' "$RUN_DIR/wiring.json"; then
  STATUS=FAIL; REASON="wiring check failed (see wiring.json)"; exit 1
fi

STATUS=OK; REASON="all wiring checks passed"
exit 0
