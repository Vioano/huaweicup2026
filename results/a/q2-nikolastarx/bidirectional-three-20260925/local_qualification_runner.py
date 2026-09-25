"""Single-admission local Mac qualification of the frozen P2 wrapper."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PYTHON = Path('/Users/nikolastar/.codex/worktrees/p2-gap500-s59ee-20260925/huaweicup2026/.venv/bin/python')
E2_ROOT = Path('/Users/nikolastar/.codex/worktrees/q2-feedback-s8ee/huaweicup2026/output/q2-e2-paircheck-603b-s8ee')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
from src.q2_nikolastarx.evaluate_feedback import monitored, dump, utc
from src.q2_nikolastarx.adaptive_guarded import check_e2_source


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, allow_nan=False).encode()).hexdigest()


MOVEMENT = ('original_graph_copy_bytes', 'scheduled_copy_bytes', 'added_copy_bytes',
            'partition_added_copy_bytes', 'spill_added_copy_bytes')


def verify_selected(plan, attempts, result, cores):
    selected_hash = canonical_sha(plan)
    matches = [a for a in attempts if a['plan_sha256'] == selected_hash]
    if len(matches) != 1:
        raise ValueError('final plan is not exactly one preselection oracle input')
    record = matches[0]['record']
    if (record.get('status') != 'ok' or record.get('route') != 'native'
            or record.get('problem') != 2 or record.get('makespan') != result.get('makespan')
            or result.get('scene') != 'B' or result.get('num_cores') != cores):
        raise ValueError('selected native score disagrees with external E0')
    native_move, official_move = record.get('data_movement_bytes'), result.get('data_movement_bytes')
    if not isinstance(native_move, dict) or not isinstance(official_move, dict):
        raise ValueError('missing movement fields')
    for field in MOVEMENT:
        if type(native_move.get(field)) is not int or native_move[field] != official_move.get(field):
            raise ValueError('selected native DDR mismatch: ' + field)
    return {'selected_candidate_sha256': selected_hash, 'native_makespan': record['makespan'],
            'official_makespan': result['makespan'],
            'movement_bytes': {field: official_move[field] for field in MOVEMENT}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--t0-gate', type=Path, required=True)
    args = ap.parse_args()
    manifest_path = HERE / 'local-manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    gate = json.loads(args.t0_gate.read_bytes())
    if gate != {'status': 'admitted', 'scope': 'local-three-cell-qualification',
                'source_commit': manifest['source_commit'],
                'manifest_sha256': sha(manifest_path)}:
        raise ValueError('T0 gate absent or mismatched; no scoring')
    started = time.perf_counter()
    deadline = started + 300
    limit = manifest['limits']
    assert limit == {'solver': 3, 'E2_api': 12, 'native': 12,
                     'fallback_target': 0, 'fallback_reserve': 1,
                     'retry': 0, 'external_E0': 3, 'workers': 1,
                     'solver_seconds': 60, 'E0_seconds': 30,
                     'batch_seconds': 300, 'rss_bytes': 536870912}
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                   text=True).strip() == manifest['source_commit']
    for name, expected in manifest['source_files'].items():
        assert sha(ROOT / name) == expected, name
    for name, expected in manifest['e2_files'].items():
        assert sha(E2_ROOT / name) == expected, name
    assert sha(HERE / 'local_qualification_runner.py') == manifest['runner_sha256']
    assert sha(PYTHON.resolve()) == manifest['python_binary_sha256']
    assert subprocess.check_output([str(PYTHON), '-c', 'import sys;print(sys.version_info[:2])'],
                                   text=True).strip() == '(3, 12)'
    assert sha(ROOT / 'data/raw/a/official/data/config.txt') == manifest['config_sha256']
    if time.perf_counter() >= deadline:
        raise TimeoutError('identity preflight exceeded batch deadline; no scoring')
    args.output.mkdir(exist_ok=False, parents=True)
    ledger = {'status': 'preflight', 'source_commit': manifest['source_commit'],
              'started_at': utc(), 'calls': {'solver': 0, 'E2_api': 0,
              'native': 0, 'fallback': 0, 'external_E0': 0, 'retry': 0},
              'rows': [], 'unknown_call_counts': False, 'runtime_python': str(PYTHON),
              'e2_root': str(E2_ROOT), 't0_gate_sha256': sha(args.t0_gate)}
    dump(args.output / 'ledger.json', ledger)
    try:
        source = check_e2_source(E2_ROOT)
        ledger['preflight'] = {'status': 'ok', 'source': source,
                               'finished_at': utc()}
        dump(args.output / 'ledger.json', ledger)
        for cell in manifest['cases']:
            if time.perf_counter() >= deadline:
                raise TimeoutError('batch deadline')
            case, cores = cell['case'], cell['cores']
            graph = Path(cell['graph'])
            if sha(graph) != cell['graph_sha256']:
                raise ValueError('raw graph drift')
            folder = args.output / f'{case}-k{cores}'
            folder.mkdir()
            row = {'case': case, 'cores': cores, 'status': 'solver_started',
                   'graph_sha256': sha(graph)}
            ledger['rows'].append(row)
            ledger['calls']['solver'] += 1
            dump(args.output / 'ledger.json', ledger)
            plan = folder / 'plan.json'
            config = ROOT / 'data/raw/a/official/data/config.txt'
            argv = [str(PYTHON), '-B', '-m', 'src.q2_nikolastarx.adaptive_bidirectional_guarded',
                    str(graph), '--config', str(config), '--cores', str(cores),
                    '--output', str(plan), '--evidence', str(folder / 'solver'),
                    '--e2-root', str(E2_ROOT), '--wall', '60']
            try:
                row['solver_process'] = monitored(argv, folder / 'solver-process',
                    min(deadline, time.perf_counter() + 60), 536870912)
            except BaseException:
                row['status'] = 'solver_supervision_failed_counts_unknown'
                ledger['unknown_call_counts'] = True
                dump(args.output / 'ledger.json', ledger)
                raise
            row['solver_wall_seconds'] = row['solver_process']['wall_seconds']
            solver_path = folder / 'solver/solver.json'
            if not solver_path.exists():
                row['status'] = 'solver_ledger_missing_counts_unknown'
                ledger['unknown_call_counts'] = True
                dump(args.output / 'ledger.json', ledger)
                raise RuntimeError('solver ledger missing; E2/fallback counts unknown; stop')
            try:
                solver = json.loads(solver_path.read_bytes())
            except BaseException:
                row['status'] = 'solver_ledger_unreadable_counts_unknown'
                ledger['unknown_call_counts'] = True
                dump(args.output / 'ledger.json', ledger)
                raise
            row['solver_ledger_sha256'] = sha(folder / 'solver/solver.json')
            calls = solver['calls']
            ledger['calls']['E2_api'] += calls['E2_api_attempted']
            ledger['calls']['native'] += calls['native_returns']
            ledger['calls']['fallback'] += calls['E0_fallback']
            if solver['request_in_flight'] or solver['possible_E0_fallback_calls']:
                ledger['unknown_call_counts'] = True
            dump(args.output / 'ledger.json', ledger)
            if (row['solver_process']['status'] != 'ok' or solver['status'] != 'ok'
                    or not solver['source_checked'] or solver['request_in_flight']
                    or solver['possible_E0_fallback_calls'] != 0
                    or calls['E0_fallback'] != 0 or calls['E2_api_attempted'] < 1
                    or calls['E2_api_attempted'] != calls['native_returns']
                    or ledger['calls']['E2_api'] > 12 or ledger['calls']['fallback'] > 1):
                raise RuntimeError('solver/native/fallback evidence failed; stop without E0')
            for attempt in solver['attempts']:
                # Evidence-only source patch must supply these originals.
                relative = Path(attempt['plan_file'])
                if relative.is_absolute() or '..' in relative.parts:
                    raise RuntimeError('unsafe candidate evidence path')
                candidate = folder / 'solver' / relative
                if (attempt['status'] != 'native' or attempt['record']['status'] != 'ok'
                        or attempt['record']['route'] != 'native'
                        or sha(candidate) != attempt['plan_sha256']):
                    raise RuntimeError('candidate original/native record missing or unknown')
            if sha(plan) != solver['plan_sha256']:
                raise RuntimeError('final plan drift')
            row.update(plan_sha256=sha(plan), status='native_verified')
            dump(args.output / 'ledger.json', ledger)
            ledger['calls']['external_E0'] += 1
            dump(args.output / 'ledger.json', ledger)
            e0 = ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'
            e0_args = [str(PYTHON), '-B', str(e0), str(graph), str(plan),
                       '--config', str(config), '--output', str(folder / 'result.json'),
                       '--trace-output', str(folder / 'trace.json'),
                       '--log-output', str(folder / 'official.log')]
            row['E0_process'] = monitored(e0_args, folder / 'E0-process',
                min(deadline, time.perf_counter() + 30), 536870912)
            if row['E0_process']['status'] != 'ok':
                raise RuntimeError('external E0 failed; stop')
            result = json.loads((folder / 'result.json').read_bytes())
            row['selected_score_match'] = verify_selected(json.loads(plan.read_bytes()),
                                                           solver['attempts'], result, cores)
            row.update(status='evaluated', result_sha256=sha(folder / 'result.json'),
                       makespan=result['makespan'])
            dump(args.output / 'ledger.json', ledger)
        ledger['status'] = 'completed'
    except BaseException as error:
        ledger.update(status='stopped', error=repr(error))
        raise
    finally:
        ledger.update(finished_at=utc(), batch_wall_seconds=time.perf_counter() - started)
        dump(args.output / 'ledger.json', ledger)


if __name__ == '__main__':
    main()
