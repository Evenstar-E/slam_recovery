#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
test -s spms_02/CLIP.json
test "$(stat -c %s spms_02/spms_02.zip)" = 4312000892
test -s spms_02/spms_02_26_65.bag
test -s spms_02/VERIFIED.sha256
test -s SPMS_PAIRED_READBACK.json
test -s SPMS_FAULT_PAIRED.sha256
test -s HILTI_REVISIT.sha256
for run in upstream_campus12_smoke upstream_spms_paired upstream_hilti_revisit; do
  test -s "$run/OBSERVED.jsonl"
  test -s "$run/SUMMARY.json"
  test -s "$run/OBSERVED.sha256"
  unlink "$run/observed.bag"
done
unlink SPMS_FAULT_PAIRED.bag
unlink HILTI_REVISIT.bag
unlink spms_02/spms_02.bag
printf '%s\n' 'Kept the verified original SPMS ZIP, fixed clip, checksums and numerical receipts.' > CLEANUP.txt
