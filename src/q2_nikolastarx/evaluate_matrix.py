"""Fixed-protocol P2 matrix producer; importing this module never runs a solver.

CLI: plan|run|status --protocol PATH --source-commit SHA --runner-commit SHA
The protocol must exist unchanged in runner_commit. Required protocol keys:
  schema_version=1, run_id, session, task_url, cases, cores, methods,
  solver_mode=direct|portfolio, solver_module, source_files,
  algorithm_id, algorithm_name, variant, method_description,
  output_prefix (under results/a/q2-nikolastarx/), config_sha256, official_sha256,
  max_E0, max_internal_per_cell, evaluation_timeout_seconds,
  solver_wall_seconds, batch_wall_seconds, rss_observation_stop_bytes,
  workers=1, retries=0, max_E1=0, max_E2=0.
Optional: extra_solver_argv, references, authors, offline_costs, python.

Both solver modes receive graph/--config/--cores/--output/--evidence/--wall.
Only portfolio receives --evaluation-timeout. Additional frozen arguments are
literal argv items, never a shell command. The solver writes online/solver.json:
status, selected, plan_sha256, calls={E0,E1,E2}, attempts=[{name,status,...}].
Successful direct mode requires E0=0 and need not have a score/selected_result.
Portfolio requires selected_result; the independent final result must match it.

Each cell has one immutable dispatch reservation, its own evidence, manifest and
one-record board feed. Existing output is never resumed automatically. `status`
lists genuinely undispatched cells separately from dispatched/unknown cells;
manual recovery needs a new explicit protocol after checking orphan processes.
No retries or automatic expansion to a larger matrix are implemented.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from . import evaluate_feedback as common

ROOT = Path(__file__).resolve().parents[2]
REPO = common.REPO
RUNNER = 'src/q2_nikolastarx/evaluate_matrix.py'
REQUIRED = set('schema_version run_id session task_url cases cores methods solver_mode solver_module source_files algorithm_id algorithm_name variant method_description output_prefix config_sha256 official_sha256 max_E0 max_internal_per_cell evaluation_timeout_seconds solver_wall_seconds batch_wall_seconds rss_observation_stop_bytes workers retries max_E1 max_E2'.split())
CONTROLLED_FLAGS = {'--config', '--cores', '--output', '--evidence', '--wall', '--evaluation-timeout'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return common.read(path)


def save(path, data):
    """Atomic and fsynced before launching any potentially expensive child."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def relative(path):
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def repo_path(value, prefix=None):
    if not isinstance(value, str) or not value or Path(value).is_absolute() or '..' in Path(value).parts:
        raise ValueError('Expected a repository-relative path')
    path = (ROOT / value).resolve()
    path.relative_to(ROOT.resolve())
    if prefix and not path.is_relative_to((ROOT / prefix).resolve()):
        raise ValueError('Path outside the producer scope')
    return path


