"""One fixed read-only recovery analysis. No constructors/evaluators imported."""
import collections, datetime, gzip, hashlib, json, signal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = ROOT / 'results/a/q3-nikolastarx/layered-one-shot-20260925'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    manifest = json.loads((HERE / 'manifest.json').read_text())
    for rel, expected in manifest['inputs'].items():
        assert digest(ROOT / rel) == expected, rel
    assert digest(Path(__file__)) == manifest['script_sha256']
    with (HERE / 'claim.json').open('x') as f:
        json.dump({'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'manifest_sha256': digest(HERE / 'manifest.json')}, f)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('120s')))
    signal.alarm(120)
    graph = json.loads((ROOT / 'data/raw/a/official/data/case_005.json').read_text())
    tensors = {str(t['id']): t for t in graph['tensors']}
    data = [json.loads(gzip.decompress(p.read_bytes())) for p in
            (BASE / 'control/P3.json.gz', BASE / 'run/p3.json.gz')]
    grouped = []
    evictions = []
    for result in data:
        assert (result['scene'], result['problem'], result['cache_mode'], result['num_cores']) == ('B', 3, 'read_only', 5)
        counts = collections.defaultdict(collections.Counter)
        histories = collections.defaultdict(list)
        removed = collections.defaultdict(list)
        for event in result['cache_events']:
            kind, key = event['event'], str(event['tensor_id'])
            assert kind in ('hit', 'miss', 'insert')
            assert key in tensors and tensors[key]['size'] == event['size_bytes']
            if kind in ('hit', 'miss'):
                counts[key][kind + '_bytes'] += event['size_bytes']
                counts[key][kind + '_count'] += 1
            else:
                for victim in event['evicted_tensor_ids']:
                    removed[str(victim)].append(event)
            histories[key].append(event)
        for kind in ('hit', 'miss'):
            assert sum(v[kind + '_bytes'] for v in counts.values()) == result['cache_stats'][kind + '_bytes']
        grouped.append((counts, histories))
        evictions.append(removed)
    all_keys = sorted(set(grouped[0][0]) | set(grouped[1][0]), key=int)
    rows = []
    for key in all_keys:
        old, new = [part[0].get(key, collections.Counter()) for part in grouped]
        rows.append({'tensor_id': key, 'size_bytes': tensors[key]['size'],
                     'old': dict(old), 'new': dict(new),
                     'miss_delta': new['miss_bytes'] - old['miss_bytes'],
                     'hit_delta': new['hit_bytes'] - old['hit_bytes'],
                     'read_delta': sum(new[k] - old[k] for k in ('miss_bytes', 'hit_bytes')),
                     'membership': 'shared' if key in grouped[0][0] and key in grouped[1][0] else
                                   'old_only' if key in grouped[0][0] else 'new_only'})
    rows.sort(key=lambda x: (-x['miss_delta'], int(x['tensor_id'])))
    assert sum(row['miss_delta'] for row in rows) == 75120
    assert sum(row['hit_delta'] for row in rows) == -318528
    assert sum(row['read_delta'] for row in rows) == -243408
    top = [r for r in rows if r['miss_delta'] > 0][:12]
    detail = []
    for row in top:
        key = row['tensor_id']
        detail.append({'tensor_id': key, 'old_events': grouped[0][1][key],
                       'new_events': grouped[1][1][key],
                       'old_evicted_by': evictions[0][key], 'new_evicted_by': evictions[1][key]})
    summary = {'schema': 'r9-cache-key-difference-v2', 'old_M3': data[0]['makespan'],
               'new_M3': data[1]['makespan'], 'source_hashes': manifest['inputs'],
               'miss_delta': 75120, 'hit_delta': -318528, 'read_delta': -243408,
               'positive_miss_sum': sum(max(0, row['miss_delta']) for row in rows),
               'negative_miss_sum': sum(min(0, row['miss_delta']) for row in rows),
               'membership_counts': dict(collections.Counter(row['membership'] for row in rows)),
               'top_positive_miss_keys': top,
               'counts': {'analysis_processes_this_recovery': 1, 'prior_failed_analysis_processes': 1,
                          'constructor': 0, 'Task': 0, 'Step': 0, 'E0': 0, 'E1': 0, 'E2': 0,
                          'pipe_bound': 0, 'automatic_retries': 0},
               'limits': ['Key is verified original logical tensor id plus original size.',
                          'Generated COPY op ids differ across plans; no per-operation pairing is asserted.',
                          'An earlier recorded eviction alone does not prove a miss caused longer makespan.',
                          'This compares existing official traces; it is not a new cache simulation.']}
    for name, obj in [('summary.json', summary), ('key-deltas.json', rows), ('top-key-events.json', detail)]:
        (HERE / name).write_text(json.dumps(obj, indent=2) + '\n')
    signal.alarm(0)
    print(json.dumps({k: summary[k] for k in ['miss_delta','hit_delta','read_delta',
                     'positive_miss_sum','negative_miss_sum','membership_counts','top_positive_miss_keys']}))

if __name__ == '__main__':
    main()
