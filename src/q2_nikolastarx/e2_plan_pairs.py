"""Bounded E2 integration check against immutable existing E0 plan results.

This is evaluator-domain validation, not a solver/algorithm performance batch.
No plan construction or new truth E0 is requested. Public E2 fallback can call
E0 once per request; those calls are explicitly reserved and counted.
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
E2_COMMIT = '603b0741e21c449d3db652ebd67c94f2dc014cc9'
MONITOR = 'src/q2_nikolastarx/evaluate_feedback.py'


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git_bytes(commit, path):
    return subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)


def pinned(ref):
    raw = git_bytes(ref['commit'], ref['path'])
    if sha(raw) != ref['sha256']:
        raise ValueError('Git artifact SHA mismatch: ' + ref['path'])
    return json.loads(gzip.decompress(raw) if ref['path'].endswith('.gz') else raw)


def prepare(manifest, e2_root, binary_source):
    """Export only pinned sources and a separately verified local ARM64 binary.

    No import, compilation, evaluator call, or change to the owner's copy.
    Existing destinations are refused so preparation cannot overwrite a run.
    """
    doc = read(manifest)
    if doc['e2_commit'] != E2_COMMIT or e2_root.exists():
        raise ValueError('Expected pinned E2 and a new export directory')
    binary = binary_source.read_bytes()
    if sha(binary) != doc['binary']['sha256'] or len(binary) != doc['binary']['bytes']:
        raise ValueError('Native binary differs from pinned build evidence')
    sources = {}
    for name, digest in doc['e2_sources'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe source path')
        raw = git_bytes(E2_COMMIT, name)
        if sha(raw) != digest:
            raise ValueError('Source differs from manifest: ' + name)
        sources[name] = raw
    sources[doc['binary']['path']] = binary
    e2_root.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        target = e2_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return dict(exported_files=len(sources), total_bytes=sum(map(len, sources.values())),
                evaluation_calls=0)


def check(manifest, e2_root, runner_commit):
    doc = read(manifest)
    if doc['e2_commit'] != E2_COMMIT or len(doc['pairs']) != 3:
        raise ValueError('Unexpected E2 pin or batch allocation')
    if doc['limits'] != dict(api_requests=6, fallback_E0=6, workers=1,
                              pair_wall_seconds=120, batch_wall_seconds=300,
                              rss_bytes=4 << 30, retries=0):
        raise ValueError('Unexpected evaluation budget')
    if runner_commit:
        if len(runner_commit) != 40 or any(c not in '0123456789abcdef' for c in runner_commit):
            raise ValueError('Runner commit must be a full lowercase SHA')
        for path in (Path(__file__), manifest, ROOT / MONITOR):
            if path.read_bytes() != git_bytes(runner_commit, path.relative_to(ROOT).as_posix()):
                raise ValueError('Unfrozen probe/manifest/monitor')
    expected_files = set(doc['e2_sources']) | {doc['binary']['path']}
    actual_files = {path.relative_to(e2_root).as_posix()
                    for path in e2_root.rglob('*') if path.is_file()}
    if actual_files != expected_files:
        raise ValueError('Unexpected or missing files in isolated evaluator export')
    for name, digest in doc['e2_sources'].items():
        raw = (e2_root / name).read_bytes()
        if sha(raw) != digest or raw != git_bytes(E2_COMMIT, name):
            raise ValueError('E2 source drift: ' + name)
    binary = e2_root / doc['binary']['path']
    if sha(binary.read_bytes()) != doc['binary']['sha256']:
        raise ValueError('Native binary differs from verified build evidence')
    config_raw = (ROOT / doc['config']['path']).read_bytes()
    if sha(config_raw) != doc['config']['sha256']:
        raise ValueError('Config drift')
    for pair in doc['pairs']:
        raw = (ROOT / pair['graph']['path']).read_bytes()
        if sha(raw) != pair['graph']['sha256']:
            raise ValueError('Graph drift')
        if len(pair['plans']) != 2:
            raise ValueError('Only two plans per graph')
        for plan in pair['plans']:
            submitted, truth = pinned(plan['plan']), pinned(plan['truth'])
            if set(submitted) != {'node_to_subgraph', 'core_schedules'}:
                raise ValueError('Invalid plan keys')
            if truth['scene'] != 'B' or truth['num_cores'] != pair['cores']:
                raise ValueError('Wrong official truth identity')
            if len(submitted['core_schedules']) != pair['cores']:
                raise ValueError('Wrong plan core budget')
    return doc


def worker(args, doc):
    """Fresh subprocess; E2 snapshot is read-only and local imports are audited."""
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    pair = doc['pairs'][args.pair]
    ledger = dict(status='starting', calls=dict(E2_api=0, native=0, E0_fallback=0),
                  request_in_flight=False, records=[])
    save(output/'ledger.json', ledger)
    # The foreign evaluator package must resolve entirely from its fixed root.
    sys.path.insert(0, str(args.e2_root))
    from research.a.e2_search import SceneBEvaluator, read_config
    import research.a.e2_search.scene_b as scene_b
    import src.eval_exact._official as official
    for module in (scene_b, official):
        if not Path(module.__file__).resolve().is_relative_to(args.e2_root):
            raise ValueError('Evaluator import resolved outside pinned root')
    cfg = read_config(ROOT/doc['config']['path'], problem=2)
    graph = read(ROOT/pair['graph']['path'])
    evaluator = SceneBEvaluator(graph, problem=2)
    for item in pair['plans']:
        plan, truth = pinned(item['plan']), pinned(item['truth'])
        ledger['calls']['E2_api'] += 1
        ledger['request_in_flight'] = True
        # A killed request may already have entered E0: never report it as zero.
        save(output/'ledger.json', ledger)
        record = evaluator.evaluate_record(plan, full=False, **cfg)
        ledger['request_in_flight'] = False
        route = record.get('route')
        if route == 'native':
            ledger['calls']['native'] += 1
        elif route == 'e0_fallback':
            ledger['calls']['E0_fallback'] += 1
        else:
            raise ValueError('Unexpected route: ' + str(route))
        fields = ('makespan', 'data_movement_bytes', 'cross_task_traffic')
        equal = record.get('status') == 'ok' and all(record.get(k) == truth[k] for k in fields)
        native_match = equal and route == 'native' and record.get('problem') == 2
        ledger['records'].append(dict(label=item['label'], native_match=native_match,
                                      official_fields_equal=equal, record=record))
        ledger['status'] = 'running' if native_match else 'stopped_mismatch_or_fallback'
        save(output/'ledger.json', ledger)
        if not native_match:
            raise RuntimeError('E2 native domain check failed; no retry')
    def key(row):
        return (row['makespan'], row['data_movement_bytes']['added_copy_bytes'])
    observed = [key(r['record']) for r in ledger['records']]
    expected = [key(pinned(i['truth'])) for i in pair['plans']]
    ledger.update(status='completed', pair_order_equal=(observed[0] <= observed[1]) == (expected[0] <= expected[1]))
    save(output/'ledger.json', ledger)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare', 'preflight', 'run', 'worker'))
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--e2-root', type=Path, required=True)
    p.add_argument('--runner-commit')
    p.add_argument('--output', type=Path)
    p.add_argument('--pair', type=int)
    p.add_argument('--binary-source', type=Path)
    args = p.parse_args()
    args.manifest = args.manifest.resolve()
    args.e2_root = args.e2_root.resolve()
    if args.mode == 'prepare':
        if args.binary_source is None:
            raise ValueError('An explicitly supplied verified binary is required')
        print(json.dumps(prepare(args.manifest, args.e2_root, args.binary_source)))
        return
    if args.mode != 'preflight' and not args.runner_commit:
        raise ValueError('Frozen runner required for evaluation')
    doc = check(args.manifest, args.e2_root, args.runner_commit)
    if args.mode == 'preflight':
        print(json.dumps(dict(preflight='ok', pairs=3, evaluation_calls=0,
                              runner_frozen=bool(args.runner_commit))))
        return
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('This manifest pins a macOS ARM64 native library')
    if args.output is None or args.output.exists():
        raise ValueError('A new output directory is required; no resume/retry')
    if args.mode == 'worker':
        if args.pair not in range(3):
            raise ValueError('Unknown pair')
        worker(args, doc)
        return
    sys.path.insert(0, str(ROOT))
    from src.q2_nikolastarx.evaluate_feedback import monitored
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    deadline = start + doc['limits']['batch_wall_seconds']
    summary = dict(status='running', e2_commit=E2_COMMIT,
                   runner_commit=args.runner_commit, pairs=[],
                   manifest_sha256=sha(args.manifest.read_bytes()),
                   runtime=dict(python=sys.version, executable=sys.executable,
                                platform=platform.platform(), machine=platform.machine()),
                   scope='E2 validation on frozen plans; no solver quality or throughput claim')
    save(output/'summary.json', summary)
    for i, pair in enumerate(doc['pairs']):
        pair_dir = output / pair['name']
        argv = [sys.executable, '-B', str(Path(__file__).resolve()), 'worker',
                '--manifest', str(args.manifest), '--e2-root', str(args.e2_root),
                '--runner-commit', args.runner_commit, '--pair', str(i),
                '--output', str(pair_dir/'records')]
        receipt = monitored(argv, pair_dir/'process', min(deadline, time.perf_counter()+120), 4 << 30)
        ledger_path = pair_dir/'records/ledger.json'
        ledger = read(ledger_path) if ledger_path.exists() else None
        ok = (receipt['status'] == 'ok' and not receipt.get('surviving_pids')
              and ledger is not None and ledger['status'] == 'completed')
        summary['pairs'].append(dict(name=pair['name'], process=receipt, ledger=ledger, accepted=ok))
        summary['wall_seconds'] = time.perf_counter()-start
        save(output/'summary.json', summary)
        if not ok:
            summary['status'] = 'stopped_first_failure'
            break
    else:
        summary['status'] = 'completed'
    save(output/'summary.json', summary)
    print(json.dumps(dict(status=summary['status'], completed_pairs=len(summary['pairs']))))
    if summary['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
