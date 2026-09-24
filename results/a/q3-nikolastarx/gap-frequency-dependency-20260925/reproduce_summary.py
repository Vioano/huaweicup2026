"""Recount saved dependency evidence; does not invoke any evaluator."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
state = json.loads((HERE / 'run.json').read_text())
assert state['status'] == 'complete'
rows = {}
for job in state['jobs']:
    path = HERE / job['name'] / 'dependency.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == job['audit_sha256']
    d = json.loads(path.read_text())
    assert d['task_builds'] == d['local_step3_simulations'] == 1
    assert d['plan_sha256'] == job['plan_sha256']
    assert d['result_sha256'] == job['existing_result_sha256']
    c = d['cores'][0]
    hist, count, cycles = Counter(), Counter(), Counter()
    for gap in c['all_M_gaps']:
        hist[gap['gap']] += 1
        key = '+'.join(sorted({p['kind'] + ':' + p['pipe'] + ':' + p['op']
                               for p in gap['tight_predecessors']}))
        count[key] += 1
        cycles[key] += gap['gap']
    assert sum(cycles.values()) == c['M_gap_sum']
    assert c['first_M_start'] + c['M_busy'] + c['M_gap_sum'] + c['tail'] == job['existing_makespan']
    rows[job['name']] = {k: v for k, v in c.items() if k != 'all_M_gaps'}
    rows[job['name']].update(positive_gaps=sum(hist.values()), gap_histogram=dict(hist),
                            immediate_tight_edge_counts=dict(count), immediate_tight_edge_cycles=dict(cycles))

family = json.loads((ROOT / 'results/a/q3-nikolastarx/band-lookahead-family-20260925/run.json').read_text())
record = next(r for r in family['records'] if r.get('case_id') == '097' and r.get('cores') == 1)
path = ROOT / record['result_path']
assert hashlib.sha256(path.read_bytes()).hexdigest() == record['result_sha256']
raw = json.loads(gzip.decompress(path.read_bytes()))
ops = {op['op_id']: op for row in raw['per_core_timeline'] for op in row['ops']}
d = json.loads((HERE / 'new_band_lookahead/dependency.json').read_text())
copy_groups = Counter()
for gap in d['cores'][0]['all_M_gaps']:
    for pred in gap['tight_predecessors']:
        if pred['op'] == 'COPY_IN':
            op = ops[pred['source']]
            assert op['end'] == gap['M_start']
            copy_groups[(gap['gap'], op['duration'], op['start'] - gap['previous_M_end'], op['memory_path'])] += 1
out = {'scope': 'Immediate tight predecessors and saved E0 timing only; upstream COPY readiness and counterfactual effects not proved',
       'source_commit_of_Task_reconstruction': state['source_commit'],
       'task_builds': 2, 'local_step3': 2, 'new_multicore_E0': 0,
       'rows': rows,
       'new_COPY_groups': [{'M_gap': k[0], 'COPY_duration': k[1], 'COPY_start_minus_previous_M_end': k[2],
                            'memory_path': k[3], 'count': n} for k, n in sorted(copy_groups.items())]}
(HERE / 'summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(out, ensure_ascii=False))
