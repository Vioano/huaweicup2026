"""Guarded, unscored P2 C02 adapter for exit-sealed regional proposals.

This does not run the native simulator, E0, or a candidate-selection oracle.
Returned plans require independent scoring and acceptance by a separate wrapper.
"""
from __future__ import annotations

from .candidate_ddr import _copy_work
from .dag_direct import DAGIndex
from .direct import derive_multicore_plan
from .exit_sealed_kernel import Problem, Seed, emit_plan, propose as kernel_propose
from .fifo_bound import fixed_fifo_lower_bound
from .receiver_closure_exchange import _rows
from .zero_spill_intervals import certify
from stub_multicore_cut_and_schedule import MulticoreCutError


def _problem_and_tensor_guard(graph, index):
    """Require D_val = retained D_exec and complete physical tensor incidence."""
    eligible = set(index.ops)
    original_ops = {o['id']: o for o in graph['ops']}
    if any('logical_tid' in tensor for tensor in graph['tensors']):
        raise ValueError('logical_tensor_alias_outside_guard')
    if any(op['pipe'] not in ('PIPE_M', 'PIPE_V') for op in index.ops.values()):
        raise ValueError('non_MV_eligible_op_outside_guard')
    if any(len(index.producers[tid]) > 1 for tid in index.tensors):
        raise ValueError('multiple_eligible_tensor_producers')
    # An excluded original consumer other than mandatory COPY_OUT means the
    # original tensor view cannot safely be represented by this kernel.
    for edge in graph['edges']:
        tid, target = edge['source'], edge['target']
        if tid in index.tensors and target in original_ops and target not in eligible:
            if original_ops[target].get('op') != 'COPY_OUT':
                raise ValueError('unrepresented_excluded_tensor_consumer')
    retained = {u: set() for u in eligible}
    for v, incoming in index.direct_inputs.items():
        for u, _ in incoming:
            retained[u].add(v)
    for tid in index.tensors:
        for u in index.producers[tid]:
            for v in index.consumers[tid]:
                if u != v:
                    retained[u].add(v)
    if retained != {u: set(index.succ[u]) for u in eligible}:
        raise ValueError('validation_and_retained_execution_DAG_differ')
    escapes = set()
    for tid in index.tensors:
        if tid in index.copy_out_inputs or not index.consumers[tid]:
            escapes.update(index.producers[tid])
    problem = Problem(
        {u: index.ops[u]['pipe'] for u in eligible},
        {u: index.duration(u) for u in eligible},
        {u: frozenset(retained[u]) for u in eligible},
        frozenset(escapes)).checked()
    return problem


def _boundary_hints(index, owner, finish, host, region, bandwidth):
    """One frozen isolated-COPY arrival hint; never a schedule or safe bound."""
    hints = {}
    for v in region:
        arrivals = [0]
        for tid in index.inputs[v]:
            size = index.tensors[tid]['size']
            copy = _copy_work(size, bandwidth)
            producers = index.producers[tid]
            if not producers:
                arrivals.append(copy)  # graph input: one isolated COPY IN
            for u in producers - region:
                arrivals.append(finish[u] + (0 if owner[u] == host else 500 + 2 * copy))
        for u, size in index.direct_inputs[v]:
            if u not in region:
                copy = _copy_work(size, bandwidth)
                arrivals.append(finish[u] + (0 if owner[u] == host else 500 + 2 * copy))
        hints[v] = max(arrivals)
    return hints


