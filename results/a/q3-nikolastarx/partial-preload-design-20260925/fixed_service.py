"""Exact single-stage, fixed-service partial-preload model; no official calls.

This is a mathematical selector, not a P3 solver or evaluator. The caller must
derive feasible prefix counts from actual consumer/subgraph boundaries and then
check the generated official Task word separately.
"""
from __future__ import annotations


def select_prefix(read_cycles, first_use_compute, release, gate_cycles,
                  total_compute, feasible_prefixes):
    """Return (chosen_q, T_by_q) in O(m + number_of_feasible_prefixes).

    ``read_cycles[r-1]`` is fixed service for cold read r (1-based).
    ``first_use_compute[r-1]`` is chain compute before its first use.
    ``release`` is the activation's fixed release time. All times are cycles.
    Ties choose the larger q to reduce activation-head waiting.
    """
    m = len(read_cycles)
    if (m != len(first_use_compute) or not isinstance(release, int)
            or not isinstance(gate_cycles, int) or not isinstance(total_compute, int)
            or min(release, gate_cycles, total_compute) < 0
            or any(not isinstance(x, int) or x <= 0 for x in read_cycles)
            or any(not isinstance(x, int) or not 0 <= x <= total_compute
                   for x in first_use_compute)
            or any(a > b for a, b in zip(first_use_compute,
                                        first_use_compute[1:]))):
        raise ValueError("invalid fixed-service chain data")
    supplied = list(feasible_prefixes)
    if not supplied or any(type(q) is not int or not 0 <= q <= m
                           for q in supplied):
        raise ValueError("feasible prefix counts must be in [0, m]")
    allowed = set(supplied)
    feasible = [q for q in range(m + 1) if q in allowed]
    U = [0]
    for cycles in read_cycles:
        U.append(U[-1] + cycles)
    # suffix[q] = max_{r>q} (U_r - P_r); no tail when q == m.
    suffix = [None] * (m + 1)
    for q in range(m - 1, -1, -1):
        value = U[q + 1] - first_use_compute[q]
        suffix[q] = value if suffix[q + 1] is None else max(value, suffix[q + 1])
    times = {}
    for q in feasible:
        tail_stall = 0 if suffix[q] is None else max(0, suffix[q] - U[q])
        times[q] = max(release, U[q]) + gate_cycles + total_compute + tail_stall
    chosen = min(feasible, key=lambda q: (times[q], -q))
    return chosen, times


if __name__ == "__main__":
    # Same graph/service, two activation release times: partial wins, then loses.
    assert select_prefix([1, 8], [0, 2], 1, 1, 3, [1, 2]) == (
        1, {1: 11, 2: 13})
    assert select_prefix([1, 8], [0, 2], 10, 1, 3, [1, 2]) == (
        2, {1: 20, 2: 14})
    print("fixed-service microexamples passed")
