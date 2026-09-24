"""Read-only comparison of the frozen reuse-family probe with its actual baseline."""
import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter

from .construct import ROOT, Index
from .feedback_benchmark import read, write
from .forest_reuse_grid import recognize, input_copy_floor


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--forest-root', type=Path, required=True)
    args = p.parse_args()
    area = ROOT / 'results/a/q3-nikolastarx/reuse-family-probe-20260925'
    state = read(area / 'run.json')
    output = []
    accounting, models = [], {}
    assert state['status'] == 'complete' and state['new_e0_calls'] == 29
    assert state['historical_results_reused'] == 2 and len(state['records']) == 33
    for row in state['records']:
        saved_plan = area / f"{row['case_id']}-k{row['cores']}" / 'plan.json'
        assert hashlib.sha256(saved_plan.read_bytes()).hexdigest() == row['plan_sha256']
        receipt_path = args.forest_root / row['baseline_receipt_path']
        receipt = read(receipt_path)
        assert receipt['plan_sha256'] == row['baseline_plan_sha256']
        assert receipt['makespan'] == row['baseline_makespan']
        raw = receipt_path.parent / 'result.json.gz'
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == receipt['result_sha256']
        base = read(raw)
        item = {k: row[k] for k in ('case_id', 'cores', 'status', 'baseline_makespan', 'plan_sha256')}
        if row['status'] == 'bound_pruned':
            assert row['certified_lower_bound_cycles'] >= row['baseline_makespan']
            output.append(item)
            continue
        raw = ROOT / row['result_path']
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == row['result_sha256']
        result = read(raw)
        assert result['problem'] == 3 and result['num_cores'] == row['cores']
        assert result['makespan'] == row['makespan']
        b, a = base['data_movement_bytes'], result['data_movement_bytes']
        item.update(makespan=result['makespan'], delta_makespan=result['makespan']-base['makespan'],
                    delta_extra_copy_bytes=a['added_copy_bytes']-b['added_copy_bytes'],
                    delta_spill_bytes=a['spill_added_copy_bytes']-b['spill_added_copy_bytes'],
                    delta_byte_hit_rate=result['cache_stats']['hit_rate']-base['cache_stats']['hit_rate'])
        case, cores = row['case_id'], row['cores']
        if case not in models:
            index = Index(read(ROOT / f'data/raw/a/official/data/case_{case}.json'))
            models[case] = index, recognize(index)
        index, model = models[case]

        def assignment(plan):
            sgcore = {sg: c for c, seq in enumerate(plan['core_schedules']) for sg in seq}
            by_core = [[] for _ in range(cores)]
            for component_id, component in enumerate(index.components):
                owners = {sgcore[plan['node_to_subgraph'][str(u)]] for u in component}
                assert len(owners) == 1, 'COPY identity requires whole trees on one core'
                by_core[owners.pop()].append(component_id)
            return by_core

        old_plan = read(receipt_path.parent.parent / f'case_{case}_multicore_res.json')
        old_d = sum(input_copy_floor(model, assignment(old_plan)))
        new_d = sum(input_copy_floor(model, assignment(read(saved_plan))))
        rhs = new_d - old_d + item['delta_spill_bytes']
        accounting.append({'case_id': case, 'cores': cores, 'old_D': old_d, 'new_D': new_d,
                           'delta_extra_copy': item['delta_extra_copy_bytes'],
                           'delta_D_plus_spill': rhs,
                           'identity_holds': rhs == item['delta_extra_copy_bytes']})
        output.append(item)
    counts = Counter('pruned' if 'delta_makespan' not in x else
                     'better' if x['delta_makespan'] < 0 else
                     'worse' if x['delta_makespan'] > 0 else 'equal' for x in output)
    summary = {'scope': 'complete recognized-family mechanism probe; not fresh unified full500',
               'source_commit': state['source_commit'], 'counts': dict(counts),
               'new_p3_e0': 29, 'historical_exact_plan_reuse': 2,
               'batch_seconds': state['elapsed_seconds'], 'rows': output}
    write(area / 'comparison.json', summary)
    write(area / 'copy-accounting-audit.json', {
        'scope': 'actual owner assignments, complete original trees, all 31 evaluated family candidates; no E0',
        'rows': accounting, 'all_equal': all(x['identity_holds'] for x in accounting)})
    print(json.dumps({k:v for k,v in summary.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
