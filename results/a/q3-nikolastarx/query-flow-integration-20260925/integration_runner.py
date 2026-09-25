"""Frozen single-process CLI adapter. Requires a reviewed manifest and approval."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OFFICIAL = ROOT / 'data/raw/a/official/code'
SOURCE = 'c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43'
LIMITS = {'p3': 4, 'p2': 2}

class TerminalEvaluationFailure(BaseException):
    pass

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_manifest(manifest):
    if manifest['source_commit'] != SOURCE or manifest['budget'] != {'p3': 4, 'p2': 2, 'phase_seconds': 90, 'total_seconds': 600, 'retries': 0}:
        raise ValueError('source or budget differs')
    delivery_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    ancestry = subprocess.run(['git', 'merge-base', '--is-ancestor', SOURCE, delivery_head], cwd=ROOT)
    if ancestry.returncode != 0:
        raise ValueError('frozen solver commit is not an ancestor of delivery HEAD')
    solver_diff = subprocess.run(['git', 'diff', '--quiet', SOURCE, '--', 'src/q3'], cwd=ROOT)
    if solver_diff.returncode != 0:
        raise ValueError('src/q3 differs from frozen solver commit')
    if manifest['output'] != str(HERE.relative_to(ROOT) / 'run'):
        raise ValueError('output path differs')
    expected_paths = {'data/raw/a/official/data/case_071.json',
                      'data/raw/a/official/data/config.txt'}
    for folder in ('src/q3', 'data/raw/a/official/code'):
        expected_paths.update(str(path.relative_to(ROOT)) for path in (ROOT / folder).rglob('*')
                              if path.is_file() and not path.name.startswith('._')
                              and path.name != '.DS_Store' and '__pycache__' not in path.parts)
    if set(manifest['inputs']) != expected_paths:
        raise ValueError('manifest source file set differs')
    for rel, expected in manifest['inputs'].items():
        path = (ROOT / rel).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != expected:
            raise ValueError(f'input differs: {rel}')
    if sha(HERE / 'integration_runner.py') != manifest['runner_sha256']:
        raise ValueError('runner differs')
    if sha(HERE / 'integration_supervisor.py') != manifest['supervisor_sha256']:
        raise ValueError('supervisor differs')
    if sha(HERE / 'resource_supervisor.py') != manifest['identity_guard_sha256']:
        raise ValueError('identity controller differs')
    return delivery_head

def reserve(ledger, phase, path):
    if phase not in LIMITS or sum(x['phase'] == phase for x in ledger) >= LIMITS[phase]:
        raise TerminalEvaluationFailure(f'{phase} budget exceeded')
    entry = {'ordinal': len(ledger), 'phase': phase, 'status': 'started', 'utc': time.time()}
    ledger.append(entry)
    path.write_text(json.dumps(ledger, indent=2) + '\n')
    return entry

def wrap_official(function, phase, ledger, path):
    def guarded(*args, **kwargs):
        entry = reserve(ledger, phase, path)  # Durable before official dispatch.
        prior = signal.getsignal(signal.SIGALRM)
        def expired(_signum, _frame):
            raise TerminalEvaluationFailure(f'{phase} exceeded 90 seconds')
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, 90)
        try:
            result = function(*args, **kwargs)
        except BaseException as error:
            entry.update(status='failed', error_type=type(error).__name__, reason=str(error))
            path.write_text(json.dumps(ledger, indent=2) + '\n')
            raise TerminalEvaluationFailure(f'{phase} official call failed: {type(error).__name__}') from error
        else:
            entry['status'] = 'complete'
            path.write_text(json.dumps(ledger, indent=2) + '\n')
            return result
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, prior)
    return guarded

def main():
    started = time.monotonic()  # Includes manifest verification, graph read, construction, E0, and publication.
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    delivery_head = verify_manifest(manifest)
    if manifest.get('execution_authorized') is not True or not manifest.get('authorization_ref'):
        raise PermissionError('integration window has no approval')
    run = (ROOT / manifest['output']).resolve()
    if not run.is_relative_to(ROOT) or run.exists():
        raise ValueError('output must be a new path within repository')
    run.mkdir(parents=True, exist_ok=False)
    ledger_path = run / 'outer_e0_ledger.json'
    ledger = []
    receipt = {'status': 'running', 'frozen_solver_commit': SOURCE,
               'delivery_head': delivery_head,
               'frozen_solver_sha256': manifest['inputs']['src/q3/query_flow_solve.py'],
               'budget': LIMITS}
    try:
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(OFFICIAL))
        import multicore_cut_evaluate_problem_2 as p2
        import multicore_cut_evaluate_problem_3 as p3
        p2.evaluate_scene_b = wrap_official(p2.evaluate_scene_b, 'p2', ledger, ledger_path)
        p3.evaluate_problem_3 = wrap_official(p3.evaluate_problem_3, 'p3', ledger, ledger_path)
        graph = ROOT / 'data/raw/a/official/data/case_071.json'
        argv = [str(ROOT / 'src/q3/query_flow_solve.py'), str(graph), '--cores', '5',
                '-o', str(run / 'plan.json'), '--evidence', str(run / 'evidence')]
        if argv != manifest['solve_argv']:
            raise ValueError('solve command differs')
        sys.argv = argv
        runpy.run_module('src.q3.query_flow_solve', run_name='__main__')
        receipt['status'] = 'complete'
    except BaseException as error:
        receipt.update(status='failed', error_type=type(error).__name__, reason=str(error))
        raise
    finally:
        receipt.update(outer_wall_seconds=time.monotonic() - started,
                       e0_calls=len(ledger), ledger='outer_e0_ledger.json',
                       timing_note='Process wall from runner entry; OS cold cache not established')
        (run / 'outer_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

if __name__ == '__main__':
    main()
