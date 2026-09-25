"""Experimental shared-input stationary waves for recognized P2 templates.

One closure-defined wave is shared by every job. This emits a priority plan,
not a simulated schedule or an official quality estimate.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .shared_input_wave import _recognize


def _stages(index, by_job, waves, anchor):
    """Assign each operation to its earliest anchor closure, then the residual."""
    emitted = set()
    stages = []

    def close(u, block):
        stack = [(u, False)]
        while stack:
            node, expanded = stack.pop()
            if node in emitted:
                continue
            if expanded:
                emitted.add(node)
                block.append(node)
            else:
                stack.append((node, True))
                stack.extend((v, False) for v in sorted(index.pred[node], reverse=True))

    for tid in waves:
        block = []
        for row in by_job:
            close(row[anchor[tid]], block)
        stages.append(block)
    residual = []
    for job in index.components:
        for u in job:
            close(u, residual)
    if residual:
        stages.append(residual)
    if len(emitted) != len(index.ops) or sum(map(len, stages)) != len(index.ops):
        raise UnsupportedStructure('closure stages do not cover every eligible operation once')
    return stages


def _balanced_bounds(work, cores):
    """Minimax contiguous partition of normalized per-pipe work; no plans scored."""
    n = len(work)
    k = min(cores, n)
    pipes = sorted({pipe for stage in work for pipe in stage})
    totals = {p: sum(stage[p] for stage in work) for p in pipes}
    prefix = {p: [0] for p in pipes}
    for stage in work:
        for p in pipes:
            prefix[p].append(prefix[p][-1] + stage[p])

    def cost(a, b):
        return max((Fraction(prefix[p][b] - prefix[p][a], totals[p])
                    for p in pipes if totals[p]), default=Fraction(0))

    dp = [[None] * (n + 1) for _ in range(k + 1)]
    prev = [[None] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = Fraction(0)
    for used in range(1, k + 1):
        for b in range(used, n + 1):
            dp[used][b], prev[used][b] = min(
                (max(dp[used - 1][a], cost(a, b)), a)
                for a in range(used - 1, b) if dp[used - 1][a] is not None)
    bounds = [n]
    b = n
    for used in range(k, 0, -1):
        b = prev[used][b]
        bounds.append(b)
    bounds.reverse()
    return bounds, dp[k][n], totals


def build_from_index(index, cores, config):
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    capacity = config['capacity']
    if (set(capacity) != {'L1', 'UB'} or
            any(type(capacity[p]) is not int or capacity[p] < 0 for p in ('L1', 'UB'))):
        raise ValueError('capacity must contain nonnegative integer L1 and UB bytes')
    by_job, waves, anchor = _recognize(index)
    stages = _stages(index, by_job, waves, anchor)
    work = [Counter({p: sum(index.duration(u) for u in stage
                            if index.ops[u]['pipe'] == p)
                     for p in {index.ops[u]['pipe'] for u in stage}})
            for stage in stages]
    bounds, balance, totals = _balanced_bounds(work, cores)
    owner = {}
    for core, (a, b) in enumerate(zip(bounds, bounds[1:])):
        for stage in stages[a:b]:
            owner.update((u, core) for u in stage)
    if len(owner) != len(index.ops):
        raise UnsupportedStructure('stage ownership lost eligible operations')
    mapping = {str(u): i for i, u in enumerate(index.order)}
    rows = [[] for _ in range(cores)]
    # This one global stage-major sequence is topological by closure construction.
    for stage in stages:
        for u in stage:
            rows[owner[u]].append(mapping[str(u)])
    plan = {'node_to_subgraph': mapping, 'core_schedules': rows}
    view = derive_multicore_plan(index.graph, plan)
    if set(view['mapping']) != set(index.ops) or sum(map(len, rows)) != len(index.ops):
        raise UnsupportedStructure('official structural derivation changed coverage')

    shared_owners = {t: {owner[row[anchor[t]]] for row in by_job} for t in waves}
    if any(len(owners) != 1 for owners in shared_owners.values()):
        raise UnsupportedStructure('shared input split across cores')
    # Same tensor/core copy granularity as the P2 builder, ignoring capacity
    # spills and Step3 timing. A source-to-destination crossing costs out+in.
    external = {t for u in index.ops for t in index.inputs[u] if not index.producers[t]}
    input_bytes = sum(index.tensors[t]['size'] * len({owner[u] for u in index.consumers[t]})
                      for t in external)
    crossing_bytes = sum(2 * index.tensors[t]['size'] *
                         len({owner[u] for u in index.consumers[t] if owner[u] != owner[p]})
                         for t in index.tensors for p in index.producers[t])
    output_bytes = sum(index.tensors[t]['size'] * len(index.producers[t])
                       for t in index.tensors if index.producers[t] and
                       (not index.consumers[t] or t in index.copy_out_inputs))
    core_work = [dict(Counter({p: sum(work[s][p] for s in range(a, b))
                               for p in totals})) for a, b in zip(bounds, bounds[1:])]
    core_work.extend({p: 0 for p in totals} for _ in range(cores - len(core_work)))
    return plan, {
        'selected_strategy': 'shared_stationary_wave',
        'jobs': len(by_job), 'requested_cores': cores, 'active_cores': len(bounds) - 1,
        'shared_external_inputs': len(waves), 'stage_count': len(stages),
        'stage_op_counts': [len(stage) for stage in stages],
        'stage_pipe_work': [dict(row) for row in work],
        'core_stage_bounds': bounds, 'core_pipe_work': core_work,
        'total_pipe_work': totals, 'normalized_minimax_work': str(balance),
        'shared_input_owner_count_max': max(map(len, shared_owners.values())),
        'estimated_transfer_bytes_without_spill': {
            'external_input': input_bytes, 'cross_core_out_plus_in': crossing_bytes,
            'terminal_output': output_bytes,
            'total': input_bytes + crossing_bytes + output_bytes},
        'official_score_available': False,
        'limitations': ['static priority order; no official Step2/Step3 makespan prediction',
                        'transfer estimate excludes spills, reorder and contention',
                        'capacity is validated as input but not certified as a zero-spill bound'],
    }


def build(graph, cores, config):
    return build_from_index(DAGIndex(graph), cores, config)
