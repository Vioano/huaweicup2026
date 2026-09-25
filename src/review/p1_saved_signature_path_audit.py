"""Static critical-path lower bounds from saved P1 PortOp signatures.

No compiler, simulator, solver, or evaluator is imported or called.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "results/a/p1-period7-colab-20260925/run-0534Z/paired-signatures.json"
INPUT_SHA256 = "2a90a5b0e8b3ff19fe88a07e6580dc4899a63b7654d0d268c0941b947549c95b"
PIPES = ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3")


def critical_path(ports, ddr_factor=1):
    """Longest weighted path in FIFO-plus-completed-prefix precedence DAG."""
    if len(ports) != 4 or type(ddr_factor) is not int or ddr_factor < 1:
        raise ValueError("invalid four-pipe signature or DDR factor")
    ops = {(p, i): op for p, port in enumerate(ports) for i, op in enumerate(port)}
    if not ops:
        raise ValueError("empty Task")
    successors = {node: [] for node in ops}
    indegree = {node: 0 for node in ops}
    weights = {}
    for node, op in ops.items():
        p, i = node
        work, ddr, need = op
        if type(work) is not int or work < 1 or type(ddr) is not bool or len(need) != 4:
            raise ValueError("invalid PortOp")
        weights[node] = work * ddr_factor if ddr else work
        predecessors = {}
        if i:
            predecessors[(p, i - 1)] = "FIFO"
        for other, prefix in enumerate(need):
            if type(prefix) is not int or not 0 <= prefix <= len(ports[other]):
                raise ValueError("invalid completed-prefix requirement")
            if prefix:
                predecessor = (other, prefix - 1)
                predecessors.setdefault(predecessor, "need")
        for predecessor, reason in predecessors.items():
            if predecessor == node or predecessor not in ops:
                raise ValueError("invalid Task predecessor")
            successors[predecessor].append((node, reason))
            indegree[node] += 1
    ready = [node for node, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    distance = dict(weights)
    parent = {}
    visited = 0
    while ready:
        source = heapq.heappop(ready)
        visited += 1
        for target, reason in successors[source]:
            candidate = distance[source] + weights[target]
            if candidate > distance[target]:
                distance[target] = candidate
                parent[target] = (source, reason)
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, target)
    if visited != len(ops):
        raise ValueError("saved Task precedence graph is cyclic")
    endpoint = max(distance, key=lambda node: (distance[node], node))
    path = []
    node = endpoint
    while True:
        op = ops[node]
        predecessor = parent.get(node)
        path.append(dict(pipe=PIPES[node[0]], rank=node[1] + 1,
                         work=weights[node], ddr=op[1],
                         incoming=predecessor[1] if predecessor else "start"))
        if predecessor is None:
            break
        node = predecessor[0]
    path.reverse()
    links = [dict(source_pipe=path[i - 1]["pipe"], source_rank=path[i - 1]["rank"],
                  target_pipe=path[i]["pipe"], target_rank=path[i]["rank"])
             for i in range(1, len(path)) if path[i]["incoming"] == "need"]
    fifo_only = max(sum(weights[p, i] for i in range(len(ports[p])))
                    for p in range(4))
    return dict(lower=distance[endpoint], operation_count=len(ops),
                path_work_check=sum(node["work"] for node in path),
                fifo_only_lower=fifo_only,
                need_extension_over_fifo_only=distance[endpoint] - fifo_only,
                path=path, cross_pipe_need_links=links,
                critical_need_count=len(links))


def analyze_variant(variant, gate, sync_rounds):
    tasks = {row["task_id"]: row for row in variant["tasks"]}
    schedules = variant["core_schedules"]
    if len(schedules) != 5 or len(tasks) != sum(map(len, schedules)):
        raise ValueError("expected five cores and complete Task schedules")
    scheduled_ids = [task_id for line in schedules for task_id in line]
    if len(set(scheduled_ids)) != len(scheduled_ids) or set(scheduled_ids) != set(tasks):
        raise ValueError("each Task must appear exactly once")
    if len(tasks) != len(variant["tasks"]):
        raise ValueError("duplicate Task IDs")
    if not 0 < sync_rounds <= min(map(len, schedules)):
        raise ValueError("invalid synchronous prefix length")
    for core, line in enumerate(schedules):
        if any(tasks[task_id]["core"] != core for task_id in line):
            raise ValueError("Task/core schedule mismatch")
    rounds, prefix = [], 0
    for index in range(sync_rounds):
        ids = [line[index] for line in schedules]
        signatures = [tasks[task_id]["ports"] for task_id in ids]
        if any(signature != signatures[0] for signature in signatures[1:]):
            raise ValueError(f"round {index} is not five-core signature-symmetric")
        evidence = critical_path(signatures[0], ddr_factor=5)
        prefix += (gate if index else 0) + evidence["lower"]
        rounds.append(dict(round=index, task_ids=ids, ddr_factor=5,
                           conditional_symmetry_checked=True, **evidence))
    tails = []
    for core, line in enumerate(schedules):
        remainder = line[sync_rounds:]
        entries = [dict(task_id=task_id, ddr_factor=1,
                        **critical_path(tasks[task_id]["ports"]))
                   for task_id in remainder]
        tail_lower = sum(item["lower"] for item in entries)
        if entries:
            tail_lower += gate * (len(entries) - 1 + int(bool(sync_rounds)))
        tails.append(dict(core=core, task_ids=remainder, lower=tail_lower,
                          task_evidence=entries))
    tail = max(tails, key=lambda item: (item["lower"], -item["core"]))
    lower = prefix + tail["lower"]
    if lower > variant["expected_model_makespan"]:
        raise ValueError("static lower exceeds saved model makespan")
    return dict(plan_sha256=variant["plan_sha256"],
                saved_model_makespan_context_only=variant["expected_model_makespan"],
                static_dag_lower=lower, unassigned_gap_to_saved_model=variant["expected_model_makespan"] - lower,
                synchronous_rounds=rounds, terminal_per_core=tails,
                terminal_controlling_core=tail["core"],
                scope="Minimum per-op service precedence bound; not simulated contention or wait attribution")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise ValueError("fixed paired-signature bytes changed")
    data = json.loads(raw)
    if data["pipes"] != list(PIPES) or data["port_op_tuple"] != ["work", "uses_ddr", "need_prefixes"]:
        raise ValueError("saved signature schema changed")
    gate = data["gate"]
    if type(gate) is not int or gate < 0:
        raise ValueError("invalid gate")
    result = dict(kind="saved-signature-DAG-lower-NOT-simulation",
                  input_sha256=hashlib.sha256(raw).hexdigest(), gate=gate,
                  calls=dict(Task_compile=0, Fraction_response=0, E0=0, E1=0, E2=0),
                  variants={
                      "whole_seed": analyze_variant(data["variants"]["whole_seed"], gate, 1),
                      "period7_seed": analyze_variant(data["variants"]["period7_seed"], gate, 3),
                  })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
