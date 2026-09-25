"""Read-only structural audit of saved 069/071 plans; standard library only."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SUMMARY = ROOT / 'results/a/q3-nikolastarx/attention-headroom-audit-20260925/summary.json'


def read(path, expected):
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    assert actual == expected, (path, actual, expected)
    return json.loads(raw)


def artifact(ref, forest_root):
    path = ROOT / ref['path']
    source = 'current_worktree'
    if not path.exists():
        path = forest_root / ref['path']
        source = 'forest_root'
    return read(path, ref['sha256']), source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--forest-root', required=True, type=Path)
    args = parser.parse_args()
    source = json.loads((ROOT / 'docs/a/source-manifest.json').read_text())
    official = {x['path']: x['sha256'] for x in source['files']}
    prior = json.loads(SUMMARY.read_text())
    output = {'prior_summary': str(SUMMARY.relative_to(ROOT)), 'prior_summary_sha256': hashlib.sha256(SUMMARY.read_bytes()).hexdigest(),
              'definition': 'A path boundary is one saved longest-path original compute dependency whose endpoints have different assigned cores. For its two capsule IDs, pair frontier is every original producer-tensor-reader dependency between those exact capsules, counted as distinct source ops, tensors, target ops, and triples. This local quotient boundary is not graph treewidth or a physical timing bound.',
              'cases': []}
    for row in prior['cases']:
        case = row['case_id']
        if case not in ('069', '071'):
            continue
        graph_path = ROOT / f'data/raw/a/official/data/case_{case}.json'
        graph = read(graph_path, official[f'data/case_{case}.json'])
        assert official[f'data/case_{case}.json'] == row['graph_sha256']
        plan, plan_source = artifact(row['artifacts']['plan'], args.forest_root)
        trace, trace_source = artifact(row['artifacts']['trace'], args.forest_root)
        selected, = [x for x in trace['candidates'] if x.get('artifacts', {}).get('plan', {}).get('sha256') == row['artifacts']['plan']['sha256']]
        dispatch = selected['metadata']['capsule_dispatch']
        owner = {}
        for item in dispatch:
            for op in item['nodes']:
                assert op not in owner
                owner[op] = {'capsule': item['capsule'], 'kind': item['kind'], 'core': item['core']}
        assert len(owner) == len(plan['node_to_subgraph'])
        ops = {x['id']: x for x in graph['ops']}
        subgraph_core = {}
        for core, schedule in enumerate(plan['core_schedules']):
            for subgraph in schedule:
                assert subgraph not in subgraph_core
                subgraph_core[subgraph] = core
        plan_core = {int(op): subgraph_core[sg] for op, sg in plan['node_to_subgraph'].items()}
        assert set(plan_core) == set(owner) <= set(ops)
        assert all(plan_core[op] == item['core'] for op, item in owner.items())
        tensors = {x['id']: x for x in graph['tensors']}
        producers, readers = defaultdict(set), defaultdict(set)
        for edge in graph['edges']:
            a, b = edge['source'], edge['target']
            if a in ops and b in tensors:
                producers[b].add(a)
            if a in tensors and b in ops:
                readers[a].add(b)
        dep = defaultdict(list)
        triples = []
        for tensor in tensors:
            for a in producers[tensor]:
                for b in readers[tensor]:
                    dep[a, b].append(tensor)
                    triples.append((a, tensor, b))
        boundaries = []
        path = row['bound']['with_cross_core_delay']
        segments = path['segments']
        assert sum(x['operations'] for x in segments) == len(path['path_ops'])
        short_count = 3 if case == '071' else 2
        short_ops = path['path_ops'][:sum(x['operations'] for x in segments[:short_count])]
        short_capsules = {owner[x]['capsule'] for x in short_ops}
        union_ops = {x for x, item in owner.items() if item['capsule'] in short_capsules}
        cut = [(a, t, b) for a, t, b in triples if (a in union_ops) != (b in union_ops)]
        union_frontier = {'path_ops': short_ops, 'capsules': sorted(short_capsules), 'union_ops': len(union_ops),
                          'external_dependency_triples': len(cut), 'external_tensors': len({t for _, t, _ in cut}),
                          'external_source_ops': len({a for a, _, _ in cut}), 'external_target_ops': len({b for _, _, b in cut}),
                          'external_tensor_bytes_unique': sum(tensors[t]['size'] for t in {t for _, t, _ in cut})}
        for i, edge in enumerate(path['cross_core_path_edges']):
            a, b = edge['source'], edge['target']
            ids = sorted(dep[a, b])
            assert ids, (case, a, b)
            own_a, own_b = owner.get(a), owner.get(b)
            assert plan_core[a] == own_a['core'] == edge['source_core']
            assert plan_core[b] == own_b['core'] == edge['target_core']
            assert plan_core[a] != plan_core[b]
            front = []
            if own_a and own_b:
                front = [(x, t, y) for x, t, y in triples if owner.get(x, {}).get('capsule') == own_a['capsule'] and owner.get(y, {}).get('capsule') == own_b['capsule']]
            boundaries.append({'source': a, 'target': b, 'source_op': ops[a]['op'], 'source_cycles': ops[a]['cycles'],
                               'target_op': ops[b]['op'], 'target_cycles': ops[b]['cycles'],
                               'source_core': edge['source_core'], 'target_core': edge['target_core'],
                               'source_capsule': own_a, 'target_capsule': own_b,
                               'connecting_tensors': [{'id': t, 'bytes': tensors[t]['size'], 'other_readers': sorted(readers[t] - {b})} for t in ids],
                               'preceding_segment_ops': segments[i]['operations'], 'following_segment_ops': segments[i+1]['operations'],
                               'pair_frontier': {'dependency_triples': len(front), 'source_ops': len({x for x, _, _ in front}), 'tensors': len({t for _, t, _ in front}), 'target_ops': len({y for _, _, y in front})} if own_a and own_b else None})
        output['cases'].append({'case_id': case, 'graph_path': str(graph_path.relative_to(ROOT)), 'graph_sha256': row['graph_sha256'],
                                'plan_path': row['artifacts']['plan']['path'], 'plan_artifact_source': plan_source, 'plan_sha256': row['artifacts']['plan']['sha256'],
                                'trace_path': row['artifacts']['trace']['path'], 'trace_artifact_source': trace_source, 'trace_sha256': row['artifacts']['trace']['sha256'],
                                'selected_candidate': selected['name'], 'capsules': len(dispatch),
                                'mapped_compute_ops': len(owner), 'path_segment_lengths': [x['operations'] for x in segments],
                                'short_interval_union_frontier': union_frontier,
                                'path_segments': [{'core': x['core'], 'ops': path['path_ops'][sum(y['operations'] for y in segments[:i]):sum(y['operations'] for y in segments[:i+1])]} for i, x in enumerate(segments)],
                                'cross_core_boundaries': boundaries})
    (HERE / 'summary.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
