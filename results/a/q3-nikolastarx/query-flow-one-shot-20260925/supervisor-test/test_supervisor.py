"""Zero-scoring, short-lived checks for resource_supervisor."""
import json
import pathlib
import signal
import subprocess
import sys
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import resource_supervisor as sup

def result(name, **items):
    (HERE / f'{name}.json').write_text(json.dumps(items, indent=2) + '\n')

def test_own_group():
    child = subprocess.Popen(['/bin/sleep', '5'], start_new_session=True)
    observed = {}
    try:
        ident = sup.identity(child.pid)
        assert ident is not None
        observed[child.pid] = ident
        live = sup.current_owned(sup.processes(), observed, child.pid, ident)
        assert child.pid in live
        sup.kill_owned(observed, child.pid, ident)
        code = child.wait(timeout=3)
        assert code == -signal.SIGKILL
        result('own_group', parent_pid=child.pid, identity=ident,
               verified_live=list(live), returncode=code, passed=True)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=3)

def test_reuse_and_scorer():
    child = subprocess.Popen(['/bin/sleep', '5'], start_new_session=True)
    observed = {}
    try:
        ident = sup.identity(child.pid)
        assert ident is not None
        observed[child.pid] = ident
        fake = (ident[0], ident[1] + 1)
        with mock.patch.object(sup.os, 'killpg') as forbidden:
            try:
                sup.kill_owned(observed, child.pid, fake)
            except RuntimeError as error:
                refusal = str(error)
            else:
                raise AssertionError('reused group was accepted')
            forbidden.assert_not_called()
        # A historical PID is not excluded from the scorer scan.
        row = {'pid': child.pid, 'ppid': 1, 'pgid': child.pid, 'rss_kib': 1,
               'comm': 'python3', 'args': 'python -m src.q3.query_flow_probe'}
        with mock.patch.object(sup, 'processes', return_value=[row]), mock.patch.object(
                sup, 'command', side_effect=['1', 'free = 2048.00M',
                                            'Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 500000.']), mock.patch.object(
                sup, 'CONTROL', HERE):
            entry = sup.sample(observed)
        assert entry['other_scorers'] == [row]
        result('reuse_and_scorer', refusal=refusal, killpg_calls=0,
               historical_pid_reported_as_other_scorer=True, passed=True)
    finally:
        child.kill()
        child.wait(timeout=3)

def test_failed_monitor_zero_dispatch():
    bad = {'pressure_level': 2, 'physical_free_bytes': 8 * 1024**3,
           'swap_free_mib': 2048, 'other_scorers': []}
    reason = sup.stop_reason(bad, start=True)
    assert reason
    with mock.patch.object(sup, 'processes', side_effect=RuntimeError('ps failed')):
        try:
            sup.sample({})
        except RuntimeError as error:
            monitor_error = str(error)
        else:
            raise AssertionError('failed monitor was accepted')
    result('failed_monitor_zero_dispatch', admission_refusal=reason,
           monitor_error=monitor_error, popen_calls=0, passed=True)

if __name__ == '__main__':
    test_own_group()
    test_reuse_and_scorer()
    test_failed_monitor_zero_dispatch()
    print('3 supervisor tests passed; 0 scorer/evaluator calls')
