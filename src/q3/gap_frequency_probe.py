"""Bounded 097/k1 dependency reconstruction against two existing P3 timelines.

This invokes official Task preparation twice (one local Step3 per Task graph).
It does not run a solver or a new multicore E0 evaluation.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from .construct import ROOT
from .feedback_benchmark import digest, git_bytes, read, run_child, utc, verify_source, write
from .memory_dependency_audit import rebuild

CASE = '097'
BAND_COMMIT = 'c4b75e1e7411a78b8611b548a433649f456415ed'
FOREST_COMMIT = 'bff88a66cd76ceb2d75242bf99d34bfe8b1879d4'
BAND_RUN = Path('results/a/q3-nikolastarx/band-lookahead-family-20260925/run.json')
OUTPUT_PARENT = ROOT / 'results/a/q3-nikolastarx'
GRAPH = Path('data/raw/a/official/data/case_097.json')
CONFIG = Path('data/raw/a/official/data/config.txt')
BUDGET = {'task_builds': 2, 'local_step3_simulations': 2, 'new_multicore_e0': 0,
          'solver_calls': 0, 'workers': 1, 'retries': 0,
          'per_build_seconds': 60, 'whole_batch_seconds': 120,
          'sampled_group_rss_tripwire_bytes': 512 * 1024 * 1024}


def frozen_file(root, commit, relative):
    path = root / relative
    raw = git_bytes(root, commit, relative.as_posix())
    if raw != path.read_bytes():
        raise ValueError(f'frozen artifact bytes differ: {relative}')
    return path, hashlib.sha256(raw).hexdigest()


def checked_artifact(root, relative, expected_hash, commit):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != 'results':
        raise ValueError(f'unsafe artifact path: {relative}')
    path, actual = frozen_file(root, commit, relative)
    if actual != expected_hash:
        raise ValueError(f'artifact hash differs: {relative}')
    return path


def evidence(forest_root, hashes, official):
    band_path, band_sha = frozen_file(ROOT, BAND_COMMIT, BAND_RUN)
    band = read(band_path)
    if band['status'] != 'complete':
        raise ValueError('band family run is incomplete')
    if (band['source_commit'] != '7773fed30433f0b1487f34962a4034224d5796cf'
            or band['official_code_sha256'] != official):
        raise ValueError('band producer source or official code identity differs')
    if (band['source_input_sha256'][GRAPH.as_posix()] != hashes[GRAPH.as_posix()]
            or band['source_input_sha256'][CONFIG.as_posix()] != hashes[CONFIG.as_posix()]):
        raise ValueError('band family graph/config identity differs')
    matches = [r for r in band['records'] if r.get('case_id') == CASE and r.get('cores') == 1]
    if len(matches) != 1 or matches[0]['status'] != 'ok':
        raise ValueError('expected one successful 097/k1 band record')
    record = matches[0]
    if record['baseline_artifact_commit'] != FOREST_COMMIT:
        raise ValueError('forest producer commit differs')
    new_plan = checked_artifact(ROOT, record['plan_path'], record['plan_sha256'], BAND_COMMIT)
    new_result = checked_artifact(ROOT, record['result_path'], record['result_sha256'], BAND_COMMIT)
    receipt_rel = Path(record['baseline_receipt'])
    receipt_path, receipt_sha = frozen_file(forest_root, FOREST_COMMIT, receipt_rel)
    receipt = read(receipt_path)
    if (receipt['graph_sha256'] != hashes[GRAPH.as_posix()]
            or receipt['config_sha256'] != hashes[CONFIG.as_posix()]
            or receipt['plan_sha256'] != record['baseline_plan_sha256']
            or receipt['result_sha256'] != record['baseline_result_sha256']):
        raise ValueError('forest graph/config/plan/result identity differs')
    selected = [c for c in receipt['candidates'] if c.get('name') == 'seed']
    if len(selected) != 1 or selected[0]['makespan'] != receipt['makespan']:
        raise ValueError('forest seed is not the selected existing result')
    cell = receipt_rel.parent.parent
    old_plan = checked_artifact(forest_root, cell / 'case_097_multicore_res.json',
                                receipt['plan_sha256'], FOREST_COMMIT)
    old_result = checked_artifact(forest_root, receipt_rel.parent / 'result.json.gz',
                                  receipt['result_sha256'], FOREST_COMMIT)
    for result_path in (old_result, new_result):
        result = read(result_path)
        if result.get('problem') != 3 or result.get('scene') != 'B' or result.get('num_cores') != 1:
            raise ValueError('pinned result must be official P3, scene B, one core')
    if (read(new_result)['makespan'] != record['makespan']
            or read(old_result)['makespan'] != receipt['makespan']
            or receipt['makespan'] != record['baseline_makespan']):
        raise ValueError('existing E0 makespan differs from pinned records')
    source = {'band_artifact_commit': BAND_COMMIT, 'band_run_sha256': band_sha,
              'forest_artifact_commit': FOREST_COMMIT, 'forest_receipt_sha256': receipt_sha,
              'graph_sha256': hashes[GRAPH.as_posix()], 'config_sha256': hashes[CONFIG.as_posix()]}
    jobs = [
        {'name': 'old_forest', 'plan': old_plan, 'result': old_result,
         'plan_sha256': receipt['plan_sha256'], 'result_sha256': receipt['result_sha256'],
         'existing_makespan': receipt['makespan']},
        {'name': 'new_band_lookahead', 'plan': new_plan, 'result': new_result,
         'plan_sha256': record['plan_sha256'], 'result_sha256': record['result_sha256'],
         'existing_makespan': record['makespan']},
    ]
    return source, jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', required=True, help='full frozen probe source commit')
    parser.add_argument('--forest-root', type=Path, required=True)
    parser.add_argument('--worker', nargs=3, metavar=('GRAPH', 'PLAN', 'RESULT'),
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        rebuild(*(Path(p) for p in args.worker), args.output, expected_cores=1)
        return
    if not re.fullmatch(r'[0-9a-f]{40}', args.source):
        parser.error('--source requires a full 40-character SHA')
    start = time.monotonic()
    official, hashes = verify_source(args.source, {CASE})
    forest_root = args.forest_root.resolve(strict=True)
    source, jobs = evidence(forest_root, hashes, official)
    output = args.output.resolve()
    if output.parent != OUTPUT_PARENT.resolve() or output.exists():
        raise ValueError('output must be a new direct child of results/a/q3-nikolastarx')
    output.mkdir(parents=False, exist_ok=False)
    state = {'status': 'running', 'scope': 'dependency reconstruction against existing E0 timelines; no new score',
             'source_commit': args.source, 'official_code_sha256': official,
             'source_input_sha256': hashes, 'existing_evidence': source,
             'budget': BUDGET, 'started_at': utc(), 'task_builds_reserved': 0,
             'local_step3_reserved': 0, 'jobs': []}

    def save():
        state['elapsed_seconds'] = time.monotonic() - start
        write(output / 'run.json', state)

    save()
    try:
        for job in jobs:
            remaining = BUDGET['whole_batch_seconds'] - (time.monotonic() - start)
            if remaining <= 0:
                raise TimeoutError('whole batch deadline reached')
            folder = output / job['name']
            folder.mkdir(exist_ok=False)
            report = folder / 'dependency.json'
            entry = {'name': job['name'], 'status': 'reserved',
                     'plan_sha256': job['plan_sha256'], 'existing_result_sha256': job['result_sha256'],
                     'existing_makespan': job['existing_makespan'], 'local_step3_reserved': 1}
            state['jobs'].append(entry)
            state['task_builds_reserved'] += 1
            state['local_step3_reserved'] += 1
            save()
            invocation = [sys.executable, '-B', '-m', 'src.q3.gap_frequency_probe', str(report),
                          '--source', args.source, '--forest-root', str(forest_root), '--worker',
                          str(ROOT / GRAPH), str(job['plan']), str(job['result'])]
            child = run_child(invocation, min(BUDGET['per_build_seconds'], remaining), folder,
                              memory_limit_bytes=BUDGET['sampled_group_rss_tripwire_bytes'])
            entry['child'] = child
            if child['status'] != 'ok' or not report.is_file():
                raise RuntimeError(f"{job['name']} Task reconstruction failed: {child['reason']}")
            audit = read(report)
            if (audit['task_builds'] != 1 or audit['local_step3_simulations'] != 1
                    or audit['plan_sha256'] != job['plan_sha256']
                    or audit['result_sha256'] != job['result_sha256']
                    or audit['critical_core'] != 0
                    or audit['cores'][0]['core_end'] != job['existing_makespan']):
                raise ValueError(f"{job['name']} rebuilt timeline differs from pinned E0 result")
            entry.update(status='ok', audit_sha256=digest(report))
            save()
        if any(digest(ROOT / path) != sha for path, sha in hashes.items()):
            raise ValueError('frozen source or input changed during reconstruction')
        state['status'] = 'complete'
    except Exception as error:
        state.update(status='stopped_on_failure', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        state['finished_at'] = utc()
        save()
    print(json.dumps({'status': state['status'], 'task_builds': state['task_builds_reserved'],
                      'local_step3_simulations': state['local_step3_reserved'],
                      'new_multicore_e0': 0, 'solver_calls': 0,
                      'elapsed_seconds': state['elapsed_seconds']}))


if __name__ == '__main__':
    main()