def validate_protocol(p):
    if REQUIRED - p.keys():
        raise ValueError('Missing protocol fields: ' + ', '.join(sorted(REQUIRED - p.keys())))
    if p['schema_version'] != 1 or p['solver_mode'] not in ('direct', 'portfolio'):
        raise ValueError('Unsupported protocol/mode')
    for field in ('run_id', 'session', 'task_url', 'algorithm_id', 'algorithm_name', 'variant', 'method_description'):
        if not isinstance(p[field], str) or not p[field].strip():
            raise ValueError('Expected nonempty string: ' + field)
    for field in ('config_sha256', 'official_sha256'):
        if not isinstance(p[field], str) or not re.fullmatch(r'[0-9a-f]{64}', p[field]):
            raise ValueError('Expected SHA256: ' + field)
    for field in ('cases', 'cores', 'methods', 'source_files'):
        values = p[field]
        if not isinstance(values, list) or not values or len(values) != len(set(values)):
            raise ValueError('Expected nonempty unique enumeration: ' + field)
    if any(not isinstance(c, str) or not re.fullmatch(r'(00[1-9]|0[1-9][0-9]|100)', c) for c in p['cases']):
        raise ValueError('Cases must be official IDs 001..100')
    if any(type(k) is not int or not 1 <= k <= 5 for k in p['cores']):
        raise ValueError('Cores must be integers 1..5')
    if any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', name) for name in p['methods']):
        raise ValueError('Invalid method enum')
    if not re.fullmatch(r'src\.q2_nikolastarx\.[a-z_]+', p['solver_module']):
        raise ValueError('Solver module outside the P2 owner scope')
    if p['solver_module'].replace('.', '/') + '.py' not in p['source_files']:
        raise ValueError('Solver entrypoint must be frozen in source_files')
    for path in p['source_files']:
        repo_path(path, 'src/q2_nikolastarx')
    repo_path(p['output_prefix'], 'results/a/q2-nikolastarx')
    for name in ('max_E0', 'max_internal_per_cell', 'max_E1', 'max_E2', 'workers', 'retries'):
        if type(p[name]) is not int or p[name] < 0:
            raise ValueError('Invalid integer budget: ' + name)
    if (p['workers'], p['retries'], p['max_E1'], p['max_E2']) != (1, 0, 0, 0):
        raise ValueError('This producer supports one worker, no retries and E0 only')
    if p['max_internal_per_cell'] > len(p['methods']):
        raise ValueError('Internal budget exceeds enumerated methods')
    if p['solver_mode'] == 'direct' and p['max_internal_per_cell'] != 0:
        raise ValueError('Direct mode must have zero online E0 budget')
    for name in ('evaluation_timeout_seconds', 'solver_wall_seconds', 'batch_wall_seconds', 'rss_observation_stop_bytes'):
        if type(p[name]) not in (int, float) or not 0 < p[name] < float('inf'):
            raise ValueError('Invalid positive limit: ' + name)
    extra = p.get('extra_solver_argv', [])
    if not isinstance(extra, list) or any(not isinstance(a, str) for a in extra):
        raise ValueError('extra_solver_argv must be a literal string array')
    if any(a.split('=', 1)[0] in CONTROLLED_FLAGS for a in extra):
        raise ValueError('extra_solver_argv cannot override controlled arguments')
    return [(case, cores) for case in p['cases'] for cores in p['cores']]


def frozen_inputs(p, protocol_path, source_commit, runner_commit):
    for commit in (source_commit, runner_commit):
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('Commit must be a full lowercase Git SHA')
    hashes = {'source': {}, 'runner': {}, 'inputs': {}, 'official': {}}
    targets = [(source_commit, path, 'source') for path in p['source_files']]
    targets += [(runner_commit, path, 'runner') for path in
                (RUNNER, 'src/q2_nikolastarx/evaluate_feedback.py', 'uv.lock',
                 'docs/a/source-manifest.json', relative(protocol_path))]
    for commit, path, category in targets:
        raw = repo_path(path).read_bytes()
        if raw != common.git_bytes(commit, path):
            raise ValueError('Unfrozen execution input: ' + path)
        hashes[category][path] = sha(raw)
    manifest = read(ROOT / 'docs/a/source-manifest.json')
    wanted = {'data/config.txt', *(f'data/case_{case}.json' for case in p['cases'])}
    for item in manifest['files']:
        path = item['path']
        if path.startswith('code/') or path in wanted:
            raw = (ROOT / common.OFFICIAL / path).read_bytes()
            if sha(raw) != item['sha256'] or len(raw) != item['bytes']:
                raise ValueError('Official byte mismatch: ' + path)
            hashes['official' if path.startswith('code/') else 'inputs'][path] = sha(raw)
    official_hash = sha(''.join(f'{k}\t{v}\n' for k, v in sorted(hashes['official'].items())).encode())
    if official_hash != p['official_sha256'] or hashes['inputs'].get('data/config.txt') != p['config_sha256']:
        raise ValueError('Wrong frozen official/config identity')
    if not wanted <= hashes['inputs'].keys():
        raise ValueError('Missing official cases')
    return hashes


