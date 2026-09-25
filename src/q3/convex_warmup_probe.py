"""Admitted one-shot 005/K5 convex warmup diagnostic. Do not use as solver timing."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
from pathlib import Path
import platform
import re
from fractions import Fraction
import runpy
import signal
import subprocess
import sys
import time

from .feedback_benchmark import digest, read, utc, verify_source, write
from .partial_preload_prepare import serializable

ROOT = Path(__file__).resolve().parents[2]
BASE = (ROOT / 'results/a/q3-nikolastarx').resolve()
GRAPH = ROOT / 'data/raw/a/official/data/case_005.json'
CONFIG = ROOT / 'data/raw/a/official/data/config.txt'
LIMIT = {'P3': 1, 'P2': 1, 'Task3': 1, 'Task2': 0, 'Step1': 5,
         'Step2': 5, 'prepareStep3': 5, 'step3_simulation': 5}


def within(path, *, strict=False):
    p = Path(path).resolve(strict=strict)
    p.relative_to(BASE)
    return p


def evidence(path, sha256, *, json_content=True):
    """Read a fixed original and reject byte drift before interpreting it."""
    if not re.fullmatch(r'[0-9a-f]{64}', sha256):
        raise ValueError('full evidence SHA-256 required')
    path = Path(path).resolve(strict=True)
    if digest(path) != sha256:
        raise ValueError(f'evidence SHA-256 differs: {path}')
    return read(path) if json_content else path


def old_control(path, sha256, *, graph_sha256, config_sha256, official_code_sha256):
    """Verify exact archived same-plan control and P2 pairing without scoring."""
    control = evidence(path, sha256)
    if control.get('schema') != 'layered-control-v1' or control.get('case_id') != '005' or control.get('cores') != 5:
        raise ValueError('old control schema/case/cores differ')
    identity = control.get('identity', {})
    expected = {'graph_sha256': graph_sha256, 'config_sha256': config_sha256,
                'official_sha256': official_code_sha256}
    if any(identity.get(k) != v for k, v in expected.items()):
        raise ValueError('old control input/official identity differs')
    if not re.fullmatch(r'[0-9a-f]{40}', control.get('source_commit', '')):
        raise ValueError('old source commit missing')
    if not re.fullmatch(r'[0-9a-f]{64}', control.get('source_feed_sha256', '')):
        raise ValueError('old source feed hash missing')
    artifacts = control.get('artifacts', {})
    if set(artifacts) != {'plan', 'P3', 'P2'}:
        raise ValueError('old artifacts differ')
    opened = {}
    for name, ref in artifacts.items():
        if not {'path', 'sha256', 'source_path'} <= set(ref):
            raise ValueError(f'old {name} reference incomplete')
        if not (ROOT / ref['path']).resolve().is_relative_to(ROOT):
            raise ValueError('old artifact path outside repo')
        opened[name] = evidence(ROOT / ref['path'], ref['sha256'])
    if identity.get('plan_sha256') != artifacts['plan']['sha256']:
        raise ValueError('old plan SHA pairing differs')
    plan = opened['plan']
    if set(plan) != {'node_to_subgraph', 'core_schedules'} or len(plan['core_schedules']) != 5:
        raise ValueError('old plan fields/cores differ')
    for name, problem in (('P3', 3), ('P2', 2)):
        result = opened[name]
        if (type(control.get('M'+str(problem))) is not int
                or control['M'+str(problem)] <= 0
                or result.get('makespan') != control['M'+str(problem)]
                or result.get('num_cores') != 5
                or (name == 'P3' and result.get('problem') != 3)):
            raise ValueError(f'old {name} result differs')
    pair = control.get('pair_evidence', {})
    if (any(pair.get(k) != v for k, v in {**expected, 'plan_sha256': identity['plan_sha256'],
                                          'cores': 5}.items())
            or pair.get('route') != 'E0'
            or pair.get('result', {}).get('sha256') != artifacts['P2']['sha256']
            or pair.get('result', {}).get('path') != artifacts['P2']['source_path']):
        raise ValueError('old P2 same-plan evidence differs')
    if abs(float(control.get('G', 0)) - control['M2'] / control['M3']) > 1e-12:
        raise ValueError('old G differs from M2/M3')
    return {'control_sha256': sha256, 'plan_sha256': identity['plan_sha256'],
            'M3': control['M3'], 'M2': control['M2'], 'source_commit': control['source_commit'],
            'source_feed_sha256': control['source_feed_sha256']}


def decide(candidate_m3, candidate_m2, old):
    """Keep R9 M2 nonworse and beat both R9 and fixed-Forest cache ratios."""
    if type(candidate_m3) is not int or candidate_m3 <= 0:
        raise ValueError('candidate P3 Makespan invalid')
    if candidate_m2 is None:
        return {'run_p2': candidate_m3 < old['M3'], 'accepted': False}
    if type(candidate_m2) is not int or candidate_m2 <= 0:
        raise ValueError('candidate P2 Makespan invalid')
    return {'run_p2': candidate_m3 < old['M3'],
            'accepted': (candidate_m3 < old['M3'] and candidate_m2 <= old['M2']
                         and Fraction(candidate_m2, candidate_m3)
                         >= max(Fraction(old['M2'], old['M3']), Fraction(37327, 30642)))}


def worker(args):
    plan_path = within(args.candidate, strict=True) / 'case_005_multicore_res.json'
    if args.plan_sha256 != '549519032c0ae7b78957463d0b6189d30184bcfd46e06fa60fc2c1fcc7dc6615' or digest(plan_path) != args.plan_sha256:
        raise ValueError('plan byte identity differs')
    official, _ = verify_source(args.source, {'005'})
    phase = args.worker
    if phase not in ('p3', 'p2') or not within(args.output, strict=True).is_dir():
        raise ValueError('worker phase/output differs')
    admission = evidence(args.admission_file, args.admission_sha256, json_content=False)
    reservation = read(args.output / f'{phase}.reservation.json')
    if reservation != {'phase': phase, 'source': args.source, 'plan_sha256': args.plan_sha256,
                       'admission_file': str(admission), 'admission_sha256': args.admission_sha256}:
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
                from .layered_prepared_guard import check_layered_prepared, PreparedGuardError
                try:
                    receipt['guard'] = check_layered_prepared(graph, plan, captured, layers=3, allow_multi=True, crossing_limit=None)
                except PreparedGuardError as error:
                    receipt['guard'] = error.as_dict()
                    write(receipt_path, receipt)
                    raise
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
    reservation = {'phase': phase, 'source': args.source, 'plan_sha256': args.plan_sha256,
                   'admission_file': str(args.admission_file), 'admission_sha256': args.admission_sha256}
    write(args.output / f'{phase}.reservation.json', reservation)
    report['reservations'].append(phase)
    write(args.output / 'run.json', report)
    cmd = [sys.executable, '-B', '-m', 'src.q3.convex_warmup_probe', str(args.candidate),
           str(args.output), '--source', args.source, '--plan-sha256', args.plan_sha256,
           '--admission-file', str(args.admission_file),
           '--admission-sha256', args.admission_sha256, '--worker', phase]
    with (args.output / f'{phase}.stdout.txt').open('x') as stdout, (
            args.output / f'{phase}.stderr.txt').open('x') as stderr:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=stdout, stderr=stderr)
        try:
            proc.wait(timeout=min(90, max(0.001, deadline - time.monotonic())))
        except BaseException:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
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
    p.add_argument('--admission-file', type=Path)
    p.add_argument('--admission-sha256')
    p.add_argument('--control', type=Path)
    p.add_argument('--control-sha256')
    p.add_argument('--worker', choices=['p3', 'p2'])
    a = p.parse_args()
    a.candidate = within(a.candidate, strict=True)
    a.output = within(a.output)
    if not re.fullmatch(r'[0-9a-f]{64}', a.plan_sha256):
        raise ValueError('full plan SHA-256 required')
    plan_path = a.candidate / 'case_005_multicore_res.json'
    if a.plan_sha256 != '549519032c0ae7b78957463d0b6189d30184bcfd46e06fa60fc2c1fcc7dc6615' or digest(plan_path) != a.plan_sha256:
        raise ValueError('plan byte identity differs')
    official, inputs = verify_source(a.source, {'005'})
    if a.worker:
        worker(a)
        return
    if not all((a.admission_file, a.admission_sha256, a.control, a.control_sha256)):
        raise ValueError('fixed admission and old control originals with SHA-256 required')
    admission_path = evidence(a.admission_file, a.admission_sha256, json_content=False)
    a.admission_file = admission_path
    old = old_control(a.control, a.control_sha256, graph_sha256=digest(GRAPH),
                      config_sha256=digest(CONFIG), official_code_sha256=official)
    a.output.mkdir(parents=False, exist_ok=False)
    report = {'status': 'running', 'started_at': utc(), 'source_commit': a.source,
              'plan_sha256': a.plan_sha256, 'admission_file': str(admission_path), 'admission_sha256': a.admission_sha256,
              'old_control': old,
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
        report['candidate_M3'] = result3['makespan']
        guard = read(a.output / 'p3.worker.json').get('guard')
        if not guard or guard.get('status') != 'passed':
            raise ValueError('P3 prepared guard receipt absent or failed')
        gate = decide(result3['makespan'], None, old)
        if gate['run_p2']:
            result2 = run_phase(a, 'p2', deadline, report)
            report['candidate_M2'] = result2['makespan']
            report['candidate_G_fraction'] = [result2['makespan'], result3['makespan']]
            report['accepted'] = decide(result3['makespan'], result2['makespan'], old)['accepted']
        else:
            report['p2_stop'] = 'candidate P3 Makespan is not strictly below verified old P3'
            report['accepted'] = False
        report['status'] = 'complete'
    except BaseException as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        report.update(finished_at=utc(), diagnostic_wall_seconds=600 - max(0, deadline - time.monotonic()))
        write(a.output / 'run.json', report)
    print(json.dumps({'status': report['status'], 'candidate_M': report.get('candidate_M3')}))


if __name__ == '__main__':
    main()
