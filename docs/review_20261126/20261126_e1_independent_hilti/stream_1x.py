"""Send LiDAR and IMU at a fixed input clock, independently of recovery processing."""
import hashlib
import io
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
import sys
from threading import Event, Thread
import time
from xmlrpc.client import ServerProxy

import cv2
import rosbag
import rosgraph
import rospy

from clock_ingress_preview import ClockWithNativeFallback, Native
from run_matrix import SOURCE, frozen


NS = 1_000_000_000
ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "FIXTURES.json"
SPMS = Path("/home/tong/e1_hilti_stream_20261126/spms_02/spms_02_26_65.bag")
SENTINEL = object()


def definition(profile):
    if profile in ("sync", "eee_clean"):
        fixture = json.loads(FIXTURE.read_text())[profile]["input"]
        return (SOURCE / "eee_03" / "study.bag", "/velodyne_points", "/imu_raw",
                fixture["origin_ns"], fixture["windows"], fixture["inputs"])
    if profile not in ("spms_clean", "spms_fault"):
        raise ValueError(profile)
    lidar, imu = "/os1_cloud_node1/points", "/imu/imu"
    origin = json.loads((SPMS.parent / "CLIP.json").read_text())["origin_ns"]
    event_defs = () if profile == "spms_clean" else (("sync", 34, 40), ("attenuation", 51, 57))
    windows = [dict(id=index, kind=kind, onset_ns=origin + start * NS,
                    end_ns=origin + end * NS, inject_z_m=.5)
               for index, (kind, start, end) in enumerate(event_defs, 1)]
    return SPMS, lidar, imu, origin, windows, None


def read_clouds(bag, topic, low, high, origin, windows):
    counts = [0] * len(windows)
    for _, msg, receipt in bag.read_messages(topics=[topic], start_time=low, end_time=high):
        stamp = msg.header.stamp.to_nsec()
        if not origin + 27 * NS <= stamp < origin + 64 * NS:
            continue
        index = next((i for i, window in enumerate(windows)
                      if window["onset_ns"] <= stamp < window["end_ns"]), None)
        if index is not None:
            counts[index] += 1
            msg = frozen.mutate(msg, windows[index]["kind"], windows[index], counts[index])
        yield msg, receipt.to_nsec(), dict(
            stamp_ns=stamp, fed_ns=msg.header.stamp.to_nsec(),
            event=index + 1 if index is not None else None,
            sha256=hashlib.sha256(msg.data).hexdigest())


