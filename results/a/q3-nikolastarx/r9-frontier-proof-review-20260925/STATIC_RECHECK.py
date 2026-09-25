"""Independent, read-only raw graph/plan R9 checks used in the proof review.

This is a saved reconstruction of the two Python heredocs executed during the
review; the original stdout is in STATIC_READBACK.md. It calls no official
Task, Step, evaluator, candidate constructor, or pipe_bound function.
"""
import json
import collections
from pathlib import Path


BASE = Path('AI chats/20260925-Pro-P3-多层查询亲和/附件')
for nn in ('005', '086'):
    graph = json.loads(Path(f'data/raw/a/official/data/case_{nn}.json').read_text())
    plan = json.loads((BASE / f'R9_candidate_{nn}_plan.json').read_text())
    meta = json.loads((BASE / f'R9_candidate_{nn}_metadata.json').read_text())
    evidence = json.loads((BASE / f'R9_candidate_{nn}_evidence.json').read_text())
    original = {o['id']: o for o in graph['ops']}
    compute = {u: o for u, o in original.items() if o['op'] not in ('COPY_IN', 'COPY_OUT')}
    tensors = {t['id']: t for t in graph['tensors']}
    mapping = {int(u): sg for u, sg in plan['node_to_subgraph'].items()}
    owner = {r['op']: r['core'] for r in evidence['ownership']}
    output = collections.defaultdict(set)
    for e in graph['edges']:
        if e['source'] in compute and e['target'] in tensors:
            output[e['source']].add(e['target'])
    print(nn, 'raw', len(original), len(tensors), len(graph['edges']),
          'eligible', len(compute), 'mapping', len(mapping), 'ownership', len(owner),
          'noout', sum(not output[u] for u in compute), 'plan-keys', list(plan),
          'meta-matches', meta['original_compute_ops'] == len(compute),
          'owner-coverage', set(owner) == set(compute),
          'mp-coverage', set(mapping) == set(compute))

    sg_to_op = {sg: u for u, sg in mapping.items()}
    words = [[sg_to_op[sg] for sg in ss] for ss in plan['core_schedules']]
    position = {u: (c, i) for c, word in enumerate(words) for i, u in enumerate(word)}
    producer = {}
    consumers = collections.defaultdict(set)
    for e in graph['edges']:
        a, b = e['source'], e['target']
        if a in compute and b in tensors:
            producer[b] = a
        if a in tensors and b in compute:
            consumers[a].add(b)
    diff = [{'L1': [0] * (len(word) + 1), 'UB': [0] * (len(word) + 1)} for word in words]
    for tid, tensor in tensors.items():
        touches = collections.defaultdict(list)
        source = producer.get(tid)
        if source in position:
            touches[position[source][0]].append(position[source][1])
        for v in consumers[tid]:
            touches[position[v][0]].append(position[v][1])
        for c, points in touches.items():
            pool = 'UB' if tensor['pos'] == 'DDR' else tensor['pos']
            first, last = min(points), max(points)
            diff[c][pool][first] += tensor['size']
            diff[c][pool][last + 1] -= tensor['size']
    peaks = []
    for row in diff:
        core_peaks = []
        for pool in ('L1', 'UB'):
            running = maximum = 0
            for delta in row[pool][:-1]:
                running += delta
                maximum = max(maximum, running)
            core_peaks.append(maximum)
        peaks.append(core_peaks)
    expected = [[c['L1']['bytes'], c['UB']['bytes']]
                for c in meta['memory']['bucket_frontier_peaks']]
    remote = collections.Counter()
    wrong = []
    by_op = {r['op']: r for r in evidence['ownership']}
    for tid, u in producer.items():
        for v in consumers[tid]:
            if owner[u] == owner[v]:
                continue
            a, b = by_op[u], by_op[v]
            if not (a['phase'] == 0 and b['phase'] > 0) and not (
                a['anchor'] and b['anchor'] and a['anchor'][0] == 'P'
                and b['anchor'][0] == 'A' and a['anchor'][1] == b['anchor'][1]
            ):
                wrong.append((u, v, a['phase'], b['phase']))
            remote[(a['phase'], b['phase'])] += 1
    print(nn, 'frontier_match', peaks == expected, 'peaks', peaks,
          'cross_bad', wrong[:3], 'cross_phase_count', dict(remote))

    priority = evidence['global_topological_priority']
    rank = {u: i for i, u in enumerate(priority)}
    edges = collections.defaultdict(dict)
    for tid, u in producer.items():
        for v in consumers[tid]:
            edges[u][v] = int(owner[u] != owner[v])
    for word in words:
        for u, v in zip(word, word[1:]):
            edges[u][v] = 0
    count = {u: 0 for u in priority}
    backward = []
    for u in priority:
        for v, crossing in edges[u].items():
            if rank[u] >= rank[v]:
                backward.append((u, v))
            count[v] = max(count[v], count[u] + crossing)
    print(nn, 'priority_cover', set(priority) == set(compute)
          and len(priority) == len(compute), 'word_cover',
          set(u for word in words for u in word) == set(compute),
          'backward', len(backward), 'max_cross', max(count.values()),
          'reported', meta['whole_path_envelope']['max_remote_edges'])
