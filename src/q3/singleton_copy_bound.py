"""Optimistic COPY/FIFO relaxation for a fixed singleton P3 plan.

No Task construction, Step2/3 or event simulation. This is not a bound on the
optimum over other plans. See docs/a/q3/SINGLETON_COPY_BOUND.md for the guards.
"""
from collections import defaultdict, deque

from .construct import Index, derive_multicore_plan
from .pipe_bound import UnsupportedBound, analyze as compute_bound
from multicore_cut_evaluate_problem_1 import _original_tensor_views


def analyze(graph, plan, *, ddr_bandwidth, cache_bandwidth,
            cross_core_delay_cycles):
    if any(type(b) is not int or b <= 0 for b in (ddr_bandwidth, cache_bandwidth)):
        raise UnsupportedBound("positive integer bandwidths required")
    base = compute_bound(graph, plan, cross_core_delay_cycles)
    index = Index(graph)
    view = derive_multicore_plan(graph, plan)
    mapping = view["mapping"]
    owner = {u: view["core_by_subgraph"][sg] for u, sg in mapping.items()}
    rank = {u: view["core_orders"][owner[u]].index(sg) for u, sg in mapping.items()}
    producers, consumers, direct = _original_tensor_views(graph)
    if any(e["source"] in owner and e["target"] in owner
           and owner[e["source"]] != owner[e["target"]] for e in direct):
        raise UnsupportedBound("cross-core direct op edges are outside this COPY proof")
    tensors = {t["id"]: t for t in graph["tensors"]}
    for tensor in tensors.values():
        if set(tensor) - {"id", "size", "pos"}:
            raise UnsupportedBound("original tensor alias/metadata fields are not proved")
        if type(tensor["size"]) is not int or tensor["size"] < 0:
            raise UnsupportedBound("nonnegative integer tensor sizes required")

    nodes = {}
    edges = defaultdict(dict)

    def node(key, duration, **metadata):
        nodes[key] = {"duration": duration, **metadata}

    def edge(u, v, delay=0):
        edges[u][v] = max(edges[u].get(v, 0), delay)

    def compute(u):
        return f"compute:{u}"

    for u in index.order:
        node(compute(u), index.duration(u), kind="compute", op_id=u, core=owner[u])
        for v in index.succ[u]:
            edge(compute(u), compute(v), cross_core_delay_cycles if owner[u] != owner[v] else 0)
    for core, schedule in view["core_orders"].items():
        previous = {}
        for sg in schedule:
            u = view["nodes_by_subgraph"][sg][0]
            pipe = index.ops[u]["pipe"]
            if pipe in previous:
                edge(compute(previous[pipe]), compute(u))
            previous[pipe] = u

    groups = defaultdict(lambda: defaultdict(list))
    copies = []
    fastest = max(ddr_bandwidth, cache_bandwidth)
    for tid in sorted(tensors):
        ps = sorted(u for u in producers.get(tid, ()) if u in owner)
        cs = sorted(u for u in consumers.get(tid, ()) if u in owner)
        if len(ps) > 1:
            raise UnsupportedBound("multiple original compute producers are outside proof")
        if not cs:
            continue
        reader_cores = sorted({owner[u] for u in cs})
        for core in reader_cores:
            local = [u for u in cs if owner[u] == core]
            if ps and owner[ps[0]] == core:
                continue
            kind = "cross_activation" if ps else "external_input"
            # No other Task can insert this external logical key. Its first
            # original COPY must miss even if Step2 later reloads that key.
            cold = not ps and len(reader_cores) == 1
            bandwidth = ddr_bandwidth if cold else fastest
            size = tensors[tid]["size"]
            duration = max(1, (size + bandwidth - 1) // bandwidth)
            key = f"copy:{tid}:{core}"
            first_rank = min(rank[u] for u in local)
            record = {"node": key, "tensor_id": tid, "core": core,
                      "bucket_rank": first_rank, "kind": kind,
                      "first_copy_proved_cold": cold, "bytes": size,
                      "duration_lower_bound": duration}
            copies.append(record)
            node(key, duration, **{k: v for k, v in record.items()
                                  if k not in {"node", "duration_lower_bound"}})
            groups[core][first_rank].append(key)
            if ps:
                # COPY_OUT service and source memory constraints are omitted.
                edge(compute(ps[0]), key, cross_core_delay_cycles)
            for u in local:
                edge(key, compute(u))

    # Stable subgraph bucketing orders different buckets. Intra-bucket COPY
    # serialization is deliberately dropped; do not sum work after max release.
    for core, buckets in groups.items():
        previous_barrier = None
        for bucket, keys in sorted(buckets.items()):
            barrier = f"barrier:{core}:{bucket}"
            node(barrier, 0, kind="copy_bucket_end", core=core, bucket_rank=bucket)
            for key in keys:
                if previous_barrier is not None:
                    edge(previous_barrier, key)
                edge(key, barrier)
            previous_barrier = barrier

    indegree = dict.fromkeys(nodes, 0)
    for targets in edges.values():
        for v in targets:
            indegree[v] += 1
    ready = deque(u for u in nodes if not indegree[u])
    starts = dict.fromkeys(nodes, 0)
    parents = {}
    visited = 0
    while ready:
        u = ready.popleft()
        visited += 1
        for v, delay in edges.get(u, {}).items():
            value = starts[u] + nodes[u]["duration"] + delay
            if value > starts[v]:
                starts[v], parents[v] = value, u
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)
    if visited != len(nodes):
        raise UnsupportedBound("relaxed fixed-plan COPY/FIFO constraints contain a cycle")
    last = max(nodes, key=lambda u: starts[u] + nodes[u]["duration"], default=None)
    path = []
    while last is not None:
        path.append({"node": last, "earliest_start": starts[last], **nodes[last]})
        last = parents.get(last)
    path.reverse()
    lower = max((starts[u] + nodes[u]["duration"] for u in nodes), default=0)
    return {"schema": "q3-singleton-copy-relaxation-v1",
            "scope": "fixed singleton M/V plan, not all-plan optimum",
            "lower_bound_cycles": lower,
            "compute_only_lower_bound_cycles": base["with_cross_core_delay"]["lower_bound_cycles"],
            "execution_legality_proved": False, "official_evaluations": 0,
            "task_builds": 0, "local_step3_simulations": 0,
            "settings": {"ddr_bandwidth": ddr_bandwidth, "cache_bandwidth": cache_bandwidth,
                         "cross_core_delay_cycles": cross_core_delay_cycles},
            "virtual_copy_count": len(copies),
            "proved_cold_first_input_count": sum(c["first_copy_proved_cold"] for c in copies),
            "nodes": len(nodes), "edges": sum(map(len, edges.values())),
            "copies": copies, "path": path}
