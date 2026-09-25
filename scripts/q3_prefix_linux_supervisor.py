"""External Linux one-shot supervisor for the frozen case 044 prefix probe.

Run this file by absolute path with cwd at the clean 62c69b20 checkout. The
child arms Linux parent-death SIGKILL before exec, covering the brief interval
before active-pgid and watchdog startup; the official worker does not spawn
subprocesses. Separate watchdogs kill the group on parent EOF or deadlines.
RSS is sampled, not a kernel hard limit, so a short spike may escape sampling.
No official work occurs in --validate-only mode.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

SOURCE = '62c69b20ab887c76567dbab5fcce6eef30107b5c'
MANIFEST_SHA = 'b2ec66eb5e4e0777519c09a3f8937e5df514e1fc6372e1a88e3aa369af9c9a14'
MI_B = 1024 * 1024
ROOT = Path.cwd().resolve()


def modules():
    sys.path.insert(0, str(ROOT))
    from src.q3 import pipeline_prefix_probe as probe
    from src.q3.feedback_benchmark import digest, read, verify_source, write
    return probe, digest, read, verify_source, write


def watchdog(read_fd, pgid, seconds):
    """Independent parent-death and phase-deadline guard."""
    deadline = time.monotonic() + seconds
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            readable, _, _ = select.select([read_fd], [], [], min(remaining, 0.1))
            if readable:
                if not os.read(read_fd, 1):
                    break
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    finally:
        os.close(read_fd)


def whole_watchdog(read_fd, active_file, seconds):
    """Guard the full two-stage window even while the parent is between phases."""
    deadline = time.monotonic() + seconds
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            readable, _, _ = select.select([read_fd], [], [], min(remaining, 0.1))
            if readable and not os.read(read_fd, 1):
                break
        try:
            pgid = int(Path(active_file).read_text())
        except (FileNotFoundError, ValueError):
            return
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    finally:
        os.close(read_fd)


def host_observation():
    mem = Path('/proc/meminfo').read_text()
    vm = Path('/proc/vmstat').read_text()
    available = next(int(x.split()[1]) for x in mem.splitlines() if x.startswith('MemAvailable:'))
    swapouts = next(int(x.split()[1]) for x in vm.splitlines() if x.startswith('pswpout '))
    return {'mem_available_mib': available / 1024, 'swapouts': swapouts}


def group_rss(pgid):
    table = subprocess.check_output(['ps', '-e', '-o', 'pgid=,rss='], text=True, timeout=5)
    total = 0
    for line in table.splitlines():
        fields = line.split()
        if len(fields) == 2 and int(fields[0]) == pgid:
            total += int(fields[1]) * 1024
    return total


def kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        return proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        return proc.wait(timeout=5)


def arm_parent_death_signal(parent_pid):
    """Executed only in the forked Linux child before its target exec."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), 'prctl(PR_SET_PDEATHSIG) failed')
    if os.getppid() != parent_pid:
        os.kill(os.getpid(), signal.SIGKILL)


