"""Static mandatory P2 Scene B COPY work for one validated candidate plan.

This counts only COPYs inserted by the frozen _build_scene_b_tasks, before
Step2 spilling. It does not run Step1/2/3 or the event simulator. Service work
is an abstract shared-DDR lower bound, not a bit-level floating-point proof of
the simulator's makespan. The standard bandwidth (60) is supported; for
conservative numeric behavior this API requires finite positive bandwidth,
sizes and durations within the exact-integer range of binary64.
"""
from __future__ import annotations

import math

from .direct import derive_multicore_plan

# direct.py installs the frozen official code directory on sys.path.
from multicore_cut_evaluate_problem_1 import _original_tensor_views


MAX_EXACT_FLOAT_INT = 2**53
CATEGORIES = ('boundary_input', 'boundary_output', 'cross_tensor', 'cross_direct')


class UnknownMandatoryDDR(ValueError):
    """The counter cannot safely certify this input/configuration."""


def _copy_work(size: int, bandwidth: int | float) -> int:
    if type(size) is not int or not 0 <= size <= MAX_EXACT_FLOAT_INT:
        raise UnknownMandatoryDDR('COPY size outside supported nonnegative exact-float range')
    # Matches frozen add_copy_in/out and Step3 _op_duration for this domain.
    quotient = size / bandwidth
    if not math.isfinite(quotient) or quotient > MAX_EXACT_FLOAT_INT:
        raise UnknownMandatoryDDR('COPY duration outside supported exact-float range')
    return max(1, math.ceil(quotient))


def mandatory_copy_work(graph_json: dict, plan: dict, bandwidth: int | float) -> dict:
    """Return mandatory original COPY transfer bytes, work, and operation counts.

    A cross-core connection contributes one OUT and one IN. The same tensor
    may also require a boundary output OUT under the official condition; these
    are distinct operations. Unknown/malformed sizes fail closed.
    """
    if (type(bandwidth) not in (int, float)
            or not 0 < bandwidth <= MAX_EXACT_FLOAT_INT
            or (type(bandwidth) is float and not math.isfinite(bandwidth))):
        raise UnknownMandatoryDDR('bandwidth must be finite and in (0, 2**53]')
    plan_view = derive_multicore_plan(graph_json, plan)
    mapping = plan_view['mapping']
    core_by_subgraph = plan_view['core_by_subgraph']
    core_by_op = {op: core_by_subgraph[sg] for op, sg in mapping.items()}
    producers, consumers, direct_edges = _original_tensor_views(graph_json)
    op_by_id = {op['id']: op for op in graph_json['ops']}
    categories = {name: {'copy_count': 0, 'transfer_bytes': 0, 'service_work': 0}
                  for name in CATEGORIES}

    def add(category: str, size: int, copies: int) -> None:
        work = _copy_work(size, bandwidth)
        row = categories[category]
        row['copy_count'] += copies
        row['transfer_bytes'] += size * copies
        row['service_work'] += work * copies
        if row['service_work'] > MAX_EXACT_FLOAT_INT:
            raise UnknownMandatoryDDR('total COPY work exceeds exact-float range')

    for tensor in graph_json['tensors']:
        tid, size = tensor['id'], tensor['size']
        source_cores = {core_by_op[op] for op in producers.get(tid, ()) if op in mapping}
        target_cores = {core_by_op[op] for op in consumers.get(tid, ()) if op in mapping}
        if not (source_cores or target_cores):
            continue
        # Verify even when a tensor happens not to induce a COPY below.
        _copy_work(size, bandwidth)
        if target_cores and not source_cores:
            add('boundary_input', size, len(target_cores))
        original_out = any(
            op_by_id[op].get('op') == 'COPY_OUT'
            for op in consumers.get(tid, ()) if op in op_by_id
        )
        if source_cores and (original_out or not target_cores):
            add('boundary_output', size, len(source_cores))
        pairs = sum(src != dst for src in source_cores for dst in target_cores)
        if pairs:
            add('cross_tensor', size, 2 * pairs)

    for edge in direct_edges:
        src, dst = edge['source'], edge['target']
        if src not in mapping or dst not in mapping or core_by_op[src] == core_by_op[dst]:
            continue
        raw_size = edge.get('data_size', 0)
        # The official int(...) coercion is permissive; accepting malformed
        # values here would silently give a certificate for the wrong graph.
        if type(raw_size) is not int or raw_size < 0:
            raise UnknownMandatoryDDR('cross-core direct edge data_size must be nonnegative integer')
        add('cross_direct', raw_size, 2)

    totals = {
        key: sum(row[key] for row in categories.values())
        for key in ('copy_count', 'transfer_bytes', 'service_work')
    }
    if totals['service_work'] > MAX_EXACT_FLOAT_INT:
        raise UnknownMandatoryDDR('total COPY work exceeds exact-float range')
    return {**totals, 'categories': categories,
            'scope': 'P2 Scene B original mandatory COPYs before Step2 spills'}
