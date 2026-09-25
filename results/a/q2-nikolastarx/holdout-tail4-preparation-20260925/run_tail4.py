"""Gate-bound continuation: saved 097 E0, then three frozen 15d cells."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from scripts import q2_bidirectional_holdout as holdout
from scripts.q2_bidirectional_holdout_supervise import host_memory_state

SCOPE = 'p2-bidirectional-holdout-tail4'
LIMITS = {'new_solver': 3, 'E2_api': 12, 'total_E0': 4,
          'fallback_reserve': 1, 'retries': 0, 'workers': 1,
          'per_process_seconds': 180, 'batch_seconds': 720,
          'rss_bytes': 2 << 30, 'swap_growth_bytes': 256 << 20,
          'disk_free_bytes': 10 << 30, 'pressure_level': 1}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_bytes())

def check_gate(gate, doc, mpath):
    if (gate.get('scope') != SCOPE or gate.get('status') != 'admitted'
            or gate.get('manifest_sha256') != sha(mpath)
            or gate.get('runner_sha256') != sha(Path(__file__))):
        raise ValueError('unadmitted_or_unpinned_gate')
    expiry = datetime.fromisoformat(gate['expires_at'].replace('Z', '+00:00'))
    if expiry.tzinfo is None or datetime.now(timezone.utc) >= expiry:
        raise ValueError('expired_gate')
    if doc.get('scope') != SCOPE or doc.get('limits') != LIMITS:
        raise ValueError('manifest_scope_or_limits_mismatch')

def file_pin(path, digest):
    if not path.is_file() or sha(path) != digest:
        raise ValueError('pin_mismatch:' + str(path))

def stage_check(output, baseline_swap):
    pressure, swap = host_memory_state()
    free = shutil.disk_usage(output.parent).free
    if pressure != 1 or swap - baseline_swap > 256 << 20 or free < 10 << 30:
        raise ValueError('host_resource_guard')
    return {'pressure_level': pressure, 'swap_used_bytes': swap,
            'swap_delta_bytes': swap-baseline_swap, 'disk_free_bytes': free}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--gate', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    started = time.perf_counter()
    mpath = HERE / 'manifest.json'
    doc = read(mpath)
    check_gate(read(a.gate), doc, mpath)  # No work or output before gate.
    if a.output.exists():
        raise ValueError('output_must_be_fresh')
    pins = doc['runtime']
    if any(not isinstance(v, str) or v.startswith('FILL_') for v in pins.values()):
        raise ValueError('runtime_pins_incomplete')
    if (not isinstance(doc.get('holdout_runner_sha256'), str)
            or doc['holdout_runner_sha256'].startswith('FILL_')):
        raise ValueError('holdout_runner_hash_unfilled')
    file_pin(ROOT / 'scripts/q2_bidirectional_holdout.py', doc['holdout_runner_sha256'])
    repo = Path(pins['repo'])
    raw = Path(pins['raw_root'])
    e2_root = Path(pins['e2_root'])
    python = Path(pins['python']).absolute()  # Preserve venv invocation symlink.
    holdout_manifest = Path(pins['holdout_manifest'])
    file_pin(holdout_manifest, doc['holdout_manifest_sha256'])
    file_pin(repo / 'src/q2_nikolastarx/evaluate_feedback.py', doc['monitor_sha256'])
    old = ROOT / doc['saved_097']['folder']
    file_pin(old / 'plan.json', doc['saved_097']['plan_sha256'])
    file_pin(old / 'online/solver.json', doc['saved_097']['ledger_sha256'])
    file_pin(old / 'solver-process/process.json', doc['saved_097']['process_sha256'])
    file_pin(old / 'cell.json', doc['saved_097']['cell_sha256'])
    ledger097 = read(old / 'online/solver.json')
    old_cell = read(old / 'cell.json')
    if (old_cell.get('solver_process', {}).get('status') != 'ok'
            or old_cell['solver_process'].get('surviving_pids')
            or old_cell['solver_process'].get('wall_seconds') !=
               doc['saved_097']['old_solver_wall_seconds']):
        raise ValueError('saved_097_solver_receipt_unverified')
    if (ledger097.get('status') != 'ok' or ledger097.get('solver_checkout_commit') != holdout.SOLVER
            or ledger097.get('plan_sha256') != doc['saved_097']['plan_sha256']
            or ledger097.get('request_in_flight') is not False
            or ledger097.get('possible_E0_fallback_calls') != 0
            or ledger097.get('calls', {}).get('E2_api_attempted') != 0
            or ledger097.get('calls', {}).get('E0_fallback') != 0):
        raise ValueError('saved_097_identity_or_calls_unverified')
    if sha(raw / 'data/case_097.json') != ledger097['graph_sha256']:
        raise ValueError('saved_097_graph_drift')
    identity_doc, identity, e2, monitored, runtime_head, _ = holdout.preflight(
        repo, raw, e2_root, python, holdout_manifest)
    if runtime_head != holdout.SOLVER or identity_doc['solver_source_commit'] != holdout.SOLVER:
        raise ValueError('wrong_fixed_solver')
    holdout.inspect_solver(old, '097', 5,
        read(old / 'solver-process/process.json'), identity_doc['solver_sources'], e2)
    baseline_swap = host_memory_state()[1]
    stage_check(a.output, baseline_swap)
    if time.perf_counter() >= started + 720:
        raise TimeoutError('preflight_exhausted_batch')
    a.output.mkdir(exist_ok=False)
    summary = {'scope': SCOPE, 'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
               'finished_at': None, 'in_flight': None, 'call_count_complete': False,
               'order': ['097-E0-only', '076', '003', '084'],
               'calls': {'new_solver_started': 0, 'E2_api_attempted': 0,
                         'E0_independent_started': 0, 'E0_fallback_possible': 0},
               'rows': [], 'runner_sha256': sha(Path(__file__)),
               'manifest_sha256': sha(mpath), 'gate_sha256': sha(a.gate),
               'saved_097_solver_wall_seconds': doc['saved_097']['old_solver_wall_seconds'],
               'saved_097_new_solver_started': False}
    holdout.save(a.output / 'summary.json', summary)
    deadline = started + 720
    try:
        stage_check(a.output, baseline_swap)
        folder = a.output / '097-k5'
        folder.mkdir()
        summary['calls']['E0_independent_started'] += 1
        summary['in_flight'] = {'case': '097', 'phase': 'E0', 'E0_independent_started': 1}
        holdout.save(a.output / 'summary.json', summary)
        graph = raw / 'data/case_097.json'
        config = raw / 'data/config.txt'
        argv = [str(python), '-B', str(repo / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
                str(graph), str(old / 'plan.json'), '--config', str(config),
                '--output', str(folder / 'result.json'), '--trace-output', str(folder / 'trace.json'),
                '--log-output', str(folder / 'official.log')]
        process = monitored(argv, folder / 'e0-process', min(deadline, time.perf_counter()+180), 2 << 30)
        stage_check(a.output, baseline_swap)
        if process.get('status') != 'ok' or process.get('surviving_pids'):
            raise ValueError('097_E0_failed_or_uncertain')
        official = holdout.metrics(read(folder / 'result.json'), official=True, cores=5)
        summary['rows'].append({'case': '097', 'status': 'accepted', 'kind': 'saved_plan_E0_only',
                                'plan_sha256': sha(old / 'plan.json'), 'official': official,
                                'result_sha256': sha(folder / 'result.json'),
                                'old_solver_wall_seconds': doc['saved_097']['old_solver_wall_seconds'],
                                'new_solver_started': False})
        summary['in_flight'] = None
        holdout.save(a.output / 'summary.json', summary)
        stage_check(a.output, baseline_swap)
        for case in ('076', '003', '084'):
            if time.perf_counter() >= deadline:
                raise TimeoutError('batch_deadline')
            stage_check(a.output, baseline_swap)
            summary['calls']['new_solver_started'] += 1
            summary['in_flight'] = {'case': case, 'phase': 'solver_and_E0',
                                    'E2_api_attempted': None,
                                    'E0_fallback_possible': 1,
                                    'call_count_complete': False}
            holdout.save(a.output / 'summary.json', summary)
            row = holdout.cell(case, 5, identity_doc, identity, e2, monitored, a.output, deadline)
            stage_check(a.output, baseline_swap)
            summary['rows'].append(row)
            calls = row.get('calls', {})
            if type(calls.get('E2_api_attempted')) is int:
                summary['calls']['E2_api_attempted'] += calls['E2_api_attempted']
            else:
                raise ValueError('unknown_E2_call_count')
            summary['calls']['E0_independent_started'] += calls.get('E0_independent_started', 0)
            fallback = calls.get('E0_fallback_possible')
            if type(fallback) is not int:
                raise ValueError('unknown_fallback_count')
            summary['calls']['E0_fallback_possible'] += fallback
            summary['in_flight'] = None
            holdout.save(a.output / 'summary.json', summary)
            if (row.get('status') != 'accepted' or fallback != 0
                    or summary['calls']['E2_api_attempted'] > 12
                    or summary['calls']['E0_independent_started']
                       + summary['calls']['E0_fallback_possible'] > 4):
                raise ValueError('first_failure_unknown_or_fallback:' + case)
            stage_check(a.output, baseline_swap)
        summary['status'] = 'completed'
        summary['call_count_complete'] = True
    except BaseException as error:
        summary.update(status='stopped', error=repr(error))
        raise
    finally:
        summary['finished_at'] = datetime.now(timezone.utc).isoformat()
        summary['wall_seconds'] = time.perf_counter()-started
        holdout.save(a.output / 'summary.json', summary)

if __name__ == '__main__':
    main()