class Journal:
    def __init__(self, path, identity, cells, budget):
        if path.exists():
            raise FileExistsError('Refusing automatic resume or redispatch: ' + str(path))
        self.path = path
        self.data = {'identity': identity, 'started_at': common.utc(), 'budget_E0': budget,
                     'cells': {f'{c}-k{k}': {'case': c, 'cores': k, 'state': 'pending', 'charged_E0': 0}
                               for c, k in cells}}
        save(path, self.data)

    def reserve(self, key, maximum):
        cell = self.data['cells'][key]
        if cell['state'] != 'pending':
            raise ValueError('Cell already dispatched; retries are forbidden')
        charged = sum(c['charged_E0'] for c in self.data['cells'].values())
        if charged + maximum > self.data['budget_E0']:
            return False
        cell.update(state='dispatching', charged_E0=maximum, reserved_at=common.utc())
        save(self.path, self.data)
        return True

    def finish(self, key, row):
        cell = self.data['cells'][key]
        actual = row['calls']['E0']
        if actual is not None and actual > cell['charged_E0']:
            raise ValueError('Actual E0 exceeded the pre-dispatch reservation')
        cell.update(state=row['status'], completed_at=common.utc(),
                    charged_E0=cell['charged_E0'] if actual is None else actual,
                    calls=row['calls'])
        save(self.path, self.data)


def recovery_status(path):
    journal = read(path)
    return {'identity': journal['identity'],
            'pending': [k for k, v in journal['cells'].items() if v['state'] == 'pending'],
            'dispatched_never_retry': [k for k, v in journal['cells'].items() if v['state'] != 'pending'],
            'warning': 'Read-only recovery plan. Check orphan processes before a separately authorized continuation; no automatic resume.'}


