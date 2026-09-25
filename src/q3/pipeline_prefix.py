"""One guarded pilot-first COPY-prefix construction; static Task skeleton only.

The official P3 builder's unchanged AST body is extracted up to ``tasks = {}``.
No Step2, Step3, prepare or evaluator is called here. The result is a candidate,
not a measured Makespan or proof of successful official execution.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from copy import deepcopy
import hashlib
from pathlib import Path

from .construct import ROOT, UnsupportedStructure
from .shared_pipeline import _stage_structure
from evaluation_validation import validate_graph
import multicore_cut_evaluate_problem_3 as scene_b
from schedule_step1 import step1_schedule
from stub_multicore_cut_and_schedule import MulticoreCutError


OFFICIAL_SOURCE = ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_3.py"
OFFICIAL_SHA256 = "eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0"


class GuardFailure(UnsupportedStructure):
    """The exact static certificate does not cover this graph or plan."""


def _official_prefix():
    if Path(scene_b.__file__).resolve() != OFFICIAL_SOURCE.resolve():
        raise GuardFailure("loaded P3 module is not the frozen source path")
    raw = OFFICIAL_SOURCE.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != OFFICIAL_SHA256:
        raise GuardFailure(f"frozen P3 source SHA differs: {actual}")
    tree = ast.parse(raw, filename=str(OFFICIAL_SOURCE))
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name == "_build_scene_b_tasks"]
    if len(matches) != 1:
        raise GuardFailure("frozen P3 builder function not unique")
    original = matches[0]
    boundaries = [i for i, statement in enumerate(original.body)
                  if isinstance(statement, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "tasks"
                          for target in statement.targets)]
    if len(boundaries) != 1:
        raise GuardFailure("frozen P3 Task loop boundary not unique")
    function = deepcopy(original)
    function.name = "_static_scene_b_prefix"
    function.body = function.body[:boundaries[0]] + [ast.Return(ast.Tuple(
        elts=[ast.Name(id=name, ctx=ast.Load())
              for name in ("tasks_data", "cross_links", "plan_view")],
        ctx=ast.Load()))]
    namespace = dict(scene_b.__dict__)  # never modify the official module globals
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(OFFICIAL_SOURCE) + "#static-prefix", "exec"), namespace)
    return namespace[function.name]


def skeleton(graph, plan, bandwidth, capacity, *, ledger=None):
    """Exact frozen P3 Task/COPY prefix, including one official derive call."""
    if type(bandwidth) is not int or bandwidth <= 0:
        raise ValueError("positive integer DDR bandwidth required")
    if (not isinstance(capacity, dict) or set(capacity) != {"L1", "UB"}
            or any(type(value) is not int or value <= 0 for value in capacity.values())):
        raise ValueError("positive explicit L1/UB capacity required")
    validate_graph(graph)
    prefix = _official_prefix()
    if ledger is None:
        ledger = {}
    ledger["static_skeleton_calls"] = ledger.get("static_skeleton_calls", 0) + 1
    # derive_multicore_plan is the first executable statement of this frozen
    # prefix. Charge its attempted call before entering the extracted body.
    ledger["derive_multicore_plan_calls"] = ledger.get("derive_multicore_plan_calls", 0) + 1
    task_data, links, view = prefix(graph, plan, bandwidth, capacity)
    return {"tasks_data": task_data, "cross_links": links, "plan_view": view,
            "ledger": dict(ledger)}


def _ports(graph):
    ops = {o["id"]: o for o in graph["ops"]}
    tensors = {t["id"]: t for t in graph["tensors"]}
    if (len(ops) != len(graph["ops"]) or len(tensors) != len(graph["tensors"])
            or set(ops) & set(tensors)):
        raise GuardFailure("op/tensor IDs must be unique and disjoint")
    prod, cons, inputs, outputs = (defaultdict(set) for _ in range(4))
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if a in ops and b in tensors:
            prod[b].add(a)
            outputs[a].add(b)
        elif a in tensors and b in ops:
            cons[a].add(b)
            inputs[b].add(a)
        else:
            raise GuardFailure("requires tensor-mediated edges only")
    return ops, tensors, prod, cons, inputs, outputs


def _check_word(graph, word):
    ops, tensors, prod, cons, _, _ = _ports(graph)
    if len(word) != len(ops) or len(set(word)) != len(word) or set(word) != set(ops):
        raise GuardFailure("word coverage mismatch")
    rank = {u: i for i, u in enumerate(word)}
    for tid in tensors:
        for u in prod[tid]:
            for v in cons[tid]:
                if rank[u] >= rank[v]:
                    raise GuardFailure("word violates a data edge")


def _interval_peaks(graph, word, capacity):
    """Step2's no-spill closed intervals, including generated Task tensors."""
    _check_word(graph, word)
    _, tensors, prod, cons, _, _ = _ports(graph)
    rank = {u: i for i, u in enumerate(word)}
    delta = {pos: [0] * (len(word) + 1) for pos in capacity}
    for tid, tensor in tensors.items():
        pos = tensor["pos"]
        if pos not in capacity:
            continue
        uses = prod[tid] | cons[tid]
        if not uses:
            continue
        if not prod[tid]:
            raise GuardFailure("initial on-chip resident tensor")
        lo, hi = min(rank[u] for u in uses), max(rank[u] for u in uses)
        delta[pos][lo] += tensor["size"]
        delta[pos][hi + 1] -= tensor["size"]
    peaks = {}
    for pos, events in delta.items():
        used = peak = 0
        for change in events:
            used += change
            peak = max(peak, used)
        peaks[pos] = peak
        if peak > capacity[pos]:
            raise GuardFailure(f"Step2 closed-interval peak {pos} {peak}>{capacity[pos]}")
    return peaks


