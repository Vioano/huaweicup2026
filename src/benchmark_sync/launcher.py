"""Stable stdlib-only parent, copied to state/start.py during installation.

The native service waits for this process across supervisor code handoffs. It
does not import the changing release or own a ledger/network credential.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

HANDOFF = 75
REPLACE_DELAYS = (.02, .04, .08, .16, .32, .5, .5, .5, .5)


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(len(REPLACE_DELAYS) + 1):
            try:
                os.replace(temporary, path)
                break
            except OSError as error:
                # Windows readers/AV can briefly deny replacement. Never unlink
                # the old destination or retry disk-full/unknown/Unix errors.
                if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == len(REPLACE_DELAYS):
                    raise
                time.sleep(REPLACE_DELAYS[attempt])
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8'))


@contextmanager
def parent_lock(path):
    # The supervisor retains its own lock; this closes the inter-process gap
    # between its clean exit and the next approved supervisor starting.
    with path.open('a+b') as stream:
        stream.seek(0); stream.write(b'0'); stream.flush(); stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run(state):
    state = Path(state).resolve()
    software = state / 'software'
    stopping = False
    def end(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, end)
    signal.signal(signal.SIGINT, end)
    with parent_lock(state / 'launcher.lock'):
        failures = 0
        while not stopping:
            config = read(state / 'config.json')
            active = software / 'active.json'
            release = read(active if active.exists() else state / 'bootstrap.json')
            environment = dict(os.environ, BENCHMARK_SYNC_LAUNCHER='1')
            proc = subprocess.Popen([config['python'], '-X', 'utf8', '-u', '-m',
                'src.benchmark_sync.supervisor', '--config', str(state / 'config.json'),
                '--bootstrap', str(state / 'bootstrap.json')], cwd=release['path'], env=environment)
            ready = False
            try:
                write(software / 'launcher.json', {'protocol': 1, 'pid': os.getpid(),
                    'supervisor_pid': proc.pid, 'release_id': release['release_id'], 'state': 'running'})
                while proc.poll() is None and not stopping:
                    try:
                        report = read(software / 'supervisor.json')
                        ready = ready or (report.get('pid') == proc.pid and report.get('state') == 'ready'
                            and report.get('release_id') == release['release_id'])
                    except (OSError, ValueError):
                        pass
                    time.sleep(.25)
                if stopping:
                    # Windows terminate() cannot run Python finally blocks.
                    # Ask the owning supervisor to stop its children first.
                    write(software / 'supervisor-stop.json', {'pid': proc.pid})
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        proc.terminate(); proc.wait(timeout=10)
                    return 0
                code = proc.wait()
            finally:
                if proc.poll() is None:
                    write(software / 'supervisor-stop.json', {'pid': proc.pid})
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        proc.terminate(); proc.wait(timeout=10)
            if code == 0:
                return 0
            if code == HANDOFF and active.exists() and read(active)['release_id'] != release['release_id']:
                failures = 0
                continue
            previous_path = software / 'previous.json'
            if not ready and previous_path.exists():
                previous = read(previous_path)
                if previous['release_id'] != release['release_id']:
                    rejected_path = software / 'rejected.json'
                    rejected = read(rejected_path) if rejected_path.exists() else {}
                    rejected[release['release_id']] = {'error': 'Supervisor exited before ready', 'exit_code': code}
                    write(rejected_path, rejected)
                    write(active, previous)
                    write(software / 'launcher.json', {'protocol': 1, 'pid': os.getpid(),
                        'state': 'rollback', 'failed_release_id': release['release_id'],
                        'release_id': previous['release_id'], 'exit_code': code})
            failures += 1
            deadline = time.monotonic() + min(30, 2 ** min(failures, 5))
            while not stopping and time.monotonic() < deadline:
                time.sleep(.25)
    return 0


if __name__ == '__main__':
    sys.exit(run(Path(__file__).resolve().parent))
