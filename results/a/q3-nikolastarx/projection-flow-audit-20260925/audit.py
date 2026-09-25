"""Trace raw Q/K/V key producer frontiers; DSU is descriptive only."""
from collections import defaultdict, deque
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
LAYERED = ROOT/'results/a/q3-nikolastarx/layered-query-flow-audit-20260925'
PART = ROOT/'results/a/q3-nikolastarx/layered-bridge-partition-20260925'
EXPECTED = {
 'src/q3/attention_rows.py':'a4076188bda3037cdaa22686bf85d20051a3d8020e02d78d46db36adc5c10bb9',
 'src/q3/construct.py':'942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73',
 'data/raw/a/official/data/case_005.json':'c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f',
 'data/raw/a/official/data/case_086.json':'ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a',
 'results/a/q3-nikolastarx/layered-query-flow-audit-20260925/005.json':'c1be132c2718c25f91fd6956c70f9200d71b801e83621be512eb3d4dc5d67f4c',
 'results/a/q3-nikolastarx/layered-query-flow-audit-20260925/086.json':'fd659ff3346171c109152c7b795572e92d24b8c11baf29e0d16676c2739bf129',
 'results/a/q3-nikolastarx/layered-bridge-partition-20260925/005.json':'ea0b246d108c2dc165dcabe7830395b9a148044ab12bb59a1a10dafeebb2c78c',
 'results/a/q3-nikolastarx/layered-bridge-partition-20260925/086.json':'ffaff44a66de6c2a643241c2df93a51a8fac1e70339a2785a1e11dbc05519f40',
}


def timeout(_signal, _frame):
    raise TimeoutError('60-second static wall limit')


def path(adj, start, target, row_nodes):
    if start == target:
        return [start]
    parent = {start: None}
    todo = deque([start])
    while todo:
        u = todo.popleft()
        for v in adj[u]:
            if v in parent or (v in row_nodes and v != target):
                continue
            parent[v] = u
            if v == target:
                chain = [v]
                while parent[chain[-1]] is not None:
                    chain.append(parent[chain[-1]])
                return list(reversed(chain))
            todo.append(v)
    raise ValueError(f'no row-stop original-edge path {start}->{target}')


def one(case):
    graph = json.loads((ROOT/f'data/raw/a/official/data/case_{case}.json').read_text())
    layered = json.loads((LAYERED/f'{case}.json').read_text())
    partition = json.loads((PART/f'{case}.json').read_text())
    index = Index(graph)
    ports = _ports(index)
    rows = _recognize(index, ports)
    if [r['sink'] for r in rows] != layered['row_sinks']:
        raise ValueError('frozen row inventory changed')
    depth = {}
    for layer in layered['layers']:
        for i in layer['row_indices']:
            depth[i] = layer['depth']
    row_nodes = {u:i for i,r in enumerate(rows) for u in r['nodes']}
    key_rows = defaultdict(set)
    for i,key in enumerate(layered['row_keys']):
        key_rows[key].add(i)
    keys = sorted(key_rows)
    key_depth = {key: {depth[i] for i in key_rows[key]} for key in keys}
    if any(len(ds) != 1 for ds in key_depth.values()):
        raise ValueError('raw key belongs to multiple depths')
    adjacency = defaultdict(list)
    raw_edges = set()
    for e in graph['edges']:
        adjacency[e['source']].append(e['target'])
        raw_edges.add((e['source'],e['target']))
    for targets in adjacency.values():
        targets.sort()
    parent = {key:key for key in keys}
    def find(key):
        while parent[key] != key:
            key = parent[key]
        return key
    unions = []
    producers = []
    for key in keys:
        producer = ports.producer.get(key)
        if producer is None:
            upstream = []
            source = True
        elif producer in row_nodes:
            upstream = [row_nodes[producer]]
            source = False
        else:
            sig = partition['node_signatures'].get(str(producer))
            if sig is None:
                raise ValueError(f'producer {producer} has no original-op signature')
            upstream = sig['up_rows']
            source = False
        producers.append({'key':key,'depth':next(iter(key_depth[key])),
                          'producer':producer,'source':source,'upstream_first_rows':upstream,
                          'upstream_keys':sorted({layered['row_keys'][i] for i in upstream})})
        for row_id in upstream:
            oldkey = layered['row_keys'][row_id]
            if oldkey == key:
                continue
            if producer in row_nodes:
                chain = [producer,key]
            else:
                chain = path(adjacency, rows[row_id]['sink'], producer, row_nodes) + [key]
            if not all((u,v) in raw_edges for u,v in zip(chain,chain[1:])):
                raise AssertionError('union path contains non-original edge')
            unions.append({'from_key':oldkey,'to_key':key,'from_row':row_id,
                           'from_depth':depth[row_id], 'to_depth':next(iter(key_depth[key])),
                           'producer':producer,'original_edge_path':chain})
            a,b = find(oldkey),find(key)
            if a != b:
                parent[max(a,b)] = min(a,b)
    groups = defaultdict(list)
    for key in keys:
        groups[find(key)].append(key)
    group_records = []
    for root, members in sorted(groups.items()):
        per_layer = {str(layer):sorted(k for k in members if layer in key_depth[k]) for layer in range(3)}
        group_records.append({'root':root,'keys':members,
                              'keys_by_layer':per_layer,
                              'rows_by_layer':{layer:sorted(i for k in per_layer[layer] for i in key_rows[k])
                                               for layer in per_layer},
                              'same_layer_collision':any(len(v)>1 for v in per_layer.values())})
    expected = 7 if case == '005' else 8
    chain = len(group_records)==expected and all(all(len(v)==1 for v in g['keys_by_layer'].values())
                                                for g in group_records)
    return {'case':case,'raw_key_count':len(keys),'union_evidence_count':len(unions),
            'producers':producers,'unions':unions,'groups':group_records,
            'same_layer_collision_groups':sum(g['same_layer_collision'] for g in group_records),
            'one_key_each_layer_chain_count':sum(all(len(v)==1 for v in g['keys_by_layer'].values())
                                                  for g in group_records),
            'expected_chain_count':expected,'all_groups_are_one_key_per_layer_chains':chain}


def main():
    wall,cpu=time.monotonic(),time.process_time()
    signal.signal(signal.SIGALRM,timeout)
    signal.alarm(60)
    actual={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in EXPECTED}
    if actual!=EXPECTED:
        raise ValueError('frozen source or input SHA mismatch')
    for case in ('005','086'):
        result=one(case)
        (OUT/f'{case}.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps({'case':case,'groups':len(result['groups']),
                          'collisions':result['same_layer_collision_groups']}),flush=True)
    (OUT/'summary.json').write_text(json.dumps({'sha256':actual,'wall_seconds':time.monotonic()-wall,
        'cpu_seconds':time.process_time()-cpu,'official_calls':0},indent=2)+'\n')
    signal.alarm(0)


if __name__=='__main__':
    main()
