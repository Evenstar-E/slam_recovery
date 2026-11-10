#!/usr/bin/env python3
"""Parse `trace_group.csv` and decide what two traces actually establish.

The predicates are declared here, before any host trace exists, so that a later run cannot
choose the reading that suits it:

  - GROUP identical + STATE diverges      -> UNKNOWN: the grouping was the same, so the split
                                             cannot be attributed to group composition (S3/S4).
  - GROUP differs                         -> GROUP_COMPOSITION_VARIES: a candidate, never a cause.
  - STATE identical                       -> NO_DIVERGENCE.
  - a trace that also diverges with tracing OFF -> the divergence is not caused by tracing.

Nothing here claims causality; it only refuses to attribute a split to a mechanism the trace
shows did not vary.
"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

KINDS = ("ARRIVE", "GROUP", "IMUINIT", "STATE")


@dataclass
class Event:
    kind: str
    wall_ns: int
    lid_stamp_ns: Optional[int] = None
    n_items: Optional[int] = None
    first_stamp_ns: Optional[int] = None
    last_stamp_ns: Optional[int] = None
    stamps_sha256: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)

    def xyz(self):
        pos = self.extra.get("pos")
        if not pos:
            return None
        # the writer must not emit commas inside `extra` (they would split the CSV column);
        # accept them anyway so an older trace still parses
        return [float(v) for v in re.split(r"[|,]", pos)]


@dataclass
class Trace:
    path: str
    events: List[Event] = field(default_factory=list)

    def of(self, kind: str) -> List[Event]:
        return [e for e in self.events if e.kind == kind]


def _i(v):
    return None if v in ("", None) else int(v)


def _extra(text: str) -> Dict[str, str]:
    out = {}
    for part in (text or "").split(";"):
        if not part:
            continue
        key, _, val = part.partition("=")
        out[key.strip()] = val.strip()
    return out


def parse(path: str) -> Trace:
    """Read the CSV. Unknown kind or a float time is an error, not a row to skip."""
    out = Trace(path=path)
    with open(path, newline="", encoding="utf-8") as fh:
        for lineno, row in enumerate(csv.DictReader(fh), start=2):
            kind = (row.get("kind") or "").strip()
            if kind not in KINDS:
                raise ValueError(f"{path}:{lineno}: unknown kind {kind!r}")
            for col in ("wall_ns", "lid_stamp_ns", "first_stamp_ns", "last_stamp_ns"):
                v = row.get(col)
                if v not in ("", None) and not str(v).lstrip("-").isdigit():
                    raise ValueError(f"{path}:{lineno}: {col} is not integer nanoseconds: {v!r}")
            if kind in ("GROUP", "IMUINIT") and not (row.get("stamps_sha256") or "").strip():
                raise ValueError(f"{path}:{lineno}: {kind} without stamps_sha256")
            out.events.append(Event(
                kind=kind,
                wall_ns=int(row["wall_ns"]),
                lid_stamp_ns=_i(row.get("lid_stamp_ns")),
                n_items=_i(row.get("n_items")),
                first_stamp_ns=_i(row.get("first_stamp_ns")),
                last_stamp_ns=_i(row.get("last_stamp_ns")),
                stamps_sha256=(row.get("stamps_sha256") or None),
                extra=_extra(row.get("extra")),
            ))
    return out


def group_signature(ev: Event):
    """What makes two groups 'the same group': size, span, exact sample set and its make-up."""
    return (ev.n_items, ev.first_stamp_ns, ev.last_stamp_ns, ev.stamps_sha256,
            ev.extra.get("mesures"), ev.extra.get("img"))


def compare_groups(a: Trace, b: Trace, limit: int = 0):
    ga, gb = a.of("GROUP"), b.of("GROUP")
    n = min(len(ga), len(gb))
    if limit:
        n = min(n, limit)
    diffs = []
    for i in range(n):
        if group_signature(ga[i]) != group_signature(gb[i]):
            diffs.append({"index": i, "a": group_signature(ga[i]), "b": group_signature(gb[i])})
    return {"compared": n, "a_groups": len(ga), "b_groups": len(gb),
            "identical": not diffs and len(ga) == len(gb), "differences": diffs[:20],
            "count_mismatch": len(ga) != len(gb)}


def compare_imuinit(a: Trace, b: Trace):
    ia, ib = a.of("IMUINIT"), b.of("IMUINIT")
    fields = [("n_items", lambda e: e.n_items), ("first_ns", lambda e: e.first_stamp_ns),
              ("last_ns", lambda e: e.last_stamp_ns), ("sha", lambda e: e.stamps_sha256),
              ("iter", lambda e: e.extra.get("iter"))]
    diffs = []
    for i in range(min(len(ia), len(ib))):
        for name, get in fields:
            if get(ia[i]) != get(ib[i]):
                diffs.append({"index": i, "field": name,
                              "a": get(ia[i]), "b": get(ib[i])})
    return {"a_calls": len(ia), "b_calls": len(ib), "differences": diffs[:20],
            "identical": not diffs and len(ia) == len(ib)}


def first_state_divergence(a: Trace, b: Trace, tol_m: float = 1e-3):
    sa, sb = a.of("STATE"), b.of("STATE")
    for i in range(min(len(sa), len(sb))):
        pa, pb = sa[i].xyz(), sb[i].xyz()
        if pa is None or pb is None or len(pa) != len(pb):
            return {"index": i, "stamp_ns": sa[i].lid_stamp_ns,
                    "why": "missing or malformed state"}
        d = max(abs(x - y) for x, y in zip(pa, pb))
        if d > tol_m:
            return {"index": i, "stamp_ns": sa[i].lid_stamp_ns,
                    "max_axis_delta_m": round(d, 6)}
    if len(sa) != len(sb):
        return {"index": min(len(sa), len(sb)), "stamp_ns": None,
                "why": f"trace length differs: {len(sa)} vs {len(sb)}"}
    return None


def judge(a: Trace, b: Trace, control=None, tol_m: float = 1e-3):
    """The declared reading. Returns a verdict plus the evidence that produced it."""
    groups = compare_groups(a, b)
    imu = compare_imuinit(a, b)
    div = first_state_divergence(a, b, tol_m=tol_m)
    control_div = first_state_divergence(*control, tol_m=tol_m) if control else None

    if div is None:
        verdict = "NO_DIVERGENCE"
        why = "the two runs agree on every state sample"
    elif groups["identical"]:
        verdict = "UNKNOWN"
        why = ("groups are identical (count, span, sample sha) yet the states diverge: group "
               "composition cannot be the mechanism, and this trace does not identify one")
    else:
        verdict = "GROUP_COMPOSITION_VARIES"
        why = ("group composition differs between the runs; that is a candidate mechanism, not "
               "a cause -- no causal claim follows from a single pair")
    if control is not None:
        if control_div is not None:
            why += ("; the tracing-off control also diverges, so the divergence is not caused "
                    "by tracing")
        else:
            why += ("; the tracing-off control does not diverge, so tracing itself is a live "
                    "perturbation candidate")
    return {"verdict": verdict, "why": why, "groups": groups, "imuinit": imu,
            "first_divergence": div, "control_divergence": control_div}


def main(argv: List[str]) -> int:
    import json
    import sys
    if len(argv) < 3:
        print("usage: trace_compare.py A.csv B.csv [CONTROL_A.csv CONTROL_B.csv]")
        return 2
    a, b = parse(argv[1]), parse(argv[2])
    control = (parse(argv[3]), parse(argv[4])) if len(argv) >= 5 else None
    print(json.dumps(judge(a, b, control), indent=1, default=str))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
