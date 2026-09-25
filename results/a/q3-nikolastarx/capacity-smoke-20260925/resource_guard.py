"""External macOS resource supervision for this single frozen experiment.

No evaluator modification. It monitors the host and terminates only process
groups in the fresh probe process tree if the admitted resource window closes.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SOURCE = 'da1c9e86f9353ad4ca1bb3b8c720cef9b5043b49'
MANIFEST = '6dc74e291e2caf20103737888397fac96dc26516581e30c252677155df7fda75'


def observation():
    pressure = int(subprocess.check_output(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], text=True))
    top = subprocess.check_output(['top', '-l', '1', '-n', '0'], text=True)
    line = next(x for x in top.splitlines() if x.startswith('PhysMem:'))
    size, unit = re.search(r'([0-9.]+)([MG]) unused', line).groups()
    free = float(size) * (1024 if unit == 'G' else 1)
    vm = subprocess.check_output(['vm_stat'], text=True)
    swapouts = int(re.search(r'^Swapouts:\s+(\d+)', vm, re.M).group(1))
    return {'utc': datetime.now(timezone.utc).isoformat(), 'pressure': pressure,
            'unused_mib': free, 'swapouts': swapouts, 'physmem': line}


def groups(root_pid):
    table = [tuple(map(int, line.split())) for line in subprocess.check_output(
        ['ps', '-axo', 'pid=,ppid=,pgid='], text=True).splitlines()]
    members = {root_pid}
    while True:
        more = {pid for pid, ppid, _ in table if ppid in members} - members
        if not more:
            break
        members.update(more)
    return {pgid for pid, _, pgid in table if pid in members and pgid in members}


def main():
    p = __import__('argparse').ArgumentParser()
    p.add_argument('--admission-reference', required=True)
    a = p.parse_args()
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() != SOURCE:
        raise RuntimeError('source HEAD changed')
    if hashlib.sha256((OUT / 'manifest.json').read_bytes()).hexdigest() != MANIFEST:
        raise RuntimeError('manifest changed')
    if (OUT / 'run').exists():
        raise RuntimeError('one-shot call already reserved; no retries')
    before = [observation(), observation()]
    ready = (all(x['pressure'] != 4 and x['unused_mib'] >= 1536 for x in before)
             and before[0]['swapouts'] == before[1]['swapouts'])
    preflight = {'observations': before, 'ready': ready,
                 'supervisor_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 'start_min_unused_mib': 1536, 'run_min_unused_mib': 1024,
                 'admission_reference': a.admission_reference, 'manifest_sha256': MANIFEST,
                 'source_commit': SOURCE, 'process_tree_rss_limit_bytes': 536870912}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    raw = json.dumps(preflight, indent=2) + '\n'
    (OUT / f'resource-preflight-{stamp}.json').write_text(raw)
    (OUT / 'resource-preflight.json').write_text(raw)
    if not ready:
        print(json.dumps({'started': False, **preflight}))
        return
    argv = [sys.executable, '-B', '-m', 'src.q3.feedback_benchmark',
            str(OUT / 'manifest.json'), str(OUT / 'run')]
    known = set()
    samples = []
    reason = None
    start = time.monotonic()
    with (OUT / 'driver.stdout.txt').open('xb') as stdout, (OUT / 'driver.stderr.txt').open('xb') as stderr:
        child = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            while child.poll() is None:
                known.update(groups(child.pid))
                x = observation()
                own_groups = groups(child.pid)
                table = [tuple(map(int, line.split())) for line in subprocess.check_output(
                    ['ps', '-axo', 'pgid=,rss='], text=True).splitlines()]
                x['process_tree_rss_bytes'] = sum(rss * 1024 for pgid, rss in table if pgid in own_groups)
                samples.append(x)
                if (x['pressure'] == 4 or x['unused_mib'] < 1024
                        or x['swapouts'] > before[-1]['swapouts']
                        or x['process_tree_rss_bytes'] > 536870912
                        or time.monotonic() - start > 190):
                    reason = 'host resource gate closed or supervisor deadline'
                    break
        except BaseException as error:
            reason = f'supervision failed: {type(error).__name__}: {error}'
        finally:
            if reason:
                known.update(groups(child.pid))
                for pgid in sorted(known, reverse=True):
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            exit_code = child.wait(timeout=10)
    report = {'started': True, 'exit_code': exit_code, 'stop_reason': reason,
              'driver_wall_seconds': time.monotonic() - start, 'samples': samples,
              'after': observation(), 'pid': child.pid,
              'scope': 'external host observations; no evaluator changes; sampled not continuous'}
    (OUT / 'resource-run.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
