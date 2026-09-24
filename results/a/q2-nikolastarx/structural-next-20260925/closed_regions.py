"""Inspect closed fork/join regions; no construction or evaluator calls."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.dag_direct import DAGIndex


def tree(order, incoming):
    """DAG dominator tree using LCA of already processed predecessors.

    None is a virtual source. Reversing the graph yields postdominators.
    This implementation climbs parent pointers, O(E * tree height).
    """
    parent, depth = {None: None}, {None: 0}

    def lca(a, b):
        while a != b:
            if depth[a] >= depth[b]:
                a = parent[a]
            else:
                b = parent[b]
        return a

    for u in order:
        ps = sorted(incoming[u])
        common = ps[0] if ps else None
        for p in ps[1:]:
            common = lca(common, p)
        parent[u] = common
        depth[u] = depth[common] + 1
    return parent, depth


def discover(index):
    post, _ = tree(list(reversed(index.order)), index.succ)
    accepted, rejected = [], Counter()
    for entry in index.order:
        if len(index.succ[entry]) < 2:
            continue
        leave = post[entry]
        if leave is None:
            rejected['no_real_common_postdominator'] += 1
            continue
        interior, todo = set(), list(index.succ[entry])
        while todo:
            u = todo.pop()
            if u == leave or u in interior:
                continue
            interior.add(u)
            todo.extend(index.succ[u])
        # Explicit boundary checks, rather than inferring closure from width.
        if any(index.pred[u] - interior - {entry} for u in interior):
            rejected['outside_incoming_edge'] += 1
            continue
        if any(index.succ[u] - interior - {leave} for u in interior):
            rejected['outside_outgoing_edge'] += 1
            continue
        pending, arms = set(interior), []
        while pending:
            arm, todo = set(), [min(pending)]
            while todo:
                u = todo.pop()
                if u not in pending:
                    continue
                pending.remove(u)
                arm.add(u)
                todo.extend((index.pred[u] | index.succ[u]) & pending)
            arms.append(arm)
        if len(arms) < 2:
            rejected['branches_connected_before_exit'] += 1
            continue
        arms.sort(key=lambda a: (-len(a), min(a)))
        work = [Counter() for _ in arms]
        for i, arm in enumerate(arms):
            for u in arm:
                work[i][index.ops[u]['pipe']] += index.duration(u)
        accepted.append({
            'entry': entry, 'exit': leave, 'interior_ops': len(interior),
            'arms': len(arms), 'arm_sizes': [len(a) for a in arms],
            'arm_pipe_work': [dict(w) for w in work],
            'same_single_compute_pipe': len({index.ops[u]['pipe'] for u in interior | {entry, leave}}) == 1,
        })
    accepted.sort(key=lambda r: (-r['interior_ops'], r['entry']))
    return accepted, dict(rejected)


def main():
    parent = Path(__file__).parent
    old = json.loads((parent / 'summary.json').read_text())
    rows = []
    for original in old['rows']:
        raw = (ROOT / f"data/raw/a/official/data/case_{original['case']}.json").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == original['graph_sha256']
        index = DAGIndex(json.loads(raw))
        regions, rejected = discover(index)
        rows.append({
            'case': original['case'], 'graph_sha256': original['graph_sha256'],
            'closed_parallel_regions': len(regions),
            'same_single_pipe_regions': sum(r['same_single_compute_pipe'] for r in regions),
            'largest_interior': max((r['interior_ops'] for r in regions), default=0),
            'rejections': rejected, 'regions': regions,
        })
    report = {
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'Original contracted compute DAG only. Regions may nest; do not sum their sizes as coverage. No memory/DDR timing or applicability of a single-pipe theorem is inferred.',
        'calls': {'solver': 0, 'E0': 0, 'E1': 0, 'E2': 0}, 'rows': rows,
    }
    out = parent / 'closed-regions.json'
    with out.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps([{k: row[k] for k in ('case', 'closed_parallel_regions', 'same_single_pipe_regions', 'largest_interior', 'rejections')} for row in rows], indent=2))


if __name__ == '__main__':
    main()
