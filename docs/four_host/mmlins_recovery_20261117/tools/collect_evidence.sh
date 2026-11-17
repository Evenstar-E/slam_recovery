#!/bin/bash
# Copy the small, self-describing evidence files out of a run directory into the repo. The host
# recording (host.bag, hundreds of MB) stays in /tmp; the report cites its rosbag info instead.
# usage: collect_evidence.sh SRC_RUN_DIR DEST_DIR
set -o pipefail
SRC="${1:?src}"; DST="${2:?dst}"
mkdir -p "$DST/ctl"
for f in pre_run.txt result.txt runner_stdout.log recovery_node.log frontend.log pgo.log play.log \
         record.log run_summary.json bag_info.txt ctl_listing_at_exit.txt pgo_hold_at_exit.txt \
         lifecycle.json; do
  [ -f "$SRC/$f" ] && cp "$SRC/$f" "$DST/$f"
done
for f in capabilities.json input_fates.jsonl ack cmd.done; do
  [ -f "$SRC/ctl/$f" ] && cp "$SRC/ctl/$f" "$DST/ctl/$f"
done
if [ -f "$SRC/host.bag" ]; then
  rosbag info "$SRC/host.bag" > "$DST/host_bag_info.txt" 2>&1 || true
  sha256sum "$SRC/host.bag" > "$DST/host_bag_sha256.txt" 2>&1 || true
fi
ls -la "$DST" > "$DST/listing.txt" 2>&1
