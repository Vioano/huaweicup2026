"""Pure mocks only. Do not start the integration runner or supervisor."""
import json
from pathlib import Path
from unittest import mock
import integration_runner as runner
import integration_supervisor as supervisor
import resource_supervisor as identity_guard

HERE = Path(__file__).resolve().parent
result = []

# Reserve happens before dispatch; the seventh call is refused without dispatch.
ledger = []
path = HERE / 'mock-ledger.json'
for phase in ['p3'] * 4 + ['p2'] * 2:
    runner.reserve(ledger, phase, path)
try:
    runner.reserve(ledger, 'p3', path)
except runner.TerminalEvaluationFailure:
    pass
else:
    raise AssertionError('P3 budget exceeded')
assert len(ledger) == 6
result.append({'case': 'budget_4p3_2p2', 'reserved': len(ledger), 'seventh_dispatch': False})

# An official failure becomes BaseException, outside candidate ValidationError catches.
ledger = []
called = []
def failed_official():
    called.append('called')
    assert len(ledger) == 1 and ledger[0]['status'] == 'started'
    raise ValueError('synthetic official failure')
with mock.patch.object(runner.signal, 'signal'), mock.patch.object(
        runner.signal, 'setitimer'), mock.patch.object(runner.signal, 'getsignal', return_value=None):
    try:
        runner.wrap_official(failed_official, 'p3', ledger, path)()
    except runner.TerminalEvaluationFailure:
        pass
    else:
        raise AssertionError('official failure did not terminate')
assert len(called) == 1 and ledger[0]['status'] == 'failed'
assert issubclass(runner.TerminalEvaluationFailure, BaseException)
assert not issubclass(runner.TerminalEvaluationFailure, Exception)
result.append({'case': 'first_official_exception', 'dispatches': 1, 'status': 'failed', 'retry': 0})

baseline = {'pressure_level': 1, 'other_scorers': [], 'disk_free_bytes': 12*1024**3,
            'owned_rss_bytes': 0, 'swap_used_mib': 1000, 'physical_free_bytes': 1}
assert supervisor.guard(baseline, 1000, start=True) is None
for field, value in [('pressure_level', 2), ('disk_free_bytes', 9*1024**3),
                     ('owned_rss_bytes', 2*1024**3 + 1), ('swap_used_mib', 1256.01)]:
    entry = {**baseline, field: value}
    assert supervisor.guard(entry, 1000) is not None
entry = {**baseline, 'other_scorers': [{'pid': 1}]}
assert supervisor.guard(entry, 1000) is not None
result.append({'case': 'resource_rules', 'pressure_disk_rss_swap_conflict': 'all_stop',
               'low_physical_free': 'observation_only'})

class Ended:
    pid = 101
    returncode = None
    def wait(self, timeout):
        assert timeout == 10
        self.returncode = 0

child = Ended()
report = {'status': 'running'}
with mock.patch.object(identity_guard, 'processes', return_value=[]), mock.patch.object(
        identity_guard, 'identity', side_effect=AssertionError('exited parent identity read')), mock.patch.object(
        identity_guard.os, 'killpg') as kill:
    identity_guard.finish_exited(child, {101: (1, 1)}, report)
    kill.assert_not_called()
assert report['status'] == 'complete' and child.returncode == 0
result.append({'case': 'short_lived_terminal', 'status': 'complete', 'signals': 0})

(HERE / 'integration-mock-results.json').write_text(json.dumps(result, indent=2) + '\n')
print('integration pure mocks passed: budget, official abort, resources, short terminal')
