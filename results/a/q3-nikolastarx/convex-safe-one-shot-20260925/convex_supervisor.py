"""One-window convex-safe/005/K5 diagnostic supervisor; never constructs a plan."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HELPER = ROOT / 'results/a/q3-nikolastarx/query-flow-integration-20260925/resource_supervisor.py'
HELPER_SHA = '9589577c7f916f3b759fe8508e8cc8304820e810de56ad767264f83a2e72b1d6'
if hashlib.sha256(HELPER.read_bytes()).hexdigest() != HELPER_SHA:
    raise RuntimeError('fixed identity helper differs')
spec = importlib.util.spec_from_file_location('convex_fixed_identity_guard', HELPER)
identity_guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity_guard)
LIMIT_RSS = 2 * 1024**3
LIMIT_SWAP_DELTA_MIB = 256
MIN_DISK = 10 * 1024**3

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_manifest(m):
    required_budget = {'workers': 1, 'P3': 1, 'P2_conditional': 1,
                       'per_phase_seconds': 90, 'total_seconds': 600, 'retries': 0}
    if m['budget'] != required_budget or m['helper_sha256'] != HELPER_SHA:
        raise ValueError('budget or identity helper differs')
    if (m['candidate_directory'] != str(HERE / 'candidate')
            or m['plan_sha256'] != '549519032c0ae7b78957463d0b6189d30184bcfd46e06fa60fc2c1fcc7dc6615'
            or m['control_file'] != str(HERE / 'control.json')
            or m['control_sha256'] != 'dea9ae082ff0edeebc8c7014f7dfc8af36c893daab9617144c115e6b6eeb2b6f'):
        raise ValueError('fixed candidate/control identity differs')
    if m['output'] != str(HERE / 'run'):
        raise ValueError('output or source identity differs')
    expected = {'data/raw/a/official/data/case_005.json',
                'data/raw/a/official/data/config.txt', 'uv.lock'}
    for folder in ('src/q3', 'data/raw/a/official/code'):
        expected.update(str(p.relative_to(ROOT)) for p in (ROOT / folder).rglob('*')
                        if p.is_file() and not p.name.startswith('._')
                        and p.name != '.DS_Store' and '__pycache__' not in p.parts)
    if set(m['inputs']) != expected:
        raise ValueError('source/input file set differs')
    for rel, digest in m['inputs'].items():
        path = (ROOT / rel).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != digest:
            raise ValueError(f'input differs: {rel}')
    fixed = {'probe_sha256': ROOT / 'src/q3/convex_warmup_probe.py',
             'guard_sha256': ROOT / 'src/q3/layered_prepared_guard.py',
             'helper_sha256': HELPER,
             'supervisor_sha256': HERE / 'convex_supervisor.py',
             'plan_sha256': Path(m['candidate_directory']) / 'case_005_multicore_res.json',
             'control_sha256': Path(m['control_file']),
             'admission_sha256': Path(m['admission_file'])}
    for field, path in fixed.items():
        if not path.resolve().is_relative_to(ROOT) and field != 'admission_sha256':
            raise ValueError(f'{field} path outside repository')
        if sha(path) != m[field]:
            raise ValueError(f'{field} differs')
    if m['inputs']['src/q3/convex_warmup_probe.py'] != m['probe_sha256'] or (
            m['inputs']['src/q3/layered_prepared_guard.py'] != m['guard_sha256']):
        raise ValueError('probe or guard identity differs from source tree')
    if not Path(m['admission_file']).resolve().is_file() or not m['admission_sha256']:
        raise ValueError('real admission file required')
    if m['source_commit'] != subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip():
        raise ValueError('source HEAD differs')
    return m

def snapshot(observed, parent=None, parent_identity=None):
    rows = identity_guard.processes()
    live = identity_guard.current_owned(rows, observed, parent, parent_identity)
    if parent is not None and any(r['pgid'] != parent for r in rows if r['pid'] in live):
        raise RuntimeError('worker left the supervisor process group')
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
    verify_manifest(manifest)
    if manifest.get('execution_authorized') is not True:
        raise PermissionError('convex-safe window has no admission authorization')
    actual = sha(Path(__file__))
    if actual != manifest['supervisor_sha256']:
        raise ValueError('supervisor SHA differs')
    run = (ROOT / manifest['output']).resolve()
    if not run.is_relative_to(ROOT) or run.exists():
        raise ValueError('run output already exists or escapes repository')
    control = HERE / 'resource-control'
    control.mkdir(exist_ok=False)
    report = {'status': 'preflight', 'manifest_sha256': sha(args.manifest),
              'supervisor_sha256': actual, 'sample_interval_seconds': 1,
              'source_commit': manifest['source_commit'],
              'probe_sha256': manifest['probe_sha256'],
              'admission_file': manifest['admission_file'],
              'admission_sha256': manifest['admission_sha256'],
              'budget': manifest['budget'], 'resource_policy': 'new_window_admission_required'}
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
        cmd = [sys.executable, '-B', '-m', 'src.q3.convex_warmup_probe',
               manifest['candidate_directory'], manifest['output'],
               '--source', manifest['source_commit'], '--plan-sha256', manifest['plan_sha256'],
               '--admission-file', manifest['admission_file'],
               '--admission-sha256', manifest['admission_sha256'],
               '--control', manifest['control_file'],
               '--control-sha256', manifest['control_sha256']]
        if cmd != manifest['command']:
            raise ValueError('probe command differs')
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