def execute_cell(p, case, cores, folder, deadline, monitor=common.monitored):
    folder.mkdir(parents=True, exist_ok=False)
    rel = relative(folder)
    row = {'case': case, 'cores': cores, 'status': 'failed', 'started_at': common.utc(),
           'calls': {'solver': 0, 'E0': 0, 'E1': 0, 'E2': 0}, 'phase': 'solver_dispatch',
           'solver_mode': p['solver_mode']}
    python = p.get('python', '.venv/bin/python')
    argv = [python, '-B', '-m', p['solver_module'], f'data/raw/a/official/data/case_{case}.json',
            '--config', str(common.CONFIG), '--cores', str(cores), '--output', rel + '/plan.json',
            '--evidence', rel + '/online', '--wall', str(p['solver_wall_seconds'])]
    if p['solver_mode'] == 'portfolio':
        argv += ['--evaluation-timeout', str(p['evaluation_timeout_seconds'])]
    argv += p.get('extra_solver_argv', [])
    save(folder / 'run.json', row)
    try:
        row['solver'] = monitor(argv, folder / 'solver-process',
                                min(deadline, time.perf_counter() + p['solver_wall_seconds']),
                                p['rss_observation_stop_bytes'])
        row['calls']['solver'] = 1 if row['solver'].get('pid') is not None else 0
        row['calls']['E0'] = None if row['calls']['solver'] else 0
        ledger = read(folder / 'online/solver.json') if (folder / 'online/solver.json').exists() else None
        row['online'] = ledger
        if ledger is not None:
            calls = ledger['calls']
            if any(type(calls.get(k)) is not int or calls[k] < 0 for k in ('E0', 'E1', 'E2')):
                raise ValueError('Unknown or malformed online call count')
            row['calls'].update(calls)
            if calls['E1'] or calls['E2'] or calls['E0'] > p['max_internal_per_cell']:
                raise ValueError('Solver violated evaluator budget')
            if any(a.get('status') == 'dispatching' for a in ledger.get('attempts', [])):
                row['calls']['E0'] = None
        if row['solver']['status'] != 'ok' or ledger is None or ledger.get('status') != 'ok':
            row['status'] = 'timeout' if row['solver']['status'] == 'timeout' else 'failed'
            raise ValueError('Solver did not complete successfully')
        names = [a['name'] for a in ledger.get('attempts', [])]
        if len(names) != len(set(names)) or not set(names) <= set(p['methods']):
            raise ValueError('Solver attempts outside frozen method enum')
        if p['solver_mode'] == 'direct' and ledger['calls']['E0'] != 0:
            raise ValueError('Direct solver performed online scoring')
        plan_raw = (folder / 'plan.json').read_bytes()
        if set(json.loads(plan_raw)) != {'node_to_subgraph', 'core_schedules'} or sha(plan_raw) != ledger['plan_sha256']:
            raise ValueError('Final plan/hash mismatch')
        if row['calls']['E0'] is None:
            raise ValueError('Unresolved online dispatch; refusing final E0')
        if time.perf_counter() >= deadline:
            row['status'] = 'timeout'
            raise ValueError('Batch deadline before independent final E0')
        row['phase'] = 'final_dispatch'
        row['final_reserved'] = True
        save(folder / 'run.json', row)
        final_argv = [python, '-B', str(common.ENTRY), f'data/raw/a/official/data/case_{case}.json',
                      rel + '/plan.json', '--config', str(common.CONFIG), '-o', rel + '/final/result.json',
                      '--trace-output', rel + '/final/trace.json', '--log-output', rel + '/final/official.log']
        row['final'] = monitor(final_argv, folder / 'final',
                               min(deadline, time.perf_counter() + p['evaluation_timeout_seconds']),
                               p['rss_observation_stop_bytes'])
        row['calls']['E0'] += 1 if row['final'].get('pid') is not None else 0
        if row['final']['status'] != 'ok':
            row['status'] = 'timeout' if row['final']['status'] == 'timeout' else 'failed'
            raise ValueError('Independent final E0 failed')
        result = common.valid_result(folder / 'final/result.json', cores)
        row['full_online_result_equal'] = None
        if p['solver_mode'] == 'portfolio':
            selected = (folder / 'online' / ledger['selected_result']).resolve()
            selected.relative_to((folder / 'online').resolve())
            row['full_online_result_equal'] = selected.read_bytes() == (folder / 'final/result.json').read_bytes()
            if not row['full_online_result_equal']:
                raise ValueError('Full online/final result mismatch')
        row.update(status='ok', phase='complete', makespan_cycles=result['makespan'])
    except Exception as error:
        row['error'] = str(error).replace(str(ROOT), '${REPO_ROOT}')
        # common.monitored persists a receipt in finally, even when it raises.
        # Distinguish a failed Popen from a child that ran before observation failed.
        phase = row['phase'].split('_')[0]
        if row['phase'].endswith('dispatch') and phase not in row:
            process_path = folder / ('solver-process' if phase == 'solver' else 'final') / 'process.json'
            if process_path.exists():
                row[phase] = read(process_path)
                spawned = row[phase].get('pid') is not None
                if phase == 'solver':
                    row['calls']['solver'] = int(spawned)
                    row['calls']['E0'] = None if spawned else 0
                elif row['calls']['E0'] is not None:
                    row['calls']['E0'] += int(spawned)
            else:
                row['calls']['E0'] = None
                if phase == 'solver':
                    row['calls']['solver'] = None
    finally:
        row['finished_at'] = common.utc()
        save(folder / 'run.json', row)
    return row


