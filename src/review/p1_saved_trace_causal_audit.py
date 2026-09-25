"""Read-only saved-trace consistency and observed-duration DAG audit.

No response model, compiler, solver, or evaluator is imported or called.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIGNATURES = ROOT / "results/a/p1-period7-colab-20260925/run-0534Z/paired-signatures.json"
PIPES = ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3")
SIGNATURES_SHA256 = "2a90a5b0e8b3ff19fe88a07e6580dc4899a63b7654d0d268c0941b947549c95b"


def audit(tasks, core_schedules, gate, trace, task_intervals, makespan):
    if not isinstance(trace, list) or not trace or not isinstance(task_intervals, list):
        raise ValueError("complete trace and task_intervals required")
    if type(gate) is not int or gate < 0 or type(makespan) is not int or makespan < 0:
        raise ValueError("integer gate/makespan required")
    by_task = {row["task_id"]: row for row in tasks}
    scheduled = [t for line in core_schedules for t in line]
    if (len(by_task) != len(tasks) or len(scheduled) != len(set(scheduled)) or
            set(by_task) != set(scheduled)):
        raise ValueError("Task/schedule coverage mismatch")
    for core, line in enumerate(core_schedules):
        if any(by_task[t]["core"] != core for t in line):
            raise ValueError("Task/core mismatch")
    intervals = {}
    for row in task_intervals:
        key = row["task"]
        if key not in by_task or key in intervals or row["core"] != by_task[key]["core"]:
            raise ValueError("duplicate or foreign Task interval")
        if any(type(row[x]) is not int for x in ("start", "end")) or row["end"] <= row["start"]:
            raise ValueError("invalid Task interval time")
        intervals[key] = row
    if set(intervals) != set(by_task):
        raise ValueError("missing Task interval")

    observed = {}
    last_retirement = -1
    for row in trace:
        task, pipe = row.get("task"), row.get("pipe")
        if task not in by_task or pipe not in PIPES or row.get("core") != by_task[task]["core"]:
            raise ValueError("foreign trace operation")
        if any(type(row.get(x)) is not int for x in ("start", "end", "work")) or type(row.get("ddr")) is not bool:
            raise ValueError("invalid trace fields")
        if row["start"] < 0 or row["end"] <= row["start"] or row["end"] < last_retirement:
            raise ValueError("trace retirement order/time ambiguity")
        last_retirement = row["end"]
        key = (task, PIPES.index(pipe))
        observed.setdefault(key, []).append(row)

    nodes, edges, indegree = {}, {}, {}
    def add(name, weight, kind, data=None):
        nodes[name] = dict(weight=weight, kind=kind, data=data or {})
        edges[name] = []
        indegree[name] = 0
    def link(source, target, reason):
        edges[source].append((target, reason))
        indegree[target] += 1

    for task_id, task in by_task.items():
        ports = task["ports"]
        if len(ports) != 4:
            raise ValueError("expected four ports")
        add((task_id, "start"), 0, "task_start", dict(task=task_id))
        add((task_id, "end"), 0, "task_end", dict(task=task_id))
        for p, port in enumerate(ports):
            seen = observed.get((task_id, p), [])
            if len(seen) != len(port):
                raise ValueError("trace operation coverage/rank ambiguous")
            for rank, (signature, row) in enumerate(zip(port, seen), 1):
                work, ddr, need = signature
                if work != row["work"] or ddr != row["ddr"] or len(need) != 4:
                    raise ValueError("trace work/DDR differs from saved signature")
                duration = row["end"] - row["start"]
                if duration < work or (not ddr and duration != work):
                    raise ValueError("observed service duration inconsistent with work")
                if not (intervals[task_id]["start"] <= row["start"] < row["end"] <= intervals[task_id]["end"]):
                    raise ValueError("operation outside its Task interval")
                if rank > 1 and seen[rank - 2]["end"] > row["start"]:
                    raise ValueError("FIFO overlap or ambiguous rank")
                name = (task_id, p, rank)
                add(name, duration, "DDR" if ddr else "compute",
                    dict(task=task_id, core=task["core"], pipe=PIPES[p], rank=rank,
                         observed_start=row["start"], observed_end=row["end"],
                         solo_work=work, duration=duration))
                link((task_id, "start"), name, "task_activation")
                link(name, (task_id, "end"), "task_completion")
        if not any(ports):
            raise ValueError("empty saved Task")
    for task_id, task in by_task.items():
        for p, port in enumerate(task["ports"]):
            for rank, signature in enumerate(port, 1):
                target = (task_id, p, rank)
                if rank > 1:
                    source = (task_id, p, rank - 1)
                    link(source, target, "FIFO")
                    if observed[(task_id, p)][rank - 2]["end"] > observed[(task_id, p)][rank - 1]["start"]:
                        raise ValueError("FIFO predecessor did not retire")
                for other, prefix in enumerate(signature[2]):
                    if type(prefix) is not int or not 0 <= prefix <= len(task["ports"][other]):
                        raise ValueError("invalid need prefix")
                    if prefix:
                        source = (task_id, other, prefix)
                        link(source, target, "need")
                        if observed[(task_id, other)][prefix - 1]["end"] > observed[(task_id, p)][rank - 1]["start"]:
                            raise ValueError("need predecessor did not retire")
    for core, line in enumerate(core_schedules):
        for index, task_id in enumerate(line):
            current = intervals[task_id]
            if index == 0:
                if current["start"] != 0:
                    raise ValueError("first Task must activate at zero")
            else:
                previous = line[index - 1]
                if current["start"] != intervals[previous]["end"] + gate:
                    raise ValueError("Task gate mismatch")
                gate_node = (task_id, "gate")
                add(gate_node, gate, "gate", dict(core=core, before_task=task_id))
                link((previous, "end"), gate_node, "serial_core")
                link(gate_node, (task_id, "start"), "gate")
            ends = [row["end"] for p in range(4) for row in observed.get((task_id, p), [])]
            if current["end"] != max(ends):
                raise ValueError("Task interval end differs from last operation")
    if makespan != max(row["end"] for row in intervals.values()):
        raise ValueError("makespan differs from final Task end")

    ready = [(repr(node), node) for node, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    distance = {node: item["weight"] for node, item in nodes.items()}
    parent = {}
    visited = 0
    while ready:
        source = heapq.heappop(ready)[1]
        visited += 1
        for target, reason in edges[source]:
            value = distance[source] + nodes[target]["weight"]
            if value > distance[target]:
                distance[target] = value
                parent[target] = (source, reason)
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, (repr(target), target))
    if visited != len(nodes):
        raise ValueError("saved trace precedence graph cyclic")
    start_slack = []
    for name, item in nodes.items():
        if item["kind"] in ("DDR", "compute"):
            actual = item["data"]["observed_end"]
            if distance[name] > actual:
                raise ValueError("observed operation ends before its precedence minimum")
            start_slack.append(actual - distance[name])
        elif item["kind"] == "task_start":
            actual = intervals[item["data"]["task"]]["start"]
            if distance[name] > actual:
                raise ValueError("Task starts before its gate predecessor")
    finish = max(((task_id, "end") for task_id in by_task), key=lambda node: distance[node])
    if distance[finish] > makespan:
        raise ValueError("observed makespan below precedence minimum")
    chain = []
    cursor = finish
    while True:
        item = nodes[cursor]
        chain.append(dict(kind=item["kind"], weight=item["weight"], **item["data"],
                          incoming=parent[cursor][1] if cursor in parent else "root"))
        if cursor not in parent:
            break
        cursor = parent[cursor][0]
    chain.reverse()
    ddr = [item for item in chain if item["kind"] == "DDR"]
    compute = [item for item in chain if item["kind"] == "compute"]
    gates = [item for item in chain if item["kind"] == "gate"]
    parts = dict(ddr_solo_work=sum(item["solo_work"] for item in ddr),
                 ddr_duration_excess_including_rounding=sum(item["duration"] - item["solo_work"] for item in ddr),
                 compute_work=sum(item["weight"] for item in compute),
                 gate=sum(item["weight"] for item in gates))
    assert sum(parts.values()) == distance[finish]
    exact_match = distance[finish] == makespan and not any(start_slack)
    return dict(status="matched_observed_duration_DAG_only" if exact_match else "undetermined_hidden_delay",
                makespan=makespan, observed_duration_DAG_longest=distance[finish],
                unexplained_gap=makespan - distance[finish], decomposition=parts,
                max_operation_start_slack=max(start_slack, default=0),
                critical_chain=chain, checked_operations=sum(len(port) for task in tasks for port in task["ports"]),
                fair_DDR_service_validated=False,
                limitation="Only observed-duration precedence algebra is checked. Fair DDR service, integer retirement legality, and counterfactual causality are NOT verified")


def synthetic_validation():
    zero = [0, 0, 0, 0]
    tasks = [dict(task_id=0, core=0, ports=[[[4, False, [0, 0, 1, 0]]], [], [[2, True, zero]], []]),
             dict(task_id=1, core=0, ports=[[], [[2, False, zero]], [], []])]
    trace = [dict(core=0, task=0, pipe="PIPE_MTE2", start=0, end=3, work=2, ddr=True),
             dict(core=0, task=0, pipe="PIPE_M", start=3, end=7, work=4, ddr=False),
             dict(core=0, task=1, pipe="PIPE_V", start=9, end=11, work=2, ddr=False)]
    intervals = [dict(core=0, task=0, start=0, end=7), dict(core=0, task=1, start=9, end=11)]
    result = audit(tasks, [[0, 1]], 2, trace, intervals, 11)
    assert result["status"] == "matched_observed_duration_DAG_only"
    assert result["fair_DDR_service_validated"] is False
    assert result["decomposition"] == dict(ddr_solo_work=2,
                                             ddr_duration_excess_including_rounding=1,
                                             compute_work=6, gate=2)
    # A separate hand-written feasible schedule: sole DDR work 2 takes 2 cycles.
    feasible_trace = [dict(trace[0], end=2), dict(trace[1], start=2, end=6),
                      dict(trace[2], start=8, end=10)]
    feasible_intervals = [dict(intervals[0], end=6), dict(intervals[1], start=8, end=10)]
    feasible = audit(tasks, [[0, 1]], 2, feasible_trace, feasible_intervals, 10)
    assert feasible["status"] == "matched_observed_duration_DAG_only"
    assert feasible["decomposition"] == dict(ddr_solo_work=2,
        ddr_duration_excess_including_rounding=0, compute_work=6, gate=2)
    broken_need = [feasible_trace[0], dict(feasible_trace[1], start=1, end=5),
                   feasible_trace[2]]
    try:
        audit(tasks, [[0, 1]], 2, broken_need, feasible_intervals, 10)
    except ValueError as error:
        assert "need predecessor" in str(error)
        premature_need_rejected = True
    else:
        raise AssertionError("operation began before required retirement")
    try:
        audit(tasks, [[0, 1]], 2, trace[:-1], intervals, 11)
    except ValueError:
        missing_trace_rejected = True
    else:
        raise AssertionError("missing trace was accepted")
    try:
        audit(tasks, [[0, 1]], 2, list(reversed(trace)), intervals, 11)
    except ValueError:
        out_of_order_rejected = True
    else:
        raise AssertionError("out-of-order retirement was accepted")
    try:
        audit(tasks, [[0, 0, 1]], 2, trace, intervals, 11)
    except ValueError:
        duplicate_schedule_rejected = True
    else:
        raise AssertionError("duplicate scheduled Task was accepted")
    return dict(kind="HANDWRITTEN_SYNTHETIC_PRECEDENCE_ONLY_DELIBERATELY_UNVERIFIED_DDR_SERVICE",
                precedence_check=result,
                feasible_handwritten=feasible,
                premature_need_rejected=premature_need_rejected,
                missing_trace_rejected=missing_trace_rejected,
                out_of_order_rejected=out_of_order_rejected,
                duplicate_schedule_rejected=duplicate_schedule_rejected,
                synthetic_known_service_violation="one DDR op with solo work 2 was assigned duration 3 without a contender",
                calls=dict(Task_compile=0, response_simulate=0, E0=0, E1=0, E2=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-self-test", action="store_true")
    parser.add_argument("--trace-json", type=Path)
    parser.add_argument("--variant", choices=("whole_seed", "period7_seed"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.synthetic_self_test:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream:
            json.dump(synthetic_validation(), stream, indent=2)
            stream.write("\n")
        return
    if args.trace_json is None or args.variant is None or args.output is None:
        parser.error("--trace-json, --variant, and --output are all required")
    saved_raw = SIGNATURES.read_bytes()
    if hashlib.sha256(saved_raw).hexdigest() != SIGNATURES_SHA256:
        raise ValueError("paired signatures differ from frozen SHA-256")
    saved = json.loads(saved_raw)
    if saved["pipes"] != list(PIPES):
        raise ValueError("saved signature Pipe order differs")
    payload_raw = args.trace_json.read_bytes()
    payload = json.loads(payload_raw)
    variant = saved["variants"][args.variant]
    if type(payload.get("makespan")) is not int or payload["makespan"] != variant["expected_model_makespan"]:
        raise ValueError("saved trace makespan differs from paired-signature model result")
    result = audit(variant["tasks"], variant["core_schedules"], saved["gate"],
                   payload["trace"], payload["task_intervals"], payload["makespan"])
    result.update(kind="SAVED_TRACE_DAG_AUDIT_NOT_E0", variant=args.variant,
                  saved_signatures_sha256=hashlib.sha256(saved_raw).hexdigest(),
                  trace_input_sha256=hashlib.sha256(payload_raw).hexdigest(),
                  calls=dict(Task_compile=0, response_simulate=0, E0=0, E1=0, E2=0))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
