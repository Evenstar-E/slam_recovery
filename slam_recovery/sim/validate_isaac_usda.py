"""Offline structural validation of the exported `hall_01_isaac_scene.usda`.

A malformed USD simply refuses to open in Isaac Sim with a terse error, so we check the things that
actually break: unbalanced delimiters, dangling material bindings, non-finite coordinates, and
out-of-range triangle indices. This does not replace opening the stage in Isaac Sim 5.1; it removes
the failure modes that would otherwise be debugged blind on the other machine.

Run: python slam_recovery/sim/validate_isaac_usda.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

OUT_DIR = Path(r"D:\REPAIR\isaac_sim_hall_01")
USDA = OUT_DIR / "hall_01_isaac_scene.usda"


def strip_strings(text: str) -> str:
    """Remove quoted string contents so delimiters inside customLayerData do not count."""
    return re.sub(r'"[^"\n]*"', '""', text)


def check_delimiters(raw: str) -> list[str]:
    text = strip_strings(raw)
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[tuple[str, int]] = []
    problems: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for ch in line:
            if ch in pairs:
                stack.append((ch, lineno))
            elif ch in pairs.values():
                if not stack:
                    problems.append(f"line {lineno}: unmatched closing '{ch}'")
                    continue
                opener, oline = stack.pop()
                if pairs[opener] != ch:
                    problems.append(
                        f"line {lineno}: '{ch}' closes '{opener}' opened at line {oline}"
                    )
    for opener, oline in stack:
        problems.append(f"line {oline}: unclosed '{opener}'")
    return problems


def parse_float_triples(block: str) -> list[tuple[float, float, float]]:
    return [
        (float(a), float(b), float(c))
        for a, b, c in re.findall(
            r"\((-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?),\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?),\s*"
            r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\)",
            block,
        )
    ]


def main() -> int:
    if not USDA.exists():
        print(f"FAIL: {USDA} not found")
        return 1
    raw = USDA.read_text(encoding="utf-8")
    report: dict[str, object] = {"file": str(USDA), "bytes": len(raw.encode("utf-8"))}

    problems = check_delimiters(raw)
    report["delimiters_ok"] = not problems
    report["delimiter_problems"] = problems[:10]

    # Material bindings must resolve to a declared Material prim.
    declared = set(re.findall(r'def Material "([A-Za-z0-9_]+)"', raw))
    bound = set(re.findall(r"rel material:binding = </World/Looks/([A-Za-z0-9_]+)>", raw))
    dangling = sorted(bound - declared)
    report["materials_declared"] = sorted(declared)
    report["materials_bound"] = sorted(bound)
    report["dangling_material_bindings"] = dangling

    # Every Mesh: finite points, indices in range, counts consistent.
    mesh_issues: list[str] = []
    mesh_summary: list[dict[str, object]] = []
    for m in re.finditer(r'def Mesh "([A-Za-z0-9_]+)"', raw):
        name = m.group(1)
        tail = raw[m.end() :]
        header = tail[: tail.find("{")] if "{" in tail else tail[:200]
        is_collider = "PhysicsMeshCollisionAPI" in header
        pts_m = re.search(r"point3f\[\] points = \[(.*?)\]\n", tail, re.S)
        idx_m = re.search(r"int\[\] faceVertexIndices = \[(.*?)\]\n", tail, re.S)
        cnt_m = re.search(r"int\[\] faceVertexCounts = \[(.*?)\]\n", tail, re.S)
        if not (pts_m and idx_m and cnt_m):
            mesh_issues.append(f"{name}: missing points/indices/counts")
            continue
        pts = parse_float_triples(pts_m.group(1))
        idx = [int(v) for v in re.findall(r"-?\d+", idx_m.group(1))]
        counts = [int(v) for v in re.findall(r"-?\d+", cnt_m.group(1))]
        bad_finite = sum(1 for p in pts if not all(abs(c) < 1e6 for c in p))
        bad_range = sum(1 for i in idx if i < 0 or i >= len(pts))
        tri_len_ok = len(idx) == 3 * len(counts)
        if bad_finite or bad_range or not tri_len_ok:
            mesh_issues.append(
                f"{name}: finite_bad={bad_finite} index_bad={bad_range} "
                f"idx={len(idx)} counts={len(counts)}"
            )
        mesh_summary.append(
            {
                "name": name,
                "vertices": len(pts),
                "triangles": len(counts),
                "collider": is_collider,
            }
        )
    report["mesh_issues"] = mesh_issues
    report["meshes"] = mesh_summary
    report["collider_meshes"] = [m["name"] for m in mesh_summary if m["collider"]]

    # Animation completeness for the four robot avatars.
    robots = re.findall(r'def Xform "(Robot_[A-Za-z0-9_]+)"', raw)
    anim = {}
    for r in robots:
        seg = raw.split(f'def Xform "{r}"', 1)[1][:6000]
        n_tr = len(re.findall(r"^\s+\d+: \(", seg, re.M))
        anim[r] = n_tr
    report["robots"] = anim

    report["has_physics_scene"] = "PhysicsScene" in raw
    report["has_collider"] = "PhysicsMeshCollisionAPI" in raw
    report["has_basis_curves"] = "def BasisCurves" in raw
    report["ok"] = (
        not problems
        and not dangling
        and not mesh_issues
        and report["has_physics_scene"]
        and report["has_collider"]
        and all(v >= 100 for v in anim.values())
    )

    print(json.dumps(report, indent=2))
    (OUT_DIR / "hall_01_usda_validation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("\nVALIDATION:", "PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
