"""Prepare one fixed 097/k1 leaf-tile plan, then reserve at most one P3 E0.

Preparation is static. Execution requires a separately admitted resource window;
the receipt records that reference, but does not grant resource authorization.
"""
import argparse
import hashlib
from pathlib import Path
import sys
import time

from .construct import Index, ROOT
from .feedback_benchmark import digest, read, run_child, utc, verify_source, write
from .gap_frequency_probe import CASE, CONFIG, GRAPH, OUTPUT_PARENT, evidence
from .leaf_tile import transform
from .safe_solve import encoded

BUDGET = {'new_p3': 1, 'new_p2': 0, 'solver_calls': 0, 'workers': 1,
          'retries': 0, 'per_call_seconds': 60,
          'sampled_group_rss_tripwire_bytes': 512 * 1024 * 1024}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare', 'run'))
    p.add_argument('output', type=Path)
    p.add_argument('--source', required=True)
    p.add_argument('--forest-root', required=True, type=Path)
    p.add_argument('--manifest-sha256')
    p.add_argument('--admission-reference')
    p.add_argument('--resource-preflight', type=Path)
    a = p.parse_args()
    official, hashes = verify_source(a.source, {CASE})
    source, controls = evidence(a.forest_root.resolve(strict=True), hashes, official)
    out = a.output.resolve()
    if out.parent != OUTPUT_PARENT.resolve():
        raise ValueError('output must be a direct child of the Q3 results directory')
    manifest_path = out / 'manifest.json'
    plan_path = out / 'plan.json'
    if a.mode == 'prepare':
        start = time.perf_counter()
        l1 = [int(line.split()[1]) for line in (ROOT / CONFIG).read_text().splitlines()
              if line.split()[:1] == ['L1']]
        if len(l1) != 1:
            raise ValueError('expected exactly one fixed L1 capacity')
        plan, meta = transform(Index(read(ROOT / GRAPH)), read(controls[0]['plan']), l1[0])
        raw = encoded(plan)
        if hashlib.sha256(raw).hexdigest() in {c['plan_sha256'] for c in controls}:
            raise ValueError('candidate duplicates an existing control')
        out.mkdir(exist_ok=False)
        plan_path.write_bytes(raw)
        state = {'schema': 'q3-leaf-tile-one-shot-v1', 'prepared_at': utc(),
                 'source_commit': a.source, 'source_input_sha256': hashes,
                 'official_code_sha256': official, 'case_id': CASE, 'cores': 1,
                 'budget': BUDGET, 'existing_evidence': source,
                 'controls': [{k: c[k] for k in ('name', 'plan_sha256', 'result_sha256',
                                               'existing_makespan')} for c in controls],
                 'plan_sha256': digest(plan_path), 'metadata': meta,
                 'construct_validate_write_seconds': time.perf_counter() - start,
                 'scope': 'one mechanism candidate, not an online solver or full500 result'}
        write(manifest_path, state)
        print({'prepared': True, 'manifest_sha256': digest(manifest_path),
               'plan_sha256': state['plan_sha256'], 'new_e0': 0})
        return
    if not a.manifest_sha256 or digest(manifest_path) != a.manifest_sha256:
        raise ValueError('prepared manifest must match the independently frozen hash')
    m = read(manifest_path)
    if (m['source_commit'] != a.source or m['source_input_sha256'] != hashes
            or m['official_code_sha256'] != official or m['budget'] != BUDGET
            or m['existing_evidence'] != source or digest(plan_path) != m['plan_sha256']):
        raise ValueError('prepared identity/budget differs')
    if not a.admission_reference or not a.resource_preflight:
        raise ValueError('execution requires the new admission and actual resource observation')
    observation = read(a.resource_preflight)
    # Unique directory prevents a retry from silently making another call.
    job = out / 'evaluation'
    job.mkdir(exist_ok=False)
    result_path = job / 'result.json.gz'
    state = {'status': 'reserved', 'started_at': utc(), 'source_commit': a.source,
             'manifest_sha256': a.manifest_sha256, 'plan_sha256': m['plan_sha256'],
             'budget': BUDGET, 'new_p3_reserved': 1, 'new_p2': 0, 'solver_calls': 0,
             'admission_reference': a.admission_reference,
             'resource_preflight': observation,
             'resource_preflight_sha256': digest(a.resource_preflight)}
    receipt = out / 'run.json'
    write(receipt, state)
    try:
        command = [sys.executable, '-B', '-m', 'src.q3.oracle', GRAPH.as_posix(),
                   str(plan_path.relative_to(ROOT)), '3', str(result_path.relative_to(ROOT))]
        child = run_child(command, BUDGET['per_call_seconds'], job,
                          memory_limit_bytes=BUDGET['sampled_group_rss_tripwire_bytes'])
        state['child'] = child
        if child['status'] != 'ok':
            raise RuntimeError(f"P3 evaluation stopped: {child['reason']}")
        result = read(result_path)
        if (result.get('problem') != 3 or result.get('scene') != 'B'
                or result.get('cache_mode') != 'read_only' or result.get('num_cores') != 1):
            raise ValueError('result is not the fixed P3/k1 evaluation')
        if (digest(plan_path) != m['plan_sha256']
                or any(digest(ROOT / path) != h for path, h in hashes.items())):
            raise ValueError('source, input or plan changed during evaluation')
        state.update(status='complete', result_sha256=digest(result_path),
                     makespan=result['makespan'], movement=result['data_movement_bytes'],
                     cache_stats=result.get('cache_stats'))
    except BaseException as error:
        state.update(status='stopped_on_failure', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        state['finished_at'] = utc()
        write(receipt, state)
    print({k: state[k] for k in ('status', 'new_p3_reserved', 'makespan')})


if __name__ == '__main__':
    main()
