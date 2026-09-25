"""Job-major, shared-input-stationary priority plan for repeated P2 components.

This is a structural constructor, not an evaluator or a zero-spill certificate.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .shared_input_wave import _raw_peak, _recognize, _pool
from .shared_stationary_wave import _stages


POOLS = ('L1', 'UB')


def _partition(index, stages, cores, capacity, job_of):
    """Minimax contiguous pipe work subject to a conservative residency screen."""
    n = len(stages)
    k = min(cores, n)
    pipes = sorted({index.ops[u]['pipe'] for stage in stages for u in stage})
    work = [Counter({p: sum(index.duration(u) for u in stage
                            if index.ops[u]['pipe'] == p) for p in pipes})
            for stage in stages]
    totals = {p: sum(row[p] for row in work) for p in pipes}
    prefix = {p: [0] for p in pipes}
    for row in work:
        for p in pipes:
            prefix[p].append(prefix[p][-1] + row[p])

    # Keep the complete produced footprint of two jobs as a reserve. This is
    # intentionally a data-derived screen, not a proof about Step2 lifetimes.
    produced = [Counter() for _ in range(max(job_of.values()) + 1)]
    for u, j in job_of.items():
        for t in index.outputs[u]:
            produced[j][_pool(index.tensors[t])] += index.tensors[t]['size']
    reserve = {p: sum(sorted((r[p] for r in produced), reverse=True)[:2]) for p in POOLS}

    # The set of external inputs touched by a core's stage interval is charged
    # once per distinct tensor, including private inputs across every job.
    external = [set() for _ in stages]
    for s, stage in enumerate(stages):
        external[s] = {t for u in stage for t in index.inputs[u]
                       if not index.producers[t]}
    ext_cache = {}

    def external_bytes(a, b):
        key = a, b
        if key not in ext_cache:
            ids = set().union(*external[a:b])
            ext_cache[key] = {p: sum(index.tensors[t]['size'] for t in ids
                                     if _pool(index.tensors[t]) == p) for p in POOLS}
        return ext_cache[key]

    def feasible(a, b):
        ext = external_bytes(a, b)
        return all(ext[p] + reserve[p] <= capacity[p] for p in POOLS)

    def cost(a, b):
        return max((Fraction(prefix[p][b] - prefix[p][a], totals[p])
                    for p in pipes if totals[p]), default=Fraction(0))

    dp = [[None] * (n + 1) for _ in range(k + 1)]
    prev = [[None] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = Fraction(0)
    for used in range(1, k + 1):
        for b in range(used, n + 1):
            choices = [(max(dp[used - 1][a], cost(a, b)), a)
                       for a in range(used - 1, b)
                       if dp[used - 1][a] is not None and feasible(a, b)]
            if choices:
                dp[used][b], prev[used][b] = min(choices)
    if dp[k][n] is None:
        raise UnsupportedStructure('no contiguous stage partition fits the external-input and two-job reserve screen')
    bounds = [n]
    b = n
    for used in range(k, 0, -1):
        b = prev[used][b]
        bounds.append(b)
    bounds.reverse()
    return bounds, dp[k][n], work, totals, reserve, [external_bytes(a, b)
                                                       for a, b in zip(bounds, bounds[1:])]


def build_from_index(index, cores, config):
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    capacity = config['capacity']
    if set(capacity) != set(POOLS) or any(type(capacity[p]) is not int or capacity[p] < 0
                                          for p in POOLS):
        raise ValueError('capacity must contain nonnegative integer L1 and UB bytes')
    by_job, waves, anchor = _recognize(index)
    stages = _stages(index, by_job, waves, anchor)
    job_of = {u: j for j, job in enumerate(index.components) for u in job}
    bounds, balance, work, totals, reserve, ext_bytes = _partition(
        index, stages, cores, capacity, job_of)
    owner = {u: c for c, (a, b) in enumerate(zip(bounds, bounds[1:]))
             for stage in stages[a:b] for u in stage}
    if len(owner) != len(index.ops):
        raise UnsupportedStructure('stage ownership lost eligible operations')

    # A job is run across this core's stages before the next job starts, so its
    # crossing outputs can become ready on the next core early. Each job keeps
    # stage order and predecessor-first order inside a stage.
    staged_jobs = [[[] for _ in by_job] for _ in stages]
    for s, stage in enumerate(stages):
        for u in stage:
            staged_jobs[s][job_of[u]].append(u)
    sequences = []
    for a, b in zip(bounds, bounds[1:]):
        sequences.append([u for j in range(len(by_job))
                          for s in range(a, b) for u in staged_jobs[s][j]])
    sequences.extend([] for _ in range(cores - len(sequences)))
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in seq] for seq in sequences]}
    view = derive_multicore_plan(index.graph, plan)
    if set(view['mapping']) != set(index.ops) or sum(map(len, sequences)) != len(index.ops):
        raise UnsupportedStructure('structural derivation changed coverage')
    shared_owners = {t: {owner[row[anchor[t]]] for row in by_job} for t in waves}
    if any(len(owners) != 1 for owners in shared_owners.values()):
        raise UnsupportedStructure('shared input split across cores')

    external = {t for u in index.ops for t in index.inputs[u] if not index.producers[t]}
    input_bytes = sum(index.tensors[t]['size'] * len({owner[u] for u in index.consumers[t]})
                      for t in external)
    crossing_bytes = sum(2 * index.tensors[t]['size'] *
                         len({owner[u] for u in index.consumers[t] if owner[u] != owner[p]})
                         for t in index.tensors for p in index.producers[t])
    output_bytes = sum(index.tensors[t]['size'] * len(index.producers[t])
                       for t in index.tensors if index.producers[t] and
                       (not index.consumers[t] or t in index.copy_out_inputs))
    core_work = [{p: sum(work[s][p] for s in range(a, b)) for p in totals}
                 for a, b in zip(bounds, bounds[1:])]
    core_work.extend({p: 0 for p in totals} for _ in range(cores - len(core_work)))
    return plan, {
        'selected_strategy': 'shared_stationary_pipeline',
        'jobs': len(by_job), 'requested_cores': cores, 'active_cores': len(bounds) - 1,
        'shared_external_inputs': len(waves), 'stage_count': len(stages),
        'core_stage_bounds': bounds, 'core_pipe_work': core_work,
        'total_pipe_work': totals, 'normalized_minimax_work': str(balance),
        'capacity_bytes': dict(capacity), 'two_job_produced_reserve_bytes': reserve,
        'core_external_input_bytes': ext_bytes,
        'core_raw_priority_peak_bytes': [_raw_peak(index, seq) for seq in sequences],
        'shared_input_owner_count_max': max(map(len, shared_owners.values())),
        'estimated_transfer_bytes_without_spill': {
            'external_input': input_bytes, 'cross_core_out_plus_in': crossing_bytes,
            'terminal_output': output_bytes,
            'total': input_bytes + crossing_bytes + output_bytes},
        'official_score_available': False, 'zero_spill_claim': False,
        'limitations': ['priority order and residency screen do not predict official Step2/Step3 timing',
                        'two-job reserve is not a memory-lifetime or zero-spill certificate',
                        'transfer estimate excludes spills, reorder and contention'],
    }


def build(graph, cores, config):
    return build_from_index(DAGIndex(graph), cores, config)
