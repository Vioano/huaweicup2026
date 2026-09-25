"""Guarded R8 query-flow affinity proposal; no evaluator or solver integration.

Only the original compute DAG and M/V FIFO are scored. The P3 Task support
certificate is derived from its tensor-ID reconstruction rule, not a runtime
simulation. Unrecognized graphs are deliberately rejected.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from pathlib import Path
import heapq

from .attention_rows import _ports, _recognize
from .construct import UnsupportedStructure

PIPES = ("PIPE_M", "PIPE_V")
STAGES = ("S", "P", "A", "O")


def _ancestors(index, seeds):
    seen, stack = set(), list(seeds)
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)
        stack.extend(index.pred[u])
    return seen


def _ancestors_without(index, seeds, excluded_edges):
    seen, stack = set(), list(seeds)
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)
        stack.extend(p for p in index.pred[u] if (p, u) not in excluded_edges)
    return seen


def _descendants(index, seeds):
    seen, stack = set(), list(seeds)
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)
        stack.extend(index.succ[u])
    return seen


def _decompose(index, ports, rows):
    """Assign every compute op to S or one P/A/O flow, then audit all edges."""
    q_ops = {row["q"] for row in rows}
    q_usage = defaultdict(set)
    k_usage = defaultdict(set)
    v_usage = defaultdict(set)
    for u in q_ops:
        for t in ports.inputs[u]:
            q_usage[t].add(u)
    for row in rows:
        for u in row["k"]:
            for t in ports.inputs[u]:
                k_usage[t].add(u)
        for u in row["v"]:
            for t in ports.inputs[u]:
                v_usage[t].add(u)
    keys = []
    for row in rows:
        projections = (row["q"], *row["k"], *row["v"])
        if any(index.ops[u]["op"] != "MATMUL" for u in projections):
            raise UnsupportedStructure("query frontier requires MATMUL projections")
        candidates = [t for t in ports.inputs[row["q"]] if k_usage[t] and v_usage[t]]
        if not candidates:
            raise UnsupportedStructure("Q projection has no raw input shared with K/V projections")
        # A parameter shared by every Q head can also occur at K/V. It is not
        # a flow key when a more local raw input exists. Equal evidence is
        # ambiguous and deliberately rejected.
        least = min(len(q_usage[t]) for t in candidates)
        best = [t for t in candidates if len(q_usage[t]) == least]
        if len(best) != 1:
            raise UnsupportedStructure("cannot uniquely identify raw query input")
        keys.append(best[0])
    flow_keys = sorted(set(keys))
    flow_of_key = {key: i for i, key in enumerate(flow_keys)}
    row_flow = [flow_of_key[key] for key in keys]
    a_nodes = [set() for _ in flow_keys]
    projections = [set() for _ in flow_keys]
    all_a = set()
    for row, i in zip(rows, row_flow):
        a_nodes[i].update(row["nodes"])
        all_a.update(row["nodes"])
        for u in (row["q"], *row["k"], *row["v"]):
            matches = [j for j, key in enumerate(flow_keys) if key in ports.inputs[u]]
            if len(matches) != 1:
                raise UnsupportedStructure("K/V projection has ambiguous query source")
            projections[matches[0]].add(u)
    if any(not nodes for nodes in projections):
        raise UnsupportedStructure("query flow has no projection")

    if sum(map(len, a_nodes)) != len(all_a):
        raise UnsupportedStructure("attention rows overlap")
    kv_edges = {(u, v) for row in rows for u in (*row["k"], *row["v"])
                for v in row["nodes"] if v in index.succ[u]}
    outputs = []
    for i, nodes in enumerate(a_nodes):
        descendants = _descendants(index, nodes)
        if (descendants & all_a) - nodes:
            raise UnsupportedStructure("one query row feeds a different query flow")
        outputs.append(descendants - all_a)
    if any(outputs[i] & outputs[j] for i in range(len(outputs)) for j in range(i + 1, len(outputs))):
        raise UnsupportedStructure("post-row cross-flow join")
    all_o = set().union(*outputs)
    if all_o & set().union(*projections):
        raise UnsupportedStructure("post-row path returns to a projection")

    # Exclude only recognized K/V broadcasts while tracing each private
    # flow. An upstream parameter used solely by several O branches is then
    # found as a common ancestor even if it feeds no Q/K/V projection.
    ancestors = [_ancestors_without(index, projections[i] | a_nodes[i] | outputs[i], kv_edges)
                 for i in range(len(flow_keys))]
    shared = {u for u in index.ops if sum(u in group for group in ancestors) > 1}
    shared = _ancestors(index, shared)
    if shared & (all_a | all_o | set().union(*projections)):
        raise UnsupportedStructure("shared upstream depends on a private row/output/projection")
    label = {u: ("S", None) for u in shared}
    for i, nodes in enumerate(ancestors):
        for u in nodes - shared - all_a - all_o:
            if u in label and label[u] != ("P", i):
                raise UnsupportedStructure("private projection ancestry overlaps another flow")
            label[u] = ("P", i)
    for i, nodes in enumerate(a_nodes):
        for u in nodes:
            if u in label and label[u] != ("A", i):
                raise UnsupportedStructure("attention row overlaps the upstream frontier")
            label[u] = ("A", i)

    for i, nodes in enumerate(outputs):
        for u in nodes:
            if u in label and label[u] != ("O", i):
                raise UnsupportedStructure("row descendant regresses stage or joins flows")
            label[u] = ("O", i)
    remaining = set(index.ops) - set(label)
    if remaining:
        raise UnsupportedStructure("compute operations outside recognized query flows")

    rank = {stage: n for n, stage in enumerate(STAGES)}
    for u in index.ops:
        su, fu = label[u]
        for v in index.succ[u]:
            sv, fv = label[v]
            if rank[su] > rank[sv]:
                raise UnsupportedStructure("original compute edge regresses stage")
            if su == "S" and sv == "S":
                continue
            if su == "S" and sv != "S":
                continue
            if fu == fv:
                continue
            if (su, sv) != ("P", "A") or (u, v) not in kv_edges:
                raise UnsupportedStructure("unexpected cross-flow compute edge")
    return label, flow_keys, rows


def _shared_components(index, label):
    shared = {u for u, (stage, _) in label.items() if stage == "S"}
    components = []
    while shared:
        root = min(shared)
        part, todo = set(), [root]
        while todo:
            u = todo.pop()
            if u not in shared:
                continue
            shared.remove(u)
            part.add(u)
            todo.extend(index.pred[u] | index.succ[u])
        components.append(part)
    return components


def _support(index, ports, owner, capacity):
    """Exact P3 on-chip Task tensor IDs under _ports' no-direct-edge guard."""
    support = [{pos: set() for pos in capacity} for _ in range(max(owner.values()) + 1)]
    for tid, tensor in ports.tensors.items():
        touched = {owner[u] for u in ports.consumers[tid] | {ports.producer.get(tid)}
                   if u in owner}
        pos = "UB" if tensor["pos"] == "DDR" else tensor["pos"]
        if pos not in capacity:
            raise UnsupportedStructure("P3 local tensor has an unknown memory pool")
        if type(tensor["size"]) is not int or tensor["size"] < 0:
            raise UnsupportedStructure("invalid physical tensor size")
        for c in touched:
            support[c][pos].add(tid)
    totals = [{pos: sum(ports.tensors[t]["size"] for t in support[c][pos])
               for pos in capacity} for c in range(len(support))]
    return totals


