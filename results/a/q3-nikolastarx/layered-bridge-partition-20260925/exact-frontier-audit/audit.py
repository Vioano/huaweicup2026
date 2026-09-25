"""Audit exact row-frontier components and both quotient DAGs."""
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
from stub_multicore_cut_and_schedule import _build_op_adjacency

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
EXPECTED = {
 'results/a/q3-nikolastarx/layered-bridge-partition-20260925/partition.py': '2ba574437560e23edd50e69ce393d57a2294f50e6c544ae5840ec7c4dd99eb3b',
 'results/a/q3-nikolastarx/layered-bridge-partition-20260925/005.json': 'ea0b246d108c2dc165dcabe7830395b9a148044ab12bb59a1a10dafeebb2c78c',
 'results/a/q3-nikolastarx/layered-bridge-partition-20260925/086.json': 'ffaff44a66de6c2a643241c2df93a51a8fac1e70339a2785a1e11dbc05519f40',
 'results/a/q3-nikolastarx/layered-bridge-partition-20260925/FRONTIER_LEMMA.md': '45e98edda00d56ec9a716716e0bac6157320eae493fcb8473db08f5d809d6bbc',
 'data/raw/a/official/data/case_005.json': 'c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f',
 'data/raw/a/official/data/case_086.json': 'ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a',
 'data/raw/a/official/code/stub_multicore_cut_and_schedule.py': '0a3a3b79b5173b466fc05fc8d33b72d11d90b4df78995435853d91c632a35892',
}


def timeout(_signum, _frame):
    raise TimeoutError('60-second total static audit wall limit')


def quotient(owner, succ, raw_succ, raw_pred):
    qsucc = {g: set() for g in set(owner.values())}
    evidence = {}
    for u in sorted(succ):
        for v in sorted(succ[u]):
            a, b = owner[u], owner[v]
            if a == b:
                continue
            qsucc[a].add(b)
            if (a, b) not in evidence:
                if v in raw_succ[u]:
                    path = [u, v]
                else:
                    middle = sorted(raw_succ[u] & raw_pred[v])
                    if not middle:
                        raise AssertionError(f'no original raw edge witness for op edge {u}->{v}')
                    path = [u, middle[0], v]
                evidence[(a, b)] = path
    degree = {g: 0 for g in qsucc}
    for targets in qsucc.values():
        for g in targets:
            degree[g] += 1
    ready = deque(sorted(g for g in degree if degree[g] == 0))
    visited = 0
    while ready:
        g = ready.popleft()
        visited += 1
        for h in sorted(qsucc[g]):
            degree[h] -= 1
            if degree[h] == 0:
                ready.append(h)
    cycle = []
    if visited != len(qsucc):
        # Explicit finite DFS cycle in the contracted quotient.
        color, parent = {}, {}
        for start in sorted(qsucc):
            if start in color:
                continue
            color[start] = 1
            stack = [(start, iter(sorted(qsucc[start])))]
            while stack and not cycle:
                u, it = stack[-1]
                try:
                    v = next(it)
                except StopIteration:
                    color[u] = 2
                    stack.pop()
                    continue
                if v not in color:
                    parent[v] = u
                    color[v] = 1
                    stack.append((v, iter(sorted(qsucc[v]))))
                elif color[v] == 1:
                    chain = [u]
                    while chain[-1] != v:
                        chain.append(parent[chain[-1]])
                    cycle = list(reversed(chain)) + [v]
            if cycle:
                break
    return {'groups': len(qsucc), 'edges': sum(map(len, qsucc.values())),
            'acyclic': not cycle and visited == len(qsucc),
            'cycle_groups': cycle,
            'cycle_original_edge_paths': [evidence[(a, b)] for a, b in zip(cycle, cycle[1:])]}