def archive_cell(folder, backup):
    compression = common.compress_jsons(folder)
    redacted = {}
    for path in folder.rglob('*'):
        if path.is_file() and path.suffix in ('.txt', '.log'):
            raw = path.read_bytes()
            if str(ROOT).encode() in raw:
                target = backup / path.relative_to(folder)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                derived = raw.replace(str(ROOT).encode(), b'${REPO_ROOT}')
                path.write_bytes(derived)
                redacted[path.relative_to(folder).as_posix()] = {'raw_sha256': sha(raw), 'shared_sha256': sha(derived)}
    save(folder / 'archive.json', {'compression': compression, 'stdout_redaction': redacted,
                                 'raw_stdout_location': 'local backup outside Git; root process prints its path'})


def artifact(path):
    return {'path': relative(path), 'sha256': sha(path.read_bytes())}


def code_source(commit, path, entrypoint):
    return {'repo': REPO, 'commit': commit, 'path': path, 'entrypoint': entrypoint}


def board_record(p, row, folder, context):
    ledger = row.get('online') or {}
    online_scoring = p['solver_mode'] == 'portfolio'
    selected_attempt = next((a for a in ledger.get('attempts', []) if a.get('name') == ledger.get('selected')), {})
    selected_strategy = selected_attempt.get('detail', {}).get('selected_strategy', ledger.get('selected'))
    result = read(folder / 'final/result.json.gz') if row['status'] == 'ok' else None
    movement = result['data_movement_bytes'] if result else {}
    env = {k: v for k, v in context['environment'].items() if k != 'logical_cpus_available'}
    env['peak_rss_bytes'] = max((row.get(k, {}).get('observed_peak_rss_bytes', 0) for k in ('solver', 'final')), default=0) or None
    source_commit, runner_commit = context['source_commit'], context['runner_commit']
    provenance = {'producer_session': p['session'], 'task_url': p['task_url'],
        'solver': {'source': code_source(source_commit, p['solver_module'].replace('.', '/') + '.py', 'main'),
                   'authors': p.get('authors', ['NikolaStarx']), 'method': p['method_description'],
                   'references': p.get('references', []), 'upstream': [],
                   'selected_algorithm_id': selected_strategy,
                   'selected_solver_commit': source_commit if selected_strategy else None},
        'runner': {'source': code_source(runner_commit, RUNNER, 'main'), 'argv': context['argv'], 'working_directory': '.'},
        'environment': env,
        'measurement': {'started_at': row['started_at'], 'finished_at': row['finished_at'], 'seed': None,
                        'repeat_index': 0, 'cold_start': True,
                        'solver_scope': 'Fresh Python process launch through observed exit and owned-descendant cleanup; input, construction and any online scoring included. OS caches not flushed; concurrent machine load not isolated.',
                        'evaluation_scope': ('Online E0 is included in solver wall. The reported evaluation_wall_seconds is only the separate final E0, outside solver wall; its full result is compared to the selected online result.'
                                             if online_scoring else 'Zero online E0. The reported evaluation_wall_seconds is the separate final E0 outside solver wall; no online result exists to compare.'),
                        'budget': {'wall_seconds': p['solver_wall_seconds'], 'candidate_limit': len(p['methods']),
                                   'stop_reason': ledger.get('stop_reason', row.get('error', 'completed'))},
                        'calls': row['calls'], 'offline_costs': p.get('offline_costs', 'Environment preparation and frozen input extraction preceded execution; their elapsed costs are unmeasured here.'),
                        'failure': None if result else {'stage': row['phase'], 'reason': row.get('error', 'incomplete'),
                            'exit_code': row.get('final', row.get('solver', {})).get('exit_code'),
                            'elapsed_seconds': row.get('solver', {}).get('wall_seconds')}},
        'missing_reasons': {}}
    def explain_nulls(value, path='provenance'):
        if isinstance(value, dict):
            for key, item in value.items():
                if key != 'missing_reasons':
                    explain_nulls(item, path + '.' + key)
        elif value is None and not path.endswith(('.failure', '.selected_algorithm_id', '.selected_solver_commit')):
            provenance['missing_reasons'][path] = ('Deterministic solver, no random seed.' if path.endswith('.seed')
                else 'Not observed/available in this actual attempt; see original failure and process receipts.')
    explain_nulls(provenance)
    artifacts = {'run': artifact(folder / 'run.json'), 'manifest': artifact(folder / 'manifest.json')}
    if result:
        artifacts.update(plan=artifact(folder / 'plan.json'), result=artifact(folder / 'final/result.json.gz'))
    record = {'attempt_id': f"{p['run_id']}-p2-{row['case']}-k{row['cores']}", 'revision': 1, 'run_id': p['run_id'],
        'algorithm_id': p['algorithm_id'], 'algorithm_name': p['algorithm_name'], 'variant': p['variant'],
        'solver_commit': source_commit, 'parameters': {'protocol': p, 'selected': ledger.get('selected'),
            'selected_strategy': selected_strategy, 'online_evaluation_in_solver_wall': online_scoring},
        'problem': 'P2', 'case_id': row['case'], 'cores': row['cores'], 'status': row['status'],
        'metrics': {'makespan_cycles': result['makespan'] if result else None,
                    'solver_wall_seconds': row.get('solver', {}).get('wall_seconds'),
                    'evaluation_wall_seconds': row.get('final', {}).get('wall_seconds'),
                    'ddr_bytes': movement.get('scheduled_copy_bytes'), 'extra_ddr_bytes': movement.get('added_copy_bytes'),
                    'spill_bytes': movement.get('spill_added_copy_bytes'), 'cache_hit_rate': None},
        'evaluator': {'route': 'E0', 'commit': source_commit, 'entrypoint': str(common.ENTRY)},
        'identity': {'graph_sha256': context['hashes']['inputs'][f"data/case_{row['case']}.json"],
                     'config_sha256': p['config_sha256'], 'official_sha256': p['official_sha256'],
                     'plan_sha256': ledger.get('plan_sha256')},
        'artifacts': artifacts, 'runtime_id': p['run_id'] + '-runtime', 'observed_at': row['started_at'],
        'timing': {'solver_includes_evaluation': False, 'evaluation_precision': 'perf_counter seconds; ps observer and cleanup overhead included', 'utc': 'UTC'},
        'provenance': provenance, 'notes': ['Producer evidence and format checks are not central import or scientific acceptance.',
            'Subprocess/RSS observations can miss short peaks. All dispatched failures remain in the journal; no automatic retry.',
            ('Portfolio online E0 is included in solver wall; the independently reported final E0 is outside it. timing.solver_includes_evaluation=false describes that final field.'
             if online_scoring else 'Direct mode uses zero online E0; independently reported final E0 is outside solver wall.')], 'source_url': p['task_url']}
    baseline = ROOT / f"results/benchmark-board/official-singlecore-20260924/{row['case']}"
    if (baseline / 'result.json.gz').exists():
        run = read(baseline / 'run.json')
        if (run['status'] != 'ok' or run['graph_sha256'] != record['identity']['graph_sha256']
                or run['config_sha256'] != p['config_sha256'] or run['official_code_hash'] != p['official_sha256']
                or artifact(baseline / 'result.json.gz')['sha256'] != run['artifacts']['result.json']['sha256']):
            raise ValueError('Shared baseline identity mismatch')
        record['baseline'] = {k: record['identity'][k] for k in ('graph_sha256', 'config_sha256', 'official_sha256')}
        record['baseline'].update(route='E0', entrypoint='singlecore_evaluate.evaluate_singlecore', result=artifact(baseline / 'result.json.gz'))
    return record


