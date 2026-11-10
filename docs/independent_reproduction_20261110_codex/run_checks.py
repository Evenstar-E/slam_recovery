"""Run the bounded independent package; only Python + NumPy + Git are needed.

Use a NEW --output directory. Exit 1 means an acceptance invariant fails;
the individual outputs distinguish that from an environment/fixture error.
Native replay, production edits, network access and dependency installation are absent.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import slam_recovery


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not sys.flags.optimize, "Run without -O; assertions are required"
    assert Path(slam_recovery.__file__).resolve().is_relative_to(ROOT), "Wrong imported package"
    args.output.mkdir(parents=True, exist_ok=False)
    evidence = {
        "scope": "Local Python integration and archived CSV, no native runs",
        "head": git("rev-parse", "HEAD").decode().strip(),
        "branch": git("branch", "--show-current").decode().strip(),
        "production_tree": git("rev-parse", "HEAD:slam_recovery").decode().strip(),
        "production_diff": git("diff", "HEAD", "--", "slam_recovery").decode(),
        "git_status": git("status", "--short").decode(),
        "platform": platform.platform(), "python": sys.version, "executable": sys.executable,
        "numpy": np.__version__, "import_path": str(Path(slam_recovery.__file__).resolve()),
        "source_sha256": {}, "checks": {},
    }
    for name in ("slam_recovery/core.py", "slam_recovery/quarantine/manager.py",
                 "slam_recovery/sim/transaction_manager_node.py",
                 "slam_recovery/tests/test_a9_repair_undo.py"):
        raw = git("show", "HEAD:"+name)
        evidence["source_sha256"][name] = {"git_blob_sha256": sha(raw),
            "loaded_file_sha256": sha((ROOT/name).read_bytes())}
    for path in HERE.glob("*.py"):
        evidence["source_sha256"][path.name] = {"file_sha256": sha(path.read_bytes())}
    jobs = (("core_tests", ["-m", "unittest", "discover", "-s", "slam_recovery/tests"]),
            ("normal_paths", [str(HERE/"normal_paths.py")]),
            ("a7_acceptance", [str(HERE/"a7_acceptance.py")]),
            ("trace_pairing_tests", [str(HERE/"test_trace_events.py")]),
            ("trace_events", [str(HERE/"trace_events.py")]))
    for name, tail in jobs:
        command = [sys.executable, "-X", "utf8", "-W", "ignore::SyntaxWarning", "-B", *tail]
        start = time.perf_counter()
        run = subprocess.run(command, cwd=ROOT, capture_output=True)
        (args.output/(name+".stdout.txt")).write_bytes(run.stdout)
        (args.output/(name+".stderr.txt")).write_bytes(run.stderr)
        record = {"command": command, "returncode": run.returncode,
                  "elapsed_seconds": time.perf_counter()-start,
                  "stdout_sha256": sha(run.stdout), "stderr_sha256": sha(run.stderr)}
        if name not in ("core_tests", "trace_pairing_tests") and run.stdout:
            try:
                record["result"] = json.loads(run.stdout)
            except ValueError:
                record["parse_error"] = "Output is not a complete JSON result"
        evidence["checks"][name] = record
    evidence["all_acceptance_checks_passed"] = all(v["returncode"] == 0 for v in evidence["checks"].values())
    (args.output/"result.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf8")
    print(json.dumps({"output": str(args.output.resolve()), "head": evidence["head"],
                      "returncodes": {k:v["returncode"] for k,v in evidence["checks"].items()},
                      "all_acceptance_checks_passed": evidence["all_acceptance_checks_passed"]}, indent=2))
    return 0 if evidence["all_acceptance_checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
