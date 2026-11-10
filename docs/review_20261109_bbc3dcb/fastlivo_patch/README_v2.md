# TRACE_GROUP v2 patch set

Base: FAST-LIVO2 `0d2c034` **plus the T3a determinism patch** (the `option(NO_MP)` / `option(DET_SYNC)`
block). Applying this set to a clean `0d2c034` fails on the CMakeLists hunk — the base really is
`0d2c034 + T3a`, which is what `/tmp/fastlivo_bin_backup/*.pre_trace` holds.

Apply with `patch -p1` from the source root. Verified 2026-11-10: applying the three files to the
`*.pre_trace` base reproduces the working tree byte-for-byte, and that tree produced the libraries
below.

| file | content |
|---|---|
| `CMakeLists.txt.v2.diff` | options NO_MP / DET_SYNC / TRACE_GROUP (all default OFF) |
| `src_LIVMapper.cpp.v2.diff` | sha256 helper, lock-free arrival ring, single-writer CSV with header, ARRIVE/GROUP/STATE emission outside the DET_SYNC guard, DET_SYNC loop |
| `src_IMU_Processing.cpp.v2.diff` | IMUINIT over every sample of the group (empty set writes `n=0`, `first/last=-1`, `sha256("")`) |
| `include_LIVMapper.h.v2.diff` | empty on purpose: v2 needs no header change |

## Build commands

```
ON      : catkin_make --pkg fast_livo -DNO_MP=ON  -DDET_SYNC=ON  -DTRACE_GROUP=ON  -DCMAKE_POLICY_VERSION_MINIMUM=3.5
OFF     : catkin_make --pkg fast_livo -DNO_MP=ON  -DDET_SYNC=ON  -DTRACE_GROUP=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5
DEFAULT : catkin_make --pkg fast_livo -DNO_MP=OFF -DDET_SYNC=OFF -DTRACE_GROUP=ON  -DCMAKE_POLICY_VERSION_MINIMUM=3.5
```

The executable links with the newer libstdc++ from `/home/R26534/mm/ros/lib` and Sophus from
`/home/R26534/fast_livo2_deps/build/Sophus`, so relinking needs both on `LIBRARY_PATH`; without it
the link stops on `GLIBCXX_3.4.32` / `-lSophus` even though the library target builds.

## Libraries that produced the archived traces

| build | library sha256 |
|---|---|
| ON (TRACE+NO_MP+DET_SYNC) | `20df3d3f…` |
| OFF (TRACE off, NO_MP+DET_SYNC) | `b5255dd3…` |
| DEFAULT (TRACE only) | `6aeef032…` |
| DEFAULT, broken emission (only IMUINIT written) | `c65f134c…` (superseded) |

## What changed on 2026-11-10 after the first default run

`ARRIVE` and `GROUP` were emitted from inside `#ifdef DET_SYNC`, so the default build wrote only the
five `IMUINIT` rows. The emission now sits under `#if defined(DET_SYNC) || defined(TRACE_GROUP)`
with the DET_SYNC `ROS_INFO` still guarded separately, and the `STATE` block's timestamp local was
renamed so the two declarations do not collide when both flags are on.
