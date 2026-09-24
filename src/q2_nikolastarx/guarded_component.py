"""Bounded component-versus-DAG comparison for an injected complete-plan oracle.

This is a component_builder callback, not a standalone solver or evaluator.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any

from . import adaptive_budget
from . import vector_lanes
from .candidate_ddr import mandatory_copy_work
from .direct import UnsupportedStructure


Score = tuple[int, int]
Oracle = Callable[[dict[str, Any]], Mapping[str, Any]]


def _score(oracle: Oracle, plan: dict[str, Any]) -> Score:
    result = oracle(plan)
    if not isinstance(result, Mapping):
        raise ValueError('oracle result must be a mapping')
    if result.get('status') != 'ok':
        raise ValueError('oracle status must be ok')
    values = (result.get('makespan'), result.get('added_copy_bytes'))
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError('oracle requires nonnegative integer makespan and added_copy_bytes')
    return values


def _pipe_work_lower_bound(index, plan: dict[str, Any]) -> int:
    """Work on each actual (core, pipe) is a conservative makespan bound.

    Original COPY operations are excluded by index.ops; only their eventual
    positive cost is omitted. Raw nonnegative cycles avoid overestimating zero.
    """
    owner = {sg: core for core, row in enumerate(plan['core_schedules']) for sg in row}
    work = defaultdict(int)
    for node, sg in plan['node_to_subgraph'].items():
        op = index.ops[int(node)]
        work[owner[sg], op['pipe']] += max(0, op['cycles'])
    return max(work.values(), default=0)


def guarded_component_route(index, cores, config, *, oracle: Oracle):
    """Construct at most two plans and request at most one score per unique plan.

    On missing or invalid evidence, preserve adaptive_budget's baseline. The
    caller owns oracle selection, complete solver timing, and any later repair.
    """
    base, base_detail = adaptive_budget.component_route(index, cores, config)
    detail = {**base_detail, 'guarded_component': {
        'constructed_plans': 1, 'oracle_requests': 0, 'selected': 'baseline',
        'score_scope': 'component_builder output before downstream repair',
    }}
    guard = detail['guarded_component']
    pressure = base_detail['component_pressure']
    if cores <= 1 or not pressure['component_exceeds_balanced_pipe_work']:
        guard['reason'] = 'pressure_not_triggered'
        return base, detail
    try:
        vector_lanes.recognize(index)
    except UnsupportedStructure:
        pass
    else:
        guard['reason'] = 'vector_template_deferred_to_semantic_repair'
        return base, detail
    try:
        dag, dag_detail = index.build(
            cores, bandwidth=config['bandwidth'],
            cross_core_delay=config['cross_core_copy_delay_cycles'])
    except Exception as error:
        guard.update(reason='dag_construction_failed', candidate_error=repr(error),
                     evidence='unknown')
        return base, detail
    guard['constructed_plans'] = 2
    if dag == base:
        guard['reason'] = 'identical_plans'
        return base, detail

    guard['oracle_requests'] += 1
    try:
        base_score = _score(oracle, base)
    except Exception as error:
        guard.update(reason='baseline_score_unavailable', baseline_error=repr(error),
                     evidence='unknown')
        return base, detail
    guard['baseline_score'] = list(base_score)
    lower_bound = _pipe_work_lower_bound(index, dag)
    guard['candidate_pipe_work_lower_bound'] = lower_bound
    if lower_bound > base_score[0]:
        guard['reason'] = 'candidate_lower_bound_strictly_worse'
        return base, detail

    guard['candidate_mandatory_ddr_model'] = (
        'P2 Scene B original mandatory COPY shared-DDR service work; '
        'excludes Step2 spills; finite supported numeric domain; '
        'abstract lower bound, not a bit-level simulator proof'
    )
    try:
        ddr = mandatory_copy_work(index.graph, dag, config['bandwidth'])
        if not isinstance(ddr, Mapping) or type(ddr.get('service_work')) is not int \
                or ddr['service_work'] < 0:
            raise ValueError('invalid mandatory COPY counter result')
        ddr_rejects = ddr['service_work'] > base_score[0]
    except Exception as error:
        guard['candidate_mandatory_ddr'] = {
            'status': 'unknown', 'error': repr(error)}
    else:
        guard['candidate_mandatory_ddr'] = ddr
        if ddr_rejects:
            guard['reason'] = 'candidate_mandatory_ddr_strictly_worse'
            return base, detail

    guard['oracle_requests'] += 1
    try:
        dag_score = _score(oracle, dag)
    except Exception as error:
        guard.update(reason='candidate_score_unavailable', candidate_error=repr(error),
                     evidence='unknown')
        return base, detail
    guard['candidate_score'] = list(dag_score)
    if dag_score < base_score:
        guard.update(selected='dag', reason='lexicographic_score',
                     candidate_constructor=dag_detail.get('strategy'))
        detail['selected_strategy'] = 'guarded_component_dag'
        return dag, detail
    guard['reason'] = 'baseline_wins_or_ties'
    return base, detail


def make_component_builder(oracle: Oracle):
    """Return a callback for adaptive_semantic.build(..., component_builder=...)."""
    def component_builder(index, cores, config):
        return guarded_component_route(index, cores, config, oracle=oracle)
    return component_builder
