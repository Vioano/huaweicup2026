"""One-shot macOS supervisor for the fixed case 044 prefix diagnostic.

This is a NEW independent admitted experiment. Invocation is intentionally not a
security boundary: run only after coordinated admission; never retry a reserved
output. Host limits are sampled tripwires, not kernel resource limits. Profiling
changes diagnostic wall time and cannot be reported as solver performance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import runpy
import signal
import subprocess
import sys
import time

from .construct import ROOT
from .feedback_benchmark import digest, read, verify_source, write

SCHEMA = 'q3-prefix-probe-v1'
BUDGET = {'workers': 1, 'max_prepare': 1, 'max_P3': 1, 'max_P2': 0,
          'max_Step3': 10, 'per_phase_seconds': 60, 'total_seconds': 120,
          'memory_limit_bytes': 536870912, 'retries': 0}
RESULT_ROOT = (ROOT / 'results/a/q3-nikolastarx').resolve()
GRAPH = ROOT / 'data/raw/a/official/data/case_044.json'
COUNT_LIMITS = {'P3': 1, 'P2': 0, 'Step1': 5, 'Step2': 5,
                'prepare_Step3': 5, 'step3_simulation': 5}


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def within_results(path, *, exists=False):
    resolved = Path(path).resolve(strict=exists)
    resolved.relative_to(RESULT_ROOT)
    return resolved


def load_manifest(path, expected_hash):
    path = within_results(path, exists=True)
    if not re.fullmatch(r'[0-9a-f]{64}', expected_hash) or digest(path) != expected_hash:
        raise ValueError('manifest byte identity differs')
    m = read(path)
    required = {'schema', 'source_commit', 'static_directory', 'static_summary_sha256',
                'plan_sha256', 'case_id', 'cores', 'budget'}
    if type(m) is not dict or set(m) != required or m['schema'] != SCHEMA:
        raise ValueError('unexpected manifest fields or schema')
    if not re.fullmatch(r'[0-9a-f]{40}', m['source_commit']):
        raise ValueError('source_commit must be a full SHA')
    for key in ('static_summary_sha256', 'plan_sha256'):
        if not re.fullmatch(r'[0-9a-f]{64}', m[key]):
            raise ValueError(f'invalid {key}')
    if m['case_id'] != '044' or type(m['cores']) is not int or m['cores'] != 5:
        raise ValueError('only case 044, five cores admitted')
    if type(m['budget']) is not dict or m['budget'] != BUDGET or any(
            type(m['budget'][key]) is not int for key in BUDGET):
        raise ValueError('budget must be exact fixed one-shot contract')
    static_name = m['static_directory']
    if (not isinstance(static_name, str) or not static_name.startswith('results/a/q3-nikolastarx/')
            or '\\' in static_name or ':' in static_name or '..' in static_name.split('/')):
        raise ValueError('static_directory must be a safe repository-relative result path')
    source = within_results(ROOT / static_name, exists=True)
    if digest(source / 'summary.json') != m['static_summary_sha256']:
        raise ValueError('static summary identity differs')
    summary = read(source / 'summary.json')
    if summary.get('status') != 'complete':
        raise ValueError('static summary is incomplete')
    recorded = summary.get('source_input_sha256')
    if not isinstance(recorded, dict) or not recorded:
        raise ValueError('static source-input identity missing')
    for name, expected in recorded.items():
        if (not isinstance(name, str) or name.startswith('/') or '..' in name.split('/')
                or not re.fullmatch(r'[0-9a-f]{64}', expected)
                or digest(ROOT / name) != expected):
            raise ValueError('static source-input bytes differ: ' + str(name))
    artifacts = summary.get('artifacts')
    if not isinstance(artifacts, dict) or 'case_044_multicore_res.json' not in artifacts:
        raise ValueError('static artifacts missing')
    for name, expected in artifacts.items():
        if (Path(name).name != name or not re.fullmatch(r'[0-9a-f]{64}', expected)
                or digest(source / name) != expected):
            raise ValueError('static artifact mismatch')
    if artifacts['case_044_multicore_res.json'] != m['plan_sha256']:
        raise ValueError('plan identity differs')
    plan = read(source / 'case_044_multicore_res.json')
    if set(plan) != {'node_to_subgraph', 'core_schedules'}:
        raise ValueError('plan has unexpected keys')
    return m, source, path


def observe():
    pressure = int(subprocess.check_output(
        ['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], text=True, timeout=5).strip())
    top = subprocess.check_output(['top', '-l', '1', '-n', '0'], text=True, timeout=8)
    line = next(x for x in top.splitlines() if x.startswith('PhysMem:'))
    match = re.search(r'([0-9.]+)([MG]) unused', line)
    if not match:
        raise RuntimeError('cannot parse macOS unused memory')
    unused = float(match.group(1)) * (1024 if match.group(2) == 'G' else 1)
    vm = subprocess.check_output(['vm_stat'], text=True, timeout=5)
    match = re.search(r'^Swapouts:\s+(\d+)', vm, re.M)
    if not match:
        raise RuntimeError('cannot parse macOS swapouts')
    return {'utc': utc(), 'pressure': pressure, 'unused_mib': unused,
            'swapouts': int(match.group(1)), 'physmem': line}


def group_rss(pgid):
    table = subprocess.check_output(['ps', '-A', '-o', 'pgid=,rss='], text=True, timeout=5)
    return sum(int(rss) * 1024 for group, rss in
               (line.split() for line in table.splitlines() if line.strip())
               if int(group) == pgid)


def kill_owned(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        return proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        return proc.wait(timeout=10)


def supervise(argv, output, phase, deadline, baseline_swapouts):
    samples = []
    start = time.monotonic()
    started_at = utc()
    reason = None
    proc = None
    with (output / f'{phase}.stdout.txt').open('xb') as stdout, (
            output / f'{phase}.stderr.txt').open('xb') as stderr:
        try:
            proc = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr,
                                    start_new_session=True, env={**os.environ, 'PYTHONUTF8': '1'})
            while True:
                now = time.monotonic()
                if now >= deadline or now - start >= BUDGET['per_phase_seconds']:
                    reason = 'deadline'
                    break
                observation = observe()
                observation['process_tree_rss_bytes'] = group_rss(proc.pid)
                samples.append(observation)
                if (observation['pressure'] != 1 or observation['unused_mib'] < 1024
                        or observation['swapouts'] > baseline_swapouts
                        or observation['process_tree_rss_bytes'] > BUDGET['memory_limit_bytes']):
                    reason = 'resource gate closed'
                    break
                if proc.poll() is not None:
                    break
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        except BaseException as error:
            reason = f'supervision failure or interrupt: {type(error).__name__}: {error}'
        finally:
            if proc is not None:
                exit_code = kill_owned(proc)
            else:
                exit_code = None
    return {'phase': phase, 'argv': argv, 'started_at': started_at,
            'wall_seconds': time.monotonic() - start, 'exit_code': exit_code,
            'stop_reason': reason, 'samples': samples,
            'status': 'complete' if reason is None and exit_code == 0 else 'failed'}


def scoring_worker(manifest_path, output, manifest_hash):
    output = within_results(output, exists=True)
    m, source, _ = load_manifest(manifest_path, manifest_hash)
    verify_source(m['source_commit'], {'044'})
    reservation = read(output / 'score-reservation.json')
    if not (output / 'run.json').is_file():
        raise ValueError('supervisor run receipt missing')
    if reservation != {'manifest_sha256': manifest_hash, 'max_P3': 1, 'max_P2': 0,
                       'max_Step3': 5, 'status': 'reserved'}:
        raise ValueError('score reservation differs')
    # Claim once before any official call. A crashed worker cannot be relaunched
    # against the same reservation and silently spend a second P3 invocation.
    with (output / 'score-worker-claim.json').open('x', encoding='utf-8') as stream:
        json.dump({'manifest_sha256': manifest_hash, 'claimed_at': utc()}, stream)
    # Import exact original functions for code-object identity. The oracle module
    # then runs unmodified through its public main entrypoint under this observer.
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3
    from schedule_step1 import step1_schedule
    from schedule_step2 import step2_spill_insertion
    from schedule_step3 import prepare_step3_execution, step3_simulation
    watched = {evaluate_problem_3.__code__: 'P3', evaluate_scene_b.__code__: 'P2',
               step1_schedule.__code__: 'Step1', step2_spill_insertion.__code__: 'Step2',
               prepare_step3_execution.__code__: 'prepare_Step3',
               step3_simulation.__code__: 'step3_simulation'}
    counts = dict.fromkeys(COUNT_LIMITS, 0)
    receipt = {'status': 'running', 'counts_started': counts, 'limits': COUNT_LIMITS,
               'manifest_sha256': manifest_hash, 'started_at': utc(),
               'scope': 'unchanged oracle P3 with exact official code-object call starts'}
    write(output / 'score-worker.json', receipt)

    def observer(frame, event, _arg):
        if event != 'call':
            return
        name = watched.get(frame.f_code)
        if name is not None:
            counts[name] += 1
            write(output / 'score-worker.json', receipt)  # durable before official call begins
            if counts[name] > COUNT_LIMITS[name]:
                raise RuntimeError(f'official {name} invocation limit exceeded')

    old_argv = sys.argv
    old_profile = sys.getprofile()
    if old_profile is not None:
        raise RuntimeError('unexpected existing profiler')
    start = time.monotonic()
    try:
        sys.argv = ['src.q3.oracle', str(GRAPH), str(source / 'case_044_multicore_res.json'),
                    '3', str(output / 'official-p3.json.gz')]
        sys.setprofile(observer)
        runpy.run_module('src.q3.oracle', run_name='__main__')
        if counts != COUNT_LIMITS:
            raise ValueError(f'unexpected official invocation counts: {counts}')
        receipt['official_result_sha256'] = digest(output / 'official-p3.json.gz')
        receipt['status'] = 'complete'
    except BaseException as error:
        receipt.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        sys.setprofile(old_profile)
        sys.argv = old_argv
        receipt.update(finished_at=utc(), diagnostic_wall_seconds=time.monotonic() - start)
        write(output / 'score-worker.json', receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--admission-reference', required=True)
    args = parser.parse_args()
    if sys.platform != 'darwin':
        raise RuntimeError('macOS host observation required')
    if not args.admission_reference.strip() or len(args.admission_reference) > 500:
        raise ValueError('nonempty bounded admission reference required')
    m, source, manifest_path = load_manifest(args.manifest, args.manifest_sha256)
    official, inputs = verify_source(m['source_commit'], {'044'})
    output = within_results(args.output)
    if output.exists() or not output.parent.is_dir():
        raise FileExistsError('one-shot output exists or parent is absent')
    preflight_path = output.with_name(output.name + '.preflight.json')
    if preflight_path.exists():
        raise FileExistsError('preflight already exists; no automatic retry')
    before = [observe(), observe()]
    ready = all(x['pressure'] == 1 and x['unused_mib'] >= 1536 for x in before)
    ready = ready and before[0]['swapouts'] == before[1]['swapouts']
    preflight = {'ready': ready, 'observations': before, 'admission_reference': args.admission_reference,
                 'manifest_sha256': args.manifest_sha256, 'source_commit': m['source_commit'],
                 'supervisor_sha256': digest(__file__), 'created_at': utc(),
                 'scope': 'macOS sampled resource preflight; no workload when false'}
    with preflight_path.open('x', encoding='utf-8') as stream:
        json.dump(preflight, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    if not ready:
        print(json.dumps({'status': 'not_admitted', 'preflight': str(preflight_path)}))
        return
    output.mkdir(exist_ok=False)
    deadline = time.monotonic() + BUDGET['total_seconds']
    report = {'status': 'running', 'source_commit': m['source_commit'],
              'manifest_sha256': args.manifest_sha256, 'static_summary_sha256': m['static_summary_sha256'],
              'plan_sha256': m['plan_sha256'], 'official_code_sha256': official,
              'source_input_sha256': inputs, 'admission_reference': args.admission_reference,
              'budget': BUDGET, 'started_at': utc(), 'phases': [],
              'scope': 'one new independent prepare plus at most one P3; diagnostic overhead included'}
    write(output / 'run.json', report)
    try:
        # Reserve the five Step3 preparations before dispatch, even if child fails.
        report['prepare_reservation'] = {'max_prepare': 1, 'max_Step3': 5, 'status': 'reserved'}
        write(output / 'run.json', report)
        prepare = supervise([sys.executable, '-B', '-m', 'src.q3.pipeline_prefix_prepare',
                             str(source), str(output / 'prepare'), '--source', m['source_commit'],
                             '--static-summary-sha256', m['static_summary_sha256']],
                            output, 'prepare', deadline, before[-1]['swapouts'])
        report['phases'].append(prepare)
        write(output / 'run.json', report)
        if prepare['status'] != 'complete':
            raise RuntimeError('prepare phase failed')
        prepared = read(output / 'prepare/run.json')
        if (prepared.get('status') != 'complete' or prepared.get('calls_started') !=
                {'Step1': 5, 'Step2': 5, 'Step3': 5} or prepared.get('new_P2') != 0
                or prepared.get('new_P3') != 0 or prepared.get('static_summary_sha256') != m['static_summary_sha256']
                or not prepared.get('prepared_sha256')
                or digest(output / 'prepare/prepared.json.gz') != prepared['prepared_sha256']
                or prepared.get('traffic', {}).get('spill_added_copy_bytes') != 0
                or len(prepared.get('checks', [])) != 5
                or not all(all(row['checks'].values()) for row in prepared['checks'])):
            raise RuntimeError('prepare receipt or prefix checks failed; scoring forbidden')
        if time.monotonic() >= deadline:
            raise RuntimeError('whole-run deadline before scoring')
        observation = observe()
        if (observation['pressure'] != 1 or observation['unused_mib'] < 1024
                or observation['swapouts'] > before[-1]['swapouts']):
            raise RuntimeError('resource gate closed before scoring')
        reservation = {'manifest_sha256': args.manifest_sha256, 'max_P3': 1,
                       'max_P2': 0, 'max_Step3': 5, 'status': 'reserved'}
        write(output / 'score-reservation.json', reservation)
        report['score_reservation'] = reservation
        write(output / 'run.json', report)
        score = supervise([sys.executable, '-B', '-m', 'src.q3.pipeline_prefix_probe',
                           '--score-worker', str(manifest_path), str(output), args.manifest_sha256],
                          output, 'score', deadline, before[-1]['swapouts'])
        report['phases'].append(score)
        write(output / 'run.json', report)
        if score['status'] != 'complete':
            raise RuntimeError('score phase failed')
        worker = read(output / 'score-worker.json')
        if (worker.get('status') != 'complete' or worker.get('counts_started') != COUNT_LIMITS
                or digest(output / 'official-p3.json.gz') != worker.get('official_result_sha256')):
            raise RuntimeError('score receipt or result differs')
        report['official_result_sha256'] = worker['official_result_sha256']
        report['status'] = 'complete'
    except BaseException as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        report['finished_at'] = utc()
        write(output / 'run.json', report)


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--score-worker':
        scoring_worker(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4])
    else:
        main()