def supervise(argv, output, phase, total_deadline, baseline_swapouts, budget):
    start = time.monotonic()
    phase_seconds = min(budget['per_phase_seconds'], max(0, total_deadline - start))
    samples = []
    reason = None
    proc = guard = None
    read_fd = write_fd = None
    exit_code = None
    with (output / f'{phase}.stdout.txt').open('xb') as stdout, (
            output / f'{phase}.stderr.txt').open('xb') as stderr:
        try:
            if phase_seconds <= 0:
                raise TimeoutError('whole-run deadline before phase')
            parent_pid = os.getpid()
            proc = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr,
                                    start_new_session=True, env={**os.environ, 'PYTHONUTF8': '1'},
                                    preexec_fn=lambda: arm_parent_death_signal(parent_pid))
            (output / 'active-pgid').write_text(str(proc.pid))
            read_fd, write_fd = os.pipe()
            guard = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                                      '--watchdog', str(read_fd), str(proc.pid), str(phase_seconds)],
                                     pass_fds=(read_fd,), start_new_session=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.close(read_fd)
            read_fd = None
            while True:
                observation = host_observation()
                observation['group_rss_bytes'] = group_rss(proc.pid)
                observation['elapsed_seconds'] = time.monotonic() - start
                samples.append(observation)
                if observation['mem_available_mib'] < 1024 or observation['swapouts'] > baseline_swapouts or observation['group_rss_bytes'] > budget['memory_limit_bytes']:
                    reason = 'resource gate closed'
                    break
                if time.monotonic() - start >= phase_seconds or time.monotonic() >= total_deadline:
                    reason = 'deadline'
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
        except BaseException as error:
            reason = f'supervision failure or interrupt: {type(error).__name__}: {error}'
        finally:
            if proc is not None:
                try:
                    exit_code = kill_group(proc)
                    (output / 'active-pgid').unlink(missing_ok=True)
                except BaseException as error:
                    reason = f'cleanup failure: {type(error).__name__}: {error}'
            if write_fd is not None:
                os.close(write_fd)
            if read_fd is not None:
                os.close(read_fd)
            if guard is not None:
                try:
                    guard.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    guard.kill()
                    guard.wait(timeout=5)
                    reason = 'watchdog did not exit cleanly'
    return {'phase': phase, 'argv': argv, 'wall_seconds': time.monotonic() - start,
            'exit_code': exit_code, 'stop_reason': reason, 'samples': samples,
            'cleanup': 'process group killed and watchdog reaped' if proc is not None else 'no child started',
            'status': 'complete' if reason is None and exit_code == 0 else 'failed'}


def validated(manifest_path, manifest_hash):
    if sys.platform != 'linux':
        raise RuntimeError('Linux cwd required')
    if Path(__file__).resolve().is_relative_to(ROOT):
        raise RuntimeError('supervisor must be outside frozen checkout')
    probe, digest, read, verify_source, write = modules()
    if manifest_hash != MANIFEST_SHA:
        raise ValueError('frozen manifest SHA differs')
    m, source, path = probe.load_manifest(manifest_path, manifest_hash)
    if m['source_commit'] != SOURCE:
        raise ValueError('frozen source SHA differs')
    official, inputs = verify_source(SOURCE, {'044'})
    return probe, digest, read, write, m, source, path, official, inputs