def build_candidate(index, anchor, cuts, bandwidth, capacity, *, ledger=None):
    """Return one candidate, metadata, and both full static Task snapshots.

    Uses two skeleton calls (anchor and candidate), one Step1 call per core,
    and zero Step2/3/evaluator calls. ``snapshots`` has ``anchor`` and
    ``candidate`` per-core graphs, raw/candidate words and annotations, plus
    identical ``cross_links``. A supplied ledger is mutated before each
    official/static subcall so a failed guard retains its partial call count.
    """
    if ledger is None:
        ledger = {}
    for key in ("static_skeleton_calls", "derive_multicore_plan_calls",
                "step1_calls", "official_priority_calls", "step2_calls", "step3_calls",
                "official_evaluations"):
        ledger.setdefault(key, 0)
    if type(bandwidth) is not int or bandwidth <= 0:
        raise ValueError("positive integer DDR bandwidth required")
    if (not isinstance(capacity, dict) or set(capacity) != {"L1", "UB"}
            or any(type(value) is not int or value <= 0 for value in capacity.values())):
        raise ValueError("positive explicit L1/UB capacity required")
    graph = index.graph
    validate_graph(graph)
    common, _, _, _ = _stage_structure(index)
    ops, tensors, prod, cons, inputs, outputs = _ports(graph)
    compute = set(index.ops)
    if set(ops) - compute != {u for u, op in ops.items()
                              if op["op"] in {"COPY_IN", "COPY_OUT"}}:
        raise GuardFailure("eligible compute set differs from official COPY exclusion")
    if any(type(t["size"]) is not int or t["size"] < 0 for t in tensors.values()):
        raise GuardFailure("invalid tensor size")
    jobs = index.components
    if (not isinstance(cuts, (tuple, list)) or len(cuts) < 3 or len(cuts) > 6
            or any(type(x) is not int for x in cuts)):
        raise GuardFailure("requires explicit 2..5 stage cuts")
    k = len(cuts) - 1
    if (len(jobs) < max(2, k) or len(anchor.get("core_schedules", [])) != k
            or cuts[0] != 0 or cuts[-1] != len(jobs[0])
            or any(a >= b for a, b in zip(cuts, cuts[1:]))
            or any(len(job) != cuts[-1] for job in jobs)):
        raise GuardFailure("requires nonempty common segments and jobs >= cores")
    if (set(u for job in jobs for u in job) != compute
            or sum(map(len, jobs)) != len(compute)):
        raise GuardFailure("jobs must partition compute operations")
    for job in jobs:
        for u, v in zip(job, job[1:]):
            if not any(u in prod[tid] for tid in inputs[v]):
                raise GuardFailure("requires actual tensor-mediated Hamiltonian chain")
    oldmap = {int(u): sg for u, sg in anchor["node_to_subgraph"].items()}
    if set(oldmap) != compute or len(set(oldmap.values())) != len(compute):
        raise GuardFailure("anchor must be a complete singleton plan")
    for core, (left, right) in enumerate(zip(cuts, cuts[1:])):
        expected = [oldmap[u] for job in jobs for u in job[left:right]]
        if anchor["core_schedules"][core] != expected:
            raise GuardFailure("anchor must be common-cut job-major")
    owner_job = {u: j for j, job in enumerate(jobs) for u in job}
    for tid in tensors:
        writers = prod[tid] & compute
        if len(writers) > 1:
            raise GuardFailure("multiple compute producers")
        if writers:
            writer = next(iter(writers))
            if any(owner_job[v] != owner_job[writer] for v in cons[tid] & compute):
                raise GuardFailure("inter-job compute dependency")

    first = skeleton(graph, anchor, bandwidth, capacity, ledger=ledger)
    anchor_data, links = first["tasks_data"], first["cross_links"]
    task_graphs, raw_words, taskports = {}, {}, {}
    common_copy = {}
    gate_copy = defaultdict(lambda: defaultdict(list))
    for core in range(k):
        data = anchor_data[core]
        task_graph = {"ops": data["ops"], "tensors": list(data["tensors"].values()),
                      "edges": data["edges"]}
        task_graphs[core] = task_graph
        ledger["step1_calls"] += 1
        raw_words[core] = step1_schedule(task_graph)
        _check_word(task_graph, raw_words[core])
        taskports[core] = _ports(task_graph)
        to, _, _, _, _, tout = taskports[core]
        common_copy[core] = {u for u, op in to.items()
                             if op["op"] == "COPY_IN" and tout[u] & common}
        expected = {tid for u in jobs[0][cuts[core]:cuts[core + 1]]
                    for tid in inputs[u] & common}
        actual = {tid for u in common_copy[core] for tid in tout[u] & common}
        if actual != expected:
            raise GuardFailure("Task shared-input COPY coverage mismatch")
    for link in links:
        core, copy_id = link["target_core"], link["target_copy_in_id"]
        _, _, _, tc, _, tout = taskports[core]
        readers = {v for tid in tout[copy_id] for v in tc[tid] if v in compute}
        js = {owner_job[v] for v in readers}
        if len(js) != 1:
            raise GuardFailure("activation COPY shared across jobs")
        gate_copy[core][next(iter(js))].append(copy_id)
    valid = set(range(len(jobs)))
    for core in range(1, k):
        rawrank = {u: i for i, u in enumerate(raw_words[core])}
        last_common = max((rawrank[u] for u in common_copy[core]), default=-1)
        valid &= {j for j in range(len(jobs)) if gate_copy[core][j]
                  and last_common < min(rawrank[u] for u in gate_copy[core][j])}
    if not valid:
        raise GuardFailure("no unique deterministic raw-late pilot")
    pilot = min(valid, key=lambda j: min(jobs[j]))
    permutation = [pilot] + [j for j in range(len(jobs)) if j != pilot]
    mapping = dict(oldmap)
    next_sg = max(mapping.values()) + 1
    for core in range(1, k):
        for u in jobs[pilot][cuts[core]:cuts[core + 1]]:
            mapping[u] = next_sg
        next_sg += 1
    schedules = []
    for core, (left, right) in enumerate(zip(cuts, cuts[1:])):
        word = []
        for j in permutation:
            for u in jobs[j][left:right]:
                sg = mapping[u]
                if not word or word[-1] != sg:
                    word.append(sg)
        if len(word) != len(set(word)):
            raise GuardFailure("candidate repeats subgraph in core order")
        schedules.append(word)
    plan = {"node_to_subgraph": {str(u): mapping[u] for u in oldmap},
            "core_schedules": schedules}

    records, self_words, self_annotations = [], {}, {}
    for core in range(k):
        graph_core = task_graphs[core]
        to, tt, tp, tc, ti, tout = taskports[core]
        order_rank = {sg: i for i, sg in enumerate(schedules[core])}
        buckets = [[] for _ in schedules[core]]
        annotation = {}
        for u in raw_words[core]:
            op = to[u]
            if u in compute:
                sg = mapping[u]
            elif op["op"] == "COPY_IN":
                readers = {v for tid in tout[u] if tt[tid]["pos"] != "DDR"
                           for v in tc[tid] if v in compute}
                if not readers:
                    raise GuardFailure("unassigned internal COPY_IN")
                sg = min((mapping[v] for v in readers), key=order_rank.get)
            elif op["op"] == "COPY_OUT":
                writers = {v for tid in ti[u] if tt[tid]["pos"] != "DDR"
                           for v in tp[tid] if v in compute}
                if not writers:
                    raise GuardFailure("unassigned internal COPY_OUT")
                sg = max((mapping[v] for v in writers), key=order_rank.get)
            else:
                raise GuardFailure("unexpected Task operation")
            annotation[u] = sg
            buckets[order_rank[sg]].append(u)
        seq = [u for bucket in buckets for u in bucket]
        self_words[core] = seq
        self_annotations[core] = annotation
        expected_compute = [u for j in permutation for u in jobs[j][cuts[core]:cuts[core + 1]]]
        if [u for u in seq if u in compute] != expected_compute:
            raise GuardFailure("compute projection changed")
        prefix = seq[:len(common_copy[core])]
        if core and set(prefix) != common_copy[core]:
            raise GuardFailure("shared inputs are not the full Task prefix")
        peaks = _interval_peaks(graph_core, seq, capacity)
        records.append({"core": core, "prefix_copy_ids": prefix if core else [],
                        "pre_step2_word": seq, "interval_peaks": peaks})

    try:
        second = skeleton(graph, plan, bandwidth, capacity,
                          ledger=ledger)  # candidate derive included
    except MulticoreCutError as error:
        raise GuardFailure(f"candidate plan rejected by official derive: {error}") from error
    if second["cross_links"] != links:
        raise GuardFailure("candidate cross links changed")
    snapshots = {"anchor": {}, "candidate": {}, "cross_links": links,
                 "frozen_p3_source_sha256": OFFICIAL_SHA256}
    for core in range(k):
        old, new = anchor_data[core], second["tasks_data"][core]
        old_graph = task_graphs[core]
        new_graph = {"ops": new["ops"], "tensors": list(new["tensors"].values()),
                     "edges": new["edges"]}
        if new_graph != old_graph:
            raise GuardFailure("candidate Task graph or COPY IDs changed")
        if new["subgraph_order"] != schedules[core]:
            raise GuardFailure("candidate official subgraph order changed")
        if new["op_subgraph"] != self_annotations[core]:
            raise GuardFailure("official COPY/subgraph annotation differs from local transform")
        ledger["official_priority_calls"] += 1
        try:
            official_seq = scene_b._prioritize_task_seq(
                new_graph, raw_words[core], new["op_subgraph"], new["subgraph_order"])
        except scene_b.SceneBEvaluationError as error:
            raise GuardFailure(f"candidate official priority rejected: {error}") from error
        if official_seq != self_words[core]:
            raise GuardFailure("official bucketed seq differs from local transform")
        # Every managed input in a Task must have a physical local producer.
        to, tt, tp, tc, ti, tout = taskports[core]
        if any(tt[tid]["pos"] in capacity and tc[tid] and not tp[tid] for tid in tt):
            raise GuardFailure("Task has initial on-chip resident tensor")
        if core:
            prefix = records[core]["prefix_copy_ids"]
            if set(prefix) != common_copy[core]:
                raise GuardFailure("shared input prefix incomplete")
            for copy_id in prefix:
                if (to[copy_id]["op"] != "COPY_IN" or len(ti[copy_id]) != 1
                        or len(tout[copy_id]) != 1
                        or next(iter(tout[copy_id])) not in common
                        or not all(tt[tid]["pos"] == "DDR" and not tp[tid]
                                   for tid in ti[copy_id])
                        or any(link["target_core"] == core
                               and link["target_copy_in_id"] == copy_id for link in links)):
                    raise GuardFailure("prefix COPY has local/cross predecessor")
            head = jobs[pilot][cuts[core]]
            if not any(head in tc[tid] for copy_id in gate_copy[core][pilot]
                       for tid in tout[copy_id]):
                raise GuardFailure("pilot stage head lacks actual cross-core COPY gate")
            for u, v in zip(jobs[pilot][cuts[core]:cuts[core + 1]],
                            jobs[pilot][cuts[core] + 1:cuts[core + 1]]):
                if not any(u in tp[tid] and v in tc[tid] for tid in ti[v]):
                    raise GuardFailure("pilot stage chain not present in Task graph")
            used = {pos: 0 for pos in capacity}
            for copy_id in prefix:
                for tid in tout[copy_id]:
                    if tt[tid]["pos"] in used:
                        used[tt[tid]["pos"]] += tt[tid]["size"]
            if any(used[pos] > capacity[pos] for pos in capacity):
                raise GuardFailure("prefix exceeds virgin capacity")
            records[core]["virgin_prefix_bytes"] = used
        snapshots["anchor"][core] = {"graph": old_graph, "raw_seq": raw_words[core],
                                      "op_subgraph": old["op_subgraph"],
                                      "subgraph_order": old["subgraph_order"]}
        snapshots["candidate"][core] = {"graph": new_graph,
                                         "raw_seq_reused": raw_words[core],
                                         "op_subgraph": new["op_subgraph"],
                                         "subgraph_order": new["subgraph_order"],
                                         "pre_step2_word": official_seq}
    metadata = {"strategy": "pilot_prefix_bucket", "pilot": pilot,
                "job_permutation": permutation, "cuts": list(cuts), "cores": records,
                "scope": "static pre-Step2 certificate; no Step2/3 or E0",
                "ledger": {**ledger, "frozen_p3_source_sha256": OFFICIAL_SHA256}}
    return plan, metadata, snapshots
