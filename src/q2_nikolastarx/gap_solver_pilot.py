"""Four-cell frozen adaptive-gap solver pilot; preflight never scores.

One full solver process (including online E2) and one independent E0 process
per cell. First fallback, uncertain request, construction error or mismatch
stops the batch. This is a partial pilot, not a full algorithm score.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from .chain_pilot import FIELDS, digest, git_bytes, pinned, save

ROOT = Path(__file__).resolve().parents[2]
SOLVER = '923b25ecb0b9d6d0e2d3f149fccef431b5403f99'
BASE = '60afc38b327680fbda0ff10182e3e05a01edd72d'
COORDS = (('003', 2), ('005', 3), ('056', 5), ('008', 5))
LIMITS = {'solver': 4, 'E2_api': 8, 'E0_fallback_reserved': 8,
          'E0_independent': 4, 'workers': 1, 'solver_seconds': 60,
          'e0_seconds': 60, 'batch_seconds': 600, 'rss_bytes': 4 << 30,
          'retries': 0}


def canonical(plan):
    # Exact score_adapter key, independent of pretty JSON output bytes.
    return digest(json.dumps(plan, sort_keys=True, allow_nan=False).encode())


def same_metrics(record, result):
    return (record['makespan'] == result['makespan']
            and record['cross_task_traffic'] == result['cross_task_traffic']
            and all(record['data_movement_bytes'][key] == result['data_movement_bytes'][key]
                    for key in FIELDS))


def preflight(manifest, e2_root, runner_commit=None):
    from .adaptive_guarded import check_e2_source
    doc = json.loads(manifest.read_bytes())
    if (doc['solver_commit'] != SOLVER or doc['baseline_commit'] != BASE
            or doc['coordinates'] != [list(x) for x in COORDS]
            or doc['limits'] != LIMITS or len(doc['rows']) != 4):
        raise ValueError('Unexpected source, coordinates or budget')
    if runner_commit:
        if len(runner_commit) != 40 or any(c not in '0123456789abcdef' for c in runner_commit):
            raise ValueError('Runner needs a full lowercase SHA')
        for path in (Path(__file__), manifest,
                     ROOT / 'src/q2_nikolastarx/evaluate_feedback.py'):
            relative = path.relative_to(ROOT).as_posix()
            if path.read_bytes() != git_bytes(runner_commit, relative):
                raise ValueError('Runner/manifest/monitor drift: ' + relative)
    paths = subprocess.check_output(
        ['git', 'ls-tree', '-r', '--name-only', SOLVER, 'src/q2_nikolastarx'],
        cwd=ROOT, text=True).splitlines()
    paths = sorted(path for path in paths if path.endswith('.py'))
    if paths != sorted(doc['solver_sources']):
        raise ValueError('Solver file set differs')
    actual = sorted(path.relative_to(ROOT).as_posix()
                    for path in (ROOT / 'src/q2_nikolastarx').glob('*.py')
                    if path.name != 'gap_solver_pilot.py')
    if actual != paths:
        raise ValueError('Solver checkout file set differs')
    for name in paths:
        raw = (ROOT / name).read_bytes()
        if digest(raw) != doc['solver_sources'][name] or raw != git_bytes(SOLVER, name):
            raise ValueError('Solver source drift: ' + name)
    e2_ref = doc['e2_manifest']
    if digest((ROOT / e2_ref['path']).read_bytes()) != e2_ref['sha256']:
        raise ValueError('E2 manifest drift')
    e2_identity = check_e2_source(e2_root)
    if e2_identity['commit'] != doc['e2_commit'] or e2_identity['manifest_sha256'] != e2_ref['sha256']:
        raise ValueError('E2 identity mismatch')
    source_raw = (ROOT / 'docs/a/source-manifest.json').read_bytes()
    if digest(source_raw) != doc['source_manifest_sha256']:
        raise ValueError('Official source manifest drift')
    source = json.loads(source_raw)
    files = {row['path']: row for row in source['files']}
    for relative in doc['official_files']:
        raw = (ROOT / 'data/raw/a/official' / relative).read_bytes()
        if digest(raw) != files[relative]['sha256'] or len(raw) != files[relative]['bytes']:
            raise ValueError('Official code drift: ' + relative)
    if digest((ROOT / doc['config']['path']).read_bytes()) != doc['config']['sha256']:
        raise ValueError('Config drift')
    feed = pinned(doc['baseline_feed'])['records']
    for row, (case, cores) in zip(doc['rows'], COORDS):
        if row['case'] != case or row['cores'] != cores:
            raise ValueError('Coordinate order mismatch')
        raw = (ROOT / row['graph']['path']).read_bytes()
        if (digest(raw) != row['graph']['sha256']
                or files['data/case_'+case+'.json']['sha256'] != row['graph']['sha256']):
            raise ValueError('Graph drift: ' + case)
        old = next((r for r in feed if r['case_id'] == case and r['cores'] == cores), None)
        if (old is None or old['identity']['graph_sha256'] != row['graph']['sha256']
                or old['identity']['config_sha256'] != doc['config']['sha256']
                or old['identity']['official_sha256'] != source['official_code_hash']
                or old['artifacts']['plan'] != {k: row['baseline_plan'][k] for k in ('path', 'sha256')}
                or old['artifacts']['result'] != {k: row['baseline_truth'][k] for k in ('path', 'sha256')}
                or old['metrics']['makespan_cycles'] != row['baseline_m']):
            raise ValueError('Baseline feed mismatch: ' + case)
        plan, truth = pinned(row['baseline_plan']), pinned(row['baseline_truth'])
        if (set(plan) != {'node_to_subgraph', 'core_schedules'}
                or len(plan['core_schedules']) != cores
                or truth['scene'] != 'B' or truth['num_cores'] != cores
                or truth['makespan'] != row['baseline_m']
                or set(truth['data_movement_bytes']) != set(FIELDS)):
            raise ValueError('Baseline artifacts mismatch: ' + case)
    return doc


def inspect_solver(case_dir, row, receipt, doc):
    ledger_path = case_dir / 'online/solver.json'
    ledger = json.loads(ledger_path.read_bytes()) if ledger_path.exists() else None
    if receipt['status'] != 'ok' or receipt.get('surviving_pids') or ledger is None:
        raise ValueError('Solver process/ledger failed or is uncertain')
    if ledger['status'] != 'ok' or ledger['request_in_flight']:
        raise ValueError('Solver failed or has an in-flight request')
    calls = ledger['calls']
    attempts = ledger['attempts']
    if (calls['E2_api_attempted'] != len(attempts) or len(attempts) > 2
            or calls['E0_fallback'] or ledger['possible_E0_fallback_calls']
            or any(a['status'] != 'native' for a in attempts)):
        raise ValueError('Fallback or uncertain E2 request; stop')
    expected_sources = {Path(name).name: sha for name, sha in doc['solver_sources'].items()}
    expected_sources['gap_solver_pilot.py'] = digest(Path(__file__).read_bytes())
    if (ledger['solver_source_sha256'] != expected_sources
            or ledger['graph_sha256'] != row['graph']['sha256']
            or ledger['config_sha256'] != doc['config']['sha256']
            or ledger['cores'] != row['cores']):
        raise ValueError('Solver source/input readback mismatch')
    detail = ledger.get('detail', {})
    if detail.get('reason') == 'candidate_construction_failed':
        error = detail.get('candidate_error', '')
        if not error.startswith('UnsupportedStructure('):
            raise ValueError('Non-structural candidate construction error: ' + error)
    plan_path = case_dir / 'plan.json'
    raw = plan_path.read_bytes()
    if digest(raw) != ledger['plan_sha256']:
        raise ValueError('Selected plan bytes mismatch')
    plan = json.loads(raw)
    if set(plan) != {'node_to_subgraph', 'core_schedules'} or len(plan['core_schedules']) != row['cores']:
        raise ValueError('Invalid selected plan')
    key = canonical(plan)
    matches = [a for a in attempts if a['plan_sha256'] == key]
    if matches:
        if len(matches) != 1:
            raise ValueError('Ambiguous selected native record')
        record = matches[0]['record']
        if record.get('route') != 'native' or record.get('status') != 'ok' or record.get('problem') != 2:
            raise ValueError('Selected E2 record unavailable')
        comparison = {'kind': 'selected_native', 'record': record, 'plan_canonical_sha256': key}
    else:
        if attempts:
            raise ValueError('Selected plan has no matching native score')
        old_plan = pinned(row['baseline_plan'])
        if canonical(old_plan) != key:
            raise ValueError('Unscored selected plan differs from frozen baseline')
        comparison = {'kind': 'frozen_baseline_zero_score',
                      'record': pinned(row['baseline_truth']), 'plan_canonical_sha256': key}
    return ledger, comparison


def run(doc, manifest, e2_root, output, runner_commit, started):
    from .evaluate_feedback import monitored
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('Pinned native E2 binary requires macOS ARM64')
    if output.exists():
        raise ValueError('Run output exists; no overwrite or retry')
    deadline = started + LIMITS['batch_seconds']
    if time.perf_counter() >= deadline:
        raise TimeoutError('Preflight exhausted batch budget')
    output.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'running', 'runner_commit': runner_commit,
               'solver_commit': SOLVER, 'manifest_sha256': digest(manifest.read_bytes()),
               'limits': LIMITS, 'rows': [], 'preflight_wall_seconds': time.perf_counter()-started,
               'calls': {'solver_started': 0, 'E2_api_attempted': 0,
                         'E0_fallback_confirmed': 0, 'E0_fallback_possible': 0,
                         'E0_independent_started': 0},
               'call_count_complete': True,
               'scope': 'four fixed coordinates; not a full 100x1-5 algorithm score'}
    save(output / 'summary.json', summary)
    for row in doc['rows']:
        case_dir = output / f"{row['case']}-k{row['cores']}"
        case_dir.mkdir(exist_ok=False)
        solver_argv = [sys.executable, '-B', '-m', 'src.q2_nikolastarx.adaptive_gap_guarded',
                       str(ROOT / row['graph']['path']), '--config', str(ROOT / doc['config']['path']),
                       '--cores', str(row['cores']), '--output', str(case_dir / 'plan.json'),
                       '--evidence', str(case_dir / 'online'), '--e2-root', str(e2_root), '--wall', '60']
        summary['calls']['solver_started'] += 1
        save(output / 'summary.json', summary)
        entry = {'case': row['case'], 'cores': row['cores'],
                 'solver_process_in_flight': True}
        summary['rows'].append(entry)
        save(output / 'summary.json', summary)
        try:
            solver_receipt = monitored(solver_argv, case_dir / 'solver-process',
                                       min(deadline, time.perf_counter()+60), LIMITS['rss_bytes'])
            entry['solver_process'] = solver_receipt
            entry['solver_process_in_flight'] = False
            ledger_path = case_dir / 'online/solver.json'
            if ledger_path.exists():
                observed = json.loads(ledger_path.read_bytes())
                entry['solver_ledger'] = observed
                summary['calls']['E2_api_attempted'] += observed['calls']['E2_api_attempted']
                summary['calls']['E0_fallback_confirmed'] += observed['calls']['E0_fallback']
                summary['calls']['E0_fallback_possible'] += observed['possible_E0_fallback_calls']
            else:
                entry['solver_ledger_missing'] = True
                summary['call_count_complete'] = False
            if (summary['calls']['E2_api_attempted'] > LIMITS['E2_api']
                    or summary['calls']['E0_fallback_possible'] > LIMITS['E0_fallback_reserved']):
                raise ValueError('Evaluation call budget exceeded')
            ledger, comparison = inspect_solver(case_dir, row, solver_receipt, doc)
            entry['selected_comparison'] = comparison
            save(output / 'summary.json', summary)
            e0_argv = [sys.executable, '-B', str(ROOT / doc['official_entry']),
                       str(ROOT / row['graph']['path']), str(case_dir / 'plan.json'),
                       '--config', str(ROOT / doc['config']['path']),
                       '--output', str(case_dir / 'result.json'),
                       '--trace-output', str(case_dir / 'trace.json'),
                       '--log-output', str(case_dir / 'official.log')]
            entry['independent_e0_in_flight'] = True
            summary['calls']['E0_independent_started'] += 1
            save(output / 'summary.json', summary)
            e0_receipt = monitored(e0_argv, case_dir / 'e0-process',
                                   min(deadline, time.perf_counter()+60), LIMITS['rss_bytes'])
            entry['e0_process'] = e0_receipt
            entry['independent_e0_in_flight'] = False
            if e0_receipt['status'] != 'ok' or e0_receipt.get('surviving_pids'):
                raise ValueError('Independent E0 failed or is uncertain')
            result = json.loads((case_dir / 'result.json').read_bytes())
            if not same_metrics(comparison['record'], result):
                raise ValueError('Selected native/frozen truth differs from independent E0')
            entry['result'] = {'makespan': result['makespan'],
                               'movement': {k: result['data_movement_bytes'][k] for k in FIELDS},
                               'cross_task_traffic': result['cross_task_traffic'],
                               'result_sha256': digest((case_dir / 'result.json').read_bytes())}
            entry['baseline_m'] = row['baseline_m']
            entry['makespan_delta'] = result['makespan'] - row['baseline_m']
            entry['status'] = 'accepted'
        except Exception as error:
            entry.update(status='stopped', error=repr(error))
            if 'solver_ledger' not in entry or entry['solver_process_in_flight']:
                summary['call_count_complete'] = False
            summary['status'] = 'stopped_first_failure'
            summary['total_wall_seconds'] = time.perf_counter()-started
            save(output / 'summary.json', summary)
            raise SystemExit(1)
        summary['total_wall_seconds'] = time.perf_counter()-started
        save(output / 'summary.json', summary)
    summary['status'] = 'completed'
    save(output / 'summary.json', summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('preflight', 'run'))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--e2-root', type=Path, required=True)
    parser.add_argument('--runner-commit')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    manifest, e2_root = args.manifest.resolve(), args.e2_root.resolve()
    if args.mode == 'run' and not args.runner_commit:
        raise ValueError('Run requires frozen runner commit')
    doc = preflight(manifest, e2_root, args.runner_commit)
    if args.mode == 'preflight':
        print(json.dumps({'status': 'preflight_ok', 'cells': 4, 'calls': 0,
                          'runner_frozen': bool(args.runner_commit)}))
        return
    if args.output is None:
        raise ValueError('Run requires fresh output directory')
    run(doc, manifest, e2_root, args.output.resolve(), args.runner_commit, started)


if __name__ == '__main__':
    main()
