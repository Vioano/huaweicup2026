"""Deterministic original-op partition by nearest recognized row frontiers."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q3.construct import Index, topo
from src.q3.attention_rows import _ports, _recognize
from stub_multicore_cut_and_schedule import _build_op_adjacency

OUT = Path(__file__).resolve().parent
AUDIT = ROOT / 'results/a/q3-nikolastarx/layered-query-flow-audit-20260925'
EXPECTED = {
 'src/q3/query_flow.py': '88aca80c6e5dac46e56a6894a165e40aab7e21ac68db66b6dac83539a1d2d2f0',
 'src/q3/attention_rows.py': 'a4076188bda3037cdaa22686bf85d20051a3d8020e02d78d46db36adc5c10bb9',
 'src/q3/construct.py': '942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73',
 'data/raw/a/official/data/case_005.json': 'c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f',
 'data/raw/a/official/data/case_086.json': 'ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a',
 'results/a/q3-nikolastarx/layered-query-flow-audit-20260925/005.json': 'c1be132c2718c25f91fd6956c70f9200d71b801e83621be512eb3d4dc5d67f4c',
 'results/a/q3-nikolastarx/layered-query-flow-audit-20260925/086.json': 'fd659ff3346171c109152c7b795572e92d24b8c11baf29e0d16676c2739bf129',
}


def timeout(_signum, _frame):
    raise TimeoutError('60-second total static partition wall limit')


def one(case):
    graph = json.loads((ROOT / f'data/raw/a/official/data/case_{case}.json').read_text())
    prior = json.loads((AUDIT / f'{case}.json').read_text())
    index = Index(graph)
    rows = _recognize(index, _ports(index))
    if [row['sink'] for row in rows] != prior['row_sinks']:
        raise ValueError('recognized row list differs from frozen layered audit')
    depth = {}
    for layer in prior['layers']:
        for i in layer['row_indices']:
            if i in depth:
                raise ValueError('duplicate row depth')
            depth[i] = layer['depth']
    if set(depth) != set(range(len(rows))):
        raise ValueError('missing row depth')
    row_keys = prior['row_keys']
    if len(row_keys) != len(rows):
        raise ValueError('row-key count mismatch')
    all_ops = {op['id']: op for op in graph['ops']}
    pred, succ = _build_op_adjacency(graph)
    order = topo(all_ops, succ)
    node_row = {}
    for i, row in enumerate(rows):
        for u in row['nodes']:
            if u in node_row:
                raise ValueError('overlapping row interiors')
            node_row[u] = i
    up = {}
    for u in order:
        up[u] = frozenset((node_row[u],)) if u in node_row else frozenset().union(*(up[p] for p in pred[u]))
    down = {}
    for u in reversed(order):
        down[u] = frozenset((node_row[u],)) if u in node_row else frozenset().union(*(down[v] for v in succ[u]))

    labels = {}
    signatures = {}
    for u in order:
        if u in node_row:
            i = node_row[u]
            labels[u] = ('row', f'L{depth[i]}', f'row_{i}')
            signatures[u] = {'up_rows': [i], 'down_rows': [i], 'up_keys': [row_keys[i]],
                             'down_keys': [row_keys[i]], 'bypass': False}
            continue
        upstream, downstream = up[u], down[u]
        ukeys = {row_keys[i] for i in upstream}
        dkeys = {row_keys[i] for i in downstream}
        udepth = {depth[i] for i in upstream}
        ddepth = {depth[i] for i in downstream}
        if upstream and downstream:
            role = 'bridge'
            band = 'U' + ','.join(map(str, sorted(udepth))) + '_D' + ','.join(map(str, sorted(ddepth)))
            relation = ('many' if len(ukeys) > 1 else 'one') + '_to_' + ('many' if len(dkeys) > 1 else 'one')
        elif downstream:
            role = 'source'
            band = 'D' + ','.join(map(str, sorted(ddepth)))
            relation = 'shared' if len(dkeys) > 1 else 'private'
        elif upstream:
            role = 'tail'
            band = 'U' + ','.join(map(str, sorted(udepth)))
            relation = 'shared' if len(ukeys) > 1 else 'private'
        else:
            role, band, relation = 'detached', 'none', 'none'
        labels[u] = (role, band, relation)
        signatures[u] = {'up_rows': sorted(upstream), 'down_rows': sorted(downstream),
                         'up_keys': sorted(ukeys), 'down_keys': sorted(dkeys),
                         'bypass': any(b-a >= 2 for a in udepth for b in ddepth)}

    # Connected components are only an inventory grouping, not merged operations.
    members = defaultdict(set)
    for u, label in labels.items():
        members[label].add(u)
    components = []
    node_to_component = {}
    for label in sorted(members):
        unseen = members[label].copy()
        while unseen:
            seed = min(unseen)
            unseen.remove(seed)
            stack, part = [seed], []
            while stack:
                u = stack.pop()
                part.append(u)
                for v in sorted((pred[u] | succ[u]) & unseen, reverse=True):
                    unseen.remove(v)
                    stack.append(v)
            part.sort()
            cid = len(components)
            for u in part:
                if u in node_to_component:
                    raise AssertionError('op assigned twice')
                node_to_component[u] = cid
            work_counter = Counter()
            for u in part:
                work_counter[all_ops[u]['pipe']] += all_ops[u]['cycles']
            components.append({'id': cid, 'role': label[0], 'band': label[1],
                               'relation': label[2], 'ops': part,
                               'op_count': len(part), 'original_pipe_cycles': dict(sorted(work_counter.items())),
                               'bypass_ops': sum(signatures[u]['bypass'] for u in part)})
    if set(node_to_component) != set(all_ops) or sum(c['op_count'] for c in components) != len(all_ops):
        raise AssertionError('original op partition incomplete')
    original_work = Counter()
    for op in all_ops.values():
        original_work[op['pipe']] += op['cycles']
    partition_work = Counter()
    for component in components:
        partition_work.update(component['original_pipe_cycles'])
    if original_work != partition_work:
        raise AssertionError('pipe-cycle work not conserved')

    raw_edges = {(e['source'], e['target']) for e in graph['edges']}
    bypass = next((edge for edge in prior['first_downstream_row_edges']
                   if edge['from_depth'] == 0 and edge['to_depth'] == 2), None)
    if bypass is None or not all((a,b) in raw_edges for a,b in zip(
            bypass['path_original_node_ids'], bypass['path_original_node_ids'][1:])):
        raise ValueError('missing or invalid original-edge bypass witness')
    summaries = defaultdict(lambda: {'op_count': 0, 'component_count': 0, 'bypass_ops': 0,
                                     'original_pipe_cycles': Counter()})
    for c in components:
        key = '|'.join((c['role'], c['band'], c['relation']))
        s = summaries[key]
        s['op_count'] += c['op_count']
        s['component_count'] += 1
        s['bypass_ops'] += c['bypass_ops']
        s['original_pipe_cycles'].update(c['original_pipe_cycles'])
    return {'case': case, 'original_op_count': len(all_ops), 'row_count': len(rows),
            'component_count': len(components), 'original_pipe_cycles': dict(sorted(original_work.items())),
            'partition_complete_unique': True, 'summary': dict(sorted(summaries.items())),
            'components': components, 'node_to_component': node_to_component,
            'node_signatures': signatures, 'bypass_original_path': bypass['path_original_node_ids']}


def main():
    start_wall, start_cpu = time.monotonic(), time.process_time()
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(60)
    actual = {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in EXPECTED}
    if actual != EXPECTED:
        raise ValueError('frozen source or input hash changed')
    for case in ('005', '086'):
        result = one(case)
        (OUT/f'{case}.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
        print(json.dumps({'case': case, 'ops': result['original_op_count'],
                          'components': result['component_count']}), flush=True)
    (OUT/'summary.json').write_text(json.dumps({'sha256': actual,
        'wall_seconds': time.monotonic()-start_wall, 'cpu_seconds': time.process_time()-start_cpu,
        'official_calls': 0}, indent=2) + '\n')
    signal.alarm(0)


if __name__ == '__main__':
    main()
