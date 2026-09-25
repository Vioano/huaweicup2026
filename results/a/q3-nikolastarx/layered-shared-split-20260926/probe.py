"""Frozen one-prefix static shared split; no official plan derivation or scoring."""
import hashlib
import json
from pathlib import Path

from src.q3 import layered_query_flow as q

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CAP = {'L1': 524288, 'UB': 131072}
GRAPH_SHA = 'dfd9a58ef9d26a8a4567026b50af8b4499d87eebb3d98f8208b909b11e963c6d'
SOURCE_SHA = 'db197556787c7818cad21c47dca52e497ba84ba56e1717d4616977fda0556d33'

def save(result):
    (OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')

def violations(memory):
    return [{'core': c, 'pool': pool, 'peak_bytes': rec['bytes'],
             'capacity_bytes': CAP[pool], 'excess_bytes': rec['bytes']-CAP[pool],
             'bucket': rec['bucket'], 'op': rec['op']}
            for c, row in enumerate(memory['bucket_frontier_peaks'])
            for pool, rec in row.items() if rec['bytes'] > CAP[pool]]

def loads(index, owner):
    return [[sum(index.duration(u) for u in index.ops
                 if owner[u] == c and index.ops[u]['pipe'] == pipe)
             for pipe in q.PIPES] for c in range(5)]

result = {'status': 'STARTED', 'graph_sha256': GRAPH_SHA,
          'construct_layered_calls': 0, 'derive_multicore_plan_calls': 0,
          'Task_Step_solver_evaluator_calls': 0, 'retry_count': 0}
save(result)
try:
    assert hashlib.sha256((ROOT / 'src/q3/layered_query_flow.py').read_bytes()).hexdigest() == SOURCE_SHA
    raw = (ROOT / 'data/raw/a/official/data/case_068.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == GRAPH_SHA
    graph = json.loads(raw)
    index = q.RawIndex.build(graph)
    ports = q._ports(index)
    rows, depth, keys, labels, kv, qsucc = q.recognize_layers(index, ports, q._recognize)
    tracks, private, parts, phase, up, down, anchors, sigs = q.decompose(index, labels, kv)
    assert len(tracks) == 4
    groups, dp = q.partition_tracks(index, private, 4, 4)
    groups.append([])
    owner, original_loads = q.assign_shared(index, ports, private, parts, groups)
    words, tau = q.priority_words(index, phase, owner, 5, 500)
    memory, intervals = q.interval_certificate(index, ports, owner, words, CAP)
    before_violations = violations(memory)
    result['before'] = {'groups': groups, 'per_core_M_V_cycles': loads(index, owner),
                        'per_core_schedule_lengths': list(map(len, words)),
                        'frontier_peaks': memory['bucket_frontier_peaks'],
                        'violations': before_violations}
    save(result)
    assert len(before_violations) == 1
    bad = before_violations[0]
    assert (bad['core'], bad['pool'], bad['bucket'], bad['op'], bad['peak_bytes'], bad['excess_bytes']) == (0, 'UB', 145, 4551, 221208, 90136)
    assert not words[4]
    live = [it for it in intervals if it['core'] == 0 and it['pool'] == 'UB'
            and it['first_bucket'] <= 145 <= it['last_bucket']]
    assert sum(it['bytes'] for it in live) == 221208
    part_of = {u: i for i, part in enumerate(parts) for u in part}
    contributions = {i: 0 for i, part in enumerate(parts) if owner[min(part)] == 0}
    unattributed = 0
    for it in live:
        producer = ports.producer.get(it['tid'])
        component = part_of.get(producer)
        if component in contributions:
            contributions[component] += it['bytes']
        else:
            unattributed += it['bytes']
    assert sum(contributions.values()) + unattributed == 221208
    ranked = sorted((i for i, b in contributions.items() if b > 0),
                    key=lambda i: (-contributions[i], min(parts[i])))
    selection = []
    selected_bytes = 0
    for i in ranked:
        selection.append(i)
        selected_bytes += contributions[i]
        if selected_bytes >= 90136:
            break
    result['attribution'] = {
        'live_interval_count': len(live), 'unattributed_bytes_remaining_core0': unattributed,
        'ranked_components': [{'component_index': i, 'min_op_id': min(parts[i]),
                               'contributed_bytes': contributions[i], 'ops': len(parts[i])}
                              for i in ranked],
        'selected_prefix_component_indices': selection,
        'selected_prefix_min_op_ids': [min(parts[i]) for i in selection],
        'selected_contributed_bytes': selected_bytes,
    }
    save(result)
    if selected_bytes < 90136 or selected_bytes > 131072:
        result['status'] = 'UNSUPPORTED_NO_FEASIBLE_PREFIX'
    else:
        after_owner = dict(owner)
        for i in selection:
            for u in parts[i]:
                after_owner[u] = 4
        assert all(after_owner[u] == owner[u] for u in private)
        assert set(after_owner) == set(index.ops)
        after_words, after_tau = q.priority_words(index, phase, after_owner, 5, 500)
        after_memory, after_intervals = q.interval_certificate(index, ports, after_owner, after_words, CAP)
        after_violations = violations(after_memory)
        result['after'] = {'per_core_M_V_cycles': loads(index, after_owner),
                           'per_core_schedule_lengths': list(map(len, after_words)),
                           'frontier_peaks': after_memory['bucket_frontier_peaks'],
                           'violations': after_violations,
                           'step2_no_spill_certificate': after_memory['step2_no_spill_certificate']}
        save(result)
        if after_violations:
            result['status'] = 'FAILED_STATIC_CAPACITY'
        else:
            compute = q.path_stats(index, after_owner, after_words, after_tau, 500)
            whole = q.path_stats(index, after_owner, after_words, after_tau, 500, True)
            traffic, links = q.traffic_counts(index, ports, after_owner, kv)
            layers = 1 + max(depth.values())
            result['after']['compute_fifo'] = compute
            result['after']['whole_path'] = whole
            result['after']['whole_path_L_plus_1_guard'] = whole['max_remote_edges'] <= layers+1
            result['after']['traffic_prediction'] = traffic
            result['status'] = ('PASSED_STATIC_GUARDS_ONLY'
                                if result['after']['whole_path_L_plus_1_guard']
                                else 'FAILED_WHOLE_PATH_GUARD')
except Exception as exc:
    result['status'] = 'STOPPED_FIRST_EXCEPTION'
    result['exception'] = f'{type(exc).__name__}: {exc}'
    raise
finally:
    save(result)
