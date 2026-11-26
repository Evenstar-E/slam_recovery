#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
release=/home/tong/fastlio_repro_work_20261126/frozen
label="${STREAM_ROUND:-stream_1x_precropped}"
[[ "$label" =~ ^stream_1x_[a-zA-Z0-9_]+$ ]]
root="$release/$label"
if [[ ! -d "$root" ]]; then
    mkdir "$root"
    source="$release/clock_ingress_comparison"
    cp "$source"/{FIXTURES.json,stamp_log.py,offline.sh,compact.py} "$root"
    cp "$source/fallback_version/clock_ingress_preview.py" "$root"
    cp stream_1x.py score_stream.py "$root"
    sed -e 's/|sbs_clean)/|sbs_clean|spms_clean|spms_fault)/' \
      -e 's#fallback_version/clock_ingress_preview.py#stream_1x.py#' \
      "$source/run_fallback_case.sh" > "$root/run_case.sh"
fi
cd "$root"
export LIO_CLOCK_READONLY_PREVIEW=1
for profile in "$@"; do
  for arm in native plugin; do
    name="${profile}_$arm"
    rc=0
    bash run_case.sh "$name" "$profile" "$arm" || rc=$?
    if [[ -s "$name/finished_at.txt" && -s "$name/exit.txt" ]]; then
      mkdir "${name}_ingress"
      for file in producer imu_arrival memory; do
        if [[ -f "$name/$file.jsonl" ]]; then
          mv "$name/$file.jsonl" "${name}_ingress/"
        fi
      done
      bash offline.sh compact.py "$name"
    fi
    printf '%s %s\n' "$name" "$rc" >> STREAM_EXIT.txt
  done
  bash offline.sh score_stream.py "$profile" | tee "$profile.json"
done
