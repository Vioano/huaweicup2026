"""Frozen one-candidate Linux mechanism test, with conditional same-plan pairs.

One prepare, one P3, and only after strict M improvement two P2 evaluations.
Diagnostic wall time is not solver latency. No automatic retries or new plans.
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tarfile
import time

from .feedback_benchmark import digest, read, verify_source, write, utc

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'results/a/q3-nikolastarx'
OLD_ARCHIVE = BASE / 'pipeline-prefix-linux-20260925/run-local/evidence.tar.gz'
OLD_ARCHIVE_SHA = 'a923a07fc1ad549eecaae227e534d7a7de83ef1647a67a60a70d130c4aef8b05'
OLD_RESULT_SHA = 'd4cdf8dbabe22923b9a74329741fb39e74a588e619d9f101db1fd28ecd629da1'
OLD_PLAN = BASE / 'pipeline-prefix-static-20260925/case_044_multicore_res.json'


def control_result():
    if digest(OLD_ARCHIVE) != OLD_ARCHIVE_SHA:
        raise ValueError('historical control archive identity differs')
    import hashlib
    with tarfile.open(OLD_ARCHIVE) as archive:
        raw = archive.extractfile('probe/official-p3.json.gz').read()
    if hashlib.sha256(raw).hexdigest() != OLD_RESULT_SHA:
        raise ValueError('historical result identity differs')
    result = json.loads(gzip.decompress(raw))
    if result['makespan'] != 38024 or result['num_cores'] != 5:
        raise ValueError('historical control coordinate differs')
    return result


def limits(problem):
    return {'P3': int(problem == 3), 'P2': int(problem == 2),
            'Step1': 5, 'Step2': 5, 'prepare_Step3': 5, 'step3_simulation': 5}


def score_worker(candidate, output, source, manifest_hash, phase):
    from .partial_preload_prepare import load_candidate
    m, *_ = load_candidate(candidate, manifest_hash)
    verify_source(source, {'044'})
    problem = 3 if phase == 'candidate-p3' else 2
    if phase not in ('candidate-p3', 'candidate-p2', 'control-p2'):
        raise ValueError('unreserved scoring phase')
    cap = limits(problem)
    reservation = read(output / f'{phase}.reservation.json')
    if reservation != {'phase': phase, 'source': source, 'manifest_sha256': manifest_hash,
                        'limits': cap}:
        raise ValueError('scoring reservation differs')
    with (output / f'{phase}.claim.json').open('x') as stream:
        json.dump({'claimed_at': utc(), 'phase': phase}, stream)
    sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3
    from schedule_step1 import step1_schedule
    from schedule_step2 import step2_spill_insertion
    from schedule_step3 import prepare_step3_execution, step3_simulation
    watched = {evaluate_scene_b.__code__: 'P2', evaluate_problem_3.__code__: 'P3',
               step1_schedule.__code__: 'Step1', step2_spill_insertion.__code__: 'Step2',
               prepare_step3_execution.__code__: 'prepare_Step3',
               step3_simulation.__code__: 'step3_simulation'}
    counts = dict.fromkeys(cap, 0)
    plan = OLD_PLAN if phase == 'control-p2' else candidate / 'case_044_multicore_res.json'
    receipt = {'status': 'running', 'phase': phase, 'source_commit': source,
               'manifest_sha256': manifest_hash, 'counts_started': counts, 'limits': cap,
               'plan_sha256': digest(plan), 'started_at': utc()}
    path = output / f'{phase}.worker.json'
    write(path, receipt)

    def observe(frame, event, value):
        if event == 'call' and frame.f_code in watched:
            key = watched[frame.f_code]
            counts[key] += 1
            write(path, receipt)
            if counts[key] > cap[key]:
                raise RuntimeError('official call budget exceeded: ' + key)

    before = sys.getprofile()
    if before is not None:
        raise RuntimeError('unexpected existing profile')
    old_argv = sys.argv
    started = time.monotonic()
    result = output / f'{phase}.json.gz'
    try:
        sys.argv = ['src.q3.oracle', str(ROOT / 'data/raw/a/official/data/case_044.json'),
                    str(plan), str(problem), str(result)]
        sys.setprofile(observe)
        runpy.run_module('src.q3.oracle', run_name='__main__')
        if counts != cap:
            raise ValueError('unexpected official call counts')
        receipt.update(status='complete', result_sha256=digest(result))
    except BaseException as error:
        receipt.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        sys.setprofile(before)
        sys.argv = old_argv
        receipt.update(finished_at=utc(), diagnostic_wall_seconds=time.monotonic() - started)
        write(path, receipt)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--source', required=True)
    p.add_argument('--manifest-sha256', required=True)
    p.add_argument('--admission-ref')
    p.add_argument('--validate-only', action='store_true')
    p.add_argument('--score-worker', choices=['candidate-p3', 'candidate-p2', 'control-p2'])
    a = p.parse_args()
    candidate = a.candidate.resolve(strict=True)
    output = a.output.resolve()
    candidate.relative_to(BASE)
    output.relative_to(BASE)
    if a.score_worker:
        score_worker(candidate, output, a.source, a.manifest_sha256, a.score_worker)
        return
    from .partial_preload_prepare import load_candidate
    m, *_ = load_candidate(candidate, a.manifest_sha256)
    official, inputs = verify_source(a.source, {'044'})
    baseline = control_result()
    if a.validate_only:
        print(json.dumps({'status': 'validated', 'official_calls': 0,
                          'manifest_sha256': a.manifest_sha256, 'old_M': baseline['makespan']}))
        return
    if sys.platform != 'linux' or not a.admission_ref or Path.cwd().resolve() != ROOT:
        raise ValueError('Linux and coordinated admission required')
    from scripts.q3_prefix_linux_supervisor import supervise, host_observation
    supervisor_path = ROOT / 'scripts/q3_prefix_linux_supervisor.py'
    if output.exists():
        raise FileExistsError('one-shot output already exists; never retry')
    output.mkdir(parents=False, exist_ok=False)
    initial = [host_observation(), host_observation()]
    ready = (all(x['mem_available_mib'] >= 1536 for x in initial)
             and initial[0]['swapouts'] == initial[1]['swapouts'])
    report = {'status': 'reserved' if ready else 'not_admitted', 'started_at': utc(),
              'source_commit': a.source, 'manifest_sha256': a.manifest_sha256,
              'admission_reference': a.admission_ref, 'budget': m['budget'],
              'official_code_sha256': official, 'source_input_sha256': inputs,
              'phases': [], 'reservations': [], 'preflight': initial,
              'control_result_sha256': OLD_RESULT_SHA,
              'environment': {'python': sys.version, 'uname': tuple(os.uname()),
                              'cpu_count': os.cpu_count()},
              'timing_scope': 'diagnostic preparation/scoring; solver_wall_seconds unknown'}
    write(output / 'run.json', report)
    if not ready:
        return
    deadline = time.monotonic() + m['budget']['total_seconds']
    rfd, wfd = os.pipe()
    try:
        guard = subprocess.Popen([sys.executable, '-B', str(supervisor_path), '--whole-watchdog',
                                  str(rfd), str(output / 'active-pgid'),
                                  str(m['budget']['total_seconds'])], pass_fds=(rfd,),
                                 start_new_session=True)
    except BaseException as error:
        os.close(rfd)
        os.close(wfd)
        report.update(status='failed', error=f'watchdog launch failed: {error}', finished_at=utc())
        write(output / 'run.json', report)
        raise
    os.close(rfd)
    common = [str(candidate), str(output), '--source', a.source,
              '--manifest-sha256', a.manifest_sha256]

    def run_phase(label, argv):
        # Record the invocation before dispatch. Failure consumes its slot.
        report['reservations'].append(label)
        write(output / 'run.json', report)
        result = supervise(argv, output, label, deadline, initial[-1]['swapouts'], m['budget'])
        report['phases'].append(result)
        write(output / 'run.json', report)
        if result['status'] != 'complete':
            raise RuntimeError('failed phase: ' + label)

    def score(label):
        problem = 3 if label == 'candidate-p3' else 2
        write(output / f'{label}.reservation.json',
              {'phase': label, 'source': a.source, 'manifest_sha256': a.manifest_sha256,
               'limits': limits(problem)})
        run_phase(label, [sys.executable, '-B', '-m', 'src.q3.partial_preload_probe',
                          *common, '--score-worker', label])
        receipt = read(output / f'{label}.worker.json')
        path = output / f'{label}.json.gz'
        if (receipt['status'] != 'complete' or receipt['counts_started'] != limits(problem)
                or digest(path) != receipt['result_sha256']):
            raise ValueError('scoring receipt mismatch')
        return read(path)

    try:
        run_phase('prepare', [sys.executable, '-B', '-m', 'src.q3.partial_preload_prepare',
                              str(candidate), str(output / 'prepare'), '--source', a.source,
                              '--manifest-sha256', a.manifest_sha256])
        prep = read(output / 'prepare/run.json')
        if (prep['status'] != 'complete' or prep['counts_started'] !=
                {'Step1': 5, 'Step2': 5, 'Step3': 5, 'Task': 1} or
                digest(output / 'prepare/prepared.json.gz') != prep['prepared_sha256']):
            raise ValueError('preparation receipt mismatch')
        current = score('candidate-p3')
        report['candidate_M'] = current['makespan']
        report['control_M'] = baseline['makespan']
        if current['makespan'] < baseline['makespan']:
            paired = score('candidate-p2')
            old_pair = score('control-p2')
            report.update(candidate_G=paired['makespan'] / current['makespan'],
                          control_G=old_pair['makespan'] / baseline['makespan'])
        else:
            report.update(candidate_G=None, control_G=None,
                          pair_stop='no strict M improvement; two conditional P2 slots unspent')
        report.update(status='complete', candidate_data_movement=current['data_movement_bytes'],
                      control_data_movement=baseline['data_movement_bytes'],
                      candidate_cache_stats=current['cache_stats'],
                      control_cache_stats=baseline['cache_stats'])
    except BaseException as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        os.close(wfd)
        try:
            guard.wait(timeout=5)
        except subprocess.TimeoutExpired:
            guard.kill()
            guard.wait(timeout=5)
            report.update(status='failed', error='whole watchdog cleanup failed')
        report['finished_at'] = utc()
        write(output / 'run.json', report)
    print(json.dumps({k: report.get(k) for k in ['status', 'candidate_M', 'control_M',
                                                'candidate_G', 'control_G']}))


if __name__ == '__main__':
    main()
