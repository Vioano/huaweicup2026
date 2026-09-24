"""Guarded adaptation of Fang's published contiguous pipeline-stage DP.

Source: 6bae8dfa317bc71226068344b59dd65d2612c32b,
src/q3_yuanzhifang/{active_stages,pipeline_stages}.py. No scoring or fallback.
"""
from __future__ import annotations

from .construct import UnsupportedStructure, derive_multicore_plan
from multicore_cut_evaluate_problem_1 import _original_tensor_views


def partition(weights, stages):
    """Minimum maximum contiguous segment sum; Fang tie rule, O(stages*n²)."""
    n = len(weights)
    if not n or any(w <= 0 for w in weights) or not 1 <= stages <= n:
        raise ValueError("positive weights and 1 <= stages <= len(weights) required")
    prefix = [0]
    for weight in weights:
        prefix.append(prefix[-1] + weight)
    infinity = float("inf")
    dp = [[infinity] * (n + 1) for _ in range(stages + 1)]
    parent = [[None] * (n + 1) for _ in range(stages + 1)]
    dp[0][0] = 0
    for stage in range(1, stages + 1):
        for end in range(stage, n + 1):
            value, start = min(
                (max(dp[stage - 1][start], prefix[end] - prefix[start]), start)
                for start in range(stage - 1, end)
            )
            dp[stage][end], parent[stage][end] = value, start
    cuts, end = [n], n
    for stage in range(stages, 0, -1):
        end = parent[stage][end]
        cuts.append(end)
    cuts.reverse()
    return cuts, dp[stages][n]


def _stage_structure(index):
    jobs = index.components
    if not jobs or not all(
        all(v in index.succ[u] for u, v in zip(job, job[1:])) for job in jobs
    ):
        raise UnsupportedStructure("requires nonempty Hamiltonian topological chains")

    producers, consumers, _ = _original_tensor_views(index.graph)
    sizes = {tensor["id"]: tensor["size"] for tensor in index.graph["tensors"]}
    eligible = set(index.ops)
    inputs = [set() for _ in jobs]
    owner = {u: j for j, job in enumerate(jobs) for u in job}
    for tensor, readers in consumers.items():
        if not any(u in eligible for u in producers[tensor]):
            for u in readers:
                if u in owner:
                    inputs[owner[u]].add(tensor)
    common = set.intersection(*inputs)
    if not common:
        raise UnsupportedStructure("requires shared external input in every job")
    if any(t not in sizes or sizes[t] < 0 for t in common):
        raise UnsupportedStructure("shared tensor sizes unavailable")

    by_op = {u: [] for u in eligible}
    for tensor in sorted(common):
        for u in consumers[tensor]:
            if u in by_op:
                by_op[u].append(tensor)
    signatures = [tuple(
        (index.ops[u]["pipe"], index.duration(u), tuple(by_op[u])) for u in job
    ) for job in jobs]
    if len(set(signatures)) != 1:
        raise UnsupportedStructure("requires identical pipe, duration and common-input consumers")
    return common, producers, consumers, sizes


def construct(index, cores):
    """Return a singleton-subgraph plan or raise UnsupportedStructure."""
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("official requested cores must be 1..5")
    common, producers, consumers, sizes = _stage_structure(index)
    jobs = index.components
    positions = len(jobs[0])
    if positions > 512 or len(jobs) < cores:
        raise UnsupportedStructure("requires at most 512 positions and jobs >= cores")
    stages = min(cores, positions)
    weights = [index.duration(u) for u in jobs[0]]
    cuts, bottleneck = partition(weights, stages)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[mapping[str(u)] for job in jobs for u in job[left:right]]
                 for left, right in zip(cuts, cuts[1:])]
    schedules.extend([] for _ in range(cores - stages))
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    derive_multicore_plan(index.graph, plan)

    core_by_op = {job[pos]: c for job in jobs for c in range(stages)
                  for pos in range(cuts[c], cuts[c + 1])}
    shared_bytes = [sum(sizes[t] for t in common
                        if any(core_by_op.get(u) == c for u in consumers[t]))
                    for c in range(stages)]
    cross_nets = [(t, p, c) for t, readers in consumers.items()
                  for p in {core_by_op[u] for u in producers[t] if u in core_by_op}
                  for c in {core_by_op[u] for u in readers if u in core_by_op}
                  if p != c]
    if any(t not in sizes for t, _, _ in cross_nets):
        raise UnsupportedStructure("crossing tensor sizes unavailable")
    return plan, {
        "guard": True, "selected": "pipeline_stages", "requested_cores": cores,
        "active_cores": stages, "jobs": len(jobs), "positions": positions,
        "cuts": cuts, "stage_compute_cycles": [sum(weights[l:r]) for l, r in zip(cuts, cuts[1:])],
        "bottleneck_cycles": bottleneck,
        "ideal_flowshop_cycles": sum(weights) + (len(jobs) - 1) * bottleneck,
        "shared_input_bytes_by_stage": shared_bytes,
        "crossing_tensor_net_copies": len(cross_nets),
        "crossing_tensor_net_bytes": sum(sizes[t] for t, _, _ in cross_nets),
        "assumption": "copy-free serial-server flowshop; not an E0 lower or upper bound",
    }
