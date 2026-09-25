"""One fixed graph/plan envelope audit; pure static graph operations only."""
import hashlib
import json
import time
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
INPUTS = {
    'graph': ('data/raw/a/official/data/case_005.json', 'c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f'),
    'base': ('results/a/q3-nikolastarx/layered-one-shot-20260925/candidate/case_005_multicore_res.json', '2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a'),
    'candidate': ('results/a/q3-nikolastarx/convex-pilot-cut-20260925/CANDIDATE_UNVALIDATED.json', 'f4c58ccf77f5a8add20687eb20247ede169ff34b78a0f24e1c8bda805f1c75a2'),
}

def load(key):
    rel, expected = INPUTS[key]
    raw = (ROOT / rel).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected, key
    return json.loads(raw)

def kahn(nodes, arcs):
    succ = {u: set() for u in nodes}
    indegree = dict.fromkeys(nodes, 0)
    for u, v in arcs:
        if v not in succ[u]:
            succ[u].add(v)
            indegree[v] += 1
    ready = deque(sorted(u for u in nodes if indegree[u] == 0))
    order = []
    while ready:
        u = ready.popleft()
        order.append(u)
        for v in sorted(succ[u]):
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)
    return {'nodes': len(nodes), 'arcs': len(arcs), 'visited': len(order),
            'acyclic': len(order) == len(nodes),
            'unvisited_first20': sorted(set(nodes) - set(order))[:20]}

def main():
    begin = time.monotonic()
    graph, base, candidate = [load(x) for x in ('graph', 'base', 'candidate')]
    ops = {o['id']: o for o in graph['ops']}
    tensors = {t['id'] for t in graph['tensors']}
    prod, cons = defaultdict(set), defaultdict(set)
    original = set()
    for edge in graph['edges']:
        u, v = edge['source'], edge['target']
        if u in ops and v in tensors: prod[v].add(u)
        elif u in tensors and v in ops: cons[u].add(v)
        elif u in ops and v in ops: original.add((u, v))
        else: raise ValueError('unrecognized edge')
    for t in tensors:
        original.update((u, v) for u in prod[t] for v in cons[t])
    mapping = {int(k): v for k, v in base['node_to_subgraph'].items()}
    target = {int(k): v for k, v in candidate['node_to_subgraph'].items()}
    assert set(mapping) == set(target)
    inverse = {sg: op for op, sg in mapping.items()}
    assert len(inverse) == len(mapping)
    core_edges = set()
    for word in base['core_schedules']:
        core_edges.update((inverse[u], inverse[v]) for u, v in zip(word, word[1:]))
    envelope = original | core_edges
    old = kahn(set(ops), envelope)
    assert old['acyclic'], 'base full-core envelope is not a DAG'
    label = {u: 'sg:' + str(target[u]) if u in target else 'raw-copy:' + str(u) for u in ops}
    vertices = set(label.values())
    arcs = {(label[u], label[v]) for u, v in envelope if label[u] != label[v]}
    new = kahn(vertices, arcs)
    result = {
        'inputs_sha256': {k: v[1] for k, v in INPUTS.items()},
        'base_envelope': old, 'candidate_envelope': new,
        'added_core_adjacencies': len(core_edges - original),
        'official_calls': 0, 'candidate_constructions': 0,
        'elapsed_seconds': time.monotonic() - begin,
        'scope': 'Fixed candidate only. Full original-op DAG plus all five core compute-word adjacency edges. These extra edges form a sufficient direction envelope, not actual execution barriers or a Makespan lower bound. Does not prove new Step1/capacity/runtime behavior.'
    }
    (OUT / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n')

if __name__ == '__main__':
    main()
