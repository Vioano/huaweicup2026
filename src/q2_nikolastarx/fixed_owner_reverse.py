"""Fixed-owner sink-first retiming on a virtual reversed chain DAG.

This changes only per-core singleton priorities. Its Pipe calendar is a static
ordering heuristic, never an official score, lower bound, or DDR simulation.
"""
from __future__ import annotations

import heapq
import math

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan, topo
from .gap_calendar import earliest, empty, reserve
from .gap_candidate import _chain_dag


def _check_total_order(index, rows):
    """Validate original data precedence together with all core order edges."""
    if sorted(u for row in rows for u in row) != sorted(index.ops):
        raise UnsupportedStructure('plan must cover each original operation exactly once')
    combined = {u: set(index.succ[u]) for u in index.ops}
    for row in rows:
        for u, v in zip(row, row[1:]):
            combined[u].add(v)
    try:
        topo(index.ops, combined)
    except ValueError as error:
        raise UnsupportedStructure('original data and core total orders form a cycle') from error


def _physical_edge_lags(index, bandwidth, cross_delay):
    """Match _chain_dag's isolated COPY estimate at original op-edge granularity."""
    sizes = {}
    for tid, producers in index.producers.items():
        for u in producers:
            for v in index.consumers[tid]:
                if u != v:
                    sizes.setdefault((u, v), []).append(index.tensors[tid]['size'])
    for v, inputs in index.direct_inputs.items():
        for u, size in inputs:
            sizes.setdefault((u, v), []).append(size)
    return {(u, v): cross_delay + 2 * sum(max(1, math.ceil(size / bandwidth))
                                          for size in edge_sizes)
            for (u, v), edge_sizes in sizes.items()}


def retime(graph, plan, config):
    """Return one guarded deterministic order with exactly the input placement."""
    bandwidth = config['bandwidth']
    cross_delay = config['cross_core_copy_delay_cycles']
    if (type(bandwidth) not in (int, float) or not math.isfinite(bandwidth) or bandwidth <= 0
            or type(cross_delay) is not int or cross_delay < 0):
        raise ValueError('invalid fixed parameters')
    index = DAGIndex(graph)
    forward_chains, _, _, _, _ = _chain_dag(index, bandwidth, cross_delay)
    edge_lag = _physical_edge_lags(index, bandwidth, cross_delay)
    try:
        view = derive_multicore_plan(graph, plan)
    except Exception as error:
        raise UnsupportedStructure('input plan failed structural validation') from error
    if any(len(nodes) != 1 for nodes in view['nodes_by_subgraph'].values()):
        raise UnsupportedStructure('requires singleton subgraphs')
    if len(plan['core_schedules']) not in range(1, 6):
        raise UnsupportedStructure('requires one to five cores')
    owner = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
    inverse = {sg: u for u, sg in view['mapping'].items()}
    input_rows = [[inverse[sg] for sg in row] for row in plan['core_schedules']]
    _check_total_order(index, input_rows)

    # Split a maximal chain only at a core boundary. A chain must not be
    # silently assigned to the first operation's core.
    segments, segment_of, chain_of = [], {}, {}
    for chain_id, chain in enumerate(forward_chains):
        for u in chain:
            chain_of[u] = chain_id
            if not segments or u == chain[0] or owner[u] != owner[segments[-1][-1]]:
                segments.append([])
            segment_of[u] = len(segments) - 1
            segments[-1].append(u)
    count = len(segments)
    forward_pred = [set() for _ in segments]
    forward_succ = [set() for _ in segments]
    forward_lag = {}
    split_cross_lags = {}
    for u in index.ops:
        for v in index.succ[u]:
            a, b = segment_of[u], segment_of[v]
            if a == b:
                continue
            forward_succ[a].add(b)
            forward_pred[b].add(a)
            static_lag = edge_lag[u, v]
            forward_lag[a, b] = max(forward_lag.get((a, b), 0), static_lag)
            if chain_of[u] == chain_of[v] and owner[u] != owner[v]:
                split_cross_lags[f'{u}->{v}'] = static_lag
    try:
        forward_order = topo(range(count), forward_succ)
    except ValueError as error:
        raise UnsupportedStructure('owner-split segment graph has a cycle') from error
    pred, succ = forward_succ, forward_pred
    lag = {(b, a): value for (a, b), value in forward_lag.items()}
    virtual_chains = [list(reversed(segment)) for segment in segments]
    virtual_order = list(reversed(forward_order))
    rank = {}
    for j in reversed(virtual_order):
        rank[j] = sum(index.duration(u) for u in virtual_chains[j]) + max(
            (rank[v] for v in succ[j]), default=0)
    degree = [len(row) for row in pred]
    ready = [(-rank[j], min(segments[j]), j) for j in range(count) if degree[j] == 0]
    heapq.heapify(ready)
    pipes = sorted({op['pipe'] for op in index.ops.values()})
    calendars = [{pipe: empty() for pipe in pipes} for _ in input_rows]
    starts, finish, dispatched = {}, {}, []
    while ready:
        _, _, j = heapq.heappop(ready)
        core = owner[segments[j][0]]
        release = max((finish[p] + (lag[p, j] if owner[segments[p][0]] != core else 0)
                       for p in pred[j]), default=0)
        for u in virtual_chains[j]:
            pipe, duration = index.ops[u]['pipe'], index.duration(u)
            start = earliest(calendars[core][pipe], release, duration)
            calendars[core][pipe] = reserve(calendars[core][pipe], start, duration)
            starts[u] = start
            release = start + duration
        finish[j] = release
        dispatched.append(j)
        for v in sorted(succ[j]):
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, (-rank[v], min(segments[v]), v))
    if len(dispatched) != count or len(starts) != len(index.ops):
        raise UnsupportedStructure('incomplete reverse fixed-owner retiming')

    rows = [[] for _ in input_rows]
    for u in index.ops:
        rows[owner[u]].append(u)
    rows = [list(reversed(sorted(row, key=lambda u: (starts[u], u)))) for row in rows]
    _check_total_order(index, rows)
    mapping = dict(plan['node_to_subgraph'])
    key_by_op = {int(key): key for key in mapping}
    output = {'node_to_subgraph': mapping,
              'core_schedules': [[mapping[key_by_op[u]] for u in row] for row in rows]}
    try:
        derive_multicore_plan(graph, output)
    except Exception as error:
        raise UnsupportedStructure('output failed structural validation') from error
    return output, {
        'selected': 'fixed_owner_reverse', 'segment_count': count,
        'owner_split_count': count - len(forward_chains),
        'modeled_reverse_compute_finish': max(finish.values(), default=0),
        'modeled_reverse_op_starts': {str(u): starts[u] for u in sorted(starts)},
        'modeled_split_cross_core_lags': split_cross_lags,
        'online_E0_calls': 0,
        'scope': ('Fixed singleton partition and owner; static reverse Pipe calendar only. '
                  'No official Makespan, COPY contention, capacity, spill, or dynamic DDR guarantee. '
                  'Byte invariance is conditional on both plans actually having zero spill.'),
    }