def _choose_shared(index, ports, label, flow_owner, components):
    owner = {u: flow_owner[i] for u, (_, i) in label.items() if i is not None}
    for part in components:
        trials = []
        for c in sorted(set(flow_owner.values())):
            bytes_out = 0
            for u in part:
                for t in ports.outputs[u]:
                    destinations = {owner[v] for v in ports.consumers[t] if v in owner}
                    bytes_out += ports.tensors[t]["size"] * len(destinations - {c})
            trials.append((bytes_out, c))
        chosen = min(trials)[1]
        owner.update((u, chosen) for u in part)
    return owner


def _stage_word(index, label, owner, cores, delay):
    """Schedule stages in priority order without a global time barrier."""
    bottom = {}
    for u in reversed(index.order):
        bottom[u] = index.duration(u) + max((bottom[v] for v in index.succ[u]), default=0)
    free = {(c, p): 0 for c in range(cores) for p in PIPES}
    finish, words = {}, [[] for _ in range(cores)]
    for stage in STAGES:
        nodes = {u for u, (s, _) in label.items() if s == stage}
        degree = {u: len(index.pred[u] & nodes) for u in nodes}
        ready = {u for u in nodes if degree[u] == 0}
        while ready:
            candidates = []
            for u in ready:
                if not index.pred[u] <= finish.keys():
                    raise UnsupportedStructure("original edge crosses backward over a stage")
                release = max((finish[v] + (delay if owner[v] != owner[u] else 0)
                               for v in index.pred[u]), default=0)
                start = max(release, free[owner[u], index.ops[u]["pipe"]])
                candidates.append((start, -bottom[u], u))
            start, _, u = min(candidates)
            ready.remove(u)
            finish[u] = start + index.duration(u)
            free[owner[u], index.ops[u]["pipe"]] = finish[u]
            words[owner[u]].append(u)
            for v in index.succ[u] & nodes:
                degree[v] -= 1
                if degree[v] == 0:
                    ready.add(v)
        if any(value for value in degree.values()):
            raise UnsupportedStructure("same-stage dependency cycle")
    if set(finish) != set(index.ops):
        raise UnsupportedStructure("stage word does not cover every compute operation")
    return words


