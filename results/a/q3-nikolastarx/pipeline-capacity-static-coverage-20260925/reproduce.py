"""Classify all100 known graphs statically at five cores, with no E0 calls."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
from src.q3.construct import Index, UnsupportedStructure
from src.q3.shared_pipeline_capacity import construct
from src.q3.pipe_bound import analyze
from src.q3.safe_solve import encoded


def main():
    start = time.perf_counter()
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    original = json.loads((ROOT / 'docs/a/source-manifest.json').read_text())
    ids = {r['path']: r['sha256'] for r in original['files']}
    snapshot = json.loads((ROOT / 'results/a/q3-nikolastarx/forest-current-headroom-20260925/cells-snapshot.json').read_text())
    old = {c['case_id']: c['best'] for c in snapshot['cells'] if c['cores'] == 5}
    config = ROOT / 'data/raw/a/official/data/config.txt'
    assert hashlib.sha256(config.read_bytes()).hexdigest() == ids['data/config.txt']
    delay, = [int(line.split()[1]) for line in config.read_text().splitlines()
              if line.split()[:1] == ['cross_core_copy_delay_cycles']]
    rows = []
    for number in range(1, 101):
        case = f'{number:03}'
        path = ROOT / f'data/raw/a/official/data/case_{case}.json'
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == ids[f'data/case_{case}.json']
        graph = json.loads(raw)
        row = {'case_id': case, 'graph_sha256': ids[f'data/case_{case}.json']}
        try:
            plan, meta = construct(Index(graph), 5)
            lower = analyze(graph, plan, delay)['with_cross_core_delay']['lower_bound_cycles']
            ph = hashlib.sha256(encoded(plan)).hexdigest()
            incumbent = old[case]
            row.update(status='recognized', plan_sha256=ph, metadata=meta,
                       plan_lower_bound_cycles=lower,
                       old_makespan_cycles=incumbent['metrics']['makespan_cycles'],
                       old_result_sha256=incumbent['artifacts']['result']['sha256'],
                       duplicate_old_plan=ph == incumbent['identity']['plan_sha256'],
                       bound_pruned=lower >= incumbent['metrics']['makespan_cycles'])
        except UnsupportedStructure as e:
            row.update(status='unsupported', reason=str(e))
        rows.append(row)
    out = {'scope': 'all100 already seen graphs at5 cores; no official Task/Step3/E0 or solver',
           'source_commit': source, 'prototype_sha256': hashlib.sha256((ROOT/'src/q3/shared_pipeline_capacity.py').read_bytes()).hexdigest(),
           'official_code_sha256': original['official_code_hash'], 'new_e0': 0,
           'cores': 5, 'count': len(rows), 'counts': dict(Counter(r['status'] for r in rows)),
           'wall_seconds': time.perf_counter() - start, 'cases': rows}
    (OUT / 'summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'counts': out['counts'], 'seconds': out['wall_seconds'],
                     'recognized': [{k: r[k] for k in ('case_id','duplicate_old_plan','bound_pruned',
                        'plan_lower_bound_cycles','old_makespan_cycles')} for r in rows if r['status']=='recognized']}))


if __name__ == '__main__':
    main()
