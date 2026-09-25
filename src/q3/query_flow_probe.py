"""Admitted one-shot 071/K5 query-flow diagnostic. Do not use as solver timing."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
from pathlib import Path
import platform
import re
import runpy
import signal
import subprocess
import sys
import time

from .feedback_benchmark import digest, read, utc, verify_source, write
from .partial_preload_prepare import serializable

ROOT = Path(__file__).resolve().parents[2]
BASE = (ROOT / 'results/a/q3-nikolastarx').resolve()
GRAPH = ROOT / 'data/raw/a/official/data/case_071.json'
CONFIG = ROOT / 'data/raw/a/official/data/config.txt'
LIMIT = {'P3': 1, 'P2': 0, 'Task3': 1, 'Task2': 0, 'Step1': 5,
         'Step2': 5, 'prepareStep3': 5, 'step3_simulation': 5}


def within(path, *, strict=False):
    p = Path(path).resolve(strict=strict)
    p.relative_to(BASE)
    return p


def copy_bytes(graph):
    """Independent COPY_IN output / COPY_OUT input tensor-size sum."""
    tensors = {t['id']: t['size'] for t in graph['tensors']}
    kind = {o['id']: o['op'] for o in graph['ops']}
    transfers = set()
    for edge in graph['edges']:
        source, target = edge['source'], edge['target']
        if kind.get(source) == 'COPY_IN' and target in tensors:
            transfers.add((source, target))
        if kind.get(target) == 'COPY_OUT' and source in tensors:
            transfers.add((target, source))
    return sum(tensors[tid] for _, tid in transfers)


def check_prepared(graph, plan, captured):
    """Pure guard for the one saved official Task return; raises before P2."""
    tasks, links, _, traffic, view = captured['task_return']
    steps = captured['step2']
    if len(tasks) != 5 or len(steps) != 5 or any(s['spill_records'] for s in steps):
        raise ValueError('Task coverage or Step2 no-spill guard failed')
    if traffic['spill_added_copy_bytes']:
        raise ValueError('spill traffic present')
    original = {o['id']: o for o in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    mapping = {int(k): v for k, v in plan['node_to_subgraph'].items()}
    compute_ids = {u for u, op in original.items() if op['op'] not in {'COPY_IN', 'COPY_OUT'}}
    if (set(mapping) != compute_ids or len(mapping) != len(set(mapping.values()))
            or len(set(mapping.values())) != sum(map(len, plan['core_schedules']))):
        raise ValueError('original compute/subgraph coverage differs')
    scheduled = [sg for order in plan['core_schedules'] for sg in order]
    if len(scheduled) != len(set(scheduled)) or set(scheduled) != set(mapping.values()):
        raise ValueError('singleton schedule coverage differs')
    core_of = {sg: c for c, order in enumerate(plan['core_schedules']) for sg in order}
    op_for_subgraph = {sg: u for u, sg in mapping.items()}
    op_core = {u: core_of[sg] for u, sg in mapping.items()}
    touched = [set() for _ in range(5)]
    producers = {tid: set() for tid in tensors}
    consumers = {tid: set() for tid in tensors}
    original_copy_out_inputs = set()
    for e in graph['edges']:
        a, b = e['source'], e['target']
        if a in mapping and b in mapping:
            raise ValueError('original direct op edge violates fixed no-direct-edge guard')
        if a in op_core and b in tensors:
            touched[op_core[a]].add(b)
            producers[b].add(a)
        if b in op_core and a in tensors:
            touched[op_core[b]].add(a)
            consumers[a].add(b)
        if a in tensors and original.get(b, {}).get('op') == 'COPY_OUT':
            original_copy_out_inputs.add(a)
    expected_task_copy = 0
    for tid, tensor in tensors.items():
        src = {op_core[u] for u in producers[tid]}
        dst = {op_core[u] for u in consumers[tid]}
        count = (len(dst) if dst and not src else 0)
        count += len(src) if src and (tid in original_copy_out_inputs or not dst) else 0
        count += 2 * sum(a != b for a in src for b in dst)
        expected_task_copy += count * tensor['size']
    observed_original = []
    for c in range(5):
        task = tasks[c]
        actual_ops = {u for u in task['op_by_id'] if u in mapping}
        expected_ops = {u for u, core in op_core.items() if core == c}
        if actual_ops != expected_ops:
            raise ValueError(f'core {c} original operation coverage differs')
        observed_original.extend(actual_ops)
        for pipe in ('PIPE_M', 'PIPE_V'):
            expected = [op_for_subgraph[sg] for sg in plan['core_schedules'][c]
                        if original[op_for_subgraph[sg]]['pipe'] == pipe]
            actual = [u for u in task['pipe_ops'].get(pipe, []) if u in original]
            if actual != expected:
                raise ValueError(f'core {c} original pipe sequence differs: {pipe}')
        found = {tid: (t['pos'], t['size']) for tid, t in task['tensor_by_id'].items()
                 if t['pos'] != 'DDR'}
        expected = {tid: ('UB' if tensors[tid]['pos'] == 'DDR' else tensors[tid]['pos'],
                          tensors[tid]['size']) for tid in touched[c]}
        if found != expected:
            raise ValueError(f'core {c} local tensor ID/position/size differs')
        if task['step3']['memory_dependencies']:
            raise ValueError(f'core {c} Step3 memory dependencies present')
        for bank in ('L1', 'UB'):
            if sum(size for pos, size in found.values() if pos == bank) > captured['capacity'][bank]:
                raise ValueError(f'core {c} {bank} static capacity exceeded')
        producer = {}
        ids = set(task['op_by_id'])
        for edge in task['graph']['edges']:
            if edge['target'] in task['tensor_by_id'] and edge['source'] in ids:
                producer.setdefault(edge['target'], set()).add(edge['source'])
        if any(len(producer.get(tid, ())) != 1 for tid in found):
            raise ValueError(f'core {c} local tensor producer is not unique')
    if len(observed_original) != len(mapping) or set(observed_original) != set(mapping):
        raise ValueError('all-core original operation coverage differs')
    raw_copy = copy_bytes(graph)
    task_copy = sum(copy_bytes(t['graph']) for t in tasks.values())
    if (raw_copy != traffic['original_graph_copy_bytes']
            or expected_task_copy != task_copy
            or task_copy != traffic['scheduled_copy_bytes']
            or task_copy - raw_copy != traffic['added_copy_bytes']):
        raise ValueError('independent COPY byte accounting differs')
    return {'original_copy_bytes': raw_copy, 'scheduled_copy_bytes': task_copy,
            'added_copy_bytes': task_copy - raw_copy,
            'predicted_task_copy_bytes': expected_task_copy,
            'method': 'independent original tensor producer/consumer core formula, cross-core pair 2x, checked against COPY edge sums',
            'cross_links': len(links), 'cores': len(tasks)}


def worker(args):
    plan_path = within(args.candidate, strict=True) / 'case_071_multicore_res.json'
    if digest(plan_path) != args.plan_sha256:
        raise ValueError('plan byte identity differs')
    official, _ = verify_source(args.source, {'071'})
    phase = args.worker
    if phase not in ('p3', 'p2') or not within(args.output, strict=True).is_dir():
        raise ValueError('worker phase/output differs')
    reservation = read(args.output / f'{phase}.reservation.json')
    if reservation != {'phase': phase, 'source': args.source, 'plan_sha256': args.plan_sha256}:
        raise ValueError('reservation differs')
    with (args.output / f'{phase}.claim.json').open('x') as f:
        json.dump({'claimed_at': utc()}, f)
    sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b, _build_scene_b_tasks as build2
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3, _build_scene_b_tasks as build3
    from schedule_step1 import step1_schedule
    from schedule_step2 import step2_spill_insertion
    from schedule_step3 import prepare_step3_execution, step3_simulation
    watched = {evaluate_problem_3.__code__: 'P3', evaluate_scene_b.__code__: 'P2',
               build3.__code__: 'Task3', build2.__code__: 'Task2',
               step1_schedule.__code__: 'Step1', step2_spill_insertion.__code__: 'Step2',
               prepare_step3_execution.__code__: 'prepareStep3',
               step3_simulation.__code__: 'step3_simulation'}
    caps = dict(LIMIT)
    caps['P3'], caps['P2'], caps['Task3'], caps['Task2'] = (1, 0, 1, 0) if phase == 'p3' else (0, 1, 0, 1)
    counts = dict.fromkeys(caps, 0)
    receipt = {'status': 'running', 'phase': phase, 'counts_started': counts,
               'source_commit': args.source, 'plan_sha256': args.plan_sha256,
               'official_code_sha256': official,
               'limits': caps, 'solver_wall_seconds': None, 'started_at': utc()}
    receipt_path = args.output / f'{phase}.worker.json'
    write(receipt_path, receipt)
    captured = {'step2': [], 'task_return': None}
    graph = read(GRAPH)
    plan = read(plan_path)

    def observe(frame, event, value):
        name = watched.get(frame.f_code)
        if name is None:
            return
        if event == 'call':
            counts[name] += 1
            write(receipt_path, receipt)
            if counts[name] > caps[name]:
                raise RuntimeError('official invocation budget exceeded: ' + name)
        if event == 'return' and phase == 'p3':
            if name == 'Step2':
                captured['step2'].append(copy.deepcopy(value))
            if name == 'Task3':
                captured['task_return'] = copy.deepcopy(value)
                from evaluation_validation import read_evaluation_config
                captured['capacity'] = read_evaluation_config(CONFIG)['capacity']
                raw = serializable(captured)
                (args.output / 'prepared.json.gz').write_bytes(gzip.compress(
                    json.dumps(raw, separators=(',', ':')).encode(), mtime=0))
                receipt['prepared_sha256'] = digest(args.output / 'prepared.json.gz')
                write(receipt_path, receipt)
                receipt['guard'] = check_prepared(graph, plan, captured)
                write(receipt_path, receipt)

    old_profile = sys.getprofile()
    if old_profile is not None:
        raise RuntimeError('unexpected existing profiler')
    old_argv = sys.argv
    started = time.monotonic()
    previous_alarm = signal.getsignal(signal.SIGALRM)
    def expired(_signal, _frame):
        raise TimeoutError('worker 90-second wall-clock limit')
    try:
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, 90)
        sys.argv = ['src.q3.oracle', str(GRAPH), str(plan_path), '3' if phase == 'p3' else '2',
                    str(args.output / f'{phase}.json.gz')]
        sys.setprofile(observe)
        runpy.run_module('src.q3.oracle', run_name='__main__')
        if counts != caps or (phase == 'p3' and not receipt.get('guard')):
            raise ValueError('official calls or guards incomplete')
        receipt.update(status='complete', result_sha256=digest(args.output / f'{phase}.json.gz'))
    except BaseException as error:
        receipt.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_alarm)
        sys.argv = old_argv
        sys.setprofile(old_profile)
        receipt['finished_at'] = utc()
        receipt['diagnostic_wall_seconds'] = time.monotonic() - started
        write(receipt_path, receipt)


def run_phase(args, phase, deadline, report):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('whole-run deadline before phase')
    reservation = {'phase': phase, 'source': args.source, 'plan_sha256': args.plan_sha256}
    write(args.output / f'{phase}.reservation.json', reservation)
    report['reservations'].append(phase)
    write(args.output / 'run.json', report)
    cmd = [sys.executable, '-B', '-m', 'src.q3.query_flow_probe', str(args.candidate),
           str(args.output), '--source', args.source, '--plan-sha256', args.plan_sha256,
           '--worker', phase]
    with (args.output / f'{phase}.stdout.txt').open('x') as stdout, (
            args.output / f'{phase}.stderr.txt').open('x') as stderr:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=stdout, stderr=stderr,
                                start_new_session=True)
        try:
            proc.wait(timeout=min(90, max(0.001, deadline - time.monotonic())))
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=10)
            raise
    report['phases'].append({'phase': phase, 'exit_code': proc.returncode,
                             'worker': f'{phase}.worker.json'})
    write(args.output / 'run.json', report)
    if proc.returncode:
        raise RuntimeError(f'{phase} worker failed; slot consumed')
    receipt = read(args.output / f'{phase}.worker.json')
    if receipt['status'] != 'complete' or digest(args.output / f'{phase}.json.gz') != receipt['result_sha256']:
        raise ValueError(f'{phase} result receipt differs')
    return read(args.output / f'{phase}.json.gz')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--source', required=True)
    p.add_argument('--plan-sha256', required=True)
    p.add_argument('--admission-ref')
    p.add_argument('--worker', choices=['p3', 'p2'])
    a = p.parse_args()
    a.candidate = within(a.candidate, strict=True)
    a.output = within(a.output)
    if not re.fullmatch(r'[0-9a-f]{64}', a.plan_sha256):
        raise ValueError('full plan SHA-256 required')
    plan_path = a.candidate / 'case_071_multicore_res.json'
    if digest(plan_path) != a.plan_sha256:
        raise ValueError('plan byte identity differs')
    official, inputs = verify_source(a.source, {'071'})
    if a.worker:
        worker(a)
        return
    if not a.admission_ref or len(a.admission_ref) > 500:
        raise ValueError('explicit admission reference required')
    a.output.mkdir(parents=False, exist_ok=False)
    report = {'status': 'running', 'started_at': utc(), 'source_commit': a.source,
              'plan_sha256': a.plan_sha256, 'admission_ref': a.admission_ref,
              'official_code_sha256': official, 'source_input_sha256': inputs,
              'budget': {'workers': 1, 'P3': 1, 'P2_conditional': 1,
                         'per_phase_seconds': 90, 'total_seconds': 600, 'retries': 0},
              'reservations': [], 'phases': [], 'solver_wall_seconds': None,
              'environment': {'platform': platform.platform(), 'python': sys.version,
                              'cpu_count': os.cpu_count()}}
    write(a.output / 'run.json', report)
    deadline = time.monotonic() + 600
    try:
        result3 = run_phase(a, 'p3', deadline, report)
        report['candidate_M'] = result3['makespan']
        if result3['makespan'] < 7782:
            guard = read(a.output / 'p3.worker.json').get('guard')
            if not guard:
                raise ValueError('P3 guard receipt absent')
            result2 = run_phase(a, 'p2', deadline, report)
            report['candidate_P2_M'] = result2['makespan']
            report['candidate_G'] = result2['makespan'] / result3['makespan']
        else:
            report['p2_stop'] = 'P3 Makespan did not strictly improve 7782'
        report['status'] = 'complete'
    except BaseException as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        report.update(finished_at=utc(), diagnostic_wall_seconds=600 - max(0, deadline - time.monotonic()))
        write(a.output / 'run.json', report)
    print(json.dumps({'status': report['status'], 'candidate_M': report['candidate_M']}))


if __name__ == '__main__':
    main()
