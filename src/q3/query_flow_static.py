"""Two frozen R8 mechanism inputs, no Task preparation or official scoring."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from .construct import Index, ROOT
from .feedback_benchmark import digest, read, utc, verify_source, write
from .pipe_bound import analyze
from .safe_solve import encoded

CASES = ('071', '069')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('--source', required=True)
    a = p.parse_args()
    official, inputs = verify_source(a.source, set(CASES))
    from .query_flow import construct
    from evaluation_validation import read_evaluation_config, read_required_settings
    cfg_path = ROOT / 'data/raw/a/official/data/config.txt'
    cfg = read_evaluation_config(cfg_path)
    delay = read_required_settings(cfg_path, 'multicore_scene_b',
                                   ('cross_core_copy_delay_cycles',))['cross_core_copy_delay_cycles']
    out = a.output.resolve()
    out.relative_to(ROOT / 'results/a/q3-nikolastarx')
    out.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'source_commit': a.source, 'started_at': utc(),
              'official_code_sha256': official, 'source_input_sha256': inputs,
              'budget': {'construct': 2, 'pipe_bound': 2, 'workers': 1,
                         'wall_seconds': 60, 'Task': 0, 'E0': 0, 'retries': 0},
              'calls': {'construct': 0, 'pipe_bound': 0}, 'rows': [],
              'scope': 'static two seen-case mechanisms; not solver wall or official performance'}
    start = time.monotonic()
    write(out / 'summary.json', report)
    # Fail closed if a future constructor unexpectedly begins official preparation.
    def audit(frame, event, value):
        if event != 'call':
            return
        if (frame.f_code.co_name in {'_build_scene_b_tasks', 'step1_schedule',
                'step2_spill_insertion', 'prepare_step3_execution', 'step3_simulation',
                'evaluate_problem_3', 'evaluate_scene_b'}):
            raise RuntimeError('official preparation/evaluation forbidden in static experiment')
        if time.monotonic() - start > 60:
            raise TimeoutError('fixed static batch wall budget exceeded')
    previous = sys.getprofile()
    if previous is not None:
        raise RuntimeError('unexpected existing profile')
    try:
        sys.setprofile(audit)
        for case in CASES:
            graph = read(ROOT / f'data/raw/a/official/data/case_{case}.json')
            index = Index(graph)
            report['calls']['construct'] += 1
            write(out / 'summary.json', report)
            plan, info = construct(index, 5, cross_delay=delay, capacity=cfg['capacity'])
            assert set(plan) == {'node_to_subgraph', 'core_schedules'}
            report['calls']['pipe_bound'] += 1
            bound = analyze(graph, plan, delay)
            assert info['L0_compute_fifo'] == bound['zero_delay']['lower_bound_cycles']
            assert info['Ldelta_compute_fifo'] == bound['with_cross_core_delay']['lower_bound_cycles']
            assert info['max_remote_edges_on_path'] <= 2
            raw = encoded(plan)
            (out / f'case_{case}_multicore_res.json').write_bytes(raw)
            write(out / f'{case}-metadata.json', info)
            write(out / f'{case}-bound.json', bound)
            report['rows'].append({'case': case, 'cores': 5,
                'plan_sha256': hashlib.sha256(raw).hexdigest(),
                'compute_bound': bound['with_cross_core_delay']['lower_bound_cycles'],
                'zero_delay_bound': bound['zero_delay']['lower_bound_cycles'],
                'metadata_sha256': digest(out / f'{case}-metadata.json')})
            write(out / 'summary.json', report)
        report['status'] = 'complete'
    except BaseException as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        sys.setprofile(previous)
        report.update(finished_at=utc(), wall_seconds=time.monotonic() - start)
        write(out / 'summary.json', report)
    print(json.dumps({'status': report['status'], 'calls': report['calls'],
                      'rows': report['rows'], 'official_calls': 0}))


if __name__ == '__main__':
    main()
