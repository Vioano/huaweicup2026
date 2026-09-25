"""Host-only mocks; never invoke the real Colab CLI."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import q3_partial_colab_control as control
import q3_partial_colab_watchdog as watchdog


class ControlTests(unittest.TestCase):
    def test_exact_empty_format_only(self):
        empty = watchdog.EMPTY
        self.assertTrue(watchdog.empty_sessions(empty + '\n', ''))
        self.assertTrue(watchdog.empty_sessions('', empty))
        for stdout, stderr in [('prefix ' + empty, ''), (empty, 'warning'),
                               ('no active sessions', ''), ('session-id: other', '')]:
            self.assertFalse(watchdog.empty_sessions(stdout, stderr))

    def test_parent_eof_stops_only_named_session_once(self):
        with tempfile.TemporaryDirectory() as d:
            read_fd, write_fd = os.pipe()
            ready_read, ready_write = os.pipe()
            os.close(write_fd)
            results = [{'returncode': 0, 'stdout': '', 'stderr': ''},
                       {'returncode': 0, 'stdout': watchdog.EMPTY, 'stderr': ''}]
            with patch.object(watchdog, 'cli_call', side_effect=results) as call:
                result = watchdog.guard(Path('fake-cli'), Path(d) / 'watchdog.json',
                                        read_fd, ready_write, watchdog.time.monotonic() + 0.01)
            self.assertEqual(os.read(ready_read, 6), b'READY\n')
            os.close(ready_read)
            self.assertEqual(result['status'], 'stopped_confirmed')
            self.assertEqual(result['trigger'], 'parent_exit_absolute_deadline')
            self.assertEqual(call.call_args_list[0].args[1], ['stop', '--session', watchdog.SESSION])
            self.assertEqual(call.call_count, 2)

    def test_deadline_causes_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            read_fd, write_fd = os.pipe()
            ready_read, ready_write = os.pipe()
            with patch.object(watchdog, 'cleanup', return_value={'status': 'called'}) as cleanup:
                result = watchdog.guard(Path('fake-cli'), Path(d) / 'watchdog.json',
                                        read_fd, ready_write, watchdog.time.monotonic() - 1)
            os.close(write_fd)
            os.close(ready_read)
            self.assertEqual(result['status'], 'called')
            self.assertEqual(cleanup.call_args.args[2], 'absolute_deadline')

    def test_hash_refusal_before_allocation(self):
        with tempfile.TemporaryDirectory() as d:
            bundle = Path(d) / 'transport.zip'
            with zipfile.ZipFile(bundle, 'w') as z:
                z.writestr('package.json', json.dumps({'controller_sha256': 'wrong'}))
            with self.assertRaisesRegex(RuntimeError, 'controller_sha256'):
                control.verify_package(bundle, control.sha(bundle))

    def exercise_controller(self, stop_rc=0, sessions_after=None, sessions_before=None):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        output = root / 'result'
        read_fd, write_fd = os.pipe()
        guard = Mock()
        calls = []
        def fake_call(_cli, _output, _record, label, _args, _timeout):
            calls.append(label)
            if label == 'sessions-before':
                return {'label': label, 'exit_code': 0, 'stdout': sessions_before if sessions_before is not None else watchdog.EMPTY, 'stderr': ''}
            if label == 'sessions-after':
                return {'label': label, 'exit_code': 0, 'stdout': sessions_after if sessions_after is not None else watchdog.EMPTY, 'stderr': ''}
            return {'label': label, 'exit_code': stop_rc if label == 'stop' else 0, 'stdout': '', 'stderr': ''}
        with patch.object(control, 'verify_package', return_value=(root / 'job.py', root / 'guard.py')), \
             patch.object(control, 'start_watchdog', return_value=(guard, write_fd)) as started, \
             patch.object(control, 'call', side_effect=fake_call):
            record = control.run(root / 'bundle.zip', output, 'hash', 'admission', root / 'cli')
        if not started.called:
            os.close(write_fd)
        command = os.read(read_fd, 1)
        os.close(read_fd)
        return temp, record, calls, command, started

    def test_stop_failure_does_not_disarm(self):
        temp, record, calls, command, _ = self.exercise_controller(stop_rc=1)
        self.addCleanup(temp.cleanup)
        self.assertEqual(record['status'], 'failed')
        self.assertEqual(record['stop_confirmation'], 'unknown_watchdog_retained')
        self.assertEqual(command, b'')

    def test_nonempty_after_stop_does_not_disarm(self):
        temp, record, _, command, _ = self.exercise_controller(sessions_after='session-id: other')
        self.addCleanup(temp.cleanup)
        self.assertEqual(record['status'], 'failed')
        self.assertEqual(command, b'')

    def test_confirmed_stop_disarms(self):
        temp, record, calls, command, started = self.exercise_controller()
        self.addCleanup(temp.cleanup)
        self.assertEqual(record['stop_confirmation'], 'confirmed_empty')
        self.assertEqual(command, b'D')
        self.assertLess(calls.index('sessions-before'), calls.index('new'))
        started.assert_called_once()

    def test_nonempty_before_refuses_allocation(self):
        temp, record, calls, command, started = self.exercise_controller(sessions_before='session-id: other')
        self.addCleanup(temp.cleanup)
        self.assertEqual(record['status'], 'failed')
        self.assertNotIn('new', calls)
        started.assert_not_called()


if __name__ == '__main__':
    unittest.main()
