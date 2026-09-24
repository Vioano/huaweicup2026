"""Necessary P3 COPY-service lower bound for guarded singleton M/V plans.

This is a static rejection certificate, not an evaluator or legality check.
"""
from __future__ import annotations

from . import pipe_bound
from .construct import Index, derive_multicore_plan
from multicore_cut_evaluate_problem_1 import _original_tensor_views


UnsupportedBound = pipe_bound.UnsupportedBound


def _positive_integer(value, name):
    if type(value) is not int or value <= 0:
        raise UnsupportedBound(f"{name} must be a positive integer")


def _service(size, bandwidth):
    return max(1, (size + bandwidth - 1) // bandwidth)


def analyze(graph, plan, delay, ddr_bandwidth, cache_bandwidth):
    """Return necessary COPY-service and prior bounds; make zero E0 calls.

    Arguments must be the frozen P3 settings for the execution being bounded.
    Unsupported graph shapes fail closed instead of guessing a COPY route.
    """
    _positive_integer(ddr_bandwidth, "ddr_bandwidth")
    _positive_integer(cache_bandwidth, "cache_bandwidth")
    # Preserve every guard of the existing bound, including COPY contraction.
    previous = pipe_bound.analyze(graph, plan, delay)
    index = Index(graph)
    view = derive_multicore_plan(graph, plan)
    owner = {u: view["core_by_subgraph"][sg]
             for u, sg in view["mapping"].items()}
    producers, consumers, direct = _original_tensor_views(graph)
    adjacency = {u: {} for u in index.ops}
    charged = []
    charged_by_pair = {}
    # A miss may be faster than a hit in a custom configuration. The frozen
    # configuration has Cache=250 > DDR=60; choosing either path's fastest
    # rate also keeps this necessary bound conservative outside that ratio.
    fastest_read_bandwidth = max(ddr_bandwidth, cache_bandwidth)

    def add_edge(u, v, lag, reason, evidence=None):
        edge = adjacency[u].setdefault(v, {"delay": 0, "reasons": set()})
        edge["delay"] = max(edge["delay"], lag)
        edge["reasons"].add(reason)
        if evidence is not None:
            charged.append(evidence)
            charged_by_pair.setdefault((u, v), []).append(evidence)

    # Match pipe_bound's proved original dependencies before adding physical
    # service. An edge without an identified COPY pair retains only delay.
    original_edges = set()
    for tensor in graph["tensors"]:
        tid = tensor["id"]
        original_edges.update((u, v) for u in producers.get(tid, ())
                              for v in consumers.get(tid, ())
                              if u in index.ops and v in index.ops and u != v)
    original_edges.update((edge["source"], edge["target"]) for edge in direct
                          if edge["source"] in index.ops
                          and edge["target"] in index.ops)
    for u, v in sorted(original_edges):
        add_edge(u, v, delay if owner[u] != owner[v] else 0,
                 "original_compute_dependency")

    def connection(u, v, size, kind, identity):
        if u not in index.ops or v not in index.ops or u == v:
            return
        if owner[u] == owner[v]:
            add_edge(u, v, 0, "original_compute_dependency")
            return
        lag = (delay + _service(size, ddr_bandwidth)
               + _service(size, fastest_read_bandwidth))
        evidence = {"source": u, "target": v,
                    "source_core": owner[u], "target_core": owner[v],
                    "kind": kind, "id": identity, "size_bytes": size,
                    "copy_out_min_cycles": _service(size, ddr_bandwidth),
                    "release_delay_cycles": delay,
                    "copy_in_min_cycles": _service(size, fastest_read_bandwidth),
                    "lag_cycles": lag}
        add_edge(u, v, lag, "cross_core_copy_pair", evidence)

    for tensor in graph["tensors"]:
        tid = tensor["id"]
        size = tensor.get("size")
        if type(size) is not int or size < 0 or tensor.get("pos") not in {"DDR", "L1", "UB"}:
            raise UnsupportedBound(f"tensor {tid}: requires nonnegative integer size and DDR/L1/UB pos")
        original_producers = producers.get(tid, set())
        if len(original_producers) > 1:
            raise UnsupportedBound(f"tensor {tid}: multiple original producers")
        # A graph input has no eligible source compute op. Official P3 inserts
        # only a per-consumer-core COPY_IN for that case.
        for u in sorted(original_producers & index.ops.keys()):
            for v in sorted(consumers.get(tid, set()) & index.ops.keys()):
                connection(u, v, size, "tensor", tid)

    for ordinal, edge in enumerate(direct):
        size = edge.get("data_size", 0)
        if type(size) is not int or size < 0:
            raise UnsupportedBound(f"direct edge {ordinal}: requires nonnegative integer data_size")
        connection(edge["source"], edge["target"], size, "direct", ordinal)

    # Every old dependency must remain present. This also makes future
    # upstream changes fail closed instead of silently weakening the bound.
    old_edges = {(u, v) for u, vs in index.succ.items() for v in vs}
    if not old_edges.issubset({(u, v) for u, vs in adjacency.items() for v in vs}):
        raise UnsupportedBound("unmatched original compute dependency")

    for core in range(view["num_cores"]):
        previous_by_pipe = {}
        for sg in view["core_orders"][core]:
            u = view["nodes_by_subgraph"][sg][0]
            pipe = index.ops[u]["pipe"]
            if pipe in previous_by_pipe:
                add_edge(previous_by_pipe[pipe], u, 0, "same_core_pipe_fifo")
            previous_by_pipe[pipe] = u

    bound = pipe_bound._longest_path(index.ops, adjacency, owner, True)
    path_edges = []
    for u, v in zip(bound["path_ops"], bound["path_ops"][1:]):
        edge = adjacency[u][v]
        if owner[u] != owner[v]:
            path_edges.append({"source": u, "target": v,
                               "lag_cycles": edge["delay"],
                               "charged_connections": [item for item in charged_by_pair.get((u, v), ())
                                                       if item["lag_cycles"] == edge["delay"]]})
    bound["charged_path_edges"] = path_edges
    return {"schema": "q3-copy-min-bound-v1", "scope": "frozen P3 singleton M/V",
            "execution_legality_proved": False, "official_optimality_proved": False,
            "official_evaluations": 0, "delay_cycles": delay,
            "ddr_bandwidth_bytes_per_cycle": ddr_bandwidth,
            "cache_bandwidth_bytes_per_cycle": cache_bandwidth,
            "legacy_bound": previous["with_cross_core_delay"],
            "copy_min_bound": bound, "charged_connections": charged}
