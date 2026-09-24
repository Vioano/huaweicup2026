"""Synthetic scheduler checks; never constructs a plan or calls an evaluator."""
import json
import tempfile
import threading
import time
from pathlib import Path
from unittest import TestCase, main, mock

from src.q2_nikolastarx import hypergap_full500 as runner


class WorkerCapTests(TestCase):
    def test_manifest_worker_caps_and_compact_summary(self):
        for workers in (1, 2):
            with self.subTest(workers=workers):
                manifest = (runner.ROOT / 'results/a/q2-nikolastarx/hypergap-full500-20260925'
                            / f'manifest-workers{workers}.json')
                doc = json.loads(manifest.read_bytes())
                self.assertEqual(doc['limits']['workers'], workers)
                self.assertEqual({k: v for k, v in doc['limits'].items() if k != 'workers'},
                                 {k: v for k, v in runner.LIMITS.items() if k != 'workers'})
                rows = [{'case': f'{i:03d}', 'cores': 1} for i in range(1, 6)]
                active = peak = 0
                lock = threading.Lock()

                def fake_cell(row, *_args):
                    nonlocal active, peak
                    with lock:
                        active += 1
                        peak = max(peak, active)
                    time.sleep(0.02)
                    with lock:
                        active -= 1
                    return {'case': row['case'], 'cores': 1, 'status': 'accepted',
                            'calls': {key: 0 for key in ('E2_api_attempted', 'native_returns',
                                     'E0_fallback_confirmed', 'E0_fallback_possible',
                                     'E0_independent_started')}}

                with tempfile.TemporaryDirectory() as temp, \
                     mock.patch.object(runner, 'cell', fake_cell), \
                     mock.patch.object(runner.platform, 'system', return_value='Darwin'), \
                     mock.patch.object(runner.platform, 'machine', return_value='arm64'):
                    summary = runner.run(doc, {'rows': rows}, {}, manifest, Path('/unused'),
                                         Path('/unused'), Path('/unused'), Path(temp)/'run',
                                         'synthetic', time.perf_counter())
                self.assertEqual(peak, workers)
                self.assertEqual(summary['calls']['solver_started'], 5)
                self.assertEqual(summary['accepted_cells'], 5)
                self.assertFalse(summary['in_flight'])
                self.assertTrue(all('solver_ledger' not in row and 'result' not in row
                                    for row in summary['rows']))


class ResourceGuardTests(TestCase):
    @staticmethod
    def fake_commands(levels, free_pages, swaps):
        values = iter(zip(levels, free_pages, swaps))
        current = [None]
        def call(argv, **_kwargs):
            if argv[0] == 'sysctl':
                current[0] = next(values)
                return mock.Mock(returncode=0, stdout=str(current[0][0]) + '\n')
            _, free, swap = current[0]
            return mock.Mock(returncode=0, stdout=(
                'Mach Virtual Memory Statistics: (page size of 16384 bytes)\n'
                f'Pages free: {free}.\nPages speculative: 0.\nSwapouts: {swap}.\n'))
        return call

    def test_thresholds_and_fail_closed(self):
        scenarios = (
            ([0], [4], [40000], [0], 'pressure_level_4'),
            ([0, 15, 31], [2]*3, [1]*3, [0]*3, 'low_physical_unused_3_samples_30s'),
            ([0, 12, 24, 36], [2]*4, [40000]*4, [0, 1, 2, 3],
             'swapouts_growth_3_samples_30s'),
        )
        for times, levels, free, swaps, expected in scenarios:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp, \
                 mock.patch.object(runner.time, 'monotonic', side_effect=times), \
                 mock.patch.object(runner.subprocess, 'run',
                                   side_effect=self.fake_commands(levels, free, swaps)):
                guard = runner.DarwinResourceGuard()
                observed = [guard.check(Path(temp)) for _ in times]
                self.assertEqual(observed[-1], expected)
                self.assertEqual(len((Path(temp)/'resources.jsonl').read_text().splitlines()),
                                 len(times))
                self.assertIn('utc_epoch_seconds',
                              json.loads((Path(temp)/'resources.jsonl').read_text().splitlines()[-1]))
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(runner.subprocess, 'run', side_effect=TimeoutError('sysctl')):
            self.assertEqual(runner.DarwinResourceGuard().check(Path(temp)),
                             'resource_sample_failed')
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(runner.subprocess, 'run',
                               side_effect=[mock.Mock(stdout='2\n'),
                                            mock.Mock(stdout='Mach Virtual Memory Statistics: '
                                                     '(page size of 16384 bytes)\nPages free: 123.\n')]):
            self.assertEqual(runner.DarwinResourceGuard().check(Path(temp)),
                             'resource_sample_failed')

    def test_stop_file_drains_inflight(self):
        manifest = (runner.ROOT / 'results/a/q2-nikolastarx/hypergap-full500-20260925'
                    / 'manifest-workers1.json')
        doc = json.loads(manifest.read_bytes())
        rows = [{'case': f'{i:03d}', 'cores': 1} for i in range(1, 4)]
        seen = []
        def fake_cell(row, *_args):
            seen.append(row['case'])
            (_args[-2] / 'STOP_REQUESTED').write_text('resource coordinator stop\n')
            time.sleep(0.02)
            return {'case': row['case'], 'cores': 1, 'status': 'accepted',
                    'calls': {key: 0 for key in ('E2_api_attempted', 'native_returns',
                             'E0_fallback_confirmed', 'E0_fallback_possible',
                             'E0_independent_started')}}
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(runner, 'cell', fake_cell), \
             mock.patch.object(runner.platform, 'system', return_value='Darwin'), \
             mock.patch.object(runner.platform, 'machine', return_value='arm64'):
            summary = runner.run(doc, {'rows': rows}, {}, manifest, Path('/unused'),
                                 Path('/unused'), Path('/unused'), Path(temp)/'run',
                                 'synthetic', time.perf_counter())
        self.assertEqual(seen, ['001'])
        self.assertEqual(summary['status'], 'stopped_resource_guard')
        self.assertEqual(summary['accepted_cells'], 1)
        self.assertFalse(summary['in_flight'])


if __name__ == '__main__':
    main()
