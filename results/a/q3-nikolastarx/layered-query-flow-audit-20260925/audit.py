"""Read-only original-edge quotient of recognized attention rows."""
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q3.construct import Index
from src.q3.attention_rows import _ports, _recognize

OUT = Path(__file__).resolve().parent
EXPECTED = {
    'src/q3/construct.py': '942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73',
    'src/q3/attention_rows.py': 'a4076188bda3037cdaa22686bf85d20051a3d8020e02d78d46db36adc5c10bb9',
    'data/raw/a/official/code/evaluation_validation.py': '103206b8c5c25e37de50cc3193de3989d7c1e01d4a11cc5f509dedd8f9be9a64',
    'data/raw/a/official/data/case_005.json': 'c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f',
    'data/raw/a/official/data/case_086.json': 'ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a',
}


def timeout(_signum, _frame):
    raise TimeoutError('30-second total audit wall limit')


def one(case):
    graph = json.loads((ROOT / f'data/raw/a/official/data/case_{case}.json').read_text())
    index = Index(graph)
    ports = _ports(index)
    rows = _recognize(index, ports)
    node_row = {}
    for i, row in enumerate(rows):
        for u in row['nodes']:
            if u in node_row:
                raise ValueError('recognized row interiors overlap')
            node_row[u] = i
    adjacency = defaultdict(list)
    raw_edges = set()
    for edge in graph['edges']:
        u, v = edge['source'], edge['target']
        adjacency[u].append(v)
        raw_edges.add((u, v))
    for targets in adjacency.values():
        targets.sort()
    quotient = [set() for _ in rows]
    example_paths = {}
    for i, row in enumerate(rows):
        start = row['sink']
        parent = {start: None}
        queue = deque([start])
        while queue:
            u = queue.popleft()
            for v in adjacency[u]:
                if v in parent:
                    continue
                parent[v] = u
                j = node_row.get(v)
                if j is not None and j != i:
                    quotient[i].add(j)
                    if (i, j) not in example_paths:
                        path = []
                        x = v
                        while x is not None:
                            path.append(x)
                            x = parent[x]
                        path.reverse()
                        if not all((a, b) in raw_edges for a, b in zip(path, path[1:])):
                            raise AssertionError('path contains non-original edge')
                        example_paths[(i, j)] = path
                    continue  # first downstream row, never traverse its interior
                queue.append(v)
    indegree = [0] * len(rows)
    for targets in quotient:
        for j in targets:
            indegree[j] += 1
    queue = deque(i for i, count in enumerate(indegree) if count == 0)
    depth = [0] * len(rows)
    seen = 0
    while queue:
        i = queue.popleft()
        seen += 1
        for j in quotient[i]:
            depth[j] = max(depth[j], depth[i] + 1)
            indegree[j] -= 1
            if indegree[j] == 0:
                queue.append(j)
    if seen != len(rows):
        raise ValueError('row quotient cycle')
    # Reproduce only R8's *key identification*, without its flow decomposition.
    q_usage = defaultdict(set)
    k_usage = defaultdict(set)
    v_usage = defaultdict(set)
    for row in rows:
        for t in ports.inputs[row['q']]:
            q_usage[t].add(row['q'])
        for u in row['k']:
            for t in ports.inputs[u]:
                k_usage[t].add(u)
        for u in row['v']:
            for t in ports.inputs[u]:
                v_usage[t].add(u)
    keys = []
    for row in rows:
        candidates = [t for t in ports.inputs[row['q']] if k_usage[t] and v_usage[t]]
        if not candidates:
            raise ValueError('no shared Q/K/V raw input key')
        least = min(len(q_usage[t]) for t in candidates)
        best = [t for t in candidates if len(q_usage[t]) == least]
        if len(best) != 1:
            raise ValueError('ambiguous shared Q/K/V raw input key')
        keys.append(best[0])
    layers = []
    for layer in range(max(depth) + 1):
        members = [i for i, value in enumerate(depth) if value == layer]
        layers.append({'depth': layer, 'row_count': len(members),
                       'row_indices': members, 'distinct_shared_qkv_keys': len({keys[i] for i in members}),
                       'shared_qkv_keys': sorted({keys[i] for i in members})})
    key_layers = defaultdict(set)
    for i, key in enumerate(keys):
        key_layers[key].add(depth[i])
    op_kind = {op['id']: op['op'] for op in graph['ops']}
    edge_records = []
    for (i, j), path in sorted(example_paths.items()):
        between = [u for u in path[1:-1] if u in op_kind and u not in node_row]
        edge_records.append({'from_row': i, 'to_row': j, 'from_depth': depth[i],
                             'to_depth': depth[j], 'path_original_node_ids': path,
                             'between_compute_ops': [{'id': u, 'op': op_kind[u]} for u in between]})
    return {'case': case, 'recognized_rows': len(rows), 'quotient_edges': sum(map(len, quotient)),
            'acyclic': True, 'maximum_depth': max(depth), 'layers': layers,
            'distinct_keys_global': len(set(keys)),
            'keys_reused_across_depths': {key: sorted(values) for key, values in key_layers.items()
                                           if len(values) > 1},
            'row_keys': keys, 'row_sinks': [row['sink'] for row in rows],
            'between_op_kind_counts_on_example_paths': dict(Counter(
                item['op'] for edge in edge_records for item in edge['between_compute_ops'])),
            'first_downstream_row_edges': edge_records}


def main():
    wall, cpu = time.monotonic(), time.process_time()
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(30)
    actual = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in EXPECTED}
    if actual != EXPECTED:
        raise ValueError('frozen input or source SHA mismatch')
    results = []
    for case in ('005', '086'):
        result = one(case)
        results.append(result)
        (OUT / f'{case}.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
        print(json.dumps({'completed_case': case, 'rows': result['recognized_rows'],
                          'depth': result['maximum_depth']}), flush=True)
    summary = {'source_commit': '65d7355ee0856783ede81328915e8bd43227c842',
               'sha256': actual, 'cases': [r['case'] for r in results],
               'cpu_seconds': time.process_time() - cpu,
               'wall_seconds': time.monotonic() - wall, 'scoring_calls': 0}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    signal.alarm(0)


if __name__ == '__main__':
    main()
