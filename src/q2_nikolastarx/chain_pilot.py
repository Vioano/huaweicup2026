"""Frozen six-case chain-packet pilot. Preflight is read-only; run needs a committed runner.

No plan is constructed here. One sequential worker per case requests public E2
once, then independently invokes frozen E0 once. Fallback, error, or mismatch
stops the batch without retries. Pilot scores are not a complete algorithm run.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CASES = ('003', '005', '056', '068', '086', '088')
PRE = 'ee4fe0282ca2ff5d73bb23d54b1c213909e1401c'
BASE = '60afc38b327680fbda0ff10182e3e05a01edd72d'
E2 = '603b0741e21c449d3db652ebd67c94f2dc014cc9'
MONITOR = ROOT / 'src/q2_nikolastarx/evaluate_feedback.py'
FIELDS = ('original_graph_copy_bytes', 'scheduled_copy_bytes',
          'added_copy_bytes', 'partition_added_copy_bytes', 'spill_added_copy_bytes')
LIMITS = dict(e2_requests=6, e2_fallback=6, independent_e0=6, retries=0,
              workers=1, case_seconds=120, batch_seconds=600, rss_bytes=4 << 30)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_bytes(commit, path):
    return subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)


def parse(raw, path):
    return json.loads(gzip.decompress(raw) if path.endswith('.gz') else raw)


def pinned(ref):
    raw = git_bytes(ref['commit'], ref['path'])
    if digest(raw) != ref['sha256']:
        raise ValueError('Pinned artifact hash mismatch: ' + ref['path'])
    return parse(raw, ref['path'])


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def preflight(manifest, e2_root, runner_commit=None):
    doc = json.loads(manifest.read_bytes())
    if (doc['cases'] != list(CASES) or doc['limits'] != LIMITS
            or doc['preflight_commit'] != PRE or doc['baseline_commit'] != BASE
            or doc['constructor_commit'] != '47baf7f89948aa0a1ea2038c823e60513c78f160'
            or doc['e2_commit'] != E2):
        raise ValueError('Unexpected identity or batch budget')
    if runner_commit:
        if len(runner_commit) != 40 or any(c not in '0123456789abcdef' for c in runner_commit):
            raise ValueError('Runner requires complete commit SHA')
        for path in (Path(__file__), manifest, MONITOR):
            relative = path.relative_to(ROOT).as_posix()
            if path.read_bytes() != git_bytes(runner_commit, relative):
                raise ValueError('Runner/manifest not frozen: ' + relative)
    constructor = doc['constructor_source']
    if (constructor['commit'] != doc['constructor_commit']
            or digest(git_bytes(constructor['commit'], constructor['path'])) != constructor['sha256']):
        raise ValueError('Constructor source identity mismatch')
    e2_manifest_path = ROOT / doc['e2_manifest']['path']
    raw = e2_manifest_path.read_bytes()
    if digest(raw) != doc['e2_manifest']['sha256']:
        raise ValueError('E2 manifest changed')
    e2doc = json.loads(raw)
    if e2doc['e2_commit'] != E2:
        raise ValueError('Wrong E2 source commit')
    expected = set(e2doc['e2_sources']) | {e2doc['binary']['path']}
    actual = {p.relative_to(e2_root).as_posix() for p in e2_root.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError('Isolated E2 export contains unexpected/missing files')
    for name, sha in e2doc['e2_sources'].items():
        body = (e2_root / name).read_bytes()
        if digest(body) != sha or body != git_bytes(E2, name):
            raise ValueError('E2 source mismatch: ' + name)
    binary = (e2_root / e2doc['binary']['path']).read_bytes()
    if digest(binary) != e2doc['binary']['sha256'] or len(binary) != e2doc['binary']['bytes']:
        raise ValueError('E2 binary mismatch')
    source_raw = (ROOT / 'docs/a/source-manifest.json').read_bytes()
    if digest(source_raw) != doc['source_manifest_sha256']:
        raise ValueError('Official source manifest changed')
    source_manifest = json.loads(source_raw)
    source_files = {row['path']: row for row in source_manifest['files']}
    for relative in doc['official_files']:
        path = ROOT / 'data/raw/a/official' / relative
        row = source_files[relative]
        body = path.read_bytes()
        if digest(body) != row['sha256'] or len(body) != row['bytes']:
            raise ValueError('Official source mismatch: ' + relative)
    config = ROOT / doc['config']['path']
    if digest(config.read_bytes()) != doc['config']['sha256']:
        raise ValueError('Official config mismatch')
    summary = pinned(doc['preflight_summary'])
    baseline_feed = pinned(doc['baseline_feed'])['records']
    if summary['source_commit'] != doc['constructor_commit'] or summary['calls']['E0']:
        raise ValueError('Candidate preflight identity mismatch')
    if len(summary['rows']) != len(CASES) or len(doc['rows']) != len(CASES):
        raise ValueError('Missing candidate preflight rows')
    for i, row in enumerate(doc['rows']):
        case = CASES[i]
        if row['case'] != case or summary['rows'][i]['case'] != case:
            raise ValueError('Unexpected case order')
        graph = ROOT / row['graph']['path']
        body = graph.read_bytes()
        if (digest(body) != row['graph']['sha256']
                or source_files['data/case_'+case+'.json']['sha256'] != row['graph']['sha256']):
            raise ValueError('Graph mismatch: ' + case)
        plan = pinned(row['candidate'])
        if set(plan) != {'node_to_subgraph', 'core_schedules'} or len(plan['core_schedules']) != 5:
            raise ValueError('Invalid candidate plan: ' + case)
        pre_row = summary['rows'][i]
        if (row['candidate']['sha256'] != pre_row['plan']['sha256']
                or pre_row['graph_sha256'] != row['graph']['sha256']):
            raise ValueError('Candidate plan not from fixed constructor: ' + case)
        truth = pinned(row['baseline_truth'])
        old = next((r for r in baseline_feed if r['case_id'] == case and r['cores'] == 5), None)
        if (old is None or old['artifacts']['result'] != {
                'path': row['baseline_truth']['path'],
                'sha256': row['baseline_truth']['sha256']}
                or old['identity']['graph_sha256'] != row['graph']['sha256']
                or old['identity']['config_sha256'] != doc['config']['sha256']
                or old['identity']['official_sha256'] != source_manifest['official_code_hash']
                or old['metrics']['makespan_cycles'] != row['baseline_m']):
            raise ValueError('Baseline feed identity mismatch: ' + case)
        if truth['scene'] != 'B' or truth['num_cores'] != 5 or truth['makespan'] != row['baseline_m']:
            raise ValueError('Baseline truth mismatch: ' + case)
        if set(truth['data_movement_bytes']) != set(FIELDS):
            raise ValueError('Baseline movement fields mismatch')
    return doc


def worker(doc, case_index, e2_root, output):
    output.mkdir(parents=True, exist_ok=False)
    row = doc['rows'][case_index]
    ledger = {'case': row['case'], 'status': 'starting', 'calls': {
        'E2_api': 0, 'native': 0, 'E0_fallback': 0, 'E0_independent': 0},
        'request_in_flight': False, 'scope': 'fixed candidate pilot; not full algorithm score'}
    save(output / 'ledger.json', ledger)
    sys.path.insert(0, str(e2_root))
    from research.a.e2_search import SceneBEvaluator, read_config
    import research.a.e2_search.scene_b as scene_b
    import src.eval_exact._official as e2_official
    if any(not Path(m.__file__).resolve().is_relative_to(e2_root)
           for m in (scene_b, e2_official)):
        raise ValueError('E2 module import escaped isolated export')
    graph = json.loads((ROOT / row['graph']['path']).read_bytes())
    plan = pinned(row['candidate'])
    cfg = read_config(ROOT / doc['config']['path'], problem=2)
    ledger['calls']['E2_api'] = 1
    ledger['request_in_flight'] = True
    ledger['fallback_status'] = 'unknown_while_request_in_flight'
    save(output / 'ledger.json', ledger)
    start_e2 = time.perf_counter()
    record = SceneBEvaluator(graph, problem=2).evaluate_record(plan, full=False, **cfg)
    ledger['e2_wall_seconds'] = time.perf_counter() - start_e2
    ledger['request_in_flight'] = False
    ledger['e2_record'] = record
    ledger['fallback_status'] = record.get('route', 'unknown')
    if record.get('route') == 'e0_fallback':
        ledger['calls']['E0_fallback'] = 1
    if record.get('route') == 'native':
        ledger['calls']['native'] = 1
    if record.get('status') != 'ok' or record.get('route') != 'native' or record.get('problem') != 2:
        ledger['status'] = 'stopped_fallback_or_e2_failure'
        save(output / 'ledger.json', ledger)
        raise RuntimeError('E2 native route unavailable; stop without independent E0')
    save(output / 'ledger.json', ledger)
    # Independent E0 is a separate process with its own official import path.
    plan_path = output / 'candidate_plan.json'
    save(plan_path, plan)
    official_path = ROOT / doc['official_entry']
    argv = [sys.executable, '-B', str(official_path), str(ROOT / row['graph']['path']),
            str(plan_path), '--config', str(ROOT / doc['config']['path']),
            '--output', str(output / 'e0_result.json'),
            '--trace-output', str(output / 'e0_trace.json'),
            '--log-output', str(output / 'e0.log')]
    ledger['calls']['E0_independent'] = 1
    ledger['e0_in_flight'] = True
    save(output / 'ledger.json', ledger)
    started = time.perf_counter()
    with (output / 'e0_stdout.txt').open('w') as out, (output / 'e0_stderr.txt').open('w') as err:
        subprocess.run(argv, cwd=ROOT, stdout=out, stderr=err, check=True)
    ledger['e0_wall_seconds'] = time.perf_counter() - started
    ledger['e0_in_flight'] = False
    truth = json.loads((output / 'e0_result.json').read_bytes())
    same = (record['makespan'] == truth['makespan']
            and record['cross_task_traffic'] == truth['cross_task_traffic']
            and all(record['data_movement_bytes'][k] == truth['data_movement_bytes'][k]
                    for k in FIELDS))
    baseline = pinned(row['baseline_truth'])
    candidate_score = (truth['makespan'], truth['data_movement_bytes']['added_copy_bytes'])
    baseline_score = (baseline['makespan'], baseline['data_movement_bytes']['added_copy_bytes'])
    ledger.update(status='completed' if same else 'stopped_e2_e0_mismatch',
                  e2_e0_equal=same,
                  candidate={'makespan': truth['makespan'],
                             'movement': {k: truth['data_movement_bytes'][k] for k in FIELDS},
                             'cross_task_traffic': truth['cross_task_traffic']},
                  baseline={'makespan': row['baseline_m'],
                            'movement': baseline['data_movement_bytes'],
                            'cross_task_traffic': baseline['cross_task_traffic']},
                  candidate_vs_baseline_m=truth['makespan'] - row['baseline_m'],
                  lexicographic_comparison=('better' if candidate_score < baseline_score else
                                            'equal' if candidate_score == baseline_score else 'worse'))
    save(output / 'ledger.json', ledger)
    if not same:
        raise RuntimeError('E2/E0 mismatch; stop batch')


def run(doc, manifest, e2_root, output, runner_commit, batch_started, preflight_seconds):
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('Pilot requires verified macOS ARM64 E2 binary')
    if output.exists():
        raise ValueError('Output exists; no overwrite/resume/retry')
    from .evaluate_feedback import monitored
    output.mkdir(parents=True, exist_ok=False)
    deadline = batch_started + LIMITS['batch_seconds']
    if time.perf_counter() >= deadline:
        raise TimeoutError('Batch budget exhausted during preflight')
    summary = {'status': 'running', 'runner_commit': runner_commit,
               'manifest_sha256': digest(manifest.read_bytes()), 'cases': [],
               'limits': LIMITS, 'preflight_wall_seconds': preflight_seconds,
               'evaluation_batch_wall_seconds': 0,
               'constructor_wall_seconds': None,
               'scope': 'six fixed chain plans; no complete solver algorithm score'}
    save(output / 'summary.json', summary)
    for i, case in enumerate(CASES):
        case_dir = output / (case + '-k5')
        argv = [sys.executable, '-B', str(Path(__file__).resolve()), 'worker',
                '--manifest', str(manifest), '--e2-root', str(e2_root),
                '--runner-commit', runner_commit, '--case-index', str(i),
                '--output', str(case_dir / 'records')]
        receipt = monitored(argv, case_dir / 'process',
                            min(deadline, time.perf_counter() + LIMITS['case_seconds']),
                            LIMITS['rss_bytes'])
        ledger_path = case_dir / 'records/ledger.json'
        ledger = json.loads(ledger_path.read_bytes()) if ledger_path.exists() else None
        accepted = (receipt['status'] == 'ok' and not receipt.get('surviving_pids')
                    and ledger is not None and ledger['status'] == 'completed')
        summary['cases'].append({'case': case, 'process': receipt,
                                 'ledger': ledger, 'accepted': accepted})
        summary['preflight_plus_evaluation_wall_seconds'] = time.perf_counter() - batch_started
        summary['evaluation_batch_wall_seconds'] = max(
            0, summary['preflight_plus_evaluation_wall_seconds'] - preflight_seconds)
        save(output / 'summary.json', summary)
        if not accepted:
            summary['status'] = 'stopped_first_failure_or_fallback'
            break
    else:
        summary['status'] = 'completed'
    save(output / 'summary.json', summary)
    if summary['status'] != 'completed':
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('preflight', 'run', 'worker'))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--e2-root', type=Path, required=True)
    parser.add_argument('--runner-commit')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--case-index', type=int)
    args = parser.parse_args()
    manifest, e2_root = args.manifest.resolve(), args.e2_root.resolve()
    if args.mode != 'preflight' and not args.runner_commit:
        raise ValueError('Run requires frozen runner commit')
    started = time.perf_counter()
    doc = preflight(manifest, e2_root, args.runner_commit)
    preflight_seconds = time.perf_counter() - started
    if args.mode == 'preflight':
        print(json.dumps({'preflight': 'ok', 'cases': len(CASES), 'calls': 0,
                          'runner_frozen': bool(args.runner_commit)}))
    elif args.mode == 'worker':
        if args.case_index not in range(len(CASES)) or args.output is None or args.output.exists():
            raise ValueError('Worker needs one known case and a fresh output directory')
        worker(doc, args.case_index, e2_root, args.output.resolve())
    else:
        if args.output is None:
            raise ValueError('Run needs a fresh output directory')
        run(doc, manifest, e2_root, args.output.resolve(), args.runner_commit,
            started, preflight_seconds)


if __name__ == '__main__':
    main()
