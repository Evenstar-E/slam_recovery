"""Execute paired EuRoC stability arms with one real subscriber per arm."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


CONDITIONS = {
    "clean": (),
    "short_long": ((25, 25.35), (38, 39.7)),
    "two_short": ((25, 25.35), (38, 38.35)),
}


def run_arm(args, condition, label, checkout, mode, extra=()):
    destination = args.out / label
    receipts = args.out / f"{label}.subscriber.jsonl"
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               ORB_VIO_DRAIN_LOCAL_MAPPING="1", PYTHONPATH=str(checkout))
    python = [sys.executable, "-m"]
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    truth = args.dataset
    settings = args.orb / "Examples/Stereo-Inertial/EuRoC.yaml"
    vocabulary = args.orb / "Vocabulary/ORBvoc.txt"
    faults = [val for start, stop in CONDITIONS[condition] for val in
              ("--occlude", str(start), str(stop))]
    with tempfile.TemporaryDirectory(prefix="vio-stability-") as scratch, ExitStack() as stack:
        address = Path(scratch) / "poses.sock"
        subscriber_log = stack.enter_context((args.out / f"{label}.subscriber.log").open("xb"))
        log = stack.enter_context((args.out / f"{label}.console").open("xb"))
        subscriber = subprocess.Popen(
            [*python, "slam_recovery.vio.subscribe", str(address), str(receipts)],
            cwd=checkout, env=env, stdout=subscriber_log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 5
            while not address.is_socket() and subscriber.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            if not address.is_socket():
                raise RuntimeError("subscriber failed to listen")
            command = [*python, "slam_recovery.vio.run_euroc", *map(str, (
                truth, args.worker, vocabulary, settings, destination)), "--mode", mode,
                "--limit", "950", "--realtime", "--subscriber", str(address), *faults, *extra]
            run = subprocess.run(["timeout", "--kill-after=10s", "240s", *command],
                                 cwd=checkout, env=env, stdout=log, stderr=subprocess.STDOUT)
            result = {"controller_exit": run.returncode, "mode": mode, "git_commit": revision,
                      "condition": condition, "sequence": truth.name, "wall_end_ns": time.monotonic_ns(),
                      "cpu_affinity": sorted(os.sched_getaffinity(0)), "extra_args": list(extra)}
        finally:
            if subscriber.poll() is None:
                try:
                    subscriber.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    subscriber.terminate()
            subscriber.wait()
    result["subscriber_exit"] = subscriber.returncode
    with (args.out / f"{label}.json").open("x") as stream:
        json.dump(result, stream, indent=2)
    print(label, result["controller_exit"], result["subscriber_exit"], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("dataset", "worker", "orb", "out", "frozen"):
        parser.add_argument(key, type=Path)
    parser.add_argument("--improved", type=Path)
    parser.add_argument("--conditions", nargs="+", choices=tuple(CONDITIONS), required=True)
    parser.add_argument("--arms", nargs="+", choices=("native", "sync", "improved"), required=True)
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--replicate", default="r1")
    args = parser.parse_args()
    for key in ("dataset", "worker", "orb", "out", "frozen", "improved"):
        if getattr(args, key):
            setattr(args, key, getattr(args, key).resolve())
    args.out.mkdir(parents=True, exist_ok=True)
    for index, condition in enumerate(args.conditions):
        order = (args.arms[::-1] if bool(index % 2) != args.reverse else args.arms)
        for arm in order:
            label = f"{args.dataset.name}-{condition}-{args.replicate}-{arm}"
            checkout = args.improved if arm == "improved" else args.frozen
            if checkout is None:
                parser.error("--improved is required for the improved arm")
            run_arm(args, condition, label, checkout, "native" if arm == "native" else "recover")


if __name__ == "__main__":
    main()
