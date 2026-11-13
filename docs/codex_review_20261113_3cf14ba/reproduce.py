"""Recheck pinned archives only; does not build, replay, or run a native host."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import sys
from datetime import datetime, timezone


def compare(actual, expected, path='result'):
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), path
        for key, value in expected.items():
            compare(actual[key], value, path + '.' + key)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), path
        for i, (a, e) in enumerate(zip(actual, expected)):
            compare(a, e, f'{path}[{i}]')
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10), path
    else:
        assert type(actual) is type(expected) and actual == expected, path


def main():
    if not __debug__:
        raise RuntimeError('Run without -O: verification assertions are required.')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--work-dir', type=Path, required=True)
    args = ap.parse_args()
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / 'INPUTS.json').read_text(encoding='utf-8'))
    expected = json.loads((here / 'checks.json').read_text(encoding='utf-8'))
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=False)
    git = ['git', '-C', str(args.repo.resolve())]
    verified = []
    for item in manifest['inputs']:
        data = subprocess.check_output(git + ['show', item['revision'] + ':' + item['path']], timeout=120)
        assert len(data) == item['bytes'], item['path']
        assert hashlib.sha256(data).hexdigest() == item['sha256'], item['path']
        target = work / item['target']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        verified.append(item)
    proc = subprocess.run([sys.executable, '-B', str(here / 'check_review.py'), '--work-dir', str(work)],
                          capture_output=True, timeout=60)
    (work / 'checker.stdout.txt').write_bytes(proc.stdout)
    (work / 'checker.stderr.txt').write_bytes(proc.stderr)
    if proc.returncode:
        raise RuntimeError(f'Checker exited {proc.returncode}; see {work}')
    actual = json.loads((work / 'checks.json').read_text(encoding='utf-8'))
    actual['core_diff_paths'] = subprocess.check_output(
        git + ['diff', '--name-only', manifest['base'], manifest['reviewed_head'], '--', 'slam_recovery/', 'tests/'],
        timeout=60).decode('utf-8').splitlines()
    actual['independent_scope'] = (
        'AST-extracted current pure functions and current pose-join statements; archived trace/JSON arithmetic. '
        'No archived CLI, native execution, full bag readback or full availability join.')
    (work / 'checks.json').write_text(json.dumps(actual, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    compare(actual, expected)
    receipt = dict(at_utc=datetime.now(timezone.utc).isoformat(), result='PASS',
                   python=platform.python_version(), numpy=importlib.metadata.version('numpy'),
                   input_files=len(verified), input_bytes=sum(x['bytes'] for x in verified),
                   verified_inputs=verified, float_relative_tolerance=1e-10, float_absolute_tolerance=1e-10,
                   matches_original_review=True, core_diff_paths=actual['core_diff_paths'],
                   native_build_run_replay_performed=False, full_availability_rejoin=False, bag_reread=False)
    (work / 'reproduction_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'verified_inputs'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
