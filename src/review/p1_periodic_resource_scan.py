"""Finite periodic resource-bound diagnostic; no Task/model/evaluator calls.

This compares a restricted pattern family, not compiled plans or makespans.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.review.p1_packet_edge_bound import Resources
from src.review.p1_packet_seed import choose_return_seed

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT = ROOT / "results/a/p1-two-task-bound-20260925/structural-audit.json"


def _value(form, q, s):
    return form[0] * q + form[1] * s + form[2]


def periodic_cost(resources: Resources, B: int, q: int, s: int):
    """Sum only each edge's lower resource max; add one terminal max."""
    if type(B) is not int or B < 1 or B != min(resources.counts):
        raise ValueError("B must equal positive min(counts)")
    if any(type(x) is not int for x in (q, s)) or not 1 <= q <= B or not 0 <= s <= q:
        raise ValueError("invalid periodic q,s")
    n = r = total = normals = 0
    segments = [(q, s)] * (B // q)
    remainder = B % q
    if remainder:
        segments.append((remainder, min(s, remainder)))
    for width, cut in segments:
        edge, _ = resources.forms(n, r, positive_s=cut > 0)
        total += max(_value(form, width, cut) for form in edge)
        if normals:
            total += resources.gate
        normals += 1
        n += width
        r = cut
    assert n == B
    largest = max(resources.counts) - B
    remainder_total = sum(resources.counts) - len(resources.counts) * B
    terminal = max(largest * (resources.a + resources.c) + r * resources.c,
                   largest * resources.b,
                   remainder_total * resources.d_whole +
                   len(resources.counts) * r * resources.d_return)
    total += terminal
    terminal_nonempty = bool(r or largest)
    if terminal_nonempty:
        total += resources.gate
    return dict(q=q, s=s, resource_lower=total, normal_count=normals,
                pending=r, terminal_resource=terminal,
                terminal_gate=resources.gate if terminal_nonempty else 0)


def scan(resources: Resources):
    B = min(resources.counts)
    if B < 1:
        return dict(B=B, top_five=[], s0_comparison=[],
                    scope="B=0: no normal periodic candidate")
    rows = [periodic_cost(resources, B, q, s)
            for q in range(1, B + 1) for s in range(q + 1)]
    ranked = sorted(rows, key=lambda row: (row["resource_lower"], row["q"], row["s"]))
    seed = choose_return_seed(resources, B)
    return dict(B=B, top_five=ranked[:5],
                s0_comparison=[row for row in rows if row["s"] == 0],
                two_stage_seed_s=seed["s"],
                two_stage_seed_resource_lower=seed["resource_lower"],
                qB_seed_with_terminal=periodic_cost(resources, B, B, seed["s"]),
                candidate_count=len(rows),
                scope="Restricted periodic integer resource lower bounds; not Task feasibility, actual makespan, solver optimum, or E0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    audit = json.loads(args.audit.read_text())
    rows = []
    for entry in audit["rows"]:
        resources = Resources(**entry["resources"], gate=entry["gate"])
        rows.append(dict(case_id=entry["case_id"], cores=entry["cores"],
                         graph_sha256=entry["graph_sha256"], diagnostic=scan(resources)))
    result = dict(kind="pure-periodic-resource-scan-NOT-E0", rows=rows,
                  calls=dict(candidate_constructor=0, Task_compile=0,
                             Fraction_response=0, E0=0, E1=0, E2=0))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
