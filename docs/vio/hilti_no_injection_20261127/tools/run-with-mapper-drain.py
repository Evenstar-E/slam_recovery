from collections import Counter
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from xmlrpc.client import ServerProxy


root = Path.home() / "vio-multiseq-20261127"
orb = Path.home() / "vio-gate-20261127"
other = Path.home() / "vio-plugin-boundary-20261127"
base = orb / "vio-native-checkpoint-20261127"
common = root / "config"
sequence, kind, mode = sys.argv[1:4]
slot = int(sys.argv[4]) if len(sys.argv) > 4 else 0
primary, standby, io = (
    ("0,1,2,3", "4,5,6,7", "0"), ("8,9,10,11", "12,13,14,15", "8"))[slot]
assert set(map(int, (primary + "," + standby + "," + io).split(","))) <= os.sched_getaffinity(0)
attempt = sys.argv[5] if len(sys.argv) > 5 else ""
label = f"{sequence}-{kind}-{mode}{attempt}"
data = root / "inputs" / sequence
run = root / "results" / label
run.mkdir()
config = run / "config"
config.mkdir()
input_receipt = json.loads((root / "receipts" / f"{sequence}-input.json").read_text())
limit = input_receipt["pairs_in_imu_support"]
duration = input_receipt["duration_s"]
checkout = (orb if kind == "orb" else other) / "checkout"
env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
           ORB_VIO_DRAIN_LOCAL_MAPPING="1", ROS_HOME=str(config),
           ROS_IP="127.0.0.1", PYTHONPATH=os.pathsep.join(filter(None, (str(checkout), os.environ.get("PYTHONPATH")))))
settings = common / "orb-rectified.yaml"
shutil.copyfile(settings, config / settings.name)
settings = config / settings.name
env["LD_LIBRARY_PATH"] = ":".join(map(str, (
    orb / "vio-async-recovery-20261127",
    orb / "hilti_orb_slam3_20261126/pangolin_build/src",
    base / "orb/Thirdparty/DBoW2/lib", base / "orb/Thirdparty/g2o/lib",
    "/opt/ros/noetic/lib", other / "hosts/vins-ws/devel/lib",
    os.environ.get("LD_LIBRARY_PATH", ""))))
py = [sys.executable, "-m"]
if kind == "orb":
    worker = orb / "vio-async-recovery-20261127/worker/orb_worker"
    command = [*py, "slam_recovery.vio.run_euroc", str(data), str(worker),
               str(base / "orb/Vocabulary/ORBvoc.txt"), str(settings), str(run / "log"),
               "--mode", mode, "--limit", str(limit), "--realtime", "--profile-stages",
               "--share-orb-features", "--feature-transport", "shared"]
    if mode == "recover":
        command.extend(("--native-checkpoints", "--rebuild-standby", "--async-recovery",
                        "--adaptive-gate", "--checkpoint-vocabulary", str(base / "ORBvoc-verified.bin")))
else:
    worker = other / "bin" / f"{kind}_worker"
    if kind == "vins":
        reference = (common / "vins-rectified.yaml").read_text()
        for i in range(2):
            shutil.copyfile(common / f"cam{i}.yaml", config / f"cam{i}.yaml")
        for lane in ("primary", "spare"):
            output = config / lane
            output.mkdir()
            lane_text = reference
            for key in ("output_path", "pose_graph_save_path"):
                lane_text = re.sub(rf"^{key}:.*$", f'{key}: "{output}/"', lane_text, flags=re.M)
            (config / f"{lane}.yaml").write_text(lane_text)
        native_config, resources = config / "primary.yaml", config
        env["VIO_VINS_SPARE_CONFIG"] = str(config / "spare.yaml")
    else:
        native_config, resources = config / "okvis.yaml", other / "hosts/okvis-build"
        shutil.copyfile(common / "okvis-rectified.yaml", native_config)
    command = [*py, "slam_recovery.vio.hosts.controller", *map(str, (
        data, worker, native_config, resources, settings, run / "log")), "--mode", mode,
        "--limit", str(limit), "--primary-cpus", primary]
    if mode == "recover":
        command.extend(("--standby-cpus", standby))


