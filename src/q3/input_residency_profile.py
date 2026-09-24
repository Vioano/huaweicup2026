"""Read-only raw-graph residency profile; no plan, Task, Step3 or E0 calls."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

from .construct import ROOT, Index
from .forest_memory_order import _original_tree
from .forest_reuse_grid import recognize
from .feedback_benchmark import digest, read, write

CASES = ('011', '021', '027', '037', '039', '058', '059', '079', '080', '097')


def profile(graph):
    index = Index(graph)
    model = recognize(index)
    sizes, outputs, trees, _ = _original_tree(index)
    group_for = {tid: g for g, tids in enumerate(model['group_tensor_ids']) for tid in tids}
    input_for = {u: [] for u in index.ops}
    for edge in graph['edges']:
        if edge['source'] in group_for and edge['target'] in input_for:
            input_for[edge['target']].append(edge['source'])
    shapes, tree_work, root_peak = Counter(), Counter(), []
    leaf_pairs = Counter()
    for tree in trees:
        signature, peak, retained = {}, {}, {}
        leaves = [u for u in index.order if u in tree['members'] and not tree['children'][u]]
        for u in index.order:
            if u not in tree['members']:
                continue
            children = sorted(tree['children'][u], key=lambda c: (-(peak[c] - retained[c]), c))
            live, front = 0, 0
            for child in children:
                front = max(front, live + peak[child])
                live += retained[child]
            retained[u] = sizes[outputs[u][0]]
            peak[u] = max(front, live + retained[u])
            if not children:
                leaf_pairs[tuple(sorted(sizes[t] for t in input_for[u]))] += 1
            signature[u] = hashlib.sha256(json.dumps([
                index.ops[u]['op'], index.ops[u]['pipe'], index.duration(u), retained[u],
                sorted(sizes[t] for t in input_for[u]), sorted(signature[c] for c in children)
            ], sort_keys=True).encode()).hexdigest()
        shapes[signature[tree['root']]] += 1
        tree_work[(len(tree['members']), len(leaves),
                   sum(index.duration(u) for u in tree['members'] if index.ops[u]['pipe'] == 'PIPE_M'),
                   sum(index.duration(u) for u in tree['members'] if index.ops[u]['pipe'] == 'PIPE_V'))] += 1
        root_peak.append(peak[tree['root']])
    axis_bytes = [[model['group_bytes'][g] for g in axis] for axis in model['axes']]
    pairs = [model['group_bytes'][a] + model['group_bytes'][b] for a, b in model['cells']]
    return {
        'axis_sizes': list(map(len, model['axes'])), 'axis_group_bytes': axis_bytes,
        'trees': len(trees), 'compute_ops': len(index.ops),
        'whole_input_pair_bytes_min': min(pairs), 'whole_input_pair_bytes_max': max(pairs),
        'tree_work_classes': [{'ops': k[0], 'leaves': k[1], 'M_cycles': k[2], 'V_cycles': k[3],
                               'count': n} for k, n in sorted(tree_work.items())],
        'leaf_external_input_size_classes': [{'bytes': list(k), 'count': n} for k, n in sorted(leaf_pairs.items())],
        'internal_output_bytes': sorted({sizes[outputs[u][0]] for u in index.ops}),
        'internal_frontier_peak_min': min(root_peak), 'internal_frontier_peak_max': max(root_peak),
        'unlabelled_tree_signature_classes': len(shapes),
        'signature_caveat': 'shape/work/size only; not proof that corresponding leaves use the same indexed operands',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = {f['path']: f for f in read(ROOT / 'docs/a/source-manifest.json')['files']}
    from evaluation_validation import read_evaluation_config
    config = ROOT / 'data/raw/a/official/data/config.txt'
    if digest(config) != manifest['data/config.txt']['sha256']:
        raise ValueError('frozen config differs')
    cfg = read_evaluation_config(config)
    cap = cfg['capacity']['L1']
    records = []
    for case in CASES:
        rel = f'data/case_{case}.json'
        raw = ROOT / 'data/raw/a/official' / rel
        if digest(raw) != manifest[rel]['sha256']:
            raise ValueError(f'frozen raw graph differs: {case}')
        row = profile(read(raw))
        row.update(case_id=case, graph_sha256=digest(raw), l1_capacity_bytes=cap,
                   whole_pair_fits_even_without_internal_outputs=row['whole_input_pair_bytes_max'] <= cap)
        records.append(row)
    files = ['src/q3/input_residency_profile.py', 'src/q3/construct.py',
             'src/q3/forest_memory_order.py', 'src/q3/forest_reuse_grid.py']
    write(args.output, {
        'scope': 'raw graph profile; whole-pair capacity is only a necessary condition for full group residency',
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_sha256': {f: digest(ROOT / f) for f in files}, 'config_sha256': digest(config),
        'task_builds': 0, 'local_step3_simulations': 0, 'e0_calls': 0, 'solver_calls': 0,
        'records': records,
    })
    print(json.dumps([{'case': r['case_id'], 'pair_bytes': r['whole_input_pair_bytes_max'],
                       'internal_frontier': r['internal_frontier_peak_max'],
                       'pair_fits': r['whole_pair_fits_even_without_internal_outputs']} for r in records]))


if __name__ == '__main__':
    main()