def one(case):
    graph = json.loads((ROOT / f'data/raw/a/official/data/case_{case}.json').read_text())
    prior = json.loads((BASE / f'{case}.json').read_text())
    ops = {op['id']: op for op in graph['ops']}
    signatures = {int(u): s for u, s in prior['node_signatures'].items()}
    if set(signatures) != set(ops):
        raise AssertionError('signature does not cover all original ops')
    pred, succ = _build_op_adjacency(graph)
    raw_succ, raw_pred = defaultdict(set), defaultdict(set)
    for edge in graph['edges']:
        u, v = edge['source'], edge['target']
        raw_succ[u].add(v)
        raw_pred[v].add(u)
    row_owner = {}
    rows = {}
    for c in prior['components']:
        if c['role'] != 'row':
            continue
        if not c['relation'].startswith('row_'):
            raise AssertionError('malformed row group')
        rid = int(c['relation'][4:])
        if rid in rows:
            raise AssertionError('row split across old components')
        rows[rid] = c['ops']
        for u in c['ops']:
            if u in row_owner:
                raise AssertionError('overlapping rows')
            row_owner[u] = f'R{rid}'
    row_only_owner = {u: row_owner.get(u, f'O{u}') for u in ops}
    row_only = quotient(row_only_owner, succ, raw_succ, raw_pred)

    by_sig = defaultdict(set)
    for u in ops:
        if u in row_owner:
            continue
        s = signatures[u]
        key = (tuple(s['up_rows']), tuple(s['down_rows']))
        by_sig[key].add(u)
    exact_components = []
    exact_owner = row_owner.copy()
    for key in sorted(by_sig):
        remaining = by_sig[key].copy()
        while remaining:
            seed = min(remaining)
            remaining.remove(seed)
            part, stack = [], [seed]
            while stack:
                u = stack.pop()
                part.append(u)
                for v in sorted((pred[u] | succ[u]) & remaining, reverse=True):
                    remaining.remove(v)
                    stack.append(v)
            part.sort()
            cid = len(exact_components)
            for u in part:
                if u in exact_owner:
                    raise AssertionError('original op assigned twice')
                exact_owner[u] = f'C{cid}'
            work = Counter()
            for u in part:
                work[ops[u]['pipe']] += ops[u]['cycles']
            exact_components.append({'id': cid, 'up_rows': list(key[0]), 'down_rows': list(key[1]),
                                     'ops': part, 'op_count': len(part),
                                     'original_pipe_cycles': dict(sorted(work.items()))})
    if set(exact_owner) != set(ops) or sum(len(c['ops']) for c in exact_components) + sum(map(len, rows.values())) != len(ops):
        raise AssertionError('unique complete original op coverage failed')
    total = Counter()
    for op in ops.values():
        total[op['pipe']] += op['cycles']
    grouped = Counter()
    for c in exact_components:
        grouped.update(c['original_pipe_cycles'])
    for members in rows.values():
        for u in members:
            grouped[ops[u]['pipe']] += ops[u]['cycles']
    if total != grouped:
        raise AssertionError('original pipe cycle conservation failed')
    joint = quotient(exact_owner, succ, raw_succ, raw_pred)
    return {'case': case, 'original_op_count': len(ops), 'row_count': len(rows),
            'exact_nonrow_component_count': len(exact_components),
            'distinct_nonrow_signatures': len(by_sig), 'coverage_unique': True,
            'original_pipe_cycles': dict(sorted(total.items())),
            'grouped_pipe_cycles': dict(sorted(grouped.items())),
            'row_only_quotient': row_only, 'joint_quotient': joint,
            'exact_components': exact_components,
            'node_to_exact_group': {str(u): exact_owner[u] for u in sorted(exact_owner)}}


def main():
    wall, cpu = time.monotonic(), time.process_time()
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(60)
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in EXPECTED}
    if hashes != EXPECTED:
        raise ValueError('frozen source or input hash changed')
    for case in ('005', '086'):
        result = one(case)
        (OUT / f'{case}.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
        print(json.dumps({'case': case, 'row_only_acyclic': result['row_only_quotient']['acyclic'],
                          'joint_acyclic': result['joint_quotient']['acyclic']}), flush=True)
    (OUT / 'summary.json').write_text(json.dumps({'sha256': hashes,
        'wall_seconds': time.monotonic()-wall, 'cpu_seconds': time.process_time()-cpu,
        'official_calls': 0}, indent=2) + '\n')
    signal.alarm(0)


if __name__ == '__main__':
    main()