def propose(graph, plan, config, critical_links, original_finish_times, *,
            incumbent_makespan, max_seeds=8, max_candidates=2):
    """Return at most two guarded full singleton plans and diagnostics.

    `critical_links` is saved witness evidence, never reconstructed here.
    Each witness must identify tensor_id, source_core, target_core, and positive
    exposed_delay (or exposed_delay_cycles). The complete eligible consumer set
    is re-read from the original tensor table, not copied from the witness.
    """
    if (type(max_seeds) is not int or not 0 <= max_seeds <= 8
            or type(max_candidates) is not int or not 1 <= max_candidates <= 2):
        raise ValueError('C02 requires max_seeds in [0,8] and max_candidates in [1,2]')
    if type(incumbent_makespan) is not int or incumbent_makespan <= 0:
        raise ValueError('positive audited incumbent_makespan required')
    meta = {'status': 'no_candidate', 'scope': 'unscored C02 static proposals',
            'rejections': {}, 'seeds_seen': 0, 'proposals_before_guards': 0,
            'validated_candidates': 0, 'official_makespan_guarantee': False,
            'score_calls': 0, 'kernel_diagnostics': None,
            'hint_rule': 'old external finish + 500 + 2 isolated COPY; graph input 1 isolated COPY'}

    def reject(reason):
        meta['rejections'][reason] = meta['rejections'].get(reason, 0) + 1

    try:
        if not isinstance(critical_links, (list, tuple)):
            raise ValueError('saved_critical_links_required')
        if config['cross_core_copy_delay_cycles'] != 500:
            raise ValueError('fixed_500_cycle_cross_delay_required')
        bandwidth = config['bandwidth']
        if type(original_finish_times) is not dict:
            raise ValueError('complete_original_finish_times_required')
        index = DAGIndex(graph)
        rows = _rows(graph, plan, index)
        if len(rows) < 2:
            raise ValueError('multiple_cores_required')
        problem = _problem_and_tensor_guard(graph, index)
        if set(original_finish_times) != set(index.ops) or any(
                type(t) is not int or t < 0 for t in original_finish_times.values()):
            raise ValueError('incomplete_or_invalid_old_finish_times')
        # kernel.propose checks old D + complete per-core chains are acyclic.
        base_cert = certify(graph, plan, config)
        if not base_cert['supported'] or not base_cert['zero_spill_certificate']:
            raise ValueError('baseline_zero_spill_certificate_unavailable')
        owner = {u: c for c, row in enumerate(rows) for u in row}
        seeds = []
        for link in critical_links:
            if not isinstance(link, dict):
                reject('invalid_link_record'); continue
            tid = link.get('tensor_id')
            source_core, target_core = link.get('source_core'), link.get('target_core')
            exposed = link.get('exposed_delay', link.get('exposed_delay_cycles'))
            if (type(tid) is not int or tid not in index.tensors
                    or type(source_core) is not int or type(target_core) is not int
                    or source_core == target_core or not 0 <= source_core < len(rows)
                    or not 0 <= target_core < len(rows)
                    or type(exposed) is not int or exposed <= 0):
                reject('invalid_or_unexposed_link'); continue
            producers = index.producers[tid]
            consumers = index.consumers[tid]
            if len(producers) != 1 or not consumers:
                reject('nonunique_producer_or_empty_consumers'); continue
            source = next(iter(producers))
            if owner[source] != source_core or not any(owner[u] == target_core for u in consumers):
                reject('witness_core_mismatch'); continue
            # Deliberately ignore any witness consumer subset: whole original
            # physical tensor eligible incidence is the source of truth.
            seeds.append(Seed(tid, source, tuple(sorted(consumers)), exposed))
        meta['seeds_seen'] = len(seeds)
        if not seeds or max_seeds == 0:
            return [], meta
        # The kernel slices at most eight roots and selects at most two whole
        # structural proposals *before* expensive physical/capacity guards.
        proposals, kernel_diag = kernel_propose(
            problem, rows, seeds, incumbent_makespan=incumbent_makespan,
            cross_delay=500, max_ops=64, max_regions=max_seeds,
            max_candidates=max_candidates,
            hint_factory=lambda region, host: _boundary_hints(
                index, owner, original_finish_times, host, region, bandwidth))
        meta['kernel_diagnostics'] = kernel_diag
        meta['proposals_before_guards'] = len(proposals)
    except (ValueError, KeyError, TypeError, OverflowError, AssertionError,
            MulticoreCutError) as error:
        meta['status'] = 'unsupported'
        reject(type(error).__name__ + ': ' + str(error))
        return [], meta

    accepted = []
    for proposal in proposals:
        try:
            candidate = emit_plan(plan, proposal['rows'])
            derive_multicore_plan(graph, candidate)
            cert = certify(graph, candidate, config)
            if not cert['supported'] or not cert['zero_spill_certificate']:
                reject('candidate_zero_spill_not_certified'); continue
            bound = fixed_fifo_lower_bound(graph, candidate)
            if not bound['supported']:
                reject('candidate_fifo_bound_unsupported'); continue
            if bound['makespan_lower_bound_cycles'] >= incumbent_makespan:
                reject('fifo_lower_bound_no_strict_gain'); continue
        except (ValueError, KeyError, TypeError, OverflowError, MulticoreCutError) as error:
            reject('candidate_guard_failure:' + type(error).__name__); continue
        accepted.append({'plan': candidate,
                         'detail': {'region': proposal['region'],
                                    'priority': proposal['priority'],
                                    'fifo_lower_bound_cycles': bound['makespan_lower_bound_cycles'],
                                    'pending': ['native score', 'independent E0 acceptance'],
                                    'official_quality': 'unmeasured'}})
    meta['validated_candidates'] = len(accepted)
    meta['status'] = 'candidates' if accepted else 'no_candidate'
    return accepted, meta
