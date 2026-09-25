"""Single cold 044/K5 job-major candidate and official P2 E0; remote only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
RAW = ROOT / 'data/raw/a/official/data'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def preflight():
    manifest = json.loads((ROOT / 'capsule-manifest.json').read_bytes())
    if (manifest['case'], manifest['cores'], manifest['strategy']) != (
            '044', 5, 'shared_stationary_pipeline'):
        raise ValueError('wrong case/cores')
    for rel, expected in manifest['files'].items():
        path = (ROOT / rel).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or sha(path) != expected:
            raise ValueError('capsule identity mismatch: ' + rel)
    return manifest


def construct(folder):
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    from src.q2_nikolastarx.shared_stationary_pipeline import build
    graph = json.loads((RAW / 'case_044.json').read_bytes())
    config = {**read_evaluation_config(RAW / 'config.txt'),
              **read_scene_b_config(RAW / 'config.txt')}
    started = time.perf_counter()
    plan, detail = build(graph, 5, config)
    save(folder / 'plan.json', plan)
    save(folder / 'detail.json', detail)
    save(folder / 'construct-receipt.json', {
        'construct_seconds': time.perf_counter() - started,
        'plan_sha256': sha(folder / 'plan.json'),
        'detail_sha256': sha(folder / 'detail.json'),
        'graph_sha256': sha(RAW / 'case_044.json'),
        'config_sha256': sha(RAW / 'config.txt')})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--construct-only', action='store_true')
    args = ap.parse_args()
    manifest = preflight()  # Every file before either construction or E0.
    if args.construct_only:
        args.output.mkdir(parents=True, exist_ok=True)
        construct(args.output)
        return
    output = args.output.resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        raise ValueError('output must be outside the capsule')
    output.mkdir(parents=True, exist_ok=False)
    from src.q2_nikolastarx.evaluate_feedback import monitored
    start = time.perf_counter()
    deadline = start + 120
    receipt = {'status': 'running', 'case': '044', 'cores': 5,
               'manifest_sha256': sha(ROOT / 'capsule-manifest.json'),
               'source_commit': manifest['solver_source_commit'],
               'python': sys.version, 'platform': platform.platform(),
               'cpu_count': os.cpu_count(),
               'limits': {'workers': 1, 'construct_seconds': 30, 'E0_seconds': 60,
                          'total_seconds': 120, 'rss_bytes': 2 << 30, 'retries': 0},
               'calls': {'construct': 0, 'E0': 0, 'E1': 0, 'E2': 0}}
    save(output / 'receipt.json', receipt)
    try:
        receipt['calls']['construct'] = 1
        save(output / 'receipt.json', receipt)
        proc = monitored([sys.executable, '-B', str(HERE / 'runner.py'),
                          '--construct-only', '--output', str(output)],
                         output / 'construct-process', min(deadline, time.perf_counter() + 30), 2 << 30)
        receipt['construct_process'] = proc
        save(output / 'receipt.json', receipt)
        if proc['status'] != 'ok' or proc['surviving_pids']:
            raise RuntimeError('construction stopped; no retry')
        e0 = [sys.executable, '-B', str(ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
              str(RAW / 'case_044.json'), str(output / 'plan.json'),
              '--config', str(RAW / 'config.txt'), '--output', str(output / 'result.json'),
              '--trace-output', str(output / 'trace.json'), '--log-output', str(output / 'official.log')]
        receipt['calls']['E0'] = 1
        save(output / 'receipt.json', receipt)
        proc = monitored(e0, output / 'e0-process', min(deadline, time.perf_counter() + 60), 2 << 30)
        receipt['e0_process'] = proc
        save(output / 'receipt.json', receipt)
        if proc['status'] != 'ok' or proc['surviving_pids']:
            raise RuntimeError('E0 stopped; no retry')
        result = json.loads((output / 'result.json').read_bytes())
        if result['scene'] != 'B' or result['num_cores'] != 5 or type(result['makespan']) is not int:
            raise ValueError('unexpected official result')
        receipt['official'] = {'makespan': result['makespan'],
                               'data_movement_bytes': result['data_movement_bytes'],
                               'result_sha256': sha(output / 'result.json'),
                               'plan_sha256': sha(output / 'plan.json'),
                               'old_makespan': manifest['old_official']['makespan']}
        receipt['status'] = 'completed'
    except BaseException as error:
        receipt.update(status='stopped', error=repr(error))
        raise
    finally:
        receipt['total_seconds'] = time.perf_counter() - start
        save(output / 'receipt.json', receipt)


if __name__ == '__main__':
    main()
