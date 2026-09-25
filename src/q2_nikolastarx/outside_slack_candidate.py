"""Bounded C03 priority recovery for already selected C02 singleton plans.

This adapter constructs at most two static proposals. It does not prepare a P2
task, schedule it, or run E0/E1/E2. Fixed-model times are not official scores.
"""
from __future__ import annotations

import hashlib
import json

from .dag_direct import DAGIndex
from .direct import derive_multicore_plan
from .exit_sealed_candidate import _problem_and_tensor_guard
from .fifo_bound import fixed_fifo_lower_bound
from .outside_slack_kernel import FixedModel, NoCandidate, emit_plan, recover
from .receiver_closure_exchange import _rows
from .zero_spill_intervals import certify
from stub_multicore_cut_and_schedule import MulticoreCutError


def _owner(rows):
    return {u: c for c, row in enumerate(rows) for u in row}


def _plan_hash(plan):
    raw = json.dumps(plan, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _certified(graph, plan, config, label):
    certificate = certify(graph, plan, config)
    if not certificate['supported'] or not certificate['zero_spill_certificate']:
        raise ValueError(label + '_static_zero_spill_unavailable')


def rebuild(graph, baseline_plan, config, c02_candidates, original_start_times,
            *, incumbent_makespan):
    """Return (up to two full plans, diagnostics), preserving each C02 identity.

    C02 entries must contain ``plan`` and ``detail.region`` with ops/exit/host,
    plus ``detail.priority.regional_word``. Every entry receives exactly one
    recovery attempt after its identity and baseline checks pass.
    """
    meta = {'status': 'no_candidate', 'scope': 'unscored C03 static proposals',
            'rejections': [], 'c02_seen': 0, 'recover_calls': 0,
            'validated_candidates': 0, 'checks': {'baseline': 0, 'c02': 0,
            'owner_equal': 0, 'exterior_equal': 0, 'word_equal': 0,
            'static_zero_spill': 0, 'fifo_bound': 0},
            'calls': {'prepare': 0, 'solver': 0, 'E0': 0, 'E1': 0, 'E2': 0},
            'official_makespan_guarantee': False,
            'official_zero_spill_verified': False}

    def reject(i, reason, original_hash=None):
        item = {'index': i, 'reason': reason}
        if original_hash is not None:
            item['original_c02_plan_sha256'] = original_hash
        meta['rejections'].append(item)

    try:
        if type(incumbent_makespan) is not int or incumbent_makespan <= 0:
            raise ValueError('positive_audited_incumbent_required')
        if type(c02_candidates) not in (list, tuple) or len(c02_candidates) > 2:
            raise ValueError('at_most_two_saved_C02_candidates_required')
        if config['cross_core_copy_delay_cycles'] != 500:
            raise ValueError('fixed_500_cycle_cross_delay_required')
        index = DAGIndex(graph)
        problem = _problem_and_tensor_guard(graph, index)
        baseline_rows = _rows(graph, baseline_plan, index)
        if len(baseline_rows) < 2:
            raise ValueError('multiple_cores_required')
        _certified(graph, baseline_plan, config, 'baseline')
        if type(original_start_times) is not dict or set(original_start_times) != set(index.ops):
            raise ValueError('complete_original_start_times_required')
        if any(type(t) is not int or t < 0 for t in original_start_times.values()):
            raise ValueError('nonnegative_integer_original_starts_required')
        baseline_owner = _owner(baseline_rows)
        meta['checks']['baseline'] = 1
    except (ValueError, KeyError, TypeError, OverflowError, AssertionError,
            MulticoreCutError) as error:
        meta['status'] = 'unsupported'
        reject(None, type(error).__name__ + ': ' + str(error))
        return [], meta

    accepted = []
    for i, entry in enumerate(c02_candidates):
        meta['c02_seen'] += 1
        original_hash = None
        try:
            if type(entry) is not dict or not {'plan', 'detail'}.issubset(entry):
                raise ValueError('C02_plan_and_detail_required')
            old_plan = entry['plan']
            if set(old_plan) != {'node_to_subgraph', 'core_schedules'}:
                raise ValueError('C02_plan_requires_two_keys')
            original_hash = _plan_hash(old_plan)
            rows = _rows(graph, old_plan, index)
            if len(rows) != len(baseline_rows):
                raise ValueError('C02_core_count_changed')
            if old_plan['node_to_subgraph'] != baseline_plan['node_to_subgraph']:
                raise ValueError('C02_singleton_mapping_changed')
            _certified(graph, old_plan, config, 'C02')
            detail = entry['detail']
            region_info, priority = detail['region'], detail['priority']
            region_ops = region_info['ops']
            word = priority['regional_word']
            host, exit_op = region_info['host'], region_info['exit']
            if (type(host) is not int or not 0 <= host < len(rows)
                    or type(exit_op) is not int or exit_op not in index.ops
                    or type(region_ops) not in (list, tuple)
                    or type(word) not in (list, tuple)
                    or not region_ops or len(region_ops) > 64
                    or len(set(region_ops)) != len(region_ops)
                    or len(word) != len(region_ops) or set(word) != set(region_ops)
                    or len(set(word)) != len(word)):
                raise ValueError('invalid_C02_region_or_word')
            region = set(region_ops)
            if exit_op not in region or baseline_owner[exit_op] != host:
                raise ValueError('C02_exit_host_mismatch')
            expected_owner = {u: host if u in region else baseline_owner[u]
                              for u in problem.pipe}
            if _owner(rows) != expected_owner:
                raise ValueError('C02_owner_not_implied_by_region_and_host')
            if any([u for u in baseline_rows[c] if u not in region] !=
                   [u for u in rows[c] if u not in region]
                   for c in range(len(rows))):
                raise ValueError('C02_exterior_priority_changed')
            if [u for u in rows[host] if u in region] != list(word):
                raise ValueError('C02_regional_word_mismatch')
            meta['checks']['c02'] += 1
            model = FixedModel(
                duration=dict(problem.duration), pipe=dict(problem.pipe),
                lags={(u, v): (500 if expected_owner[u] != expected_owner[v] else 0)
                      for u, vs in index.succ.items() for v in vs},
                release={u: 0 for u in problem.pipe})
            meta['recover_calls'] += 1
            recovered = recover(model, baseline_rows, original_start_times,
                                word, host, incumbent_makespan)
            candidate = emit_plan(baseline_plan, recovered)
            if set(candidate) != {'node_to_subgraph', 'core_schedules'}:
                raise AssertionError('recovered_plan_keys_changed')
            new_rows = _rows(graph, candidate, index)
            derive_multicore_plan(graph, candidate)
            if _owner(new_rows) != _owner(rows):
                raise AssertionError('recovery_changed_C02_owner')
            meta['checks']['owner_equal'] += 1
            if any([u for u in baseline_rows[c] if u not in region] !=
                   [u for u in new_rows[c] if u not in region]
                   for c in range(len(rows))):
                raise AssertionError('recovery_changed_exterior_priority')
            meta['checks']['exterior_equal'] += 1
            if [u for u in new_rows[host] if u in region] != list(word):
                raise AssertionError('recovery_changed_regional_word')
            meta['checks']['word_equal'] += 1
            _certified(graph, candidate, config, 'recovered')
            meta['checks']['static_zero_spill'] += 1
            bound = fixed_fifo_lower_bound(graph, candidate)
            if not bound['supported']:
                raise ValueError('candidate_fifo_bound_unsupported')
            meta['checks']['fifo_bound'] += 1
            if bound['makespan_lower_bound_cycles'] >= incumbent_makespan:
                raise ValueError('fifo_lower_bound_no_strict_gain')
            accepted.append({'plan': candidate,
                'detail': {'region': region_info,
                           'priority': {**priority,
                                        'regional_word': recovered['regional_word'],
                                        'global_priority_order': recovered['global_priority_order']},
                           'original_c02_priority': priority,
                           'original_c02_plan_sha256': original_hash,
                           'owner_equal_to_c02': True,
                           'exterior_priority_preserved': True,
                           'regional_word_preserved': True,
                           'witness_start': recovered['witness_start'],
                           'exterior_reserved_start': recovered['exterior_reserved_start'],
                           'exterior_latest_start': recovered['exterior_latest_start'],
                           'regional_completion_deadline': recovered['regional_completion_deadline'],
                           'pipe_orders': recovered['pipe_orders'],
                           'calendar_intervals_visited': recovered['calendar_intervals_visited'],
                           'fifo_lower_bound_cycles': bound['makespan_lower_bound_cycles'],
                           'official_quality': 'unmeasured',
                           'pending': ['native score', 'independent E0 spill_added_copy_bytes == 0'],
                           'scope': recovered['scope']}})
        except (ValueError, KeyError, TypeError, OverflowError, AssertionError,
                MulticoreCutError) as error:
            reason = str(error) if isinstance(error, NoCandidate) else type(error).__name__ + ': ' + str(error)
            reject(i, reason, original_hash)
    meta['validated_candidates'] = len(accepted)
    meta['status'] = 'candidates' if accepted else 'no_candidate'
    return accepted, meta
