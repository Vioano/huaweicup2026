"""Static, L1-capacity-constrained contiguous pipeline construction.

This prototype does no scoring or fallback and does not modify the graph.
"""
from __future__ import annotations

from .construct import ROOT, UnsupportedStructure, derive_multicore_plan
from .shared_pipeline import _stage_structure


def official_l1_capacity():
    """Read the frozen official L1 capacity rather than embedding a case constant."""
    path = ROOT / "data/raw/a/official/data/config.txt"
    section = None
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        fields = line.split()
        if section == "capacity" and len(fields) == 2 and fields[0] == "L1":
            value = int(fields[1])
            if value <= 0:
                raise ValueError("official L1 capacity must be positive")
            return value
    raise ValueError(f"official L1 capacity unavailable: {path}")


def interval_shared_bytes(position_tensors, sizes):
    """Exact distinct shared-input bytes for each half-open position interval."""
    n = len(position_tensors)
    result = [[0] * (n + 1) for _ in range(n + 1)]
    for left in range(n):
        seen = set()
        total = 0
        for right in range(left + 1, n + 1):
            for tensor in position_tensors[right - 1]:
                if tensor not in seen:
                    seen.add(tensor)
                    total += sizes[tensor]
            result[left][right] = total
    return result


def partition(weights, position_tensors, sizes, capacity, stages):
    """Minimize maximum compute segment sum among exactly stages feasible segments.

    Equal objective values use the smallest preceding cut, as in Fang's DP.
    Returns (cuts, bottleneck, shared bytes by segment); infeasibility is explicit.
    """
    n = len(weights)
    if (not n or any(type(w) is not int or w <= 0 for w in weights)
            or len(position_tensors) != n or type(capacity) is not int or capacity <= 0
            or type(stages) is not int or not 1 <= stages <= n):
        raise ValueError("positive integer weights/capacity and valid stages required")
    if any(t not in sizes or type(sizes[t]) is not int or sizes[t] < 0
           for ts in position_tensors for t in ts):
        raise ValueError("shared tensor sizes must be nonnegative integers")
    bytes_by_interval = interval_shared_bytes(position_tensors, sizes)
    prefix = [0]
    for weight in weights:
        prefix.append(prefix[-1] + weight)
    infinity = float("inf")
    dp = [[infinity] * (n + 1) for _ in range(stages + 1)]
    parent = [[None] * (n + 1) for _ in range(stages + 1)]
    dp[0][0] = 0
    for stage in range(1, stages + 1):
        for end in range(stage, n + 1):
            best = (infinity, None)
            for start in range(stage - 1, end):
                if dp[stage - 1][start] == infinity:
                    continue
                if bytes_by_interval[start][end] > capacity:
                    continue
                candidate = (max(dp[stage - 1][start], prefix[end] - prefix[start]), start)
                if candidate[0] < best[0] or (candidate[0] == best[0]
                                              and (best[1] is None or start < best[1])):
                    best = candidate
            dp[stage][end], parent[stage][end] = best
    if parent[stages][n] is None:
        raise UnsupportedStructure("no capacity-feasible contiguous partition")
    cuts = [n]
    end = n
    for stage in range(stages, 0, -1):
        end = parent[stage][end]
        cuts.append(end)
    cuts.reverse()
    return (cuts, dp[stages][n],
            [bytes_by_interval[left][right] for left, right in zip(cuts, cuts[1:])])


def construct(index, cores):
    """Return original-graph singleton plan and static metadata, or reject."""
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("official requested cores must be 1..5")
    common, _producers, consumers, sizes = _stage_structure(index)
    jobs = index.components
    positions = len(jobs[0])
    if positions > 512 or len(jobs) < cores:
        raise UnsupportedStructure("requires at most 512 positions and jobs >= cores")
    tensor_by_id = {t["id"]: t for t in index.graph["tensors"]}
    if any(tensor_by_id[t].get("pos") != "L1" for t in common):
        raise UnsupportedStructure("requires all common external inputs in L1")
    first_job = jobs[0]
    readers_by_op = {u: set() for u in first_job}
    for tensor in common:
        for u in consumers[tensor]:
            if u in readers_by_op:
                readers_by_op[u].add(tensor)
    position_tensors = [readers_by_op[u] for u in first_job]
    weights = [index.duration(u) for u in first_job]
    stages = min(cores, positions)
    capacity = official_l1_capacity()
    cuts, bottleneck, shared_bytes = partition(
        weights, position_tensors, sizes, capacity, stages)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[mapping[str(u)] for job in jobs for u in job[left:right]]
                 for left, right in zip(cuts, cuts[1:])]
    schedules.extend([] for _ in range(cores - stages))
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    derive_multicore_plan(index.graph, plan)
    return plan, {
        "guard": True, "selected": "pipeline_l1_capacity", "requested_cores": cores,
        "active_cores": stages, "jobs": len(jobs), "positions": positions,
        "cuts": cuts,
        "stage_compute_cycles": [sum(weights[l:r]) for l, r in zip(cuts, cuts[1:])],
        "bottleneck_cycles": bottleneck,
        "ideal_flowshop_cycles": sum(weights) + (len(jobs) - 1) * bottleneck,
        "shared_input_bytes_by_stage": shared_bytes,
        "shared_input_capacity_bytes": capacity,
        "assumption": "distinct common original L1 inputs only; not a spill or E0 bound",
    }
