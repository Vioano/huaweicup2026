"""Freeze two capacity-DP plans and evaluate each once in an admitted window.

This is a mechanism experiment, not an online solver or a full-suite score.
Preparation performs only original-graph construction and static validation.
"""
import argparse
from pathlib import Path
import sys
import time

from .construct import Index, ROOT
from .feedback_benchmark import digest, read, run_child, utc, verify_source, write
from .pipe_bound import analyze
from .safe_solve import encoded
from .shared_pipeline_capacity import construct

CASES = ('044', '046')
CORES = 5
SNAPSHOT = Path('results/a/q3-nikolastarx/forest-current-headroom-20260925/cells-snapshot.json')
PARENT = ROOT / 'results/a/q3-nikolastarx'
CONFIG = 'data/raw/a/official/data/config.txt'
BUDGET = {'new_p3': 2, 'new_p2': 0, 'solver_calls': 0, 'workers': 1,
          'retries': 0, 'per_call_seconds': 60, 'whole_batch_seconds': 120,
          'sampled_group_rss_tripwire_bytes': 512 * 1024 * 1024}


def controls(forest_root, hashes, official):
    """Verify preserved full500 result bytes, not only the board's report."""
    snapshot = read(ROOT / SNAPSHOT)
    records = []
    for case in CASES:
        row, = [c['best'] for c in snapshot['cells']
                if c['case_id'] == case and c['cores'] == CORES]
        graph = f'data/raw/a/official/data/case_{case}.json'
        expected = row['identity']
        if (row['run_id'] != 'q3-forest-full500-20260925-s59'
                or row['solver_commit'] != '311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1'
                or expected['graph_sha256'] != hashes[graph]
                or expected['config_sha256'] != hashes[CONFIG]
                or expected['official_sha256'] != official):
            raise ValueError('frozen control identity mismatch')
        refs = row['artifacts']
        for name in ('plan', 'result', 'trace'):
            rel = Path(refs[name]['path'])
            if rel.is_absolute() or '..' in rel.parts or rel.parts[0] != 'results':
                raise ValueError('unsafe control path')
            if digest(forest_root / rel) != refs[name]['sha256']:
                raise ValueError(f'control artifact mismatch: {case}/{name}')
        result = read(forest_root / refs['result']['path'])
        trace = read(forest_root / refs['trace']['path'])
        if (result.get('problem') != 3 or result.get('num_cores') != CORES
                or result.get('scene') != 'B' or result.get('cache_mode') != 'read_only'
                or result['makespan'] != row['metrics']['makespan_cycles']
                or trace['graph_sha256'] != expected['graph_sha256']
                or trace['config_sha256'] != expected['config_sha256']
                or trace['plan_sha256'] != expected['plan_sha256']
                or trace['result_sha256'] != refs['result']['sha256']):
            raise ValueError('control result/receipt mismatch')
        records.append({'case_id': case, 'cores': CORES, 'artifacts': refs,
                        'identity': expected, 'existing_makespan': result['makespan'],
                        'movement': result['data_movement_bytes'],
                        'cache_stats': result['cache_stats']})
    return records


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
    official, hashes = verify_source(a.source, set(CASES))
    baseline = controls(a.forest_root.resolve(strict=True), hashes, official)
    out = a.output.resolve()
    if out.parent != PARENT.resolve():
        raise ValueError('output must be a direct child of the Q3 results directory')
    manifest_path = out / 'manifest.json'
    if a.mode == 'prepare':
        start = time.perf_counter()
        delay, = [int(line.split()[1]) for line in (ROOT / CONFIG).read_text().splitlines()
                  if line.split()[:1] == ['cross_core_copy_delay_cycles']]
        plans = []
        for record in baseline:
            case = record['case_id']
            graph = read(ROOT / f'data/raw/a/official/data/case_{case}.json')
            plan, meta = construct(Index(graph), CORES)
            bound = analyze(graph, plan, delay)['with_cross_core_delay']['lower_bound_cycles']
            plans.append((case, encoded(plan), meta, bound))
        out.mkdir(exist_ok=False)
        jobs = []
        for case, raw, meta, bound in plans:
            path = out / f'case_{case}_multicore_res.json'
            path.write_bytes(raw)
            control, = [b for b in baseline if b['case_id'] == case]
            if digest(path) == control['identity']['plan_sha256']:
                raise ValueError('candidate duplicates control')
            jobs.append({'case_id': case, 'cores': CORES, 'plan_file': path.name,
                         'plan_sha256': digest(path), 'metadata': meta,
                         'static_plan_lower_bound': bound,
                         'bound_pruned': bound >= control['existing_makespan']})
        manifest = {'schema': 'q3-pipeline-capacity-two-shot-v1', 'prepared_at': utc(),
                    'source_commit': a.source, 'source_input_sha256': hashes,
                    'official_code_sha256': official, 'budget': BUDGET,
                    'snapshot_sha256': digest(ROOT / SNAPSHOT), 'controls': baseline,
                    'jobs': jobs, 'prepare_seconds': time.perf_counter() - start,
                    'scope': 'two seen structural mechanism cases, not a full solver or holdout'}
        write(manifest_path, manifest)
        print({'prepared': True, 'manifest_sha256': digest(manifest_path), 'new_e0': 0,
               'plans': [{k: j[k] for k in ('case_id', 'plan_sha256', 'bound_pruned')}
                         for j in jobs]})
        return
    if not a.manifest_sha256 or digest(manifest_path) != a.manifest_sha256:
        raise ValueError('manifest must match its separately frozen hash')
    m = read(manifest_path)
    if (m['source_commit'] != a.source or m['source_input_sha256'] != hashes
            or m['official_code_sha256'] != official or m['budget'] != BUDGET
            or m['controls'] != baseline or m['snapshot_sha256'] != digest(ROOT / SNAPSHOT)):
        raise ValueError('prepared identity/budget differs')
    if not a.admission_reference or not a.resource_preflight:
        raise ValueError('new admission and actual resource preflight required')
    observation = read(a.resource_preflight)
    if not observation.get('ready'):
        raise ValueError('resource preflight did not admit execution')
    for job in m['jobs']:
        if digest(out / job['plan_file']) != job['plan_sha256']:
            raise ValueError('prepared plan differs')
    evaluation = out / 'evaluation'
    evaluation.mkdir(exist_ok=False)  # no retry or silent extra evaluation
    start = time.monotonic()
    state = {'status': 'running', 'started_at': utc(), 'source_commit': a.source,
             'manifest_sha256': digest(manifest_path), 'budget': BUDGET,
             'admission_reference': a.admission_reference, 'resource_preflight': observation,
             'resource_preflight_sha256': digest(a.resource_preflight),
             'new_p3_reserved': 0, 'new_p2': 0, 'solver_calls': 0, 'jobs': []}
    try:
        for job in m['jobs']:
            record = dict(job)
            state['jobs'].append(record)
            if job['bound_pruned']:
                record['status'] = 'static_bound_pruned'
                continue
            remaining = BUDGET['whole_batch_seconds'] - (time.monotonic() - start)
            if remaining <= 0:
                raise TimeoutError('whole-batch time budget exhausted')
            folder = evaluation / job['case_id']
            folder.mkdir(exist_ok=False)
            result_path = folder / 'result.json.gz'
            state['new_p3_reserved'] += 1
            record['status'] = 'reserved'
            write(out / 'run.json', state)
            graph = f"data/raw/a/official/data/case_{job['case_id']}.json"
            argv = [sys.executable, '-B', '-m', 'src.q3.oracle', graph,
                    str((out / job['plan_file']).relative_to(ROOT)), '3',
                    str(result_path.relative_to(ROOT))]
            child = run_child(argv, min(BUDGET['per_call_seconds'], remaining), folder,
                              memory_limit_bytes=BUDGET['sampled_group_rss_tripwire_bytes'])
            record['child'] = child
            if child['status'] != 'ok':
                raise RuntimeError(f"official evaluation failed: {child['reason']}")
            result = read(result_path)
            if (result.get('problem') != 3 or result.get('num_cores') != CORES
                    or result.get('scene') != 'B' or result.get('cache_mode') != 'read_only'):
                raise ValueError('unexpected official result identity')
            if digest(out / job['plan_file']) != job['plan_sha256']:
                raise ValueError('plan changed during evaluation')
            record.update(status='ok', result_sha256=digest(result_path),
                          makespan=result['makespan'], movement=result['data_movement_bytes'],
                          cache_stats=result['cache_stats'])
            write(out / 'run.json', state)
        if any(digest(ROOT / path) != h for path, h in hashes.items()):
            raise ValueError('source changed during evaluation')
        state['status'] = 'complete'
    except BaseException as error:
        state.update(status='stopped_on_failure', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        state.update(finished_at=utc(), wall_seconds=time.monotonic() - start)
        write(out / 'run.json', state)
    print({k: state[k] for k in ('status', 'new_p3_reserved', 'wall_seconds')})


if __name__ == '__main__':
    main()
