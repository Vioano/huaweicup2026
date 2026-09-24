"""One-leaf lookahead for independent M roots; never scores or runs Step3."""
from __future__ import annotations

from .construct import UnsupportedStructure, derive_multicore_plan


def transform(index, plan):
    """Move each next independent M root across exactly one preceding V block.

    ``index.pred`` is the compute-only dependency view, so external COPY input
    readiness is deliberately not part of the independent-leaf guard. Per core,
    ``prefix,M0,V0,M1,V1,...,Mn,Vn`` becomes
    ``prefix,M0,M1,V0,M2,V1,...,Mn,V(n-1),Vn``. M/V projections and ownership
    stay fixed. This is only a static frontier experiment, not an L1/UB proof.
    """
    view = derive_multicore_plan(index.graph, plan)
    if any(len(nodes) != 1 for nodes in view['nodes_by_subgraph'].values()):
        raise UnsupportedStructure('requires singleton subgraphs')
    if any(op.get('pipe') not in {'PIPE_M', 'PIPE_V'}
           for op in index.ops.values()):
        raise UnsupportedStructure('requires original compute ops on PIPE_M/PIPE_V only')
    m_leaves = [u for u, op in index.ops.items() if op.get('pipe') == 'PIPE_M']
    if not m_leaves:
        raise UnsupportedStructure('requires at least one PIPE_M operation')
    if any(index.pred[u] for u in m_leaves):
        raise UnsupportedStructure('every PIPE_M operation must have no compute predecessor')

    op_for_sg = {sg: nodes[0] for sg, nodes in view['nodes_by_subgraph'].items()}
    original_projection = {}
    schedules = []
    moved_v_counts = []
    for core in range(view['num_cores']):
        order = view['core_orders'].get(core, [])
        original_projection[core] = {
            pipe: [sg for sg in order if index.ops[op_for_sg[sg]]['pipe'] == pipe]
            for pipe in ('PIPE_M', 'PIPE_V')
        }
        first_m = next((i for i, sg in enumerate(order)
                        if index.ops[op_for_sg[sg]]['pipe'] == 'PIPE_M'), None)
        if first_m is None:
            schedules.append(list(order))
            moved_v_counts.append(0)
            continue
        prefix = order[:first_m]
        tail = order[first_m:]
        m_word, v_blocks = [], []
        pos = 0
        while pos < len(tail):
            sg = tail[pos]
            if index.ops[op_for_sg[sg]]['pipe'] != 'PIPE_M':
                raise UnsupportedStructure('expected M/V alternating-block suffix')
            m_word.append(sg)
            pos += 1
            end = pos
            while end < len(tail) and index.ops[op_for_sg[tail[end]]]['pipe'] == 'PIPE_V':
                end += 1
            v_blocks.append(tail[pos:end])
            pos = end
        transformed = prefix + [m_word[0]]
        for i in range(1, len(m_word)):
            transformed.append(m_word[i])
            transformed.extend(v_blocks[i - 1])
        transformed.extend(v_blocks[-1])
        after = {
            pipe: [sg for sg in transformed if index.ops[op_for_sg[sg]]['pipe'] == pipe]
            for pipe in ('PIPE_M', 'PIPE_V')
        }
        if after != original_projection[core]:
            raise AssertionError('one-leaf lookahead changed a per-core pipe projection')
        schedules.append(transformed)
        moved_v_counts.append(sum(map(len, v_blocks[:-1])))

    candidate = {
        'node_to_subgraph': dict(plan['node_to_subgraph']),
        'core_schedules': schedules,
    }
    updated = derive_multicore_plan(index.graph, candidate)
    if updated['core_by_subgraph'] != view['core_by_subgraph']:
        raise AssertionError('one-leaf lookahead changed operation ownership')
    return candidate, {
        'strategy': 'one_leaf_lookahead',
        'cores': view['num_cores'],
        'independent_m_leaves': len(m_leaves),
        'm_operations_by_core': [len(original_projection[c]['PIPE_M'])
                                 for c in range(view['num_cores'])],
        'v_operations_delayed_by_one_m_by_core': moved_v_counts,
        'ownership_preserved': True,
        'pipe_projections_preserved': True,
        'plan_guard_validated': True,
        'prediction_scope': 'static ordering/frontier condition only; not official L1/UB capacity or performance certificate',
        'official_evaluations': 0,
    }
