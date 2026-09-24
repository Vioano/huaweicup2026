"""Archive accepted gap-full500 cells as immutable board-submission-v1 shards.

This module only reads a completed prefix and never imports a solver or evaluator.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPO = 'huaweibei123/huaweicup2026'
SOLVER = '923b25ecb0b9d6d0e2d3f149fccef431b5403f99'
BASE = '60afc38b327680fbda0ff10182e3e05a01edd72d'
E2 = '603b0741e21c449d3db652ebd67c94f2dc014cc9'
OFFICIAL = '2794ceba93acc1f7fc119154f61082511843d4b3'
FANG = '71616ac7c4c7fca56e37e2d3245dd13725316d82'
P3_CALENDAR = 'a37eb931a22fb7df7e0d00d193538ce5289ae045'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def jbytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def read(path):
    return json.loads(path.read_bytes())


def source(commit, path, entrypoint):
    return {'repo': REPO, 'commit': commit, 'path': path, 'entrypoint': entrypoint}


def frozen_feed(manifest):
    ref = manifest['baseline_feed']
    if ref['commit'] != BASE:
        raise ValueError('Unexpected baseline commit')
    raw = subprocess.check_output(['git', 'show', ref['commit'] + ':' + ref['path']], cwd=ROOT)
    if sha(raw) != ref['sha256']:
        raise ValueError('Baseline feed drift')
    records = json.loads(raw)['records']
    table = {(r['case_id'], r['cores']): r for r in records}
    if len(records) != 500 or len(table) != 500:
        raise ValueError('Baseline feed not unique full500')
    return table


def accepted_prefix(summary, manifest):
    rows = summary['rows']
    prefix = []
    for position, row in enumerate(rows):
        if row.get('status') != 'accepted':
            break
        expected = manifest['rows'][position]
        if (row['case'], row['cores']) != (expected['case'], expected['cores']):
            raise ValueError('Accepted prefix coordinate mismatch')
        prefix.append(row)
    if any(row.get('status') == 'accepted' for row in rows[len(prefix):]):
        raise ValueError('Noncontiguous accepted prefix')
    if len(prefix) > 500:
        raise ValueError('Too many accepted cells')
    return prefix


def archive_file(src, dest, *, pack=False):
    raw = src.read_bytes()
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError('Raw artifact exceeds 64 MiB: ' + str(src))
    data = gzip.compress(raw, mtime=0) if pack else raw
    if len(data) > 64 * 1024 * 1024:
        raise ValueError('Artifact exceeds 64 MiB: ' + str(src))
    if dest.exists():
        if dest.read_bytes() != data:
            raise ValueError('Immutable artifact differs: ' + str(dest))
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write(data)
    return {'path': dest.relative_to(ROOT).as_posix(), 'sha256': sha(data)}


def archive_bytes(data, dest):
    if dest.exists():
        if dest.read_bytes() != data:
            raise ValueError('Immutable receipt differs: ' + str(dest))
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write(data)
    return {'path': dest.relative_to(ROOT).as_posix(), 'sha256': sha(data)}


def export(summary_path, manifest_path, output_root, run_id, shard, producer_session,
           task_url, runtime_id, source_reference, final=False,
           range_start=None, range_end=None):
    from src.benchmark_board.protocol import validate_feed
    summary_raw = summary_path.read_bytes()  # Exactly one snapshot, including a moving run.
    summary = json.loads(summary_raw)
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    if (summary['solver_commit'] != SOLVER or manifest['solver_commit'] != SOLVER
            or manifest['baseline_commit'] != BASE or manifest['e2_commit'] != E2
            or summary['manifest_sha256'] != sha(manifest_raw)
            or len(manifest['rows']) != 500):
        raise ValueError('Source or manifest mismatch')
    if not run_id or len(run_id) > 150 or not run_id.isascii() or not all(c.isalnum() or c in '-_' for c in run_id):
        raise ValueError('run_id must be a short unique ASCII identifier')
    if (not source_reference or len(source_reference) > 300 or source_reference.startswith('/')
            or '..' in Path(source_reference).parts or '\\' in source_reference):
        raise ValueError('Provide a non-absolute source summary reference')
    prefix = accepted_prefix(summary, manifest)
    terminated = summary['status'] != 'running'
    if range_start is None and range_end is None:
        if shard is None or shard < 0 or shard > 9:
            raise ValueError('Legacy shard must be 0..9')
        start = shard * 50
        end = min(start + 50, len(prefix))
        if end <= start or (end - start < 50 and not (final and terminated)):
            raise ValueError('Shard incomplete; partial shard requires explicit final terminated run')
    else:
        if (shard is not None or type(range_start) is not int or type(range_end) is not int
                or not 1 <= range_start <= range_end <= 500 or range_end-range_start+1 > 50
                or len(prefix) < range_end):
            raise ValueError('Range must be 1-based, accepted, at most 50, and exclusive of --shard')
        start, end = range_start-1, range_end
    if final and not terminated:
        raise ValueError('Cannot final-export a running batch')
    if not output_root.is_relative_to(ROOT / 'results/a/q2-nikolastarx'):
        raise ValueError('Output must be in P2 results area')
    if output_root.is_symlink():
        raise ValueError('Output root symlink forbidden')
    for other in output_root.glob('shard-???-???'):
        try:
            lo, hi = (int(x) for x in other.name.split('-')[1:])
        except ValueError:
            raise ValueError('Malformed existing shard: ' + other.name)
        if (lo, hi) != (start+1, end) and lo <= end and start+1 <= hi:
            raise ValueError('Overlapping immutable shard: ' + other.name)
    baselines = frozen_feed(manifest)
    folder = output_root / f'shard-{start+1:03d}-{end:03d}'
    if folder.is_symlink():
        raise ValueError('Shard symlink forbidden')
    records = []
    official = read(ROOT / 'docs/a/source-manifest.json')['official_code_hash']
    for position in range(start, end):
        row = prefix[position]
        spec = manifest['rows'][position]
        case, cores = row['case'], row['cores']
        cell = summary_path.parent / f'{case}-k{cores}'
        archive = folder / f'{case}-k{cores}'
        plan_raw = (cell / 'plan.json').read_bytes()
        result_raw = (cell / 'result.json').read_bytes()
        if sha(plan_raw) != row['solver_ledger']['plan_sha256'] or sha(result_raw) != row['result']['result_sha256']:
            raise ValueError('Raw plan/result hash mismatch')
        result = json.loads(result_raw)
        process = read(cell / 'solver-process/process.json')
        e0_process = read(cell / 'e0-process/process.json')
        ledger = read(cell / 'online/solver.json')
        if (process != row['solver_process'] or e0_process != row['e0_process']
                or ledger != row['solver_ledger'] or row['status'] != 'accepted'
                or process['status'] != 'ok' or e0_process['status'] != 'ok'
                or result['makespan'] != row['result']['makespan']
                or result['num_cores'] != cores or result['scene'] != 'B'
                or any(result['data_movement_bytes'][k] != row['result']['movement'][k]
                       for k in row['result']['movement'])
                or result['cross_task_traffic'] != row['result']['cross_task_traffic']):
            raise ValueError('Accepted row differs from raw evidence')
        base = baselines[(case, cores)]['baseline']
        if (base['route'] != 'E0' or base['graph_sha256'] != spec['graph']['sha256']
                or base['config_sha256'] != manifest['config']['sha256']
                or base['official_sha256'] != official):
            raise ValueError('Single-core denominator identity differs')
        base_path = ROOT / base['result']['path']
        if sha(base_path.read_bytes()) != base['result']['sha256']:
            raise ValueError('Single-core denominator artifact differs')
        evidence = {
            'solver_process': archive_file(cell / 'solver-process/process.json', archive / 'solver-process.json'),
            'e0_process': archive_file(cell / 'e0-process/process.json', archive / 'e0-process.json'),
            'online_ledger': archive_file(cell / 'online/solver.json', archive / 'online-ledger.json'),
        }
        artifacts = {
            'plan': archive_file(cell / 'plan.json', archive / 'plan.json.gz', pack=True),
            'result': archive_file(cell / 'result.json', archive / 'result.json.gz', pack=True),
            'run': archive_bytes(jbytes({'accepted_row': row, 'raw_evidence': evidence}), archive / 'run.json'),
        }
        movement = result['data_movement_bytes']
        p = process
        env = {'os': ledger['runtime'].get('platform'), 'cpu': None, 'gpu': None,
               'ram_bytes': None, 'python': ledger['runtime'].get('python'),
               'dependencies': 'frozen solver and E2 source identities in archived online ledger',
               'threads': None, 'workers': 1,
               'peak_rss_bytes': max(p['observed_peak_rss_bytes'], e0_process['observed_peak_rss_bytes'])}
        provenance = {
            'producer_session': producer_session, 'task_url': task_url,
            'solver': {'source': source(SOLVER, 'src/q2_nikolastarx/adaptive_gap_guarded.py',
                                        'src.q2_nikolastarx.adaptive_gap_guarded.main'),
                       'authors': ['NikolaStarx', 'yuanzhifang30-sudo'],
                       'method': 'Adaptive budget baseline versus join/gap complete-plan candidate; native E2 selects strict Makespan/DDR improvement; independent E0 confirms selected plan.',
                       'references': [f'https://github.com/{REPO}/blob/{FANG}/src/q2/feedback/gap_packet.py',
                                      f'https://github.com/{REPO}/blob/{P3_CALENDAR}/src/q3_yuanzhifang/gap_calendar.py'],
                       'upstream': [source(FANG, 'src/q2/feedback/gap_packet.py', None),
                                    source(P3_CALENDAR, 'src/q3_yuanzhifang/gap_calendar.py', None)],
                       'selected_algorithm_id': None,
                       'selected_solver_commit': None},
            'runner': {'source': source(summary['runner_commit'], 'src/q2_nikolastarx/gap_full500.py',
                                        'src.q2_nikolastarx.gap_full500.main'),
                       'argv': process['argv'], 'working_directory': '.'},
            'environment': env,
            'measurement': {'started_at': p['started_at'], 'finished_at': p['finished_at'],
                            'seed': None, 'repeat_index': 0, 'cold_start': None,
                            'solver_scope': 'Outer child start through exit includes graph read, candidate construction, online native E2, plan/evidence writes and cleanup.',
                            'evaluation_scope': 'Separate independent official E0 child; its wall is not included in solver wall.',
                            'budget': {'wall_seconds': 60, 'candidate_limit': 2,
                                       'stop_reason': 'completed'},
                            'calls': {'solver': 1, 'E0': 1, 'E1': 0,
                                      'E2': ledger['calls']['E2_api_attempted']},
                            'offline_costs': 'none', 'failure': None},
            'missing_reasons': {
                'provenance.environment.cpu': 'Per-run CPU model was not recorded.',
                'provenance.environment.gpu': 'GPU presence was not recorded.',
                'provenance.environment.ram_bytes': 'Physical RAM size was not recorded.',
                'provenance.environment.threads': 'Thread count was not sampled.',
                'provenance.measurement.seed': 'Deterministic construction; no seed.',
                'provenance.measurement.cold_start': 'Fresh child process, but OS cache state not controlled.',
            },
        }
        record = {
            'attempt_id': f'{run_id}-P2-{case}-k{cores}', 'revision': 1,
            'run_id': run_id, 'algorithm_id': 'q2-adaptive-gap-guarded',
            'algorithm_name': 'Adaptive budget with join/gap guarded candidate',
            'variant': 'complete-plan-native-e2-select-independent-e0',
            'solver_commit': SOLVER,
            'parameters': {'global_budget': manifest['limits'], 'candidate_limit': 2,
                           'selection': 'strict_lexicographic_makespan_added_copy_bytes',
                           'retry': False},
            'problem': 'P2', 'case_id': case, 'cores': cores, 'status': 'ok',
            'metrics': {'makespan_cycles': result['makespan'],
                        'solver_wall_seconds': p['wall_seconds'],
                        'evaluation_wall_seconds': e0_process['wall_seconds'],
                        'ddr_bytes': movement['scheduled_copy_bytes'],
                        'extra_ddr_bytes': movement['added_copy_bytes'],
                        'spill_bytes': movement['spill_added_copy_bytes'],
                        'cache_hit_rate': None},
            'evaluator': {'route': 'E0', 'commit': OFFICIAL,
                          'entrypoint': 'multicore_cut_evaluate_problem_2.evaluate_problem_2'},
            'identity': {'graph_sha256': spec['graph']['sha256'],
                         'config_sha256': manifest['config']['sha256'],
                         'official_sha256': official, 'plan_sha256': artifacts['plan']['sha256']},
            'artifacts': artifacts, 'runtime_id': runtime_id,
            'observed_at': e0_process['finished_at'],
            'timing': {'solver_includes_evaluation': False,
                       'evaluation_precision': 'Outer perf_counter child wall; online E2 is included in solver wall.',
                       'utc': 'UTC'},
            'provenance': provenance,
            'notes': ['One cell of a fresh fixed-solver P2 run; full-suite claim requires 500 accepted cells.',
                      'Online E2 is selection evidence; independent E0 is final score.',
                      'Single-core denominator is fixed 60afc38 official E0, not the old solver makespan.'],
            'source_url': task_url, 'baseline': base, 'cache_pair': None,
        }
        records.append(record)
    feed = {'schema_version': 1, 'submission_version': 1, 'records': records}
    validate_feed(feed, submission=True)
    snapshot_path = folder / 'snapshot.json'
    if snapshot_path.exists():
        prior = read(snapshot_path)
        if (prior['shard'] != [start+1, end] or prior['run_id'] != run_id
                or prior['manifest_sha256'] != sha(manifest_raw)
                or prior['accepted_prefix'] < end):
            raise ValueError('Prior immutable snapshot differs')
    else:
        archive_bytes(jbytes({'summary_sha256': sha(summary_raw), 'summary_status': summary['status'],
                              'accepted_prefix': len(prefix), 'shard': [start+1, end],
                              'source_summary_reference': source_reference,
                              'manifest_sha256': sha(manifest_raw), 'run_id': run_id}),
                      snapshot_path)
    feed_path = folder / 'board-feed.json'
    archive_bytes(jbytes(feed), feed_path)
    return {'feed': str(feed_path.relative_to(ROOT)), 'records': len(records),
            'summary_sha256': sha(summary_raw), 'evaluations': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--summary', required=True, type=Path)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--output-root', required=True, type=Path)
    p.add_argument('--run-id', required=True)
    p.add_argument('--shard', type=int, help='legacy 0 for cells 1-50, through 9')
    p.add_argument('--range-start', type=int, help='1-based inclusive start; pair with --range-end')
    p.add_argument('--range-end', type=int, help='1-based inclusive end; at most 50 cells')
    p.add_argument('--producer-session', required=True)
    p.add_argument('--task-url', required=True)
    p.add_argument('--runtime-id', required=True)
    p.add_argument('--source-reference', required=True,
                   help='Portable label for the scoring-run summary; never a local absolute path')
    p.add_argument('--final', action='store_true')
    args = p.parse_args()
    print(json.dumps(export(args.summary.resolve(), args.manifest.resolve(),
                            args.output_root.resolve(), args.run_id, args.shard,
                            args.producer_session, args.task_url, args.runtime_id,
                            args.source_reference, args.final,
                            args.range_start, args.range_end), ensure_ascii=False))


if __name__ == '__main__':
    main()
