"""One admitted CLI allocation with an independent absolute 600s host stop guard."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import zipfile

from q3_partial_colab_watchdog import SESSION, empty_sessions


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_package(bundle, expected):
    if sha(bundle) != expected:
        raise RuntimeError('package identity differs')
    script = Path(__file__).resolve()
    job = script.with_name('q3_partial_colab_job.py')
    watchdog = script.with_name('q3_partial_colab_watchdog.py')
    with zipfile.ZipFile(bundle) as archive:
        package = json.loads(archive.read('package.json'))
    for key, path in [('controller_sha256', script), ('job_sha256', job),
                      ('watchdog_sha256', watchdog)]:
        if package.get(key) != sha(path):
            raise RuntimeError(key + ' differs from transport manifest')
    return job, watchdog


def call(cli, output, record, label, args, timeout):
    try:
        result = subprocess.run([str(cli), '--auth', 'oauth2', *args],
                                capture_output=True, text=True, timeout=timeout)
        entry = {'label': label, 'exit_code': result.returncode,
                 'stdout': result.stdout, 'stderr': result.stderr}
    except subprocess.TimeoutExpired as error:
        entry = {'label': label, 'timeout': timeout, 'exit_code': None,
                 'stdout': str(error.stdout or ''), 'stderr': str(error.stderr or '')}
    except OSError as error:
        entry = {'label': label, 'exit_code': None,
                 'error': type(error).__name__ + ': ' + str(error), 'stdout': '', 'stderr': ''}
    (output / (label + '.stdout.txt')).write_text(entry['stdout'])
    (output / (label + '.stderr.txt')).write_text(entry['stderr'])
    record['attempts'].append({k: v for k, v in entry.items() if k not in ('stdout', 'stderr')})
    (output / 'control.json').write_text(json.dumps(record, indent=2) + '\n')
    return entry


def require_success(entry):
    if entry['exit_code'] != 0:
        raise RuntimeError(entry['label'] + ' did not complete successfully')
    return entry


def start_watchdog(cli, watchdog, output, deadline):
    arm_read, arm_write = os.pipe()
    ready_read, ready_write = os.pipe()
    try:
        with (output / 'watchdog.stderr.txt').open('xb') as stderr:
            child = subprocess.Popen([sys.executable, '-B', str(watchdog.resolve()),
                                      '--cli', str(cli.resolve()), '--receipt', str(output / 'watchdog.json'),
                                      '--arm-fd', str(arm_read), '--ready-fd', str(ready_write),
                                      '--deadline', str(deadline)],
                                     pass_fds=(arm_read, ready_write), start_new_session=True,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=stderr)
    except BaseException:
        for fd in (arm_read, arm_write, ready_read, ready_write):
            os.close(fd)
        raise
    os.close(arm_read)
    os.close(ready_write)
    try:
        readable, _, _ = select.select([ready_read], [], [], 5)
        if not readable or os.read(ready_read, 6) != b'READY\n' or child.poll() is not None:
            raise RuntimeError('independent watchdog did not confirm readiness')
    except BaseException:
        os.close(arm_write)
        child.wait(timeout=40)
        raise
    finally:
        os.close(ready_read)
    return child, arm_write


def run(bundle, output, package_sha256, admission_ref, cli):
    if not admission_ref.strip() or len(admission_ref) > 500:
        raise ValueError('bounded admission reference required')
    job, watchdog = verify_package(bundle, package_sha256)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    record = {'session': SESSION, 'admission_reference': admission_ref,
              'package_sha256': package_sha256, 'status': 'starting', 'attempts': [],
              'allocation_attempted': False, 'watchdog_ready': False,
              'absolute_stop_deadline_monotonic': started + 600}
    (output / 'control.json').write_text(json.dumps(record, indent=2) + '\n')
    guard = arm_fd = None
    confirmed = False
    bootstrap = output / 'bootstrap.py'
    bootstrap.write_text("import runpy\njob=runpy.run_path('/content/q3_partial_colab_job.py')\n"
                         + "job['run']('/content/q3-partial-package.zip', "
                         + repr(package_sha256) + ', ' + repr(admission_ref) + ')\n')
    try:
        before = require_success(call(cli, output, record, 'sessions-before', ['sessions'], 10))
        if not empty_sessions(before['stdout'], before['stderr']):
            raise RuntimeError('fresh Colab sessions were not exactly empty')
        guard, arm_fd = start_watchdog(cli, watchdog, output, started + 600)
        record['watchdog_ready'] = True
        (output / 'control.json').write_text(json.dumps(record, indent=2) + '\n')
        record['allocation_attempted'] = True  # Durable before CLI new can allocate.
        (output / 'control.json').write_text(json.dumps(record, indent=2) + '\n')

        def work(label, args, cap):
            remaining = started + 545 - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('host stop budget reached before ' + label)
            return require_success(call(cli, output, record, label, args, min(cap, remaining)))

        work('new', ['new', '--session', SESSION], 60)
        work('upload-package', ['upload', str(bundle.resolve()), '/content/q3-partial-package.zip', '--session', SESSION], 30)
        work('upload-job', ['upload', str(job.resolve()), '/content/q3_partial_colab_job.py', '--session', SESSION], 30)
        work('execute', ['exec', '--session', SESSION, '--file', str(bootstrap.resolve()), '--timeout', '545'], 555)
        record['status'] = 'remote_command_completed'
    except BaseException as error:
        record.update(status='failed', error=type(error).__name__ + ': ' + str(error))
    finally:
        if record['allocation_attempted']:
            try:
                require_success(call(cli, output, record, 'download',
                                     ['download', '/content/q3-partial-817e-evidence.tar.gz',
                                      str((output / 'evidence.tar.gz').resolve()), '--session', SESSION], 20))
            except BaseException as error:
                record['download_error'] = type(error).__name__ + ': ' + str(error)
            stop = call(cli, output, record, 'stop', ['stop', '--session', SESSION], 25)
            after = call(cli, output, record, 'sessions-after', ['sessions'], 10)
            confirmed = stop['exit_code'] == 0 and after['exit_code'] == 0 and empty_sessions(after['stdout'], after['stderr'])
            record['stop_confirmation'] = 'confirmed_empty' if confirmed else 'unknown_watchdog_retained'
            if not confirmed:
                record['status'] = 'failed'
                record['stop_error'] = 'stop rc0 and fresh exact empty sessions required'
        if arm_fd is not None:
            if confirmed:
                try:
                    os.write(arm_fd, b'D')
                except BrokenPipeError:
                    record['watchdog_notice'] = 'guard already exited; inspect independent receipt'
            os.close(arm_fd)
            if confirmed:
                try:
                    guard.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    record['watchdog_error'] = 'confirmed guard did not exit within bounded wait'
                    record['status'] = 'failed'
            else:
                record['watchdog_pending'] = 'independent absolute deadline remains armed; slot not released'
        record['wall_seconds'] = time.monotonic() - started
        (output / 'control.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('package', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--package-sha256', required=True)
    p.add_argument('--admission-ref', required=True)
    p.add_argument('--cli', type=Path, required=True)
    a = p.parse_args()
    result = run(a.package, a.output, a.package_sha256, a.admission_ref, a.cli)
    print(json.dumps(result, indent=2))
    if result['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
