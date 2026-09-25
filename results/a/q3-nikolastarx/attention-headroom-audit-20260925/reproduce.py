"""Read three saved forest plans and compute proved static plan bounds; zero E0."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
from src.q3.feedback_benchmark import read
from src.q3.pipe_bound import analyze


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--forest-root', required=True, type=Path)
    args = p.parse_args()
    snap_path = ROOT / 'results/a/q3-nikolastarx/forest-current-headroom-20260925/cells-snapshot.json'
    snapshot = read(snap_path)
    official = read(ROOT / 'docs/a/source-manifest.json')
    identities = {f['path']: f['sha256'] for f in official['files']}
    config = ROOT / 'data/raw/a/official/data/config.txt'
    assert sha(config) == identities['data/config.txt']
    delay, = [int(line.split()[1]) for line in config.read_text().splitlines()
              if line.split()[:1] == ['cross_core_copy_delay_cycles']]
    result = {'scope': 'three already-seen attention cases; static bounds, no new performance',
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'snapshot_sha256': sha(snap_path), 'snapshot_as_of': snapshot['as_of'],
              'pipe_bound_code_sha256': sha(ROOT / 'src/q3/pipe_bound.py'),
              'new_e0_calls': 0, 'new_solver_calls': 0, 'new_task_step3_calls': 0, 'cases': []}
    for case in ('071', '069', '005'):
        row, = [c['best'] for c in snapshot['cells'] if c['case_id'] == case and c['cores'] == 5]
        artifacts = {}
        for name in ('plan', 'trace', 'result'):
            ref = row['artifacts'][name]
            path = args.forest_root / ref['path']
            assert sha(path) == ref['sha256']
            artifacts[name] = read(path)
        graph_path = ROOT / f'data/raw/a/official/data/case_{case}.json'
        assert sha(graph_path) == identities[f'data/case_{case}.json']
        bound = analyze(read(graph_path), artifacts['plan'], delay)
        m = artifacts['result']['makespan']
        assert m == row['metrics']['makespan_cycles']
        result['cases'].append({'case_id': case, 'cores': 5,
                               'graph_sha256': sha(graph_path), 'artifacts': row['artifacts'],
                               'selected_strategy': artifacts['trace']['selected_strategy'],
                               'existing_makespan_cycles': m, 'bound': bound,
                               'existing_candidates': [{k: c.get(k) for k in ('name', 'status', 'makespan')}
                                                       for c in artifacts['trace']['candidates']]})
    (OUT / 'summary.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps([{'case': c['case_id'], 'M': c['existing_makespan_cycles'],
                      'bound': c['bound']['with_cross_core_delay']['lower_bound_cycles']}
                     for c in result['cases']]))


if __name__ == '__main__':
    main()
