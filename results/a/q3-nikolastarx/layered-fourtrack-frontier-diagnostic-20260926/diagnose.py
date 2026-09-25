"""Single frozen static frontier diagnostic; see FROZEN.md."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from src.q3 import layered_query_flow as q

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
GRAPH = ROOT / 'data/raw/a/official/data/case_068.json'
EXPECTED = 'dfd9a58ef9d26a8a4567026b50af8b4499d87eebb3d98f8208b909b11e963c6d'
CAP = {'L1': 524288, 'UB': 131072}

def save(obj):
    (OUT / 'result.json').write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n')

result = {'status': 'STARTED', 'graph_sha256': EXPECTED, 'helper_calls': {},
          'construct_layered_calls': 0, 'derive_multicore_plan_calls': 0,
          'Task_Step_solver_evaluator_calls': 0, 'retries': 0, 'runs': []}
save(result)
try:
    raw = GRAPH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED
    graph = json.loads(raw)
    index = q.RawIndex.build(graph)
    ports = q._ports(index)
    rows, depth, keys, labels, kv, qsucc = q.recognize_layers(index, ports, q._recognize)
    tracks, private, parts, phase, up, down, anchors, sigs = q.decompose(index, labels, kv)
    result['decomposition'] = {'tracks': tracks, 'track_count': len(tracks),
                               'private_ops': len(private), 'shared_ops': sum(map(len, parts)),
                               'shared_components': len(parts), 'rows': len(rows)}
    save(result)
    for cores in (5, 4):
        run = {'cores': cores}
        result['runs'].append(run)
        for name in ('partition_tracks', 'assign_shared', 'priority_words', 'interval_certificate'):
            result['helper_calls'][name] = result['helper_calls'].get(name, 0) + 1
            save(result)
            if name == 'partition_tracks':
                groups, dp = q.partition_tracks(index, private, len(tracks), cores)
            elif name == 'assign_shared':
                owner, loads = q.assign_shared(index, ports, private, parts, groups)
            elif name == 'priority_words':
                words, tau = q.priority_words(index, phase, owner, cores, 500)
            else:
                memory, intervals = q.interval_certificate(index, ports, owner, words, CAP)
        shared_placements = [
            {'component_index': i, 'owner': owner[min(part)], 'ops': len(part),
             'M_cycles': sum(index.duration(u) for u in part if index.ops[u]['pipe'] == 'PIPE_M'),
             'V_cycles': sum(index.duration(u) for u in part if index.ops[u]['pipe'] == 'PIPE_V')}
            for i, part in enumerate(parts)]
        violations = []
        for core, row in enumerate(memory['bucket_frontier_peaks']):
            for pool, rec in row.items():
                excess = rec['bytes'] - CAP[pool]
                if excess <= 0:
                    continue
                bucket = rec['bucket']
                live = [it for it in intervals if it['core'] == core and it['pool'] == pool
                        and it['first_bucket'] <= bucket <= it['last_bucket']]
                assert sum(it['bytes'] for it in live) == rec['bytes']
                live.sort(key=lambda it: (-it['bytes'], it['tid']))
                contributors = []
                for it in live[:25]:
                    tid = it['tid']
                    producer = ports.producer.get(tid)
                    consumers = ports.consumers[tid]
                    contributors.append({**it, 'producer_op': producer,
                                         'producer_owner': owner.get(producer),
                                         'local_consumer_count': sum(owner.get(u) == core for u in consumers),
                                         'shared_producer': producer in set().union(*parts)})
                violations.append({'core': core, 'pool': pool, 'bucket': bucket, 'op': rec['op'],
                                   'peak_bytes': rec['bytes'], 'capacity_bytes': CAP[pool],
                                   'excess_bytes': excess, 'live_tensor_count': len(live),
                                   'top25_live_intervals': contributors,
                                   'top25_bytes': sum(it['bytes'] for it in live[:25]),
                                   'all_live_bytes_checked': sum(it['bytes'] for it in live)})
        run.update(groups=groups, per_core_M_V_cycles=loads,
                   per_core_schedule_lengths=list(map(len, words)),
                   shared_component_placements=shared_placements,
                   shared_component_counts_by_core=dict(Counter(x['owner'] for x in shared_placements)),
                   frontier_peaks=memory['bucket_frontier_peaks'],
                   no_spill_guard=memory['step2_no_spill_certificate'],
                   union_guard=memory['union_guard_passes'],
                   violations=violations,
                   max_excess_bytes=max((x['excess_bytes'] for x in violations), default=0))
        save(result)
    result['status'] = 'COMPLETED_STATIC_ONLY'
except Exception as exc:
    result['status'] = 'STOPPED_FIRST_EXCEPTION'
    result['exception'] = f'{type(exc).__name__}: {exc}'
    raise
finally:
    save(result)