def run(manifest_path, output_path, manifest_hash, admission_ref, validate_only=False):
    probe, digest, read, write, m, source, manifest_path, official, inputs = validated(manifest_path, manifest_hash)
    if validate_only:
        return {'status': 'validated', 'source_commit': SOURCE, 'manifest_sha256': manifest_hash,
                'official_code_sha256': official, 'source_input_sha256': inputs}
    if not admission_ref or len(admission_ref) > 500:
        raise ValueError('admission reference required')
    output = probe.within_results(output_path)
    if output.exists() or not output.parent.is_dir():
        raise FileExistsError('one-shot output exists or parent is absent')
    preflight_path = output.with_name(output.name + '.preflight.json')
    if preflight_path.exists():
        raise FileExistsError('preflight already exists; no retry')
    before = [host_observation(), host_observation()]
    ready = all(x['mem_available_mib'] >= 1536 for x in before) and before[0]['swapouts'] == before[1]['swapouts']
    preflight = {'ready': ready, 'observations': before, 'admission_reference': admission_ref,
                 'manifest_sha256': manifest_hash, 'supervisor_sha256': digest(__file__),
                 'scope': 'Linux sampled preflight; no workload when false'}
    with preflight_path.open('x', encoding='utf-8') as stream:
        json.dump(preflight, stream, indent=2)
    if not ready:
        return {'status': 'not_admitted', 'preflight': str(preflight_path)}
    output.mkdir(exist_ok=False)
    deadline = time.monotonic() + m['budget']['total_seconds']
    report = {'status': 'running', 'source_commit': SOURCE, 'manifest_sha256': manifest_hash,
              'static_summary_sha256': m['static_summary_sha256'], 'plan_sha256': m['plan_sha256'],
              'official_code_sha256': official, 'source_input_sha256': inputs,
              'admission_reference': admission_ref, 'budget': m['budget'], 'phases': [],
              'started_at': probe.utc(), 'supervisor_sha256': digest(__file__),
              'resource_semantics': 'Linux MemAvailable and process-group RSS sampled tripwires',
              'environment': {'uname': tuple(os.uname()), 'python': sys.version,
                              'cpu_count': os.cpu_count(), 'cwd': str(ROOT),
                              'python_executable': sys.executable}}
    write(output / 'run.json', report)
    whole_read, whole_write = os.pipe()
    try:
        whole_guard = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                                        '--whole-watchdog', str(whole_read),
                                        str(output / 'active-pgid'), str(m['budget']['total_seconds'])],
                                       pass_fds=(whole_read,), start_new_session=True,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except BaseException:
        os.close(whole_read)
        os.close(whole_write)
        report.update(status='failed', error='whole-run watchdog failed to start', finished_at=probe.utc())
        write(output / 'run.json', report)
        raise
    os.close(whole_read)
    try:
        report['prepare_reservation'] = {'max_prepare': 1, 'max_Step3': 5, 'status': 'reserved'}
        write(output / 'run.json', report)
        prepare = supervise([sys.executable, '-B', '-m', 'src.q3.pipeline_prefix_prepare',
                             str(source), str(output / 'prepare'), '--source', SOURCE,
                             '--static-summary-sha256', m['static_summary_sha256']],
                            output, 'prepare', deadline, before[-1]['swapouts'], m['budget'])
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
        obs = host_observation()
        if obs['mem_available_mib'] < 1024 or obs['swapouts'] > before[-1]['swapouts']:
            raise RuntimeError('resource gate closed before scoring')
        reservation = {'manifest_sha256': manifest_hash, 'max_P3': 1,
                       'max_P2': 0, 'max_Step3': 5, 'status': 'reserved'}
        write(output / 'score-reservation.json', reservation)
        report['score_reservation'] = reservation
        write(output / 'run.json', report)
        score = supervise([sys.executable, '-B', '-m', 'src.q3.pipeline_prefix_probe',
                           '--score-worker', str(manifest_path), str(output), manifest_hash],
                          output, 'score', deadline, before[-1]['swapouts'], m['budget'])
        report['phases'].append(score)
        write(output / 'run.json', report)
        if score['status'] != 'complete':
            raise RuntimeError('score phase failed')
        worker = read(output / 'score-worker.json')
        if (worker.get('status') != 'complete' or worker.get('counts_started') != probe.COUNT_LIMITS
                or digest(output / 'official-p3.json.gz') != worker.get('official_result_sha256')):
            raise RuntimeError('score receipt or result differs')
        report['official_result_sha256'] = worker['official_result_sha256']
        report['status'] = 'complete'
    except BaseException as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        os.close(whole_write)
        try:
            whole_guard.wait(timeout=5)
        except subprocess.TimeoutExpired:
            whole_guard.kill()
            whole_guard.wait(timeout=5)
            report.update(status='failed', error='whole-run watchdog did not exit cleanly')
        report['finished_at'] = probe.utc()
        write(output / 'run.json', report)
    return report


def main():
    if len(sys.argv) == 5 and sys.argv[1] == '--watchdog':
        watchdog(int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]))
        return
    if len(sys.argv) == 5 and sys.argv[1] == '--whole-watchdog':
        whole_watchdog(int(sys.argv[2]), sys.argv[3], float(sys.argv[4]))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--admission-ref')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.output, args.manifest_sha256,
                         args.admission_ref, args.validate_only), default=str))


if __name__ == '__main__':
    main()
