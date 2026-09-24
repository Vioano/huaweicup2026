"""Compile a conservative P1 Task subset through the frozen official Step1/2/3.

This adapter does not evaluate a plan. It only translates the official, fixed
per-Pipe FIFO and completed-operation dependencies into prefix requirements for
the mathematical response model. Unsupported execution semantics fail closed.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from src.q1.response_oracle import PIPES, PortOp, Task


class UnsupportedResponse(ValueError):
    """The response model cannot represent this official Task compilation."""


_OFFICIAL = (
    Path(__file__).resolve().parents[2]
    / "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"
)


def _official_modules():
    # The frozen evaluator uses sibling absolute imports. This is the official
    # source tree, not an archived transcription or a copied scheduler.
    directory = str(_OFFICIAL.parent)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    import multicore_cut_evaluate_problem_1 as scene
    import stub_multicore_cut_and_schedule as plans
    import schedule_step3 as step3
    import schedule_step1 as step1
    import schedule_step2 as step2
    import evaluation_validation as validation

    for module in (scene, plans, step1, step2, step3, validation):
        if Path(module.__file__).resolve().parent != _OFFICIAL.parent:
            raise UnsupportedResponse(
                f"official compiler module shadowed: {module.__name__}")
    if step3.PIPE_SLOTS != 1 or set(step3.PIPES) != set(PIPES):
        raise UnsupportedResponse("response needs one slot on each of four Pipes")

    return scene, plans, step3, validation


def _require_parameters(capacity, bandwidth):
    if not isinstance(capacity, dict) or set(capacity) != {"L1", "UB"}:
        raise ValueError("capacity must contain exactly L1 and UB")
    if any(type(value) is not int or value < 0 for value in capacity.values()):
        raise ValueError("capacity values must be nonnegative integers")
    if type(bandwidth) is not int or bandwidth <= 0:
        raise ValueError("bandwidth must be a positive integer")
    if tuple(PIPES) != ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3"):
        raise ValueError("unexpected response model Pipe order")


def _check_original_graph(graph, capacity):
    for op in graph["ops"]:
        if "SPILL" in op["op"]:
            raise UnsupportedResponse("original graph contains a spill operation")
    for edge in graph["edges"]:
        if edge.get("dependency", "").upper().startswith("MEM"):
            raise UnsupportedResponse("original graph contains a memory-reuse edge")
    op_ids = {op["id"] for op in graph["ops"]}
    producers = {tensor["id"]: set() for tensor in graph["tensors"]}
    for edge in graph["edges"]:
        if edge["source"] in op_ids and edge["target"] in producers:
            producers[edge["target"]].add(edge["source"])
    for tensor in graph["tensors"]:
        tid = tensor["id"]
        if len(producers[tid]) > 1:
            raise UnsupportedResponse(f"tensor {tid} has multiple producers")
        # P1 converts an original DDR tensor into a UB Task-local counterpart.
        local_pos = "UB" if tensor["pos"] == "DDR" else tensor["pos"]
        if tensor["size"] > capacity[local_pos]:
            raise UnsupportedResponse(
                f"tensor {tid} exceeds {local_pos} capacity")


def _compile_task(task_id, official, capacity, bandwidth, step3):
    graph = official["graph"]
    ops = official["op_by_id"]
    tensor_by_id = official["tensor_by_id"]
    if official["step3"]["memory_dependencies"]:
        raise UnsupportedResponse(f"task {task_id}: memory-reuse dependency")
    if any("SPILL" in op["op"] for op in graph["ops"]):
        raise UnsupportedResponse(f"task {task_id}: Step2 inserted spill operation")
    if any(edge.get("dependency", "").upper().startswith("MEM")
           for edge in graph["edges"]):
        raise UnsupportedResponse(f"task {task_id}: memory-reuse edge")

    # The response oracle has no dynamic allocation state. Requiring the whole
    # managed footprint to fit is a conservative sufficient capacity condition.
    footprint = {position: 0 for position in capacity}
    producers = {tid: set() for tid in tensor_by_id}
    for op_id, tids in official["out_tids"].items():
        for tid in tids:
            producers[tid].add(op_id)
    for tid, tensor in tensor_by_id.items():
        position = tensor["pos"]
        if position in capacity:
            if len(producers[tid]) != 1:
                raise UnsupportedResponse(
                    f"task {task_id}: managed tensor {tid} lacks unique producer")
            footprint[position] += tensor["size"]
    for position, used in footprint.items():
        if used > capacity[position]:
            raise UnsupportedResponse(
                f"task {task_id}: {position} footprint {used} exceeds capacity "
                f"{capacity[position]}")

    orders = official["pipe_ops"]
    if set(orders) != set(PIPES):
        raise UnsupportedResponse(f"task {task_id}: unexpected Pipe set")
    positions = {}
    for pipe_index, pipe in enumerate(PIPES):
        for rank, op_id in enumerate(orders[pipe], 1):
            if op_id in positions:
                raise UnsupportedResponse(f"task {task_id}: duplicate FIFO operation")
            positions[op_id] = (pipe_index, rank)
    if set(positions) != set(ops):
        raise UnsupportedResponse(f"task {task_id}: FIFO does not cover operations")

    ports = []
    for pipe in PIPES:
        compiled = []
        for op_id in orders[pipe]:
            need = [0] * len(PIPES)
            for predecessor in official["op_preds"][op_id]:
                if predecessor not in positions:
                    raise UnsupportedResponse(
                        f"task {task_id}: predecessor outside Task")
                pipe_index, rank = positions[predecessor]
                need[pipe_index] = max(need[pipe_index], rank)
            op = ops[op_id]
            work = step3._op_duration(
                op, official["in_tids"], official["out_tids"],
                tensor_by_id, bandwidth)
            ddr = step3._uses_ddr_bandwidth(
                op, official["in_tids"], official["out_tids"], tensor_by_id)
            if type(work) is not int or work < 1:
                raise UnsupportedResponse(f"task {task_id}: noninteger work")
            compiled.append(PortOp(work, bool(ddr), tuple(need), op_id))
        ports.append(tuple(compiled))
    return Task(tuple(ports), task_id), footprint


def compile_plan(graph, plan, capacity, bandwidth=60):
    """Return per-core ordered response Tasks plus a static source certificate.

    The accepted subset has no cross-core Task dependency, spill, memory reuse,
    multi-producer managed tensor, or aggregate managed footprint overflow.
    """
    _require_parameters(capacity, bandwidth)
    scene, plans, step3, validation = _official_modules()
    validation.validate_graph(graph)
    _check_original_graph(graph, capacity)
    view = plans.derive_multicore_plan(graph, plan)
    validation.validate_task_order(view)
    for target, predecessors in view["subgraph_preds"].items():
        for source in predecessors:
            if view["core_by_subgraph"][source] != view["core_by_subgraph"][target]:
                raise UnsupportedResponse(
                    f"cross-core Task dependency {source} -> {target}")

    try:
        tasks, cross_traffic, traffic, official_view = scene._build_scene_a_tasks(
            graph, plan, bandwidth, capacity)
    except RuntimeError as exc:
        # Official Step2/3 can fail while compiling inputs outside this small
        # static subset. Keep that failure separate from a response prediction.
        raise UnsupportedResponse(f"official Task compilation failed: {exc}") from exc
    # Official `cross_task_traffic` includes same-core Task boundaries too.
    # Cross-core dependencies were rejected above using actual Task ownership;
    # a same-core cut is represented by boundary COPYs and the Task gate.
    if traffic["spill_added_copy_bytes"]:
        raise UnsupportedResponse("Step2 inserted spill traffic")
    compiled = {}
    certificate_tasks = {}
    for task_id, official in tasks.items():
        response_task, footprint = _compile_task(
            task_id, official, capacity, bandwidth, step3)
        compiled[task_id] = response_task
        certificate_tasks[task_id] = {
            "core_id": official["core_id"],
            "footprint": footprint,
            "op_count": sum(map(len, response_task.ports)),
        }
    lines = [
        [compiled[task_id] for task_id in official_view["core_orders"][core]]
        for core in range(official_view["num_cores"])
    ]
    certificate = {
        "official_source": "data/raw/a/official/code/" + _OFFICIAL.name,
        "official_sha256": hashlib.sha256(_OFFICIAL.read_bytes()).hexdigest(),
        "compiler_source_hashes": {
            name: hashlib.sha256((_OFFICIAL.parent / name).read_bytes()).hexdigest()
            for name in ("multicore_cut_evaluate_problem_1.py", "schedule_step1.py",
                         "schedule_step2.py", "schedule_step3.py",
                         "stub_multicore_cut_and_schedule.py", "evaluation_validation.py")
        },
        "capacity": dict(capacity),
        "bandwidth": bandwidth,
        "tasks": certificate_tasks,
        "traffic": traffic,
        "cross_task_tensor_bytes": cross_traffic,
        "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
    }
    return lines, certificate
