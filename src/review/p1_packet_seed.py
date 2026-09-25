"""Pure resource-bound seed for one q=B normal edge and merged terminal.

This orders a possible construction attempt. It is not a compiled feasible
Task, an exact-model incumbent, or an E0/global optimum claim.
"""
from __future__ import annotations

from fractions import Fraction

from src.review.p1_packet_edge_bound import Resources


def choose_return_seed(resources: Resources, B: int):
    if not isinstance(resources, Resources):
        raise TypeError("Resources required")
    if type(B) is not int or B < 0 or B != min(resources.counts):
        raise ValueError("B must equal the minimum per-core chain count")
    scope = "conditional resource lower bound only; try first, then compile and validate"
    if B == 0:
        return dict(s=None, resource_lower=None, path=(),
                    why="B=0 has no normal edge", scope=scope)

    positive_witness = None
    candidates = {0}
    if B >= 1:
        positive = resources.box(0, 0, (B, B, 1, B))
        positive_witness = Fraction(positive["witness"][1])
        lo = positive_witness.numerator // positive_witness.denominator
        hi = -(-positive_witness.numerator // positive_witness.denominator)
        candidates.update(s for s in (lo, hi) if 1 <= s <= B)
    evaluated = {s: resources.box(0, 0, (B, B, s, s))["frontier_lower_bound"]
                 for s in sorted(candidates)}
    chosen = min(evaluated, key=lambda s: (evaluated[s], s))
    return dict(s=chosen, resource_lower=evaluated[chosen],
                path=(("normal", (0, 0), (B, chosen)),
                      ("terminal", (B, chosen), "merge")),
                why={"method": "compare s=0 and floor/ceil of convex positive-s real witness",
                     "positive_real_witness_s": str(positive_witness),
                     "tested_s_resource_lowers": evaluated,
                     "tie_break": "smallest s"},
                scope=scope)
