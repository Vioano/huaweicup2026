"""One frozen shared-component relocation; never calls the full constructor."""
import hashlib
import json
from pathlib import Path

from src.q3 import layered_query_flow as q

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CAP = {'L1': 524288, 'UB': 131072}
EXPECTED = 'dfd9a58ef9d26a8a4567026b50af8b4499d87eebb3d98f8208b909b11e963c6d'
SOURCE = 'db197556787c7818cad21c47dca52e497ba84ba56e1717d4616977fda0556d33'

def save(receipt):
    (OUT / 'result.json').write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + '\n')

def summarize(index, ports, kv, owner, words, tau, memory, intervals, layers):
    violations = [
        {'core': c, 'pool': p, 'bucket': rec['bucket'], 'op': rec['op'],
         'peak_bytes': rec['bytes'], 'excess_bytes': rec['bytes']-CAP[p]}
        for c, row in enumerate(memory['bucket_frontier_peaks'])
        for p, rec in row.items() if rec['bytes'] > CAP[p]]
    compute = q.path_stats(index, owner, words, tau, 500)
    whole = q.path_stats(index, owner, words, tau, 500, True)
    traffic, links = q.traffic_counts(index, ports, owner, kv)
    return {
        'per_core_M_V_cycles': [[sum(index.duration(u) for u in index.ops
                                     if owner[u] == c and index.ops[u]['pipe'] == p)
                                 for p in q.PIPES] for c in range(5)],
        'per_core_schedule_lengths': list(map(len, words)),
        'frontier_peaks': memory['bucket_frontier_peaks'],
        'no_spill_frontier_guard': memory['step2_no_spill_certificate'],
        'violations': violations, 'compute_fifo': compute,
        'whole_path': whole, 'whole_path_L_plus_1_guard': whole['max_remote_edges'] <= layers+1,
        'traffic_prediction': traffic,
        'cross_link_count': len(links),
        'original_edge_owner_coverage': set(owner) == set(index.ops),
    }

receipt = {'status': 'STARTED', 'input_sha256': EXPECTED,
           'construct_layered_calls': 0, 'derive_multicore_plan_calls': 0,
           'Task_Step_solver_evaluator_calls': 0, 'retry_count': 0}
save(receipt)
try:
    assert hashlib.sha256((ROOT / 'src/q3/layered_query_flow.py').read_bytes()).hexdigest() == SOURCE
    raw = (ROOT / 'data/raw/a/official/data/case_068.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED
    graph = json.loads(raw)
    index = q.RawIndex.build(graph)
    ports = q._ports(index)
    rows, depth, keys, labels, kv, qsucc = q.recognize_layers(index, ports, q._recognize)
    tracks, private, parts, phase, up, down, anchors, sigs = q.decompose(index, labels, kv)
    assert len(tracks) == 4
    groups, dp = q.partition_tracks(index, private, len(tracks), 4)
    groups.append([])
    before_owner, original_loads = q.assign_shared(index, ports, private, parts, groups)
    before_words, before_tau = q.priority_words(index, phase, before_owner, 5, 500)
    before_memory, before_intervals = q.interval_certificate(index, ports, before_owner, before_words, CAP)
    layers = 1 + max(depth.values())
    before = summarize(index, ports, kv, before_owner, before_words, before_tau,
                       before_memory, before_intervals, layers)
    receipt['before'] = before
    receipt['groups'] = groups
    receipt['shared_component_count'] = len(parts)
    save(receipt)
    assert before['violations'], 'no baseline frontier violation'
    worst = max(before['violations'], key=lambda v: (v['excess_bytes'], -v['core'], v['pool']))
    source_core = worst['core']
    assert source_core != 4 and not before_words[4]
    moved = [part for part in parts if before_owner[min(part)] == source_core]
    assert moved and all(all(before_owner[u] == source_core for u in part) for part in moved)
    after_owner = dict(before_owner)
    for part in moved:
        for u in part:
            after_owner[u] = 4
    assert all(after_owner[u] == before_owner[u] for u in private)
    assert set(after_owner) == set(index.ops)
    receipt['move'] = {'source_core': source_core, 'target_core': 4, 'worst_before': worst,
                       'moved_shared_components': len(moved),
                       'moved_shared_ops': sum(map(len, moved)),
                       'moved_M_V_cycles': [sum(index.duration(u) for part in moved for u in part
                                                if index.ops[u]['pipe'] == p) for p in q.PIPES],
                       'moved_component_min_op_ids': [min(part) for part in moved]}
    save(receipt)
    after_words, after_tau = q.priority_words(index, phase, after_owner, 5, 500)
    after_memory, after_intervals = q.interval_certificate(index, ports, after_owner, after_words, CAP)
    receipt['after'] = summarize(index, ports, kv, after_owner, after_words, after_tau,
                                 after_memory, after_intervals, layers)
    receipt['status'] = 'COMPLETED_STATIC_ONLY'
except Exception as exc:
    receipt['status'] = 'STOPPED_FIRST_EXCEPTION'
    receipt['exception'] = f'{type(exc).__name__}: {exc}'
    raise
finally:
    save(receipt)
