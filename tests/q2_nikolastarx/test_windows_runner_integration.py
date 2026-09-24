"""Platform/CLI substitutes: never dispatch a solver, E0 or Windows native call."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import evaluate_feedback as common
from src.q2_nikolastarx import evaluate_matrix as matrix
from src.q2_nikolastarx import windows_process
from src.benchmark_board.protocol import validate_feed
from tests.q2_nikolastarx import test_matrix_runner as fixtures

protocol = fixtures.protocol


class PlatformTests(unittest.TestCase):
    def test_windows_route_has_explicit_environment_copy_and_no_posix_call(self):
        expected = {'status': 'synthetic-only'}
        with patch.object(common, 'is_windows', return_value=True), \
             patch.object(common, '_monitored_posix', side_effect=AssertionError('POSIX used')), \
             patch.object(windows_process, 'monitored', return_value=expected) as native:
            self.assertIs(common.monitored(['explicit.exe'], Path('unused'), 123, 456, cleanup_timeout=2), expected)
        self.assertEqual(native.call_args.kwargs['cwd'], common.ROOT)
        self.assertEqual(native.call_args.kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual(native.call_args.kwargs['env']['PYTHONUTF8'], '1')
        self.assertEqual(native.call_args.kwargs['cleanup_timeout'], 2)
        self.assertIsNot(native.call_args.kwargs['env'], common.os.environ)

    def test_posix_route_keeps_original_monitor(self):
        with patch.object(common, 'is_windows', return_value=False), \
             patch.object(common, '_monitored_posix', return_value={'synthetic': True}) as native, \
             patch.object(windows_process, 'monitored', side_effect=AssertionError('Windows used')):
            common.monitored(['unused'], Path('unused'), 123, 456)
        native.assert_called_once_with(['unused'], Path('unused'), 123, 456)

    def test_windows_environment_keeps_missing_values_and_reasons(self):
        missing = {'cpu': 'synthetic registry access failure', 'ram_bytes': 'synthetic memory query failure'}
        with patch.object(common, 'is_windows', return_value=True), \
             patch.object(common, '_windows_host_info', return_value=(None, None, missing)), \
             patch.object(common.platform, 'platform', return_value='synthetic Windows'), \
             patch.object(common.subprocess, 'check_output', side_effect=AssertionError('sysctl used')):
            env = common.environment()
        self.assertIsNone(env['cpu'])
        self.assertIsNone(env['ram_bytes'])
        self.assertEqual(env['_missing_reasons'], missing)

    def test_interpreter_and_grace_selection(self):
        p = protocol()
        with patch.object(common, 'is_windows', return_value=True):
            self.assertEqual(matrix.python_command(p), sys.executable)
            self.assertEqual(matrix.cleanup_grace(p), 5)
            p['python'] = 'explicit/python.exe'
            self.assertEqual(matrix.python_command(p), 'explicit/python.exe')
        with patch.object(common, 'is_windows', return_value=False):
            del p['python']
            self.assertEqual(matrix.python_command(p), '.venv/bin/python')
            self.assertEqual(matrix.cleanup_grace(p), 0)

    def test_partial_rss_unknown_is_not_replaced_by_other_stage_peak(self):
        self.assertIsNone(common.observed_rss_peak({'solver': {'observed_peak_rss_bytes': None}, 'final': {'observed_peak_rss_bytes': 9}}))
        self.assertEqual(common.observed_rss_peak({'solver': {'observed_peak_rss_bytes': 0}}), 0)

    def test_cleanup_unknown_stops_dispatch_even_if_status_is_wrongly_ok(self):
        for extra in ({'cleanup_verified': False}, {'surviving_pids': None}, {'stop_dispatch': True}):
            row = {'calls': {'solver': 1, 'E0': 0}, 'solver': {'status': 'ok', **extra}}
            self.assertIsNotNone(matrix.stop_dispatch_reason(row))

    def test_plan_cli_windows_is_zero_dispatch_with_actual_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = protocol(); p.update(solver_wall_seconds=30, evaluation_timeout_seconds=60)
            matrix.save(root / 'protocol.json', p)
            argv = ['matrix', 'plan', '--protocol', str(root/'protocol.json'), '--source-commit', 'a'*40, '--runner-commit', 'b'*40]
            output = io.StringIO()
            with patch.object(matrix, 'ROOT', root), patch.object(sys, 'argv', argv), \
                 patch.object(matrix, 'frozen_inputs', return_value={'synthetic': 'no source claim'}), \
                 patch.object(common, 'is_windows', return_value=True), \
                 patch.object(common, 'monitored', side_effect=AssertionError('dispatch forbidden')), \
                 patch.object(common, 'environment', side_effect=AssertionError('native environment forbidden')), redirect_stdout(output):
                matrix.main()
            result = json.loads(output.getvalue())
            self.assertEqual(result['dispatched'], 0)
            self.assertEqual(result['python'], sys.executable)
            self.assertFalse((root/p['output_prefix']).exists())

    def test_windows_default_grace_cannot_exceed_phase_cap(self):
        with patch.object(common, 'is_windows', return_value=True):
            with self.assertRaisesRegex(ValueError, 'Cleanup grace'):
                matrix.validate_protocol(protocol())

    def test_windows_precheck_uses_monitored_process_and_not_raw_subprocess(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def monitor(argv, folder, deadline, rss, **kwargs):
                folder.mkdir()
                (folder/'stdout.txt').write_bytes(b'synthetic format check')
                (folder/'stderr.txt').write_bytes(b'')
                return {'status': 'runner_error', 'created': True, 'exit_code': 0,
                        'cleanup_verified': False, 'surviving_pids': None}
            with patch.object(common, 'is_windows', return_value=True), patch.object(matrix, 'ROOT', root), \
                 patch.object(common, 'monitored', side_effect=monitor), \
                 patch.object(matrix.subprocess, 'run', side_effect=AssertionError('uncontained process forbidden')):
                result = matrix.run_precheck(protocol(), root/'feed.json', root/'precheck', 10**12)
            self.assertEqual(result['status'], 'runner_error')
            self.assertEqual(result['evaluation_calls'], {'E0': 0, 'E1': 0, 'E2': 0})
            self.assertIsNone(result['process']['surviving_pids'])

    def test_utf8_record_serialization_preserves_unicode_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'中文.json'
            matrix.save(path, {'path': '中文 空格'})
            self.assertEqual(json.loads(path.read_bytes()), {'path': '中文 空格'})


class NullableFeedTests(unittest.TestCase):
    """Reuse the established synthetic result writer, plus these new boundaries."""
    setUp = fixtures.MatrixTests.setUp
    fake_monitor = fixtures.MatrixTests.fake_monitor
    def test_nullable_windows_environment_exports_valid_failed_feed(self):
        p = protocol()
        folder = self.root / p['output_prefix'] / '002-k2'
        row = matrix.execute_cell(p, '002', 2, folder, 10**12, self.fake_monitor(timeout=True))
        row['solver']['observed_peak_rss_bytes'] = None
        matrix.save(folder/'run.json', row)
        matrix.archive_cell(folder, self.root/'backup')
        matrix.write_manifest(folder)
        context = {'source_commit': 'd'*40, 'runner_commit': 'e'*40, 'argv': ['synthetic'],
            'hashes': {'inputs': {'data/case_002.json': 'a'*64}},
            'environment': {'os':'synthetic Windows','cpu':None,'gpu':'none','ram_bytes':None,
                'python':'synthetic','dependencies':'synthetic','threads':1,'workers':1,
                '_missing_reasons': {'cpu':'registry query failed', 'ram_bytes':'RAM query failed'}}}
        record = matrix.board_record(p, row, folder, context)
        self.assertIsNone(record['provenance']['environment']['peak_rss_bytes'])
        self.assertEqual(record['provenance']['missing_reasons']['provenance.environment.cpu'], 'registry query failed')
        self.assertNotIn('_missing_reasons', record['provenance']['environment'])
        self.assertTrue(validate_feed({'schema_version':1,'submission_version':1,'records':[record]}, submission=True))

    def test_unverified_solver_cleanup_cannot_dispatch_final(self):
        normal = self.fake_monitor()
        def monitor(*args):
            result = normal(*args)
            result.update(cleanup_verified=False, surviving_pids=None)
            return result
        p = protocol()
        row = matrix.execute_cell(p, '002', 2, self.root/'cell', 10**12, monitor)
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(len(self.argv), 1)
        self.assertEqual(row['calls']['E0'], 0)


if __name__ == '__main__':
    unittest.main()
