"""Exact Pareto DP for a static pipeline startup/throughput proxy.

This constructor does no official evaluation or online candidate selection.
The proxy is not an official Makespan bound.
"""
from __future__ import annotations

from .construct import ROOT, UnsupportedStructure, derive_multicore_plan
from .shared_pipeline import _stage_structure
from .shared_pipeline_capacity import interval_shared_bytes, official_l1_capacity
from evaluation_validation import read_bandwidth_config


# Resource guards reject the entire construction. They never truncate a frontier.
MAX_STORED_STATES = 250_000
MAX_TRANSITIONS = 5_000_000


def partition(weights, position_tensors, sizes, capacity, k, jobs, bandwidth):
    """Exactly minimize sum(max(b*C, B)) + b*(jobs-1)*max(C).

    C is segment compute, B is its distinct common-input bytes, b is official
    DDR bytes/cycle. All arithmetic is integral in bandwidth-scaled units.
    Returns (cuts, objective, compute_by_stage, bytes_by_stage, DP diagnostics).
    """
    n = len(weights)
    if (not n or any(type(w) is not int or w <= 0 for w in weights)
            or len(position_tensors) != n
            or any(type(v) is not int or v <= 0 for v in (capacity, k, jobs, bandwidth))
            or k > n):
        raise ValueError("positive integer weights, capacities, stages, jobs and bandwidth required")
    if any(t not in sizes or type(sizes[t]) is not int or sizes[t] < 0
           for ts in position_tensors for t in ts):
        raise ValueError("shared tensor sizes must be nonnegative integers")
    if n > 512:
        raise UnsupportedStructure("more than 512 positions")
    segment_bytes = interval_shared_bytes(position_tensors, sizes)
    prefix = [0]
    for weight in weights:
        prefix.append(prefix[-1] + weight)

    # State=(A, h, cuts). At a fixed (stage,end), lower A and h can never
    # become worse under a common future segment: both updates are monotone.
    # Equal (A,h) retains lexicographically smallest cuts for determinism.
    dp = [[[] for _ in range(n + 1)] for _ in range(k + 1)]
    dp[0][0] = [(0, 0, (0,))]
    total_states = 1
    transitions = 0
    peak_frontier = 1
    for stage in range(1, k + 1):
        for end in range(stage, n + 1):
            candidates = []
            for start in range(stage - 1, end):
                if segment_bytes[start][end] > capacity:
                    continue
                previous = dp[stage - 1][start]
                transitions += len(previous)
                if transitions > MAX_TRANSITIONS:
                    raise UnsupportedStructure("Pareto DP transition resource guard")
                compute = prefix[end] - prefix[start]
                cost = max(bandwidth * compute, segment_bytes[start][end])
                candidates.extend((A + cost, max(h, compute), cuts + (end,))
                                  for A, h, cuts in previous)
            # Increasing h, then A. A state survives iff A is strictly less
            # than every state with no larger h: exact two-dimensional Pareto.
            candidates.sort(key=lambda state: (state[1], state[0], state[2]))
            best_A = None
            frontier = []
            for state in candidates:
                if best_A is None or state[0] < best_A:
                    frontier.append(state)
                    best_A = state[0]
            dp[stage][end] = frontier
            total_states += len(frontier)
            peak_frontier = max(peak_frontier, len(frontier))
            if total_states > MAX_STORED_STATES:
                raise UnsupportedStructure("Pareto DP state resource guard")
    if not dp[k][n]:
        raise UnsupportedStructure("no capacity-feasible contiguous partition")
    A, h, cuts = min(dp[k][n], key=lambda state: (
        state[0] + bandwidth * (jobs - 1) * state[1],
        state[0], state[1], state[2]))
    computes = [prefix[right] - prefix[left]
                for left, right in zip(cuts, cuts[1:])]
    byte_counts = [segment_bytes[left][right]
                   for left, right in zip(cuts, cuts[1:])]
    diagnostics = {"states_stored": total_states, "transitions": transitions,
                   "peak_frontier": peak_frontier, "final_frontier": len(dp[k][n])}
    return list(cuts), A + bandwidth * (jobs - 1) * h, computes, byte_counts, diagnostics


def construct(index, cores):
    """Build one original-graph singleton plan with shared position cuts."""
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("official requested cores must be 1..5")
    common, _producers, consumers, sizes = _stage_structure(index)
    jobs = index.components
    positions = len(jobs[0])
    if positions > 512 or len(jobs) < cores:
        raise UnsupportedStructure("requires at most 512 positions and jobs >= cores")
    tensors = {tensor["id"]: tensor for tensor in index.graph["tensors"]}
    if any(tensors[t].get("pos") != "L1" for t in common):
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
    bandwidth = read_bandwidth_config(ROOT / "data/raw/a/official/data/config.txt")
    cuts, objective, computes, byte_counts, diagnostics = partition(
        weights, position_tensors, sizes, capacity, stages, len(jobs), bandwidth)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[mapping[str(u)] for job in jobs for u in job[left:right]]
                 for left, right in zip(cuts, cuts[1:])]
    schedules.extend([] for _ in range(cores - stages))
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    derive_multicore_plan(index.graph, plan)
    return plan, {
        "guard": True, "selected": "pipeline_startup_proxy",
        "requested_cores": cores, "active_cores": stages,
        "jobs": len(jobs), "positions": positions, "cuts": cuts,
        "stage_compute_cycles": computes,
        "shared_input_bytes_by_stage": byte_counts,
        "shared_input_capacity_bytes": capacity,
        "ddr_bandwidth_bytes_per_cycle": bandwidth,
        "proxy_scaled_objective": objective,
        "proxy_definition": "sum(max(b*C,B))+b*(jobs-1)*max(C); heuristic, not official bound",
        "pareto_dp": diagnostics,
    }
