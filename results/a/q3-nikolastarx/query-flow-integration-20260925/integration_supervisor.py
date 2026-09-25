"""One-window resource supervisor for the reviewed integration manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import resource_supervisor as identity_guard
import integration_runner as runner

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LIMIT_RSS = 2 * 1024**3
LIMIT_SWAP_DELTA_MIB = 256
MIN_DISK = 10 * 1024**3

def snapshot(observed, parent=None, parent_identity=None):
    rows = identity_guard.processes()
    live = identity_guard.current_owned(rows, observed, parent, parent_identity)
    pressure = int(identity_guard.command(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level']).strip())
    swap_text = identity_guard.command(['sysctl', '-n', 'vm.swapusage'])
    swap_used = float(re.search(r'used\s*=\s*([0-9.]+)M', swap_text)[1])
    swap_free = float(re.search(r'free\s*=\s*([0-9.]+)M', swap_text)[1])
    vm = identity_guard.command(['vm_stat'])
    page_size = int(re.search(r'page size of (\d+) bytes', vm)[1])
    free_bytes = int(re.search(r'Pages free:\s*(\d+)', vm)[1]) * page_size
    other = [r for r in rows if r['pid'] not in live and r['pid'] != os.getpid()
             and any(s in r['args'] for s in ('src.q1.', 'src.q2.', 'src.q3.',
                                              'evaluate_problem', 'evaluate_scene',
                                              'benchmark_runner', 'batch_runner'))
             and 'python' in r['comm'].lower()]
    return {'utc': identity_guard.now(), 'pressure_level': pressure,
            'physical_free_bytes': free_bytes, 'swap_used_mib': swap_used,
            'swap_free_mib': swap_free,
            'disk_free_bytes': shutil.disk_usage(ROOT).free,
            'owned_rss_bytes': sum(r['rss_kib'] for r in rows if r['pid'] in live) * 1024,
            'owned_processes': [r for r in rows if r['pid'] in live], 'other_scorers': other}

def guard(entry, swap_t0, *, start=False):
    if entry['pressure_level'] != 1:
        return 'memory pressure is not level 1'
    if entry['other_scorers']:
        return 'another scorer detected'
    if entry['disk_free_bytes'] < MIN_DISK:
        return 'disk free below 10GiB'
    if not start and entry['owned_rss_bytes'] > LIMIT_RSS:
        return 'owned group RSS above 2GiB'
    if not start and entry['swap_used_mib'] - swap_t0 > LIMIT_SWAP_DELTA_MIB:
        return 'swap used rose above 256MiB from T0'
    return None

def write(control, name, value):
    (control / name).write_text(json.dumps(value, indent=2) + '\n')

def terminal_cleanup(observed, exited_parent):
    """Ignore only the already-exited parent row; verify all remaining groups."""
    rows = [r for r in identity_guard.processes() if r['pid'] != exited_parent]
    unknown = [r['pid'] for r in rows if str(HERE / 'run') in r.get('args', '')
               and r['pid'] not in observed]
    if unknown:
        raise RuntimeError(f'unobserved run process after parent exit: {unknown}')
    groups = {r['pgid'] for r in rows if r['pgid'] in observed}
    verified = []
    for group in sorted(groups):
        members = [r for r in rows if r['pgid'] == group]
        if group == os.getpgrp() or not any(r['pid'] == group for r in members):
            raise RuntimeError(f'terminal group leader unverified: {group}')
        if any(r['pid'] not in observed or identity_guard.identity(r['pid']) != observed[r['pid']]
               for r in members):
            raise RuntimeError(f'terminal group identity unverified: {group}')
        verified.append(group)
    for group in verified:
        current = [r for r in identity_guard.processes()
                   if r['pid'] != exited_parent and r['pgid'] == group]
        if not current or not any(r['pid'] == group for r in current) or any(
                r['pid'] not in observed or identity_guard.identity(r['pid']) != observed[r['pid']]
                for r in current):
            raise RuntimeError(f'terminal group changed before signal: {group}')
        os.killpg(group, signal.SIGKILL)
    return verified

def finish_exited(child, observed, report):
    report['terminal_branch'] = 'parent_exited'
    try:
        stopped = terminal_cleanup(observed, child.pid)
        if stopped:
            report['cleanup_error'] = f'exited parent left verified groups; stopped {stopped}'
    finally:
        child.wait(timeout=10)
    report['status'] = ('complete' if report.get('status') == 'running'
                        and child.returncode == 0 and 'cleanup_error' not in report else 'failed')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    delivery_head = runner.verify_manifest(manifest)
    if manifest.get('execution_authorized') is not True or not manifest.get('authorization_ref'):
        raise PermissionError('integration window has no approval')
    actual = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if actual != manifest['supervisor_sha256']:
        raise ValueError('supervisor SHA differs')
    run = (ROOT / manifest['output']).resolve()
    if not run.is_relative_to(ROOT) or run.exists():
        raise ValueError('run output already exists or escapes repository')
    control = HERE / 'integration-control'
    control.mkdir(exist_ok=False)
    report = {'status': 'preflight', 'manifest_sha256': runner.sha(args.manifest),
              'supervisor_sha256': actual, 'sample_interval_seconds': 1,
              'delivery_head': delivery_head, 'frozen_solver_commit': runner.SOURCE,
              'frozen_solver_sha256': manifest['inputs']['src/q3/query_flow_solve.py'],
              'budget': manifest['budget'], 'resource_policy': 'proposal_pending_scheduler_approval'}
    write(control, 'receipt.json', report)
    observed = {}
    child = None
    parent_identity = None
    started = time.monotonic()  # Includes initial observation, launch, monitoring, and final observation.
    try:
        initial = snapshot(observed)
        with (control / 'samples.jsonl').open('a') as stream:
            stream.write(json.dumps(initial) + '\n')
        reason = guard(initial, initial['swap_used_mib'], start=True)
        if reason:
            report.update(status='not_started', error=reason)
            return
        cmd = [sys.executable, '-B', str(HERE / 'integration_runner.py'),
               '--manifest', str(args.manifest.resolve())]
        if cmd != manifest['runner_command']:
            raise ValueError('runner command differs')
        report.update(status='running', command=cmd, T0=identity_guard.now(),
                      swap_used_t0_mib=initial['swap_used_mib'])
        write(control, 'receipt.json', report)
        with (control / 'stdout.txt').open('x') as stdout, (control / 'stderr.txt').open('x') as stderr:
            child = subprocess.Popen(cmd, cwd=ROOT, stdout=stdout, stderr=stderr,
                                     start_new_session=True)
            parent_identity = identity_guard.identity(child.pid)
            if parent_identity is None:
                if identity_guard.exit_event(child):
                    finish_exited(child, observed, report)
                    report.update(exit_code=child.returncode, T1=identity_guard.now())
                    return
                raise RuntimeError('new child start identity unavailable')
            observed[child.pid] = parent_identity
            report.update(parent_pid=child.pid, parent_start_identity=parent_identity)
            while True:
                tick = time.monotonic()
                if identity_guard.exit_event(child):
                    finish_exited(child, observed, report)
                    break
                try:
                    entry = snapshot(observed, child.pid, parent_identity)
                except RuntimeError:
                    if not identity_guard.exit_event(child):
                        raise
                    finish_exited(child, observed, report)
                    break
                with (control / 'samples.jsonl').open('a') as stream:
                    stream.write(json.dumps(entry) + '\n')
                reason = guard(entry, initial['swap_used_mib'])
                if time.monotonic() - started >= 600:
                    reason = 'whole-window 600-second deadline'
                if identity_guard.exit_event(child):
                    if reason:
                        report.update(status='resource_stopped', error=reason)
                    finish_exited(child, observed, report)
                    break
                if reason:
                    report.update(status='resource_stopped', error=reason)
                    identity_guard.kill_owned(observed, child.pid, parent_identity)
                    child.wait(timeout=10)
                    break
                time.sleep(max(0, 1 - (time.monotonic() - tick)))
        report.update(exit_code=child.returncode, T1=identity_guard.now())
    except BaseException as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        if child is not None and child.returncode is None and parent_identity is not None:
            try:
                if identity_guard.exit_event(child):
                    finish_exited(child, observed, report)
                else:
                    identity_guard.kill_owned(observed, child.pid, parent_identity)
                    child.wait(timeout=10)
            except BaseException as cleanup_error:
                report['cleanup_error'] = f'{type(cleanup_error).__name__}: {cleanup_error}'
        raise
    finally:
        if child is not None and child.returncode is None and parent_identity is not None:
            try:
                if identity_guard.exit_event(child):
                    finish_exited(child, observed, report)
                else:
                    identity_guard.kill_owned(observed, child.pid, parent_identity)
                    child.wait(timeout=10)
            except BaseException as cleanup_error:
                report['cleanup_error'] = f'{type(cleanup_error).__name__}: {cleanup_error}'
                report['status'] = 'failed'
        try:
            final_entry = snapshot(observed)
            with (control / 'samples.jsonl').open('a') as stream:
                stream.write(json.dumps(final_entry) + '\n')
            report['final_sample'] = final_entry
        except BaseException as monitor_error:
            report['final_sample_error'] = f'{type(monitor_error).__name__}: {monitor_error}'
            report['status'] = 'failed'
        report.update(outer_supervisor_wall_seconds=time.monotonic() - started,
                      finished_at=identity_guard.now(), observed_owned_pids=sorted(observed),
                      resource_note='1-second samples; not a hard peak guarantee; physical free and swap free observed only')
        write(control, 'receipt.json', report)
        print(json.dumps(report))

if __name__ == '__main__':
    main()
