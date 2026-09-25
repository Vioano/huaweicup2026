"""Frozen 15d86e1 P2 bidirectional holdout12 Mac producer; preflight has no score calls."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = None
PYTHON = None
E2_ROOT = None
RAW_ROOT = None
SOLVER = '15d86e13b4a8abb4bce445ac241aecac13f553bf'
MODULE = 'src.q2_nikolastarx.adaptive_bidirectional_guarded'
COORDS = None  # exact ordered coordinates are loaded from the pinned selection manifest
SELECTION_SHA = '6060d2a281e963614eb0634dbf90454b3b7b52be73d0d6cc67287436e33d16b1'
SALT = 'p2-15d-k5-holdout-v1'
EXCLUDED = ('005', '010', '064', '068', '069', '071', '086', '088')
FIELDS = ('original_graph_copy_bytes', 'scheduled_copy_bytes', 'added_copy_bytes',
          'partition_added_copy_bytes', 'spill_added_copy_bytes')
LIMITS = {'cells': 12, 'workers': 1, 'E2_api': 48,
          'E0_independent': 12, 'solver_seconds': 180, 'e0_seconds': 180,
          'batch_seconds': 1800, 'rss_bytes_per_cell': 2 << 30,
          'rss_bytes_total': 2 << 30, 'retries': 0, 'E0_fallback_reserve': 1}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def runtime_import_preflight(python, e2_root):
    """Import E2 dependencies with the actual invocation path, without scoring."""
    code = ('import pathlib, sys\n'
            'root = pathlib.Path(sys.argv[1]).resolve()\n'
            'if pathlib.Path(sys.executable) != pathlib.Path(sys.argv[2]):\n'
            '    raise RuntimeError("Python invocation path changed")\n'
            'if sys.prefix == sys.base_prefix: raise RuntimeError("venv not active")\n'
            'sys.path.insert(0, str(root))\n'
            'import research.a.e2_search as e2\n'
            'import src.eval_exact._official as official\n'
            'for module in (e2, official):\n'
            '    if not pathlib.Path(module.__file__).resolve().is_relative_to(root):\n'
            '        raise RuntimeError("foreign evaluator import")\n')
    result = subprocess.run([str(python), '-B', '-c', code, str(e2_root), str(python)],
                            cwd=ROOT, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ValueError('Interpreter/E2 import-only preflight failed: ' + result.stderr[-2000:])


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def canonical(plan):
    if not isinstance(plan, dict) or set(plan) != {'node_to_subgraph', 'core_schedules'}:
        raise ValueError('Wrong complete-plan keys')
    return digest(json.dumps(plan, sort_keys=True, allow_nan=False).encode())


def load_selection(doc, manifest_path, raw_root):
    """Independently reconstruct the preregistered raw-ops strata, with no score data."""
    ref = doc.get('selection_manifest')
    if (not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}
            or ref['sha256'] != SELECTION_SHA or Path(ref['path']).is_absolute()
            or '..' in Path(ref['path']).parts):
        raise ValueError('Frozen selection reference mismatch')
    parent = manifest_path.resolve().parent
    path = (parent / ref['path']).resolve(strict=True)
    if not path.is_relative_to(parent) or sha(path) != SELECTION_SHA:
        raise ValueError('Frozen selection bytes differ')
    selection = read(path)
    if (selection.get('schema') != 'p2-holdout12-selection-v1'
            or selection.get('salt') != SALT
            or selection.get('excluded_cases') != list(EXCLUDED)
            or selection.get('scoring_calls') != 0):
        raise ValueError('Selection identity differs')
    rows = []
    for number in range(1, 101):
        case = f'{number:03d}'
        if case in EXCLUDED:
            continue
        raw = (raw_root / 'data' / f'case_{case}.json').read_bytes()
        graph = json.loads(raw)
        if not isinstance(graph.get('ops'), list):
            raise ValueError('Raw graph ops absent: ' + case)
        rows.append({'case': case, 'node_count': len(graph['ops']),
                     'graph_sha256': digest(raw),
                     'selection_key': digest((SALT + case).encode('utf-8'))})
    rows.sort(key=lambda row: (row['node_count'], row['case']))
    if len(rows) != 92:
        raise ValueError('Wrong eligible case count')
    expected_strata, chosen = [], []
    for q in range(4):
        members = rows[q*23:(q+1)*23]
        picked = [r['case'] for r in sorted(members,
                  key=lambda r: (r['selection_key'], r['case']))[:3]]
        expected_strata.append({'quartile': q+1, 'node_count_min': members[0]['node_count'],
                                'node_count_max': members[-1]['node_count'],
                                'members': members, 'selected': picked})
        chosen.extend(picked)
    coords = [[case, 5] for case in chosen]
    if (selection.get('strata') != expected_strata or selection.get('coordinates') != coords
            or doc.get('coordinates') != coords or len(set(chosen)) != 12):
        raise ValueError('Selection does not match raw-ops deterministic recomputation')
    return tuple((case, 5) for case in chosen)


def metrics(record, *, official, cores=None):
    if not isinstance(record, dict) or record.get('status') not in (None, 'ok'):
        raise ValueError('Evaluation status unavailable')
    if official and (record.get('scene') != 'B' or record.get('num_cores') != cores):
        raise ValueError('Official scene/core identity mismatch')
    if not official and (record.get('route') != 'native' or record.get('problem') != 2):
        raise ValueError('Online score is not native P2')
    movement = record.get('data_movement_bytes')
    if (type(record.get('makespan')) is not int or record['makespan'] <= 0
            or not isinstance(movement, dict) or set(movement) != set(FIELDS)
            or any(type(movement[k]) is not int or movement[k] < 0 for k in FIELDS)
            or type(record.get('cross_task_traffic')) is not int
            or record['cross_task_traffic'] < 0):
        raise ValueError('Incomplete exact P2 metrics')
    return {'makespan': record['makespan'], 'cross_task_traffic': record['cross_task_traffic'],
            'data_movement_bytes': {k: movement[k] for k in FIELDS}}


def preflight(repo, raw_root, e2_root, python, manifest_path):
    global ROOT, PYTHON, E2_ROOT, RAW_ROOT, COORDS
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('Requires macOS arm64')
    ROOT, PYTHON, E2_ROOT, RAW_ROOT = (repo.resolve(strict=True), python.absolute(),
                                      e2_root.resolve(strict=True), raw_root.resolve(strict=True))
    if not PYTHON.is_file():
        raise ValueError('Python invocation path missing')
    doc = read(manifest_path)
    if (doc.get('schema') != 'q2-bidirectional-holdout12-v1'
            or doc.get('solver_source_commit') != SOLVER
            or doc.get('solver_module') != MODULE
            or doc.get('limits') != LIMITS):
        raise ValueError('Frozen local manifest/scope mismatch')
    COORDS = load_selection(doc, manifest_path, RAW_ROOT)
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() != SOLVER:
        raise ValueError('Detached source checkout HEAD differs')
    if sha(PYTHON.resolve(strict=True)) != doc['python_sha256'] or sha(Path(__file__)) != doc['runner_sha256']:
        raise ValueError('Python or runner bytes differ')
    if subprocess.check_output([str(PYTHON), '-c', 'import sys;print(sys.version_info[:2])'],
                               text=True).strip() != '(3, 12)':
        raise ValueError('Requires fixed Python 3.12')
    runtime_import_preflight(PYTHON, E2_ROOT)
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', SOLVER,
                                     'src/q2_nikolastarx', 'data/raw/a/official/code'],
                                    cwd=ROOT, text=True).splitlines()
    if set(doc['source_files']) != set(names):
        raise ValueError('Fixed source file set differs')
    actual_python = {p.relative_to(ROOT).as_posix()
                     for p in (ROOT / 'src/q2_nikolastarx').rglob('*.py')}
    expected_python = {n for n in names if n.startswith('src/q2_nikolastarx/') and n.endswith('.py')}
    if actual_python != expected_python:
        raise ValueError('Untracked or missing solver Python module')
    for name, expected in doc['source_files'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Frozen source drift: ' + name)
    # The CLI records its immediate Python source directory, not official code.
    # Keep the exact checked subset for runtime receipt comparisons in cell().
    doc['solver_sources'] = {name: doc['source_files'][name] for name in expected_python}
    fixed = read(ROOT / 'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json')
    if fixed['e2_commit'] != '603b0741e21c449d3db652ebd67c94f2dc014cc9' or len(fixed['e2_sources']) != 50:
        raise ValueError('Wrong E2 source manifest')
    e2_files = {**fixed['e2_sources'], fixed['binary']['path']: fixed['binary']['sha256']}
    if doc['e2_files'] != e2_files or {x.relative_to(E2_ROOT).as_posix() for x in E2_ROOT.rglob('*') if x.is_file()} != set(e2_files):
        raise ValueError('E2 export file set differs')
    for name, expected in e2_files.items():
        if sha(E2_ROOT / name) != expected:
            raise ValueError('E2 source/native drift: ' + name)
    official_doc = read(ROOT / 'docs/a/source-manifest.json')
    entries = {x['path']: x for x in official_doc['files']}
    official_names = ['data/config.txt', *(f'data/case_{i:03d}.json' for i in range(1, 101)),
                      *(x for x in entries if x.startswith('code/') and x.endswith('.py'))]
    if set(doc['official_inputs']) != set(official_names):
        raise ValueError('Official input set differs')
    for name in official_names:
        path = RAW_ROOT / name
        if sha(path) != entries[name]['sha256'] or path.stat().st_size != entries[name]['bytes']:
            raise ValueError('Official input/source drift: ' + name)
        if doc['official_inputs'][name] != entries[name]['sha256']:
            raise ValueError('Frozen official input hash differs: ' + name)
        if name.startswith('code/') and sha(ROOT / 'data/raw/a/official' / name) != entries[name]['sha256']:
            raise ValueError('Detached official code differs')
    if doc['official_source_manifest_sha256'] != sha(ROOT / 'docs/a/source-manifest.json'):
        raise ValueError('Official manifest drift')
    baseline_path = manifest_path.resolve().parent / doc['singlecore_baseline']['path']
    baseline = read(baseline_path)
    if sha(baseline_path) != doc['singlecore_baseline']['sha256'] or len(baseline['records']) != 100:
        raise ValueError('Single-core baseline identity/coverage mismatch')
    doc['singlecore_baseline_m'] = {r['case']: r['makespan'] for r in baseline['records']}
    if set(doc['singlecore_baseline_m']) != {f'{i:03d}' for i in range(1, 101)}:
        raise ValueError('Single-core denominator coverage mismatch')
    for row in baseline['records']:
        if (row['graph_sha256'] != doc['official_inputs'][f"data/case_{row['case']}.json"]
                or row['config_sha256'] != doc['official_inputs']['data/config.txt']):
            raise ValueError('Single-core denominator input mismatch')
    doc['baseline_provenance'] = {k: baseline[k] for k in ('source_commit', 'feed_path', 'feed_sha256')}
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
    from src.q2_nikolastarx.adaptive_guarded import check_e2_source
    from src.q2_nikolastarx import evaluate_feedback
    if Path(evaluate_feedback.__file__).resolve().parents[2] != ROOT:
        raise ValueError('Monitor imported from a different checkout')
    e2 = check_e2_source(E2_ROOT)
    return doc, {'native_binary_sha256': e2['native_binary_sha256']}, e2, evaluate_feedback.monitored, SOLVER, sha(manifest_path)


def inspect_solver(folder, case, cores, process, sources, e2):
    ledger_path = folder / 'online/solver.json'
    if not ledger_path.exists():
        raise ValueError('Solver ledger absent; E2 count unknown')
    ledger = read(ledger_path)
    calls, attempts = ledger.get('calls', {}), ledger.get('attempts', [])
    if (process.get('status') != 'ok' or process.get('surviving_pids')
            or ledger.get('status') != 'ok' or ledger.get('request_in_flight')
            or type(calls.get('E2_api_attempted')) is not int
            or not 0 <= calls['E2_api_attempted'] <= 4
            or len(attempts) != calls['E2_api_attempted']
            or calls.get('native_returns') != len(attempts)
            or calls.get('E0_fallback') != 0 or calls.get('E0') != 0
            or ledger.get('possible_E0_fallback_calls') != 0
            or any(a.get('status') != 'native' for a in attempts)):
        raise ValueError('Solver failed, fallback, over cap or E2 outcome unknown')
    if (ledger.get('source_checked') != bool(attempts)
            or (attempts and any(ledger.get('source', {}).get(k) != e2[k]
                                 for k in ('commit', 'manifest_sha256', 'native_binary_sha256')))):
        raise ValueError('Online E2 source identity differs from preflight')
    expected_hashes = {Path(p).name: h for p, h in sources.items()}
    if (ledger.get('solver_source_sha256') != expected_hashes
            or ledger.get('graph_sha256') != sha(RAW_ROOT / f'data/case_{case}.json')
            or ledger.get('config_sha256') != sha(RAW_ROOT / 'data/config.txt')
            or ledger.get('cores') != cores):
        raise ValueError('Solver runtime input/source readback mismatch')
    detail = ledger.get('detail')
    base = detail.get('incumbent_detail') if isinstance(detail, dict) else None
    if (not isinstance(base, dict) or detail.get('score_evidence') == 'unknown'
            or base.get('score_evidence') == 'unknown'
            or any(x.get('kind') == 'unexpected' for x in base.get('construction_errors', []))):
        raise ValueError('Unknown or unexpected route detail')
    plan_path = folder / 'plan.json'
    if sha(plan_path) != ledger.get('plan_sha256'):
        raise ValueError('Selected plan byte hash differs from ledger')
    plan = read(plan_path)
    if len(plan.get('core_schedules', [])) != cores:
        raise ValueError('Selected plan core count mismatch')
    key = canonical(plan)
    for index, attempt in enumerate(attempts, 1):
        relative = attempt.get('plan_file')
        if relative != f'oracle-plans/{index:03d}.json':
            raise ValueError('Missing or out-of-order complete oracle plan')
        original = folder / 'online' / relative
        if sha(original) != attempt.get('plan_sha256') or canonical(read(original)) != attempt['plan_sha256']:
            raise ValueError('Complete oracle plan original/hash mismatch')
        metrics(attempt.get('record'), official=False)
    selected = [a['record'] for a in attempts if a.get('plan_sha256') == key]
    if attempts:
        if (detail.get('score_evidence') != 'injected_oracle_complete_plan_scores'
                or len(selected) != 1):
            raise ValueError('Selected plan lacks unique native E2 score')
        score = metrics(selected[0], official=False)
        route = 'selected_native'
    else:
        if (base.get('score_evidence') != 'not_requested'
                or base.get('unique_plans') != 1 or detail.get('selected') != 'incumbent'
                or detail.get('score_evidence') != 'not_requested'
                or detail.get('unique_scored_plans') != 0
                or detail.get('skip_reason') not in ('single_core', 'reverse_duplicates_incumbent')):
            raise ValueError('Zero E2 allowed only for one-plan structural route')
        score, route = None, 'single_plan_independent_E0_only'
    return ledger, score, route


def cell(case, cores, doc, identity, e2, monitored, output, deadline):
    folder = output / f'{case}-k{cores}'
    folder.mkdir(exist_ok=False)
    row = {'case': case, 'cores': cores, 'status': 'running',
           'calls': {'solver_started': 1, 'E2_api_attempted': None,
                     'native_returns': None, 'E0_fallback_possible': None,
                     'E0_independent_started': 0},
           'paths': {'folder': folder.relative_to(output).as_posix(),
                     'plan': (folder / 'plan.json').relative_to(output).as_posix(),
                     'solver_ledger': (folder / 'online/solver.json').relative_to(output).as_posix(),
                     'result': (folder / 'result.json').relative_to(output).as_posix()}}
    save(folder / 'cell.json', row)
    try:
        graph = RAW_ROOT / f'data/case_{case}.json'
        config = RAW_ROOT / 'data/config.txt'
        cmd = [str(PYTHON), '-B', '-m', MODULE, str(graph), '--config', str(config),
               '--cores', str(cores), '--output', str(folder / 'plan.json'),
               '--evidence', str(folder / 'online'), '--e2-root', str(E2_ROOT), '--wall', '180']
        row['solver_process_in_flight'] = True
        save(folder / 'cell.json', row)
        process = monitored(cmd, folder / 'solver-process', min(deadline, time.perf_counter() + 180),
                            LIMITS['rss_bytes_per_cell'])
        row['solver_process_in_flight'] = False
        row['solver_process'] = {k: process.get(k) for k in
            ('status', 'wall_seconds', 'observed_peak_rss_bytes', 'surviving_pids')}
        row['solver_process']['path'] = (folder / 'solver-process/process.json').relative_to(output).as_posix()
        ledger_path = folder / 'online/solver.json'
        if ledger_path.exists():
            ledger = read(ledger_path)
            calls = ledger.get('calls', {})
            row['calls'].update(E2_api_attempted=calls.get('E2_api_attempted'),
                                native_returns=calls.get('native_returns'),
                                E0_fallback_possible=ledger.get('possible_E0_fallback_calls'))
            row['request_in_flight'] = ledger.get('request_in_flight')
            row['call_count_complete'] = (ledger.get('request_in_flight') is False
                                          and type(calls.get('E2_api_attempted')) is int
                                          and ledger.get('possible_E0_fallback_calls') ==
                                          calls.get('E0_fallback'))
            row['solver_ledger_sha256'] = sha(ledger_path)
        else:
            row['call_count_complete'] = False
        save(folder / 'cell.json', row)
        ledger, score, route = inspect_solver(folder, case, cores, process,
                                              doc['solver_sources'], e2)
        row['selected_comparison_kind'] = route
        row['selected_E2'] = score
        row['plan_sha256'] = sha(folder / 'plan.json')
        row['solver_wall_seconds'] = process['wall_seconds']
        if time.perf_counter() >= deadline:
            raise TimeoutError('Batch deadline before independent E0')
        row['calls']['E0_independent_started'] = 1
        row['independent_e0_in_flight'] = True
        save(folder / 'cell.json', row)
        e0_cmd = [str(PYTHON), '-B', str(ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
                  str(graph), str(folder / 'plan.json'), '--config', str(config),
                  '--output', str(folder / 'result.json'),
                  '--trace-output', str(folder / 'trace.json'),
                  '--log-output', str(folder / 'official.log')]
        result_process = monitored(e0_cmd, folder / 'e0-process',
                                   min(deadline, time.perf_counter() + 180),
                                   LIMITS['rss_bytes_per_cell'])
        row['independent_e0_in_flight'] = False
        row['e0_process'] = {k: result_process.get(k) for k in
            ('status', 'wall_seconds', 'observed_peak_rss_bytes', 'surviving_pids')}
        row['e0_process']['path'] = (folder / 'e0-process/process.json').relative_to(output).as_posix()
        if result_process.get('status') != 'ok' or result_process.get('surviving_pids'):
            raise ValueError('Independent E0 failed/uncertain')
        official = metrics(read(folder / 'result.json'), official=True, cores=cores)
        if score is not None and score != official:
            raise ValueError('Selected native E2 and independent E0 differ')
        row['official'] = official
        row['result_sha256'] = sha(folder / 'result.json')
        row['singlecore_baseline_m'] = doc['singlecore_baseline_m'][case]
        row['speedup'] = row['singlecore_baseline_m'] / official['makespan']
        row['status'] = 'accepted'
    except Exception as error:
        row.update(status='stopped', error=repr(error))
    finally:
        save(folder / 'cell.json', row)
    return row


def run(doc, identity, e2, monitored, manifest_sha, runtime_head, output):
    if output.exists():
        raise ValueError('Output exists; no resume or repeat')
    started = time.perf_counter()
    deadline = started + LIMITS['batch_seconds']
    output.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'running', 'solver_commit': SOLVER,
               'runner_sha256': doc['runner_sha256'],
               'selection_sha256': SELECTION_SHA,
               'repo_head': runtime_head, 'local_manifest_sha256': manifest_sha,
               'e2_native_binary_sha256': identity['native_binary_sha256'],
               'limits': doc['limits'], 'accepted_cells': 0, 'rows': [], 'in_flight': [],
               'calls': {'solver_started': 0, 'E2_api_attempted': 0,
                         'native_returns': 0, 'E0_fallback_possible': 0,
                         'E0_independent_started': 0},
               'call_count_complete': True,
               'scope': 'p2-bidirectional-holdout12',
               'baseline_scope': 'fixed 100-case single-core M only; no old-plan first-native comparison'}
    summary['baseline_provenance'] = doc['baseline_provenance']
    summary['singlecore_baseline_sha256'] = doc['singlecore_baseline']['sha256']
    save(output / 'summary.json', summary)
    next_index, stop, running = 0, False, {}
    with ThreadPoolExecutor(max_workers=doc['limits']['workers']) as pool:
        while next_index < len(COORDS) or running:
            while (not stop and next_index < len(COORDS)
                   and len(running) < doc['limits']['workers'] and time.perf_counter() < deadline):
                if summary['calls']['E2_api_attempted'] + 4 * (len(running) + 1) > LIMITS['E2_api']:
                    stop = True
                    summary['status'] = 'stopped_E2_dispatch_budget'
                    break
                case, cores = COORDS[next_index]
                next_index += 1
                key = f'{case}-k{cores}'
                summary['in_flight'].append(key)
                summary['calls']['solver_started'] += 1
                save(output / 'summary.json', summary)
                running[pool.submit(cell, case, cores, doc, identity, e2, monitored,
                                    output, deadline)] = key
            if not running:
                break
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in done:
                key = running.pop(future)
                try:
                    entry = future.result()
                except Exception as error:
                    entry = {'case': key.split('-')[0], 'cores': int(key.split('k')[1]),
                             'status': 'stopped', 'error': 'Worker raised: '+repr(error),
                             'calls': {'E2_api_attempted': None, 'native_returns': None,
                                       'E0_independent_started': None}}
                summary['in_flight'].remove(key)
                summary['rows'].append({k: v for k, v in entry.items()
                                        if k not in ('solver_process_in_flight', 'independent_e0_in_flight')})
                for name in ('E2_api_attempted', 'native_returns', 'E0_fallback_possible',
                             'E0_independent_started'):
                    value = entry.get('calls', {}).get(name)
                    if type(value) is int:
                        summary['calls'][name] += value
                    else:
                        summary['call_count_complete'] = False
                        if name == 'E0_fallback_possible':
                            # A missing ledger is unknown, not proof of zero internal E0.
                            # Reserve one possible call and stop on this failed cell.
                            summary['calls'][name] += 1
                if entry['status'] != 'accepted':
                    stop = True
                    summary['status'] = 'stopped_first_failure'
                else:
                    summary['accepted_cells'] += 1
                if entry.get('call_count_complete') is False:
                    summary['call_count_complete'] = False
                if (summary['calls']['E2_api_attempted'] > LIMITS['E2_api']
                        or summary['calls']['E0_independent_started'] > LIMITS['E0_independent']
                        or summary['calls']['E0_fallback_possible'] > LIMITS['E0_fallback_reserve']
                        or summary['calls']['E0_independent_started'] +
                           summary['calls']['E0_fallback_possible'] > LIMITS['E0_independent']):
                    stop = True
                    summary['status'] = 'stopped_budget_exceeded'
                summary['total_wall_seconds'] = time.perf_counter() - started
                save(output / 'summary.json', summary)
        summary['total_wall_seconds'] = time.perf_counter() - started
        if not stop and summary['accepted_cells'] == 12:
            summary['status'] = 'completed'
        elif summary['status'] == 'running':
            summary['status'] = 'stopped_incomplete_or_deadline'
        save(output / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('preflight', 'run'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--raw-root', type=Path, required=True)
    parser.add_argument('--e2-root', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    doc, identity, e2, monitored, runtime_head, manifest_sha = preflight(
        args.repo, args.raw_root, args.e2_root, args.python, args.manifest)
    if args.mode == 'preflight':
        print(json.dumps({'status': 'preflight_ok', 'cells': 12, 'calls': 0,
                          'selection_sha256': SELECTION_SHA,
                          'upstream_solver': SOLVER, 'repo_head': runtime_head}))
        return
    if args.output is None:
        parser.error('run needs --output')
    output = args.output.resolve()
    if any(output == fixed or output.is_relative_to(fixed)
           for fixed in (ROOT, RAW_ROOT, E2_ROOT)):
        raise ValueError('Write results outside source and fixed input roots')
    summary = run(doc, identity, e2, monitored, manifest_sha, runtime_head, output)
    if summary['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
