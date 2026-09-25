"""Mock protocol tests only; no official evaluator or cloud work."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


PATH = Path(__file__).resolve().parents[2] / 'scripts/q3_prefix_linux_supervisor.py'
spec = importlib.util.spec_from_file_location('q3_prefix_linux_supervisor', PATH)
linux = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linux)


class SupervisorTests(unittest.TestCase):
    def fixture(self, root):
        probe = Mock()
        probe.within_results.side_effect = lambda p: Path(p)
        probe.utc.return_value = 'mock-time'
        probe.COUNT_LIMITS = {'P3': 1}
        output = root / 'run'
        manifest = root / 'manifest.json'
        manifest.write_text('{}')
        m = {'source_commit': linux.SOURCE, 'static_summary_sha256': 'static',
             'plan_sha256': 'plan', 'budget': {'total_seconds': 120,
             'per_phase_seconds': 60, 'memory_limit_bytes': 512 * linux.MI_B}}
        def digest(p):
            return 'prepared' if Path(p).name == 'prepared.json.gz' else 'hash'
        def read(p):
            return json.loads(Path(p).read_text())
        def write(p, value):
            Path(p).write_text(json.dumps(value))
        valid = (probe, digest, read, write, m, root, manifest, 'official', {'input': 'hash'})
        return output, manifest, valid

    def run_mock(self, output, manifest, valid):
        return linux.run(manifest, output, linux.MANIFEST_SHA, 'admitted')

    def test_validate_only_does_not_reserve_or_observe(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            output, manifest, valid = self.fixture(root)
            with patch.object(linux, 'validated', return_value=valid), patch.object(linux, 'host_observation') as obs:
                result = linux.run(manifest, output, linux.MANIFEST_SHA, None, True)
            self.assertEqual(result['status'], 'validated')
            obs.assert_not_called()
            self.assertFalse(output.exists())

    def test_duplicate_output_refused_before_work(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            output, manifest, valid = self.fixture(root)
            output.mkdir()
            with patch.object(linux, 'validated', return_value=valid), patch.object(linux, 'supervise') as phase:
                with self.assertRaises(FileExistsError):
                    self.run_mock(output, manifest, valid)
            phase.assert_not_called()

    def test_prepare_failure_never_scores(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            output, manifest, valid = self.fixture(root)
            with patch.object(linux, 'validated', return_value=valid), \
                 patch.object(linux, 'host_observation', return_value={'mem_available_mib': 2048, 'swapouts': 0}), \
                 patch.object(linux.subprocess, 'Popen', return_value=Mock()), \
                 patch.object(linux, 'supervise', return_value={'status': 'failed'}) as phase:
                with self.assertRaisesRegex(RuntimeError, 'prepare phase failed'):
                    self.run_mock(output, manifest, valid)
            self.assertEqual(phase.call_count, 1)
            self.assertEqual(json.loads((output / 'run.json').read_text())['status'], 'failed')

    def test_two_phases_and_reservation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            output, manifest, valid = self.fixture(root)
            def phase(_argv, out, name, *_rest):
                if name == 'prepare':
                    (out / 'prepare').mkdir()
                    (out / 'prepare/prepared.json.gz').write_text('mock')
                    (out / 'prepare/run.json').write_text(json.dumps({
                        'status': 'complete', 'calls_started': {'Step1': 5, 'Step2': 5, 'Step3': 5},
                        'new_P2': 0, 'new_P3': 0, 'static_summary_sha256': 'static',
                        'prepared_sha256': 'prepared', 'traffic': {'spill_added_copy_bytes': 0},
                        'checks': [{'checks': {'ok': True}}] * 5}))
                else:
                    self.assertEqual(json.loads((out / 'score-reservation.json').read_text())['max_P3'], 1)
                    (out / 'official-p3.json.gz').write_text('mock')
                    (out / 'score-worker.json').write_text(json.dumps({
                        'status': 'complete', 'counts_started': {'P3': 1},
                        'official_result_sha256': 'hash'}))
                return {'status': 'complete', 'phase': name}
            with patch.object(linux, 'validated', return_value=valid), \
                 patch.object(linux, 'host_observation', return_value={'mem_available_mib': 2048, 'swapouts': 0}), \
                 patch.object(linux.subprocess, 'Popen', return_value=Mock()), \
                 patch.object(linux, 'supervise', side_effect=phase) as call:
                result = self.run_mock(output, manifest, valid)
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(call.call_count, 2)
            self.assertEqual([x['phase'] for x in result['phases']], ['prepare', 'score'])

    def test_resource_excess_kills_child(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proc = Mock(pid=123)
            proc.wait.return_value = -9
            guard = Mock()
            budget = {'per_phase_seconds': 60, 'memory_limit_bytes': 512 * linux.MI_B}
            with patch.object(linux.subprocess, 'Popen', side_effect=[proc, guard]), \
                 patch.object(linux, 'host_observation', return_value={'mem_available_mib': 2048, 'swapouts': 0}), \
                 patch.object(linux, 'group_rss', return_value=513 * linux.MI_B), \
                 patch.object(linux, 'kill_group', return_value=-9) as killed:
                result = linux.supervise(['fake'], root, 'prepare', linux.time.monotonic() + 120, 0, budget)
            self.assertEqual(result['stop_reason'], 'resource gate closed')
            killed.assert_called_once_with(proc)

    def test_timeout_kills_child(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proc = Mock(pid=123)
            proc.poll.return_value = None
            guard = Mock()
            budget = {'per_phase_seconds': 60, 'memory_limit_bytes': 512 * linux.MI_B}
            ticks = iter([0, 0, 0, 61, 61, 61])
            with patch.object(linux.subprocess, 'Popen', side_effect=[proc, guard]), \
                 patch.object(linux.time, 'monotonic', side_effect=lambda: next(ticks, 61)), \
                 patch.object(linux, 'host_observation', return_value={'mem_available_mib': 2048, 'swapouts': 0}), \
                 patch.object(linux, 'group_rss', return_value=0), \
                 patch.object(linux, 'kill_group', return_value=-9) as killed:
                result = linux.supervise(['fake'], root, 'prepare', 120, 0, budget)
            self.assertEqual(result['stop_reason'], 'deadline')
            killed.assert_called_once_with(proc)

    def test_whole_watchdog_parent_eof_kills_active_group(self):
        with tempfile.TemporaryDirectory() as d:
            active = Path(d) / 'active-pgid'
            active.write_text('123')
            read_fd, write_fd = os.pipe()
            os.close(write_fd)
            with patch.object(linux.os, 'killpg') as kill:
                linux.whole_watchdog(read_fd, active, 120)
            kill.assert_called_once_with(123, linux.signal.SIGKILL)

    def test_parent_death_arm_and_race_check(self):
        libc = Mock()
        libc.prctl.return_value = 0
        with patch.object(linux.ctypes, 'CDLL', return_value=libc), \
             patch.object(linux.os, 'getppid', return_value=999), \
             patch.object(linux.os, 'getpid', return_value=123), \
             patch.object(linux.os, 'kill') as kill:
            linux.arm_parent_death_signal(777)
        libc.prctl.assert_called_once_with(1, linux.signal.SIGKILL, 0, 0, 0)
        kill.assert_called_once_with(123, linux.signal.SIGKILL)


if __name__ == '__main__':
    unittest.main()