def run(out, profile, arm):
    path, lidar, imu, origin, windows, expected = definition(profile)
    lo, hi = (frozen.time_to_ros(origin + second * NS) for second in (26, 65))
    with rosbag.Bag(str(path)) as bag:
        inertial = [(msg, stamp.to_nsec()) for _, msg, stamp in
                    bag.read_messages(topics=[imu], start_time=lo, end_time=hi)]
    if not inertial:
        raise RuntimeError("input window has no IMU messages")
    rospy.init_node("streaming_clock_acceptance", disable_signals=True)
    ctl = {"native": Native, "plugin": ClockWithNativeFallback}[arm](
        out, [msg for msg, _ in inertial])
    ctl.arm = "sparse_localization"
    ctl.imu_through = lambda stamp: None  # IMU publisher uses the independent arrival clock.
    ctl.wait(lambda: ctl.native_pub.get_num_connections() > 0 and
             ctl.imu_pub.get_num_connections() > 0, 12, "missing native input subscribers")
    queue = Queue(maxsize=32)
    errors = []
    with rosbag.Bag(str(path)) as bag:
        lidar_population = list(read_clouds(bag, lidar, lo, hi, origin, windows))
    if len(lidar_population) > 500:
        raise RuntimeError("unexpected LiDAR clip size")
    if expected is not None and [row for _, _, row in lidar_population] != expected:
        raise RuntimeError("frozen LiDAR identities changed")
    node_uri = rosgraph.Master(rospy.get_name()).lookupNode("/laserMapping")
    status, _, host_pid = ServerProxy(node_uri).getPid(rospy.get_name())
    if status != 1:
        raise RuntimeError("could not bind resource monitoring to the native host")
    monitor_done = Event()
    wall_origin = time.monotonic_ns() + 500_000_000 - 26 * NS

    def arrive(recorded):
        deadline = wall_origin + recorded - origin
        remaining = deadline - time.monotonic_ns()
        if remaining > 0:
            time.sleep(remaining / NS)
        wall = time.monotonic_ns()
        return deadline, wall

    def produce_clouds():
        try:
            with (out / "producer.jsonl").open("x") as trace:
                for msg, recorded, identity in lidar_population:
                    deadline, wall = arrive(recorded)
                    row = dict(identity, recorded_ns=recorded, deadline_ns=deadline,
                               received_wall_ns=wall, receiver_ns=origin + wall - wall_origin)
                    try:
                        queue.put_nowait((msg, row))
                        dropped = False
                    except Full:
                        dropped = True
                    trace.write(json.dumps(dict(row, dropped=dropped, depth=queue.qsize())) + "\n")
        except Exception as exc:
            errors.append(str(exc))
        finally:
            queue.put(SENTINEL)

    def produce_imu():
        try:
            with (out / "imu_arrival.jsonl").open("x") as trace:
                for msg, recorded in inertial:
                    packed = io.BytesIO()
                    msg.serialize(packed)
                    deadline, wall = arrive(recorded)
                    ctl.imu_pub.publish(msg)
                    ctl.sent_imu += 1
                    trace.write(json.dumps([msg.header.stamp.to_nsec(), deadline, wall,
                                           hashlib.sha256(packed.getvalue()).hexdigest()]) + "\n")
        except Exception as exc:
            errors.append(str(exc))

    def poll_memory():
        with (out / "memory.jsonl").open("x") as trace:
            while not monitor_done.is_set():
                memory = {}
                for pid in (os.getpid(), host_pid):
                    for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
                        if line.startswith(("Pss:", "SwapPss:")):
                            key, amount, _ = line.split()
                            memory.setdefault(str(pid), {})[key.rstrip(":")] = int(amount)
                trace.write(json.dumps({"wall_ns": time.monotonic_ns(), "pid_kib": memory}) + "\n")
                trace.flush()
                monitor_done.wait(0.5)

    threads = [Thread(target=fn, daemon=True) for fn in (produce_clouds, produce_imu)]
    monitor = Thread(target=poll_memory, daemon=True)
    monitor.start()
    for worker in threads:
        worker.start()
    count = 0
    while True:
        try:
            item = queue.get(timeout=12)
        except Empty as exc:
            raise RuntimeError("no LiDAR input for 12 seconds") from exc
        if item is SENTINEL:
            break
        msg, row = item
        count += 1
        row["wall_feed_ns"] = time.monotonic_ns()
        ctl.input_file.write(json.dumps(row) + "\n")
        if arm == "plugin" and row["stamp_ns"] < origin + 31 * NS:
            ctl.diagnose(msg, origin, row["receiver_ns"])
        ctl.receive(msg, origin, row["receiver_ns"], row["received_wall_ns"])
    for worker in threads:
        worker.join(timeout=12)
    if errors or any(worker.is_alive() for worker in threads):
        raise RuntimeError(f"producer failure or timeout: {errors}")
    ctl.flush_clock(origin)
    if arm == "native" or ctl.mode == "ARMED":
        ctl.wait_pose(ctl.latest_scan, 10)
    monitor_done.set()
    monitor.join()
    (out / "completion.json").write_text(json.dumps(dict(
        profile=profile, arm=arm, mode=ctl.mode, speed=1, groups=count, windows=windows,
        origin_ns=origin, input=str(path), tail=ctl.send("status")), indent=2) + "\n")


if __name__ == "__main__":
    cv2.setNumThreads(1)
    assert Path(frozen.__file__).resolve() == Path(os.environ["FROZEN_VERSION_DIR"]) / "mixed_controller.py"
    run(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
