"""Pure mocks: no Popen, process creation, solver, or evaluator."""
import json
from pathlib import Path
from unittest import mock
import resource_supervisor as sup

HERE = Path(__file__).resolve().parent

class Child:
    pid = 101
    returncode = None
    def wait(self, timeout):
        assert timeout == 10
        self.returncode = 0
        return 0

def row(pid, pgid):
    return {'pid': pid, 'ppid': 1, 'pgid': pgid}

out = []

# Normal exit: parent has no libproc identity, and no observed group remains.
child = Child()
report = {'status': 'running'}
with mock.patch.object(sup, 'processes', return_value=[]), mock.patch.object(
        sup, 'identity', side_effect=AssertionError('exited parent identity queried')), mock.patch.object(
        sup.os, 'killpg') as kill:
    sup.finish_exited(child, {101: (1, 1)}, report)
    kill.assert_not_called()
assert report['status'] == 'complete' and child.returncode == 0
out.append({'case': 'normal_exit', 'status': report['status'], 'signals': 0})

# Exited parent, historically verified worker leader still alive with same identity.
child = Child()
report = {'status': 'running'}
with mock.patch.object(sup, 'processes', return_value=[row(202, 202)]), mock.patch.object(
        sup, 'identity', side_effect=lambda pid: (2, 2) if pid == 202 else None), mock.patch.object(
        sup.os, 'getpgrp', return_value=999), mock.patch.object(sup.os, 'killpg') as kill:
    sup.finish_exited(child, {101: (1, 1), 202: (2, 2)}, report)
    kill.assert_called_once_with(202, sup.signal.SIGKILL)
assert report['status'] == 'failed' and child.returncode == 0
out.append({'case': 'verified_residual', 'status': report['status'], 'signalled_group': 202})

# Reused PID (or unavailable identity) is never signalled after parent exit.
for current in ((3, 3), None):
    child = Child()
    report = {'status': 'running'}
    with mock.patch.object(sup, 'processes', return_value=[row(202, 202)]), mock.patch.object(
            sup, 'identity', return_value=current), mock.patch.object(
            sup.os, 'getpgrp', return_value=999), mock.patch.object(sup.os, 'killpg') as kill:
        try:
            sup.finish_exited(child, {101: (1, 1), 202: (2, 2)}, report)
        except RuntimeError as error:
            error_text = str(error)
            assert 'identity unverified' in error_text
        else:
            raise AssertionError('unknown identity accepted')
        kill.assert_not_called()
    assert child.returncode == 0
    out.append({'case': 'reused_pid' if current else 'unknown_identity',
                'signals': 0, 'error': error_text})

(HERE / 'terminal-mock-results.json').write_text(json.dumps(out, indent=2) + '\n')
print('terminal mocks passed: normal exit, verified residual, reused PID, unknown identity; no real process')
