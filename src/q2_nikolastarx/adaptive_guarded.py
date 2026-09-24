"""P2 structural solver with at most two guarded native E2 scoring requests.

Run as ``python -m src.q2_nikolastarx.adaptive_guarded`` from this repository.
The E2 process is isolated so its ``src.eval_exact`` cannot alias our ``src``.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import time

from . import adaptive_semantic, guarded_component
from .baseline import ROOT
from .direct import derive_multicore_plan
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config

E2_COMMIT = '603b0741e21c449d3db652ebd67c94f2dc014cc9'
E2_BINARY_SHA256 = '0f765b7b1229ea221881ff8e017ba7d37b64461eded6afb7f48e9cf61bfd4e94'
MANIFEST = ROOT / 'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json'


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def check_e2_source(e2_root):
    """Check the copied E2 source and native library against the pinned manifest."""
    doc = json.loads(MANIFEST.read_text())
    if doc['e2_commit'] != E2_COMMIT:
        raise ValueError('E2 manifest commit mismatch')
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('verified native binary is for macOS arm64 only')
    e2_root = Path(e2_root).resolve(strict=True)
    approved = set(doc['e2_sources']) | {doc['binary']['path']}
    actual = {path.relative_to(e2_root).as_posix()
              for path in e2_root.rglob('*') if path.is_file()}
    if actual != approved:
        raise ValueError('unexpected or missing files in isolated E2 export')
    # One Git process keeps source verification affordable in an online solver.
    # Read tar members in memory, never extract paths into the worktree.
    archive = subprocess.check_output(
        ['git', 'archive', E2_COMMIT, '--', *doc['e2_sources']], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as frozen:
        for name, digest in doc['e2_sources'].items():
            raw = (e2_root / name).read_bytes()
            member = frozen.extractfile(name)
            if member is None or _sha(raw) != digest or raw != member.read():
                raise ValueError('E2 source drift: ' + name)
    binary = doc['binary']
    if binary['sha256'] != E2_BINARY_SHA256 or _sha((e2_root / binary['path']).read_bytes()) != E2_BINARY_SHA256:
        raise ValueError('E2 native binary drift')
    return {'commit': E2_COMMIT, 'manifest_sha256': _sha(MANIFEST.read_bytes()),
            'native_binary_sha256': binary['sha256'], 'root': str(e2_root)}


_E2_WORKER = '''import json, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from research.a.e2_search import SceneBEvaluator, read_config
import research.a.e2_search.scene_b as scene_b
import src.eval_exact._official as official
for module in (scene_b, official):
    if not pathlib.Path(module.__file__).resolve().is_relative_to(root):
        raise RuntimeError("foreign evaluator import")
payload = json.load(sys.stdin)
cfg = read_config(payload["config"], problem=2)
record = SceneBEvaluator(payload["graph"], problem=2).evaluate_record(
    payload["plan"], full=False, **cfg)
print(json.dumps(record, allow_nan=False))
'''


def native_e2(e2_root, graph, config_path, plan, timeout):
    """A fresh foreign process for one public E2 API request."""
    payload = {'graph': graph, 'config': str(config_path), 'plan': plan}
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if timeout <= 0:
        raise TimeoutError('no solver wall time remains before E2 request')
    completed = subprocess.run(
        [sys.executable, '-B', '-c', _E2_WORKER, str(e2_root)],
        input=json.dumps(payload, allow_nan=False), text=True, capture_output=True,
        cwd=e2_root, env=env, timeout=timeout, check=True)
    return json.loads(completed.stdout)


def score_adapter(evaluator, ledger, ledger_path, *, prepare=None, remaining_wall=None):
    """Reserve and persist a request before crossing the evaluator boundary."""
    def oracle(plan):
        calls = ledger['calls']
        if ledger['request_in_flight']:
            raise RuntimeError('uncertain E2 request blocks further scoring')
        if calls['E2_api_attempted'] >= 2:
            raise RuntimeError('two-request E2 cap reached')
        if prepare is not None:
            prepare()
        if remaining_wall is not None and remaining_wall() <= 0:
            raise TimeoutError('no solver wall time remains before E2 request')
        attempt = {'plan_sha256': _sha(json.dumps(plan, sort_keys=True, allow_nan=False).encode()),
                   'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'in_flight'}
        attempt_start = time.perf_counter()
        ledger.setdefault('attempts', []).append(attempt)
        calls['E2_api_attempted'] += 1
        calls['E2'] = calls['E2_api_attempted']
        ledger['request_in_flight'] = True
        ledger['possible_E0_fallback_calls'] = calls['E0_fallback'] + 1
        calls['E0'] = ledger['possible_E0_fallback_calls']
        _save(ledger_path, ledger)
        try:
            record = evaluator(plan)
        except Exception as error:
            attempt.update(status='uncertain_exception', error=repr(error),
                           wall_seconds=time.perf_counter()-attempt_start)
            _save(ledger_path, ledger)
            raise
        attempt.update(record=record, wall_seconds=time.perf_counter()-attempt_start)
        route = record.get('route') if isinstance(record, dict) else None
        if route == 'e0_fallback':
            calls['E0_fallback'] += 1
        elif route == 'native':
            calls['native_returns'] += 1
        else:
            attempt['status'] = 'uncertain_route'
            _save(ledger_path, ledger)
            raise ValueError('unknown E2 route; request outcome uncertain')
        attempt['status'] = route
        ledger['request_in_flight'] = False
        ledger['possible_E0_fallback_calls'] = calls['E0_fallback']
        calls['E0'] = calls['E0_fallback']
        _save(ledger_path, ledger)
        if route != 'native' or record.get('status') != 'ok' or record.get('problem') != 2:
            raise ValueError('native P2 E2 score unavailable')
        movement = record.get('data_movement_bytes')
        added = movement.get('added_copy_bytes') if isinstance(movement, dict) else None
        return {'status': 'ok', 'makespan': record.get('makespan'),
                'added_copy_bytes': added}
    return oracle


def build_guarded(graph, cores, config, oracle):
    return adaptive_semantic.build(
        graph, cores, config,
        component_builder=guarded_component.make_component_builder(oracle))


def main(argv=None, *, constructor=build_guarded):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--config', type=Path, default=ROOT/'data/raw/a/official/data/config.txt')
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--e2-root', type=Path, required=True)
    parser.add_argument('--wall', type=float, default=240)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    args.evidence.mkdir(parents=True, exist_ok=False)
    ledger_path = args.evidence/'solver.json'
    ledger = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
              'calls': {'E0': 0, 'E1': 0, 'E2': 0, 'E2_api_attempted': 0,
                        'native_returns': 0, 'E0_fallback': 0},
              'attempts': [], 'source_checked': False,
              'possible_E0_fallback_calls': 0, 'request_in_flight': False,
              'runtime': {'python': sys.version.split()[0], 'platform': platform.platform()},
              'validation_scope': 'official structural check; no final E0/P2 feasibility certificate'}
    _save(ledger_path, ledger)
    try:
        if not math.isfinite(args.wall) or args.wall <= 0:
            raise ValueError('wall must be finite and positive')
        graph_raw, config_raw = args.graph.read_bytes(), args.config.read_bytes()
        graph = json.loads(graph_raw)
        config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
        ledger.update(graph_sha256=_sha(graph_raw), config_sha256=_sha(config_raw),
                      cores=args.cores,
                      solver_checkout_commit=subprocess.check_output(
                          ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                      solver_source_sha256={path.name: _sha(path.read_bytes())
                          for path in sorted(Path(__file__).parent.glob('*.py'))})
        _save(ledger_path, ledger)
        source = None
        def remaining():
            return args.wall - (time.perf_counter()-started)
        def prepare():
            nonlocal source
            if source is not None:
                return
            if remaining() <= 0:
                raise TimeoutError('no wall time remains for E2 source check')
            prepared_at = time.perf_counter()
            try:
                source = check_e2_source(args.e2_root)
            finally:
                ledger['source_check_wall_seconds'] = time.perf_counter()-prepared_at
                _save(ledger_path, ledger)
            ledger.update(source=source, source_checked=True)
            _save(ledger_path, ledger)
        def evaluate(plan):
            return native_e2(source['root'], graph, args.config.resolve(), plan,
                             remaining())
        plan, detail = constructor(graph, args.cores, config,
                                   score_adapter(evaluate, ledger, ledger_path,
                                                 prepare=prepare, remaining_wall=remaining))
        if set(plan) != {'node_to_subgraph', 'core_schedules'}:
            raise ValueError('plan must have exactly the two submission keys')
        if len(plan['core_schedules']) != args.cores:
            raise ValueError('core schedule count mismatch')
        derive_multicore_plan(graph, plan)
        raw = (json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode()
        if time.perf_counter()-started > args.wall:
            raise TimeoutError('solver wall limit exceeded')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(raw)
        ledger.update(status='ok', detail=detail, plan_sha256=_sha(raw),
                      stop_reason='single_structural_route_completed')
    except Exception as error:
        ledger.update(status='failed', error=repr(error))
    finally:
        ledger.update(finished_at=datetime.now(timezone.utc).isoformat(),
                      internal_wall_seconds=time.perf_counter()-started)
        _save(ledger_path, ledger)
    print(json.dumps({'status': ledger['status'], 'calls': ledger['calls'],
                      'internal_wall_seconds': ledger['internal_wall_seconds']}))
    if ledger['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
