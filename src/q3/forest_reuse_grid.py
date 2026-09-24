"""Recognize Cartesian external-input reuse and balance whole-tree ownership.

One deterministic proposal compares the two axis traversals using mandatory
per-core input COPY bytes. This proxy ignores reloads, Cache hits, and latency.
"""
from collections import defaultdict, deque

from .construct import UnsupportedStructure, derive_multicore_plan
from .forest_memory_order import construct as memory_order
from multicore_cut_evaluate_problem_1 import _original_tensor_views


def recognize(index):
    owner = {u: j for j, component in enumerate(index.components) for u in component}
    producers, consumers, _ = _original_tensor_views(index.graph)
    sizes = {t["id"]: t["size"] for t in index.graph["tensors"]}
    groups = defaultdict(list)
    for tid, readers in consumers.items():
        selected = readers & index.ops.keys()
        if selected and not (producers[tid] & index.ops.keys()):
            mask = tuple(sorted({owner[u] for u in selected}))
            if len(mask) < 2 or sizes[tid] <= 0:
                raise UnsupportedStructure("all external inputs must be reused across components")
            groups[mask].append(tid)
    masks = sorted(groups)
    if len(masks) < 4:
        raise UnsupportedStructure("requires two nontrivial input-group axes")
    memberships = defaultdict(list)
    for i, mask in enumerate(masks):
        for j in mask:
            memberships[j].append(i)
    if set(memberships) != set(range(len(index.components))) or any(
            len(value) != 2 for value in memberships.values()):
        raise UnsupportedStructure("each component must read exactly two external-input groups")
    adjacent = [set() for _ in masks]
    pairs = set()
    for a, b in memberships.values():
        if (a, b) in pairs:
            raise UnsupportedStructure("input groups intersect in more than one component")
        pairs.add((a, b))
        adjacent[a].add(b)
        adjacent[b].add(a)
    color = {0: 0}
    queue = deque([0])
    while queue:
        u = queue.popleft()
        for v in sorted(adjacent[u]):
            if v in color and color[v] == color[u]:
                raise UnsupportedStructure("input-group overlap is not bipartite")
            if v not in color:
                color[v] = 1 - color[u]
                queue.append(v)
    if len(color) != len(masks):
        raise UnsupportedStructure("input-group overlap is disconnected")
    axes = [[i for i in range(len(masks)) if color[i] == c] for c in range(2)]
    if min(map(len, axes)) < 2 or len(axes[0]) * len(axes[1]) != len(index.components):
        raise UnsupportedStructure("input groups do not form a complete Cartesian grid")
    pipes = sorted({op["pipe"] for op in index.ops.values()})
    loads = [tuple(sum(index.duration(u) for u in component if index.ops[u]["pipe"] == pipe)
                   for pipe in pipes) for component in index.components]
    if len(set(loads)) != 1:
        raise UnsupportedStructure("requires identical per-pipe compute work per component")
    cells = {}
    for j, (a, b) in memberships.items():
        cells[(a, b) if color[a] == 0 else (b, a)] = j
    group_bytes = [sum(sizes[tid] for tid in groups[mask]) for mask in masks]
    return {"axes": axes, "cells": cells, "memberships": memberships,
            "group_bytes": group_bytes, "group_tensor_ids": [sorted(groups[m]) for m in masks],
            "component_pipe_work": dict(zip(pipes, loads[0]))}


def input_copy_floor(model, assignment):
    return [sum(model["group_bytes"][group] for group in
                {g for component in components for g in model["memberships"][component]})
            for components in assignment]


def balanced_slices(order, cores):
    q, r = divmod(len(order), cores)
    groups, cursor = [], 0
    for core in range(cores):
        size = q + (core < r)
        groups.append(order[cursor:cursor + size])
        cursor += size
    return groups


def construct(index, cores):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("official requested cores must be 1..5")
    model = recognize(index)
    _, tree_metadata = memory_order(index, cores)  # Also checks the raw-tree guard.
    postorder = {tree["min_op_id"]: tree["dfs_postorder"]
                 for tree in tree_metadata["predicted_frontier"]}
    candidates = []
    for axis in (0, 1):
        outer, inner = model["axes"][axis], model["axes"][1 - axis]
        order = [model["cells"][(a, b) if axis == 0 else (b, a)]
                 for a in outer for b in inner]
        assignment = balanced_slices(order, cores)
        floor = input_copy_floor(model, assignment)
        candidates.append(((sum(floor), max(floor), axis), assignment, floor))
    key, assignment, floor = min(candidates, key=lambda item: item[0])
    baseline_floor = input_copy_floor(model, index.assignment(cores))
    if sum(floor) >= sum(baseline_floor):
        raise UnsupportedStructure("axis partition does not reduce mandatory input COPY bytes")
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[mapping[str(u)] for j in jobs
                  for u in postorder[min(index.components[j])]] for jobs in assignment]
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    derive_multicore_plan(index.graph, plan)
    return plan, {"strategy": "forest_reuse_grid", "axis_sizes": list(map(len, model["axes"])),
                  "selected_axis": key[2], "components_by_core": assignment,
                  "component_pipe_work": model["component_pipe_work"],
                  "input_copy_floor_bytes_by_core": floor,
                  "old_input_copy_floor_bytes_by_core": baseline_floor,
                  "input_group_bytes": model["group_bytes"],
                  "proxy_scope": "mandatory input COPY bytes for this ownership, not physical DDR traffic, total bytes or Makespan; L1 reloads and L2 sharing ignored",
                  "selection": "compare two axis traversals algebraically; no evaluator or parameter sweep",
                  "tree_order": "original-tree DFS frontier order; no operation rewriting"}
