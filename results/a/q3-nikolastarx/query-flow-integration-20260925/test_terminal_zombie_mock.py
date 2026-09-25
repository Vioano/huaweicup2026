"""Pure-mock regression for the current integration supervisor terminal path."""
import json
from pathlib import Path
from unittest import mock
import integration_supervisor as sup

class Ended:
    pid = 101
    returncode = None
    def wait(self, timeout):
        assert timeout == 10
        self.returncode = 0

parent = {'pid': 101, 'ppid': 1, 'pgid': 101, 'args': 'exited parent'}
worker = {'pid': 202, 'ppid': 1, 'pgid': 202, 'args': 'worker'}
results = []

child = Ended()
report = {'status': 'running'}
with mock.patch.object(sup.identity_guard, 'processes', return_value=[parent]), mock.patch.object(
        sup.identity_guard, 'identity', side_effect=AssertionError('zombie identity queried')), mock.patch.object(
        sup.os, 'killpg') as kill:
    sup.finish_exited(child, {101: (1, 1)}, report)
    kill.assert_not_called()
assert report['status'] == 'complete'
results.append({'case': 'zombie_parent_only', 'status': report['status'], 'signals': 0})

child = Ended()
report = {'status': 'running'}
with mock.patch.object(sup.identity_guard, 'processes', return_value=[parent, worker]), mock.patch.object(
        sup.identity_guard, 'identity', side_effect=lambda pid: (2, 2) if pid == 202 else None), mock.patch.object(
        sup.os, 'getpgrp', return_value=999), mock.patch.object(sup.os, 'killpg') as kill:
    sup.finish_exited(child, {101: (1, 1), 202: (2, 2)}, report)
    kill.assert_called_once_with(202, sup.signal.SIGKILL)
assert report['status'] == 'failed'
results.append({'case': 'verified_residual_group', 'status': report['status'],
                'signalled_group': 202})

for identity in ((3, 3), None):
    child = Ended()
    with mock.patch.object(sup.identity_guard, 'processes', return_value=[parent, worker]), mock.patch.object(
            sup.identity_guard, 'identity', return_value=identity), mock.patch.object(
            sup.os, 'getpgrp', return_value=999), mock.patch.object(sup.os, 'killpg') as kill:
        try:
            sup.finish_exited(child, {101: (1, 1), 202: (2, 2)}, {'status': 'running'})
        except RuntimeError:
            pass
        else:
            raise AssertionError('reused or unknown worker identity accepted')
        kill.assert_not_called()
    results.append({'case': 'reused_pid' if identity else 'unknown_identity', 'signals': 0})

child = Ended()
report = {'status': 'failed', 'error': 'earlier monitoring failure'}
with mock.patch.object(sup.identity_guard, 'processes', return_value=[parent]), mock.patch.object(
        sup.identity_guard, 'identity', side_effect=AssertionError('zombie identity queried')), mock.patch.object(
        sup.os, 'killpg') as kill:
    sup.finish_exited(child, {101: (1, 1)}, report)
    kill.assert_not_called()
assert report['status'] == 'failed' and report['error'] == 'earlier monitoring failure'
results.append({'case': 'failure_status_preserved', 'status': report['status'], 'signals': 0})

Path(__file__).with_name('terminal-zombie-mock-results.json').write_text(
    json.dumps(results, indent=2) + '\n')
print('current terminal pure mocks passed: zombie, known group, reuse, unknown, failed status')