def sample(pid, log):
    rows = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            row = (path / "stat").read_text().rsplit(")", 1)[1].split()
            rows[int(path.name)] = (int(row[1]), int(row[21]), int(row[11]) + int(row[12]))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    tree = {pid}
    while True:
        descendants = tree | {child for child, row in rows.items() if row[0] in tree}
        if descendants == tree:
            break
        tree = descendants
    page, tick = os.sysconf("SC_PAGE_SIZE"), os.sysconf("SC_CLK_TCK")
    rss = sum(max(0, rows[child][1]) * page for child in tree if child in rows)
    cpu = {child: rows[child][2] / tick for child in tree if child in rows}
    memory = {row.split()[0].rstrip(":"): int(row.split()[1]) * 1024
              for row in Path("/proc/meminfo").read_text().splitlines() if len(row.split()) > 1}
    usage = shutil.disk_usage("/mnt/c")
    log.write(json.dumps(dict(t_ns=time.monotonic_ns(), process_tree_rss_bytes=rss,
                              cpu_s_by_pid=cpu, available_ram=memory["MemAvailable"],
                              swap_free=memory["SwapFree"], disk_c_free=usage.free)) + "\n")
    log.flush()
    return usage.free


def start_ros(log):
    with socket.socket() as endpoint:
        endpoint.bind(("127.0.0.1", 0))
        port = endpoint.getsockname()[1]
    env["ROS_MASTER_URI"] = f"http://127.0.0.1:{port}/"
    return subprocess.Popen(("roscore", "-p", str(port)), env=env, stdout=log,
                            stderr=subprocess.STDOUT)


def await_ros(ros):
    deadline = time.monotonic() + 15
    while ros.poll() is None and time.monotonic() < deadline:
        try:
            code, _, _ = ServerProxy(env["ROS_MASTER_URI"]).getPid("/vio_arm")
            if code == 1:
                return
        except OSError:
            pass
        time.sleep(.1)
    raise RuntimeError("private ROS master failed to start")


def stop(proc):
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


revision = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
receipt = dict(sequence=sequence, host=kind, mode=mode, injected_faults=[], input_pairs=limit,
               duration_s=duration, input_input_receipt=input_receipt,
               plugin_revision=revision, worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
               cpu_slot=slot, primary_cpus=primary, standby_cpus=standby, replay_cpus=io,
               started_wall_ns=time.time_ns(), config_sha256={
                   item.name: hashlib.sha256(item.read_bytes()).hexdigest()
                   for item in config.iterdir() if item.is_file()})
server = subscriber = current = None
started = time.monotonic()
try:
    with tempfile.TemporaryDirectory(prefix="vio-matrix-") as scratch, ExitStack() as stack:
        def open_log(name):
            return stack.enter_context((run / name).open("x"))

        address = Path(scratch) / "pose.sock"
        if kind == "vins":
            server = start_ros(open_log("roscore.log"))
            await_ros(server)
        subscriber = subprocess.Popen(
            [*py, "slam_recovery.vio.subscribe", str(address), str(run / "external.jsonl")],
            env=env, stdout=open_log("subscriber.log"), stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 10
        while not address.is_socket() and subscriber.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        if not address.is_socket():
            raise RuntimeError("subscriber did not listen")
        if kind == "orb":
            command.extend(("--subscriber", str(address)))
        else:
            command.insert(9, str(address))
        core_budget = primary + "," + standby + "," + io
        command = ["timeout", "--kill-after=8s", f"{max(180, duration * 5 + 90):.3f}s",
                   "taskset", "-c", core_budget, *command]
        receipt["command"] = command
        (run / "start.json").write_text(json.dumps(receipt, indent=2))
        current = subprocess.Popen(command, cwd=checkout, env=env, stdout=open_log("console"),
                                   stderr=subprocess.STDOUT)
        stats = open_log("resources.jsonl")
        while current.poll() is None:
            if sample(current.pid, stats) < 8 * 2**30:
                receipt["resource_stop"] = "remote Windows C drive below 8 GiB"
                stop(current)
                break
            try:
                current.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        receipt["controller_exit"] = current.returncode
        try:
            subscriber.wait(timeout=5)
        except subprocess.TimeoutExpired:
            stop(subscriber)
        receipt["subscriber_exit"] = subscriber.returncode
except Exception as exc:
    receipt["harness_error"] = f"{type(exc).__name__}: {exc}"
    raise
finally:
    stop(current)
    stop(subscriber)
    stop(server)
    receipt["end_wall_ns"] = time.time_ns()
    receipt["wall_elapsed_s"] = time.monotonic() - started
    (run / "result.json").write_text(json.dumps(receipt, indent=2))
    print(label, {key: receipt.get(key) for key in
                  ("controller_exit", "subscriber_exit", "harness_error", "wall_elapsed_s")}, flush=True)
