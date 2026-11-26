#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
revision=4a1b869551e7baff1eb6157a61c2f5c3e3d5ffbd
url="https://hf-mirror.com/datasets/Yuan-Shenghai/NTU-VIRAL-DATASET/resolve/$revision"
mkdir spms_02
cd spms_02
curl -fsSL --connect-timeout 15 --max-time 90 -o ground_truth.csv "$url/ground_truth/spms_02/ground_truth.csv"
test "$(stat -c %s ground_truth.csv)" = 658001
test "$(git hash-object ground_truth.csv)" = 9cb64b7583883f90c54d427ab69409b01f2d375f
curl -fL --silent --show-error --connect-timeout 20 --max-time 1500 -o spms_02.zip.partial "$url/sequences/spms_02.zip"
test "$(stat -c %s spms_02.zip.partial)" = 4312000892
printf '%s\n' '3b5fe5a6b9337fca227d62c6c140933c672b58a7d4b03a93cb833f41490aa0af  spms_02.zip.partial' | sha256sum -c
mv spms_02.zip.partial spms_02.zip
unzip -Z1 spms_02.zip > CONTENTS.txt
member=$(grep -E '(^|/)spms_02\.bag$' CONTENTS.txt)
test -n "$member"
test "$(printf '%s\n' "$member" | wc -l)" = 1
unzip -p spms_02.zip "$member" > spms_02.bag.partial
mv spms_02.bag.partial spms_02.bag
sha256sum ground_truth.csv spms_02.bag spms_02.zip > VERIFIED.sha256
