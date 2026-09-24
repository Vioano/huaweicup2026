"""Rebuild two fixed official Task graphs and explain recorded PIPE_M gaps.

Runs official Step1/2/3 preparation (10 local Step3 simulations total), but no
new multicore P2/P3 simulation or solver. Timings come from existing E0 outputs.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import time

from .construct import ROOT
from .feedback_benchmark import digest, git_bytes, read, utc, verify_source, write

FOREST_COMMIT = 'bff88a66cd76ceb2d75242bf99d34bfe8b1879d4'
BAND_RUN = 'results/a/q3-nikolastarx/band-mechanism-20260925/run.json'
BUDGET = {'task_builds': 2, 'local_step3_simulations': 10, 'new_multicore_e0': 0,
          'solver_calls': 0, 'workers': 1, 'retries': 0,
          'per_build_seconds': 90, 'whole_batch_seconds': 180}


def rebuild(graph_path, plan_path, result_path, output_path):
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
    graph, plan, result = read(graph_path), read(plan_path), read(result_path)
    cfg = read_evaluation_config(ROOT / 'data/raw/a/official/data/config.txt')
    before = time.monotonic()
    tasks, links, _, traffic, _ = _build_scene_b_tasks(graph, plan, **cfg)
    assert len(tasks) == 5 and not links and not result['cross_core_transfers']
    assert traffic == result['data_movement_bytes']
    summaries = []
    for core, task in tasks.items():
        timeline = result['per_core_timeline'][core]['ops']
        observed = {r['op_id']: r for r in timeline}
        assert set(observed) == set(task['op_by_id'])
        assert len(task['step3']['memory_dependencies']) == result['step3_by_core'][str(core)]['memory_dependency_count']
        for pipe, order in task['pipe_ops'].items():
            actual = sorted((r for r in timeline if r['pipe'] == pipe),
                            key=lambda r: (r['start'], task['seq_pos'][r['op_id']]))
            assert [r['op_id'] for r in actual] == order
        memory = {(d['source'], d['target']): d for d in task['step3']['memory_dependencies']}
        gaps, matches, previous_end = [], 0, 0
        for position, op in enumerate(task['pipe_ops']['PIPE_M']):
            obs = observed[op]
            preds = task['op_preds'][op]
            ready = max([previous_end, *[observed[p]['end'] for p in preds]])
            if ready != obs['start']:
                raise ValueError(f'Unexplained M readiness at core {core}, op {op}: {ready} != {obs["start"]}')
            matches += 1
            if position and obs['start'] > previous_end:
                blockers = []
                for pred in sorted(preds):
                    if observed[pred]['end'] != ready:
                        continue
                    edge = memory.get((pred, op))
                    blockers.append({'source': pred, 'op': observed[pred]['op'],
                                     'pipe': observed[pred]['pipe'], 'end': ready,
                                     'kind': 'memory_reuse' if edge else 'data',
                                     'memory_dependency': edge})
                assert blockers
                gaps.append({'target_M': op, 'position': position,
                             'previous_M_end': previous_end, 'M_start': ready,
                             'gap': ready - previous_end, 'tight_predecessors': blockers})
            previous_end = obs['end']
        by_kind = Counter()
        for gap in gaps:
            key = '+'.join(sorted({p['kind'] for p in gap['tight_predecessors']}))
            by_kind[key] += gap['gap']
        m = [observed[u] for u in task['pipe_ops']['PIPE_M']]
        summaries.append({'core': core, 'core_end': max(r['end'] for r in timeline),
                          'M_busy': sum(r['duration'] for r in m), 'first_M_start': m[0]['start'],
                          'M_gap_sum': sum(g['gap'] for g in gaps),
                          'tail': max(r['end'] for r in timeline)-m[-1]['end'],
                          'matched_M_ready_times': matches, 'gap_cycles_by_tight_edge_kind': dict(by_kind),
                          'memory_dependency_count': len(memory), 'all_M_gaps': gaps})
    critical = max(summaries, key=lambda c: (c['core_end'], -c['core']))
    write(output_path, {'scope': 'official Task preparation and recorded-timeline dependency audit, not new P3 result',
                        'task_builds': 1, 'local_step3_simulations': len(tasks),
                        'new_multicore_e0': 0, 'task_build_and_audit_seconds': time.monotonic()-before,
                        'plan_sha256': digest(plan_path), 'result_sha256': digest(result_path),
                        'critical_core': critical['core'], 'cores': summaries})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('--source')
    p.add_argument('--forest-root', type=Path)
    p.add_argument('--worker', nargs=3, metavar=('GRAPH', 'PLAN', 'RESULT'))
    args = p.parse_args()
    if args.worker:
        rebuild(*map(Path, args.worker), args.output)
        return
    start = time.monotonic()
    if not args.source or not args.forest_root:
        p.error('--source and --forest-root required for the bounded batch')
    official, hashes = verify_source(args.source, {'079'})
    band = read(ROOT / BAND_RUN)
    new = next(r for r in band['results'] if (r['case_id'], r['order_mode'], r['problem']) == ('079', 'pair_cache_model', 3))
    proposal = next(r for r in band['plans'] if (r['case_id'], r['order_mode']) == ('079', 'pair_cache_model'))
    coverage = next(r for r in read(ROOT / 'results/a/q3-nikolastarx/reuse-coverage-20260925/coordinates.json') if r['case']==79 and r['cores']==5)
    receipt_path = Path(coverage['receipt_path'])
    receipt_raw = git_bytes(args.forest_root, FOREST_COMMIT, str(receipt_path))
    assert receipt_raw == (args.forest_root / receipt_path).read_bytes()
    receipt = json.loads(receipt_raw)
    jobs = [('new_pair', ROOT / proposal['plan_path'], ROOT / new['result_path'], new['plan_sha256'], new['result_sha256']),
            ('old_forest', args.forest_root / receipt_path.parent.parent / 'case_079_multicore_res.json',
             args.forest_root / receipt_path.parent / 'result.json.gz', receipt['plan_sha256'], receipt['result_sha256'])]
    for _, plan, result, ph, rh in jobs:
        assert digest(plan) == ph and digest(result) == rh
    out = args.output.resolve()
    out.relative_to(ROOT / 'results/a/q3-nikolastarx')
    out.mkdir(parents=True, exist_ok=False)
    state = {'status': 'running', 'source_commit': args.source, 'started_at': utc(),
             'official_code_sha256': official, 'source_input_sha256': hashes,
             'budget': BUDGET, 'builds_reserved': 0, 'jobs': []}

    def save():
        state['elapsed_seconds'] = time.monotonic()-start
        write(out/'run.json', state)

    save()
    try:
        for name, plan, result, ph, rh in jobs:
            remaining = BUDGET['whole_batch_seconds'] - (time.monotonic()-start)
            if remaining <= 0:
                raise TimeoutError('preparation budget reached')
            target = out/f'{name}.json'
            record = {'name': name, 'plan_sha256': ph, 'existing_result_sha256': rh,
                      'status': 'reserved', 'local_step3_reserved': 5}
            state['jobs'].append(record)
            state['builds_reserved'] += 1
            save()
            with (out/f'{name}.stdout.txt').open('xb') as stdout, (out/f'{name}.stderr.txt').open('xb') as stderr:
                subprocess.run([sys.executable, '-m', 'src.q3.memory_dependency_audit', str(target), '--worker',
                                str(ROOT/'data/raw/a/official/data/case_079.json'), str(plan), str(result)],
                               cwd=ROOT, stdout=stdout, stderr=stderr,
                               timeout=min(BUDGET['per_build_seconds'], remaining), check=True)
            record.update(status='ok', output_sha256=digest(target))
            save()
        assert all(digest(ROOT/path)==sha for path,sha in hashes.items())
        state['status']='complete'
    except Exception as error:
        state.update(status='stopped_on_failure', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        state['finished_at']=utc()
        save()
    print(json.dumps({'status':state['status'],'task_builds':state['builds_reserved'],
                      'local_step3_simulations':10,'new_multicore_e0':0,'seconds':state['elapsed_seconds']}))


if __name__=='__main__':
    main()
