"""Audit the saved job-major 044/K5 Colab receipt without an evaluator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ZIP = HERE / 'run/colab-results.zip'
CAPSULE = HERE / 'capsule.zip'
SUMMARY = ROOT / 'results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json'
EXPECTED_RESULT_ZIP = 'c639330713bf80f4b1eee639c1aef1879bbc764e212a890aa387740edd7633b7'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    assert sha(ZIP.read_bytes()) == EXPECTED_RESULT_ZIP
    preflight = json.loads((HERE / 'preflight.json').read_bytes())
    assert sha(CAPSULE.read_bytes()) == preflight['capsule_sha256']
    assert (preflight['solver_calls'], preflight['E0_calls'], preflight['E1_calls'],
            preflight['E2_calls']) == (0, 0, 0, 0)
    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        assert len(names) == len(set(names)) and z.testzip() is None
        assert all(not Path(name).is_absolute() and '..' not in Path(name).parts
                   for name in names)
        required = ('completion.json', 'capsule-manifest.json', 'output/plan.json',
                    'output/detail.json', 'output/construct-receipt.json',
                    'output/receipt.json', 'output/result.json', 'output/trace.json',
                    'output/official.log', 'output/construct-process/process.json',
                    'output/e0-process/process.json', 'launcher-process/process.json')
        assert all(name in names for name in required)

        def read(name: str):
            return json.loads(z.read(name))

        completion, manifest, receipt = (read(name) for name in
            ('completion.json', 'capsule-manifest.json', 'output/receipt.json'))
        assert manifest['strategy'] == 'shared_stationary_pipeline'
        construct = read('output/construct-receipt.json')
        official = read('output/result.json')
        processes = {name: read(name + '/process.json') for name in
                     ('launcher-process', 'output/construct-process', 'output/e0-process')}
        assert z.read('capsule-manifest.json') == (HERE / 'capsule-manifest.json').read_bytes()
        assert sha(z.read('capsule-manifest.json')) == preflight['manifest_sha256']
        assert completion['capsule_sha256'] == preflight['capsule_sha256']
        assert (completion['status'], completion['returncode'], completion['surviving_pids']) == ('ok', 0, [])
        assert receipt['status'] == 'completed' and receipt['manifest_sha256'] == preflight['manifest_sha256']
        assert receipt['calls'] == {'construct': 1, 'E0': 1, 'E1': 0, 'E2': 0}
        assert receipt['source_commit'] == manifest['solver_source_commit']
        assert construct['plan_sha256'] == receipt['official']['plan_sha256'] == sha(z.read('output/plan.json'))
        assert construct['graph_sha256'] == manifest['files']['data/raw/a/official/data/case_044.json']
        assert construct['config_sha256'] == manifest['files']['data/raw/a/official/data/config.txt']
        assert receipt['official']['result_sha256'] == sha(z.read('output/result.json'))
        assert (official['scene'], official['num_cores'], type(official['makespan'])) == ('B', 5, int)
        assert receipt['official']['makespan'] == official['makespan']
        assert receipt['official']['data_movement_bytes'] == official['data_movement_bytes']
        for row in processes.values():
            assert row['status'] == 'ok' and row['exit_code'] == 0 and row['surviving_pids'] == []
            assert row['observed_peak_rss_bytes'] <= 2 << 30
        assert processes['output/construct-process']['wall_seconds'] <= 30
        assert processes['output/e0-process']['wall_seconds'] <= 60
        assert receipt['total_seconds'] <= 120 and completion['launcher_wall_seconds'] <= 130
        assert 'multicore_cut_evaluate_problem_2.py' in processes['output/e0-process']['argv'][2]

    summary = json.loads(SUMMARY.read_bytes())
    assert summary['solver_commit'] == manifest['old_solver_commit']
    old_rows = [row for row in summary['rows'] if row['case'] == '044' and row['cores'] == 5]
    assert len(old_rows) == 1
    old = old_rows[0]
    assert old['status'] == 'accepted'
    assert (old['graph_sha256'], old['config_sha256']) == (
        construct['graph_sha256'], construct['config_sha256'])
    assert old['official']['result_sha256'] == manifest['old_official']['result_sha256']
    old_m = old['official']['makespan']
    old_b = old['official']['movement']['added_copy_bytes']
    assert (old_m, old_b) == (manifest['old_official']['makespan'],
                             manifest['old_official']['added_copy_bytes'])
    new_m = official['makespan']
    new_b = official['data_movement_bytes']['added_copy_bytes']
    report = {
        'status': 'verified_single_cell_primary_improvement', 'case': '044', 'cores': 5,
        'fixed_package_commit': '1e9188e41ca54ef3baa3c265d14fb0d2f99c7b3c',
        'solver_source_commit': manifest['solver_source_commit'],
        'control_solver_commit': manifest['old_solver_commit'],
        'capsule_sha256': preflight['capsule_sha256'],
        'result_zip_sha256': EXPECTED_RESULT_ZIP,
        'plan_sha256': construct['plan_sha256'],
        'official_result_sha256': receipt['official']['result_sha256'],
        'calls': receipt['calls'], 'old_official': {'makespan_cycles': old_m,
                'added_copy_bytes': old_b},
        'new_official': {'makespan_cycles': new_m, 'added_copy_bytes': new_b,
                'spill_added_copy_bytes': official['data_movement_bytes']['spill_added_copy_bytes'],
                'task_count': official['task_count'],
                'cross_core_transfer_count': len(official['cross_core_transfers'])},
        'difference': {'makespan_cycles': new_m - old_m,
                       'makespan_percent': 100 * (new_m / old_m - 1),
                       'added_copy_bytes': new_b - old_b},
        'core_task_intervals': [[task['start'], task['end']]
                                for row in official['per_core_timeline'] for task in row['tasks']],
        'processes': {name: {'status': row['status'], 'wall_seconds': row['wall_seconds'],
                             'observed_peak_rss_bytes': row['observed_peak_rss_bytes'],
                             'surviving_pids': row['surviving_pids']}
                      for name, row in processes.items()},
        'limits_and_caveats': ['This is one official case and one core count, not a full-algorithm score.',
                               'The strict constructor is statically eligible on only 3 of 100 official graphs at K5.',
                               'Colab timing is not directly comparable with the old Mac batch.'],
    }
    (HERE / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
