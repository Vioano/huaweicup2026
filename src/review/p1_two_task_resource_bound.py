"""Exact integer optimum of a restricted W-first P two-task resource relaxation.

This is a compute/DDR lower-bound model only. It does not validate a graph,
construct Tasks, or certify an official E0 Makespan.
"""
from __future__ import annotations


def _integer(value: int, name: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def solve(counts: list[int] | tuple[int, ...], *, a: int, b: int, c: int,
          d_prefix: int, d_return: int, d_whole: int, gate: int = 0) -> dict:
    """Minimize max(compute bounds, DDR bound) over integer 0 <= x_i <= N_i.

    ``x_i`` is the number of W-first P cuts assigned to core i. The x=0
    branch is deliberately separate: a positive gate can make x=1 worse.
    """
    if not isinstance(counts, (list, tuple)):
        raise ValueError("counts must be a sequence")
    for i, n in enumerate(counts):
        _integer(n, f"counts[{i}]")
    for name, value in (("a", a), ("b", b), ("c", c)):
        _integer(value, name, 1)
    if b < a:
        raise ValueError("b must be >= a")
    for name, value in (("d_prefix", d_prefix), ("d_return", d_return),
                        ("d_whole", d_whole), ("gate", gate)):
        _integer(value, name)
    delta = d_prefix + d_return - d_whole
    if delta < 0:
        raise ValueError("delta must be nonnegative")
    width = a + b + c
    total = sum(counts)

    def cuts_at(threshold: int) -> tuple[int, ...] | None:
        if threshold < 0:
            return None
        cuts = []
        for n in counts:
            base = n * width
            if threshold >= base:
                x = 0
            else:
                # For x >= 1: base - a*(x-1) + gate <= threshold.
                x = (base + a + gate - threshold + a - 1) // a
            if x > n:
                return None
            cuts.append(x)
        answer = tuple(cuts)
        return answer if total * d_whole + delta * sum(answer) <= threshold else None

    low, high = 0, max((max(counts, default=0) * width), total * d_whole)
    while low < high:
        mid = (low + high) // 2
        if cuts_at(mid) is None:
            low = mid + 1
        else:
            high = mid
    chosen = cuts_at(low)
    assert chosen is not None and cuts_at(low - 1) is None
    return {"objective": low, "cuts": list(chosen), "feasible_T": low,
            "infeasible_T_minus_1": low - 1, "delta": delta,
            "scope": "restricted integer compute/DDR resource relaxation; not an E0 certificate"}
