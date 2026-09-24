"""Recompute the finite band experiment's comparisons from verified raw bytes."""
import argparse
import json
from pathlib import Path

from .construct import ROOT, Index
from .feedback_benchmark import digest, git_bytes, read, write
from .forest_reuse_grid import recognize, input_copy_floor

AREA = "results/a/q3-nikolastarx/band-mechanism-20260925"
CONTROL = "results/a/q3-nikolastarx/forest-reuse-grid-probe-20260925"
FOREST_ARTIFACT = "bff88a66cd76ceb2d75242bf99d34bfe8b1879d4"


def owners(plan):
    sgcore = {sg: core for core, seq in enumerate(plan['core_schedules']) for sg in seq}
    return {int(op): sgcore[sg] for op, sg in plan['node_to_subgraph'].items()}


def whole_tree_d(index, model, plan):
    owner = owners(plan)
    assignment = [[] for _ in plan['core_schedules']]
    for cid, component in enumerate(index.components):
        cs = {owner[u] for u in component}
        assert len(cs) == 1
        assignment[cs.pop()].append(cid)
    return sum(input_copy_floor(model, assignment))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forest-root', required=True, type=Path)
    args = parser.parse_args()
    area = ROOT / AREA
    run = read(area / 'run.json')
    assert run['status'] == 'complete' and run['e0_calls'] == 8
    for path, expected in run['source_input_sha256'].items():
        assert digest(ROOT / path) == expected, path
    proposal = {(p['case_id'], p['order_mode']): p for p in run['plans']}
    results = {(r['case_id'], r['order_mode'], r['problem']): r for r in run['results']}
    old = read(ROOT / CONTROL / 'run.json')
    old_rows = {(r['case_id'], r['problem']): r for r in old['results']}
    coverage = {(f"{r['case']:03d}", r['cores']): r for r in read(
        ROOT / 'results/a/q3-nikolastarx/reuse-coverage-20260925/coordinates.json')}
    for path, expected in old['source_input_sha256'].items():
        if path.startswith('data/raw/'):
            assert digest(ROOT / path) == expected
    rows = []
    differences = []
    for case in ('058', '079'):
        index = Index(read(ROOT / f'data/raw/a/official/data/case_{case}.json'))
        model = recognize(index)
        control_ref = coverage[(case, 5)]
        receipt_path = Path(control_ref['receipt_path'])
        assert (args.forest_root / receipt_path).read_bytes() == git_bytes(
            args.forest_root, FOREST_ARTIFACT, str(receipt_path))
        receipt = read(args.forest_root / receipt_path)
        forest_result = args.forest_root / receipt_path.parent / 'result.json.gz'
        forest_plan = args.forest_root / receipt_path.parent.parent / f'case_{case}_multicore_res.json'
        assert digest(forest_result) == receipt['result_sha256']
        assert digest(forest_plan) == receipt['plan_sha256'] == control_ref['forest500_plan_sha256']
        baseline = read(forest_result)
        baseline_d = whole_tree_d(index, model, read(forest_plan))
        rows.append({'case_id': case, 'variant': 'forest500', 'makespan': baseline['makespan'],
                     'D': baseline_d, 'movement': baseline['data_movement_bytes'],
                     'hit_rate': baseline['cache_stats']['hit_rate'],
                     'source': {'artifact_commit': FOREST_ARTIFACT, 'receipt_path': str(receipt_path)}})
        op_owners = None
        for mode in ('plain_axis_control', 'component_id', 'pair_cache_model'):
            pair = []
            if mode == 'plain_axis_control':
                plan = ROOT / CONTROL / f'case_{case}_multicore_res.json'
                metadata = None
            else:
                p = proposal[(case, mode)]
                plan = ROOT / p['plan_path']
                assert digest(plan) == p['plan_sha256']
                metadata = p['metadata']
                current_owner = owners(read(plan))
                if op_owners is not None:
                    assert op_owners == current_owner, 'actual op owners differ between orders'
                op_owners = current_owner
            for problem in (2, 3):
                r = old_rows[(case, problem)] if metadata is None else results[(case, mode, problem)]
                assert digest(plan) == r['plan_sha256']
                assert digest(ROOT / r['result_path']) == r['result_sha256']
                raw = read(ROOT / r['result_path'])
                assert raw['makespan'] == r['makespan'] and raw['num_cores'] == 5
                pair.append(raw)
            p2, p3 = pair
            d = whole_tree_d(index, model, read(plan))
            if metadata:
                assert d == metadata['coverage_bytes']
            movement = p3['data_movement_bytes']
            delta_extra = movement['added_copy_bytes'] - baseline['data_movement_bytes']['added_copy_bytes']
            delta_spill = movement['spill_added_copy_bytes'] - baseline['data_movement_bytes']['spill_added_copy_bytes']
            assert delta_extra == d - baseline_d + delta_spill
            rows.append({'case_id': case, 'variant': mode, 'D': d, 'makespan': p3['makespan'],
                         'p2_makespan': p2['makespan'], 'cache_gain': p2['makespan']/p3['makespan'],
                         'movement': movement, 'hit_rate': p3['cache_stats']['hit_rate'],
                         'delta_forest_M': p3['makespan'] - baseline['makespan'],
                         'delta_forest_extra': delta_extra, 'delta_forest_spill': delta_spill,
                         'copy_accounting_identity': True})
        fixed, reordered = rows[-2:]
        differences.append({'case_id': case, 'same_owner_verified': True,
                            'delta_M': reordered['makespan'] - fixed['makespan'],
                            'delta_extra': reordered['movement']['added_copy_bytes'] - fixed['movement']['added_copy_bytes'],
                            'delta_spill': reordered['movement']['spill_added_copy_bytes'] - fixed['movement']['spill_added_copy_bytes']})
    summary = {'scope': '2 seen graphs, 4 new plans, 8 new E0; existing controls are historical',
               'source_commit': run['source_commit'], 'elapsed_seconds': run['elapsed_seconds'],
               'rows': rows, 'same_owner_order_effect': differences}
    write(area / 'comparison.json', summary)
    print(json.dumps({'rows': len(rows), 'same_owner_order_effect': differences}))


if __name__ == '__main__':
    main()
