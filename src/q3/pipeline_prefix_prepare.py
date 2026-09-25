"""Observe one unchanged official preparation for the frozen prefix candidate.

Run only inside an admitted, bounded subprocess. This does not call P2 or P3.
Python return tracing records intermediate Step1/Step2 values without replacing
official functions. Its wall time is diagnostic overhead, not solver latency.
"""
import argparse
import copy
import gzip
import json
from pathlib import Path
import sys
import time

from .construct import ROOT
from .feedback_benchmark import digest, read, utc, verify_source, write


def serializable(value):
    if isinstance(value, dict):
        return {str(k): serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(v) for v in value]
    if isinstance(value, set):
        return [serializable(v) for v in sorted(value)]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('static', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', required=True)
    parser.add_argument('--static-summary-sha256', required=True)
    args = parser.parse_args()
    official, inputs = verify_source(args.source, {'044'})
    source = args.static.resolve(strict=True)
    if digest(source / 'summary.json') != args.static_summary_sha256:
        raise ValueError('static summary identity differs')
    summary = read(source / 'summary.json')
    if summary['status'] != 'complete':
        raise ValueError('static candidate did not complete')
    for name, expected in summary['artifacts'].items():
        if Path(name).name != name or digest(source / name) != expected:
            raise ValueError('static artifact mismatch')
    for name, expected in summary['source_input_sha256'].items():
        if name.startswith('data/') and digest(ROOT / name) != expected:
            raise ValueError('frozen official input differs from static reconstruction')
    out = args.output.resolve()
    out.relative_to(ROOT / 'results/a/q3-nikolastarx')
    out.mkdir(parents=True, exist_ok=False)
    from evaluation_validation import read_evaluation_config, validate_execution
    from multicore_cut_evaluate_problem_3 import _build_scene_b_tasks
    from schedule_step1 import step1_schedule
    from schedule_step2 import step2_spill_insertion
    from schedule_step3 import prepare_step3_execution
    watched = {step1_schedule.__code__: 'Step1',
               step2_spill_insertion.__code__: 'Step2',
               prepare_step3_execution.__code__: 'Step3'}
    counts = {name: 0 for name in watched.values()}
    intermediates = {name: [] for name in watched.values()}
    state = {'status': 'running', 'source_commit': args.source,
             'official_code_sha256': official, 'source_input_sha256': inputs,
             'static_summary_sha256': args.static_summary_sha256,
             'started_at': utc(), 'new_P2': 0, 'new_P3': 0,
             'task_builds_reserved': 1, 'calls_started': counts,
             'scope': 'official preparation and dependency audit only'}
    write(out / 'run.json', state)

    def observer(frame, event, value):
        name = watched.get(frame.f_code)
        if name is None:
            return
        if event == 'call':
            counts[name] += 1
            write(out / 'run.json', state)
            if counts[name] > 5:
                raise RuntimeError('preparation invocation limit exceeded')
        elif event == 'return':
            record = {'result': copy.deepcopy(value)}
            if name == 'Step2':
                record.update(graph=copy.deepcopy(frame.f_locals['graph_json']),
                              seq=list(frame.f_locals['seq']))
            intermediates[name].append(record)

    start = time.perf_counter()
    try:
        graph = read(ROOT / 'data/raw/a/official/data/case_044.json')
        plan = read(source / 'case_044_multicore_res.json')
        cfg = read_evaluation_config(ROOT / 'data/raw/a/official/data/config.txt')
        old_profile = sys.getprofile()
        if old_profile is not None:
            raise RuntimeError('unexpected existing profiler')
        try:
            sys.setprofile(observer)
            tasks, links, cross_bytes, traffic, plan_view = _build_scene_b_tasks(graph, plan, **cfg)
        finally:
            sys.setprofile(old_profile)
        validate_execution(tasks, links)
        if counts != {'Step1': 5, 'Step2': 5, 'Step3': 5}:
            raise ValueError('unexpected official preparation count')
        # Preserve the full evidence before interpreting it, including failures.
        payload = serializable({'tasks': tasks, 'cross_links': links,
                                'cross_task_traffic': cross_bytes, 'traffic': traffic,
                                'plan_view': plan_view, 'intermediates': intermediates})
        (out / 'prepared.json.gz').write_bytes(gzip.compress(
            json.dumps(payload, separators=(',', ':')).encode(), mtime=0))
        state['prepared_sha256'] = digest(out / 'prepared.json.gz')
        certificate = read(source / 'certificate.json')
        rows = []
        for record in certificate['cores']:
            c = record['core']
            task = tasks[c]
            prefix = record['prefix_copy_ids']
            prefix_set = set(prefix)
            checks = {
                'pre_step2_word_equal': intermediates['Step2'][c]['seq'] == record['pre_step2_word'],
                'no_spill_records': not intermediates['Step2'][c]['result']['spill_records'],
                'extended_word_unchanged': task['seq'] == record['pre_step2_word'],
            }
            if c:
                checks.update(
                    mte2_prefix_equal=task['pipe_ops']['PIPE_MTE2'][:len(prefix)] == prefix,
                    no_cross_release=not any(l['target_core'] == c and l['target_copy_in_id'] in prefix_set for l in links),
                    no_outside_local_predecessor=all(set(task['op_preds'][u]) <= prefix_set for u in prefix),
                    no_reuse_into_prefix=not any(d['target'] in prefix_set for d in task['step3']['memory_dependencies']),
                )
            rows.append({'core': c, 'checks': checks, 'prefix': prefix})
        state.update(checks=rows, traffic=traffic)
        if traffic['spill_added_copy_bytes'] or not all(all(r['checks'].values()) for r in rows):
            raise ValueError('prepared graph falsifies prefix or no-spill certificate; stop before scoring')
        state['status'] = 'complete'
    except BaseException as error:
        state.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        state.update(finished_at=utc(), wall_seconds=time.perf_counter() - start)
        write(out / 'run.json', state)
    print(json.dumps({'status': state['status'], 'calls': counts, 'traffic': traffic}))


if __name__ == '__main__':
    main()