def write_manifest(folder):
    save(folder / 'manifest.json', {p.relative_to(folder).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
        for p in sorted(folder.rglob('*')) if p.is_file() and p.name != 'manifest.json'})


def stop_dispatch_reason(row):
    if row['calls']['E0'] is None or row['calls']['solver'] is None:
        return 'unknown_dispatch_or_call_count'
    for stage in ('solver', 'final'):
        receipt = row.get(stage, {})
        if receipt.get('status') in ('rss_limit', 'runner_error'):
            return stage + '_' + receipt['status']
        if receipt.get('surviving_pids'):
            return stage + '_owned_processes_still_live'
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'run', 'status'])
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--runner-commit', required=True)
    args = parser.parse_args()
    protocol_path = args.protocol.resolve()
    p = read(protocol_path)
    cells = validate_protocol(p)
    output = repo_path(p['output_prefix'], 'results/a/q2-nikolastarx')
    if args.action == 'status':
        print(json.dumps(recovery_status(output / 'journal.json'), ensure_ascii=False))
        return
    hashes = frozen_inputs(p, protocol_path, args.source_commit, args.runner_commit)
    if args.action == 'plan':
        print(json.dumps({'cells': cells, 'cell_count': len(cells), 'mode': p['solver_mode'],
                          'maximum_E0_per_cell': p['max_internal_per_cell'] + 1, 'budget_E0': p['max_E0'],
                          'frozen': hashes, 'dispatched': 0}, ensure_ascii=False))
        return
    output.mkdir(parents=True, exist_ok=False)
    context = {'source_commit': args.source_commit, 'runner_commit': args.runner_commit,
               'protocol_sha256': sha(protocol_path.read_bytes()), 'hashes': hashes,
               'environment': common.environment(),
               'argv': [p.get('python', '.venv/bin/python'), '-B', '-m', 'src.q2_nikolastarx.evaluate_matrix',
                        'run', '--protocol', relative(protocol_path), '--source-commit', args.source_commit,
                        '--runner-commit', args.runner_commit]}
    save(output / 'context.json', context)
    journal = Journal(output / 'journal.json', {k: context[k] for k in ('source_commit', 'runner_commit', 'protocol_sha256')}, cells, p['max_E0'])
    backup = Path(tempfile.mkdtemp(prefix='q2-matrix-raw-'))
    print(json.dumps({'raw_stdout_backup': str(backup)}), flush=True)
    batch_start = time.perf_counter()
    deadline = batch_start + p['batch_wall_seconds']
    for case, cores in cells:
        key = f'{case}-k{cores}'
        if time.perf_counter() >= deadline:
            journal.data['stop_reason'] = 'batch_wall_budget'
            break
        frozen_inputs(p, protocol_path, args.source_commit, args.runner_commit)
        if not journal.reserve(key, p['max_internal_per_cell'] + 1):
            journal.data['stop_reason'] = 'e0_reservation_budget'
            break
        folder = output / key
        row = execute_cell(p, case, cores, folder, deadline)
        journal.finish(key, row)
        archive_cell(folder, backup / key)
        write_manifest(folder)
        feed_path = output / f'board-feed-{key}.json'
        save(feed_path, {'schema_version': 1, 'submission_version': 1,
                         'records': [board_record(p, row, folder, context)]})
        command = [p.get('python', '.venv/bin/python'), '-B', 'src/benchmark_board/protocol.py', relative(feed_path), '--submission']
        checked = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        save(output / f'precheck-{key}.json', {'argv': command, 'exit_code': checked.returncode,
                                            'stdout': checked.stdout, 'stderr': checked.stderr})
        if checked.returncode:
            raise ValueError('Producer precheck failed; evidence retained, no rerun')
        print(json.dumps({'cell': key, 'status': row['status'], 'calls': row['calls'], 'feed': relative(feed_path)}), flush=True)
        reason = stop_dispatch_reason(row)
        if reason:
            journal.data['stop_reason'] = reason
            break
    journal.data['finished_at'] = common.utc()
    journal.data['execution_wall_seconds'] = time.perf_counter() - batch_start
    journal.data.setdefault('stop_reason', 'all_fixed_cells_dispatched')
    save(journal.path, journal.data)


if __name__ == '__main__':
    main()
