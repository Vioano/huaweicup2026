"""Compile validated P1 Step3 Tasks, including frozen memory-reuse edges.

The returned FIFO model is rational research machinery, not E0 arithmetic.
Only the official Step1/2/3 path may establish capacity feasibility here.
"""

from __future__ import annotations

import hashlib

from src.q1.response_compile import (
    UnsupportedResponse, _OFFICIAL, _official_modules, _require_parameters,
)
from src.q1.response_oracle import PIPES, PortOp, Task


def _check_original(graph, capacity):
    ops = {op["id"] for op in graph["ops"]}
    producers = {tensor["id"]: set() for tensor in graph["tensors"]}
    for op in graph["ops"]:
        if "SPILL" in op["op"]:
            raise UnsupportedResponse("original graph contains spill operation")
    for edge in graph["edges"]:
        if edge["source"] in ops and edge["target"] in producers:
            producers[edge["target"]].add(edge["source"])
    for tensor in graph["tensors"]:
        tid = tensor["id"]
        if len(producers[tid]) > 1:
            raise UnsupportedResponse(f"tensor {tid} has multiple producers")
        position = "UB" if tensor["pos"] == "DDR" else tensor["pos"]
        if tensor["size"] > capacity[position]:
            raise UnsupportedResponse(f"tensor {tid} exceeds {position} capacity")


def _task(task_id, official, capacity, bandwidth, step3):
    if official["step3"].get("execution_contract_validated") is not True:
        raise UnsupportedResponse(f"task {task_id}: Step3 contract not validated")
    graph = official["graph"]  # Step3 execution_graph, never Step2 ext_graph.
    if any("SPILL" in op["op"] for op in graph["ops"]):
        raise UnsupportedResponse(f"task {task_id}: Step2 inserted spill")
    ops = official["op_by_id"]
    tensors = official["tensor_by_id"]
    producers = {tid: set() for tid in tensors}
    for op_id, tids in official["out_tids"].items():
        for tid in tids:
            producers[tid].add(op_id)
    footprint = {position: 0 for position in capacity}
    for tid, tensor in tensors.items():
        position = tensor["pos"]
        if position in capacity:
            if len(producers[tid]) != 1:
                raise UnsupportedResponse(
                    f"task {task_id}: managed tensor {tid} lacks unique producer")
            footprint[position] += tensor["size"]
    peak = official["step3"]["memory_peak"]
    if any(peak[position] > capacity[position] for position in capacity):
        raise UnsupportedResponse(f"task {task_id}: Step3 peak exceeds capacity")

    orders = official["pipe_ops"]
    if set(orders) != set(PIPES):
        raise UnsupportedResponse(f"task {task_id}: unexpected Pipe set")
    positions = {}
    for pipe_index, pipe in enumerate(PIPES):
        for rank, op_id in enumerate(orders[pipe], 1):
            if op_id in positions:
                raise UnsupportedResponse(f"task {task_id}: duplicate FIFO operation")
            positions[op_id] = pipe_index, rank
    if set(positions) != set(ops):
        raise UnsupportedResponse(f"task {task_id}: incomplete FIFO")

    ports = []
    by_id = {}
    for pipe in PIPES:
        port = []
        for op_id in orders[pipe]:
            need = [0] * 4
            for predecessor in official["op_preds"][op_id]:
                if predecessor not in positions:
                    raise UnsupportedResponse(f"task {task_id}: external op predecessor")
                predecessor_pipe, rank = positions[predecessor]
                need[predecessor_pipe] = max(need[predecessor_pipe], rank)
            op = ops[op_id]
            work = step3._op_duration(
                op, official["in_tids"], official["out_tids"], tensors, bandwidth)
            ddr = step3._uses_ddr_bandwidth(
                op, official["in_tids"], official["out_tids"], tensors)
            if type(work) is not int or work < 1:
                raise UnsupportedResponse(f"task {task_id}: invalid operation duration")
            converted = PortOp(work, bool(ddr), tuple(need), op_id)
            port.append(converted)
            by_id[op_id] = converted
        ports.append(tuple(port))

    # Both newly emitted MEM edges and dependencies already present as data
    # edges must have reached the compiled completed-prefix requirements.
    memory_pairs = {(dep["source"], dep["target"])
                    for dep in official["step3"]["memory_dependencies"]}
    memory_pairs.update((edge["source"], edge["target"])
                        for edge in graph["edges"]
                        if str(edge.get("dependency", "")).upper().startswith("MEM"))
    for source, target in memory_pairs:
        if source not in positions or target not in by_id:
            raise UnsupportedResponse(f"task {task_id}: MEM edge is not op-to-op")
        if source not in official["op_preds"][target]:
            raise UnsupportedResponse(f"task {task_id}: MEM predecessor missing")
        pipe_index, rank = positions[source]
        if by_id[target].need[pipe_index] < rank:
            raise UnsupportedResponse(f"task {task_id}: MEM prefix missing")
    return Task(tuple(ports), task_id), {
        "core_id": official["core_id"], "footprint": footprint,
        "memory_peak": dict(peak),
        "memory_dependencies": official["step3"]["memory_dependencies"],
        "memory_edge_pairs": sorted(memory_pairs),
        "op_count": len(positions),
        "execution_contract_validated": True,
    }


def compile_plan(graph, plan, capacity, bandwidth=60):
    """Compile a no-spill P1 plan with Step3's full fixed execution graph."""
    _require_parameters(capacity, bandwidth)
    scene, plans, step3, validation = _official_modules()
    validation.validate_graph(graph)
    _check_original(graph, capacity)
    view = plans.derive_multicore_plan(graph, plan)
    validation.validate_task_order(view)
    for target, predecessors in view["subgraph_preds"].items():
        for source in predecessors:
            if view["core_by_subgraph"][source] != view["core_by_subgraph"][target]:
                raise UnsupportedResponse(f"cross-core Task dependency {source} -> {target}")
    try:
        tasks, cross_task_bytes, traffic, prepared_view = scene._build_scene_a_tasks(
            graph, plan, bandwidth, capacity)
    except RuntimeError as error:
        raise UnsupportedResponse(f"official Task compilation failed: {error}") from error
    if traffic["spill_added_copy_bytes"]:
        raise UnsupportedResponse("Step2 inserted spill traffic")
    converted, details = {}, {}
    for task_id, official in tasks.items():
        converted[task_id], details[task_id] = _task(
            task_id, official, capacity, bandwidth, step3)
    lines = [[converted[task_id] for task_id in prepared_view["core_orders"][core]]
             for core in range(prepared_view["num_cores"])]
    source_files = sorted(_OFFICIAL.parent.glob("*.py"))
    config_file = _OFFICIAL.parent.parent / "data/config.txt"
    certificate = {
        "kind": "validated-Step3-rational-response-NOT-E0",
        "official_source": "data/raw/a/official/code/" + _OFFICIAL.name,
        "compiler_source_hashes": {
            **{"code/" + path.name: hashlib.sha256(path.read_bytes()).hexdigest()
               for path in source_files},
            "data/config.txt": hashlib.sha256(config_file.read_bytes()).hexdigest(),
        },
        "capacity": dict(capacity), "bandwidth": bandwidth,
        "tasks": details, "traffic": traffic,
        "cross_task_tensor_bytes": cross_task_bytes,
        "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
    }
    return lines, certificate