def _longest(index, words, owner, delay):
    edges = {u: {v: int(owner[u] != owner[v]) for v in index.succ[u]}
             for u in index.ops}
    for word in words:
        tails = {}
        for u in word:
            pipe = index.ops[u]["pipe"]
            if pipe in tails:
                p = tails[pipe]
                edges[p][u] = max(edges[p].get(u, 0), 0)
            tails[pipe] = u
    degree = dict.fromkeys(index.ops, 0)
    for adjacent in edges.values():
        for v in adjacent:
            degree[v] += 1
    ready = [u for u in degree if degree[u] == 0]
    heapq.heapify(ready)
    zero, weighted, count = {}, {}, {}
    while ready:
        u = heapq.heappop(ready)
        z = zero[u] = zero.get(u, 0)
        w = weighted.get(u, 0)
        crossings = count.get(u, 0)
        for v, remote in edges[u].items():
            zero[v] = max(zero.get(v, 0), z + index.duration(u))
            weighted[v] = max(weighted.get(v, 0), w + index.duration(u) + delay * remote)
            count[v] = max(count.get(v, 0), crossings + remote)
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, v)
    if len(weighted | zero) != len(index.ops) or any(degree.values()):
        raise UnsupportedStructure("compute plus FIFO graph is cyclic")
    l0 = max((zero.get(u, 0) + index.duration(u) for u in index.ops), default=0)
    ld = max((weighted.get(u, 0) + index.duration(u) for u in index.ops), default=0)
    return l0, ld, max(count.values(), default=0)


def _copy_bytes(ports, owner):
    total = 0
    for tid, source in ports.producer.items():
        if source not in owner:
            continue
        destinations = {owner[u] for u in ports.consumers[tid] if u in owner}
        total += ports.tensors[tid]["size"] * len(destinations - {owner[source]})
    return total


def _capacity_from_config():
    from evaluation_validation import read_evaluation_config
    path = Path(__file__).resolve().parents[2] / "data/raw/a/official/data/config.txt"
    return read_evaluation_config(path)["capacity"]


def construct(index, cores, cross_delay=500, *, capacity=None):
    """Return (singleton plan, proxy/certificate info) or UnsupportedStructure."""
    if type(cores) is not int or cores < 1:
        raise ValueError("cores must be a positive integer")
    if type(cross_delay) is not int or cross_delay < 0:
        raise ValueError("cross_delay must be a nonnegative integer")
    capacity = dict(_capacity_from_config() if capacity is None else capacity)
    if set(capacity) != {"L1", "UB"} or any(type(v) is not int or v <= 0 for v in capacity.values()):
        raise ValueError("capacity requires positive integer L1 and UB byte limits")
    ports = _ports(index)  # Includes no direct edges, unique producers and COPY-contraction audit.
    rows = _recognize(index, ports)
    label, flow_keys, rows = _decompose(index, ports, rows)
    r = len(flow_keys)
    if r > cores + 1:
        raise UnsupportedStructure("query streams exceed cores plus one")
    pairs = [None] if r <= cores else list(combinations(range(r), 2))
    components = _shared_components(index, label)
    candidates = []
    rejected_capacity = 0
    for pair in pairs:
        groups = []
        for i in range(r):
            if pair is not None and i == pair[1]:
                continue
            groups.append((i, pair[1]) if pair is not None and i == pair[0] else (i,))
        flow_owner = {i: c for c, group in enumerate(groups) for i in group}
        owner = _choose_shared(index, ports, label, flow_owner, components)
        if set(owner) != set(index.ops):
            raise UnsupportedStructure("owner cover is incomplete")
        support = _support(index, ports, owner, capacity)
        support.extend({pos: 0 for pos in capacity} for _ in range(cores - len(support)))
        if any(total[pos] > capacity[pos] for total in support for pos in capacity):
            rejected_capacity += 1
            continue
        words = _stage_word(index, label, owner, cores, cross_delay)
        l0, ld, max_crossings = _longest(index, words, owner, cross_delay)
        if max_crossings > 2 or ld > l0 + 2 * cross_delay:
            raise UnsupportedStructure("two-crossing certificate failed")
        bytes_out = _copy_bytes(ports, owner)
        candidates.append((ld, bytes_out, groups, words, support, l0, max_crossings))
    if not candidates:
        raise UnsupportedStructure(f"all {len(pairs)} canonical placements exceed physical Task support capacity")
    ld, bytes_out, groups, words, support, l0, crossings = min(candidates, key=lambda c: c[:3])
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {"node_to_subgraph": mapping,
            "core_schedules": [[mapping[str(u)] for u in word] for word in words]}
    return plan, {"strategy": "query_flow_affinity_r8", "flow_count": r,
                  "row_count": len(rows), "canonical_states": len(pairs),
                  "stage_counts": {stage: sum(kind == stage for kind, _ in label.values())
                                   for stage in STAGES},
                  "capacity_rejected_states": rejected_capacity,
                  "selected_groups": [list(group) for group in groups],
                  "query_tensors": flow_keys, "L0_compute_fifo": l0,
                  "Ldelta_compute_fifo": ld, "max_remote_edges_on_path": crossings,
                  "cross_core_tensor_bytes_proxy": bytes_out,
                  "task_support_bytes": support, "capacity_bytes": capacity,
                  "physical_support_certificate": True,
                  "official_evaluation_calls": 0,
                  "scope": "compute plus M/V FIFO proxy; no COPY, DDR, cache or official Makespan claim"}
