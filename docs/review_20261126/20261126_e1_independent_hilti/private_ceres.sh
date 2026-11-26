#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
stage=ceres
packages=(libceres-dev libceres1 libsuitesparse-dev libatlas3-base libamd2 libcamd2 libccolamd2
          libcolamd2 libcholmod3 libspqr2 libsuitesparseconfig5 libcxsparse3 libmetis5 libtbb2)
if [[ "${1:-}" == scipy ]]; then
  stage=scipy
  packages=(python3-scipy python3-decorator liblbfgsb0)
fi
mkdir "$stage-debs"
cd "$stage-debs"
apt-get --print-uris download "${packages[@]}" > URIS.txt
while read -r quoted filename bytes checksum; do
  url=${quoted:1:${#quoted}-2}
  url="https${url#http}"
  curl -fsSL --retry 1 --connect-timeout 10 --max-time 90 -o "$filename" "$url"
  test "$(stat -c %s "$filename")" = "$bytes"
  if [[ "$checksum" == SHA256:* ]]; then
    printf '%s  %s\n' "${checksum#SHA256:}" "$filename" | sha256sum -c
  else
    meta=$(apt-cache show "$(dpkg-deb -f "$filename" Package)=$(dpkg-deb -f "$filename" Version)")
    expected=$(printf '%s\n' "$meta" | awk '$1=="SHA256:" {print $2; exit}')
    test -n "$expected"
    printf '%s  %s\n' "$expected" "$filename" | sha256sum -c
  fi
  dpkg-deb -x "$filename" "../$stage-root"
done < URIS.txt
sha256sum ./*.deb > DEBS.sha256
