"""Merge disjoint adjacent Tasks of the frozen shared-input constructor.

Only a merged pair needs the full incident-tensor union capacity certificate.
Unmerged Tasks may spill; their Step1/2 sequence and spill traffic are
invariant under strictly order-preserving boundary COPY ID renaming. This is
not a Step3 or Makespan invariant. No evaluator is used for plan selection.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))

from evaluation_validation import read_capacity_config, validate_graph, validate_task_order  # noqa: E402
from stub_multicore_cut_and_schedule import derive_multicore_plan, _build_op_adjacency  # noqa: E402
from src.q1.shared_input_budget import construct as shared_construct  # noqa: E402

CONFIG = ROOT / "data/raw/a/official/data/config.txt"
COPY = frozenset(("COPY_IN", "COPY_OUT"))


def _copy_bridge(graph: dict) -> bool:
    """Detect a compute -> excluded COPY(+) -> compute path."""
    ops = {op["id"]: op for op in graph["ops"]}
    pred, succ = _build_op_adjacency(graph)
    degree = {u: len(pred[u]) for u in ops}
    ready = deque(u for u in ops if not degree[u])
    topo = []
    while ready:
        u = ready.popleft()
        topo.append(u)
        for v in succ[u]:
            degree[v] -= 1
            if degree[v] == 0:
                ready.append(v)
    if len(topo) != len(ops):
        raise ValueError("Cyclic operation graph")
    ancestor, descendant = {}, {}
    for u in topo:
        ancestor[u] = any(ops[v]["op"] not in COPY or ancestor[v] for v in pred[u])
    for u in reversed(topo):
        descendant[u] = any(ops[v]["op"] not in COPY or descendant[v] for v in succ[u])
    return any(ops[u]["op"] in COPY and ancestor[u] and descendant[u] for u in ops)


def _resident_by_task(graph: dict, view: dict, capacity: dict) -> tuple[dict, dict, list] | tuple[None, str, list]:
    ops = {op["id"]: op for op in graph["ops"]}
    tensors = {tensor["id"]: tensor for tensor in graph["tensors"]}
    producers = defaultdict(set)
    incident = {task: set() for task in view["subgraph_ids"]}
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u in ops and v in tensors:
            producers[v].add(u)
        if u in view["mapping"] and v in tensors:
            incident[view["mapping"][u]].add(v)
        if u in tensors and v in view["mapping"]:
            incident[view["mapping"][v]].add(u)
    if any(len(ps) > 1 for ps in producers.values()):
        return None, "tensor_has_multiple_producers", []
    pos = {t: ("UB" if item["pos"] == "DDR" else item["pos"])
           for t, item in tensors.items()}
    oversized = []
    for task, ids in incident.items():
        bytes_by_pos = {kind: sum(tensors[t]["size"] for t in ids if pos[t] == kind)
                        for kind in capacity}
        if any(bytes_by_pos[kind] > limit for kind, limit in capacity.items()):
            oversized.append({"task": task, "resident_union_bytes": bytes_by_pos})
    return incident, {t: (pos[t], item["size"]) for t, item in tensors.items()}, oversized


def _fits(ids: set[int], resident: dict, capacity: dict) -> bool:
    return all(sum(resident[t][1] for t in ids if resident[t][0] == kind) <= limit
               for kind, limit in capacity.items())


def merge_plan(graph: dict, base: dict, capacity: dict) -> tuple[dict, dict]:
    """Return the unchanged base on any unsupported structure."""
    view = derive_multicore_plan(graph, base)
    validate_task_order(view)
    info = {"base_tasks": len(view["subgraph_ids"]), "merged_pairs": [],
            "capacity_bytes": dict(capacity)}

    def fallback(reason: str):
        info.update(selected="base", reason=reason, tasks=len(view["subgraph_ids"]))
        return base, info

    validate_graph(graph)
    if _copy_bridge(graph):
        return fallback("excluded_copy_bridge_between_compute_ops")
    if any(view["core_by_subgraph"][a] != view["core_by_subgraph"][b]
           for a, b in view["dependency_pairs"]):
        return fallback("remote_task_dependency")
    contents = _resident_by_task(graph, view, capacity)
    if contents[0] is None:
        return fallback(contents[1])
    incident, resident, oversized = contents
    info["oversize_original_tasks"] = oversized
    remap, schedules = {}, []
    for order in base["core_schedules"]:
        kept = []
        i = 0
        while i < len(order):
            left = order[i]
            if i + 1 < len(order):
                right = order[i + 1]
                union = incident[left] | incident[right]
                if _fits(union, resident, capacity):
                    remap[right] = left
                    kept.append(left)
                    info["merged_pairs"].append({
                        "left": left, "right": right,
                        "resident_union_bytes": {
                            kind: sum(resident[t][1] for t in union if resident[t][0] == kind)
                            for kind in capacity},
                    })
                    i += 2
                    continue
            kept.append(left)
            i += 1
        schedules.append(kept)
    if not remap:
        return fallback("no_adjacent_pair_within_resident_union_capacity")
    result = {
        "node_to_subgraph": {u: remap.get(t, t) for u, t in view["mapping"].items()},
        "core_schedules": schedules,
    }
    after = derive_multicore_plan(graph, result)
    validate_task_order(after)
    info.update(selected="adjacent-spill-invariant", tasks=len(after["subgraph_ids"]))
    return result, info


def construct(graph: dict, cores: int, *, base_constructor=None) -> tuple[dict, dict]:
    start = time.perf_counter()
    constructor = shared_construct if base_constructor is None else base_constructor
    base, base_info = constructor(graph, cores)
    plan, info = merge_plan(graph, base, read_capacity_config(CONFIG))
    info.update(algorithm_id="q1-adjacent-spill-invariant-stage-n",
                base_algorithm=base_info,
                cli_body_construct_seconds=time.perf_counter() - start,
                timing_scope="Base construction, guards, merge, and validation; excludes imports and file I/O. External runner measures full cold wall.",
                quality_scope="No Makespan dominance claim; no online evaluator")
    return plan, info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.diagnostics.resolve():
        raise ValueError("Plan and diagnostics must have different output paths")
    if args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("Refuse to overwrite existing experiment artifacts")
    body_start = time.perf_counter()
    graph_bytes = args.graph.read_bytes()
    graph_hash = hashlib.sha256(graph_bytes).hexdigest()
    graph = json.loads(graph_bytes)
    plan, info = construct(graph, args.cores)
    info["graph_sha256"] = graph_hash
    info["cli_body_through_plan_wall_seconds"] = time.perf_counter() - body_start
    info["cli_body_timing_scope"] = "Read and hash original graph bytes, parse JSON, construct and validate plan; excludes imports, output writes and process exit."
    for path in (args.output, args.diagnostics):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(plan, f, separators=(",", ":"))
        f.write("\n")
    with args.diagnostics.open("x", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
