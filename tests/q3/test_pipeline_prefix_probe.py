"""Runner protocol and stop behavior, with no real subprocess or evaluator."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from src.q3 import pipeline_prefix_probe as probe


class ProbeContractTests(unittest.TestCase):
    def fixture(self, root):
        static = root / 'results/a/q3-nikolastarx/static'
        static.mkdir(parents=True)
        source = root / 'src/old.py'
        source.parent.mkdir()
        source.write_text('old source\n')
        plan = static / 'case_044_multicore_res.json'
        plan.write_text(json.dumps({'node_to_subgraph': {'1': 0}, 'core_schedules': [[0], [], [], [], []]}))
        summary = {'status': 'complete', 'source_commit': 'a' * 40,
                   'source_input_sha256': {'src/old.py': probe.digest(source)},
                   'artifacts': {plan.name: probe.digest(plan)}}
        (static / 'summary.json').write_text(json.dumps(summary))
        manifest = {'schema': probe.SCHEMA, 'source_commit': 'b' * 40,
                    'static_directory': str(static.relative_to(root)),
                    'static_summary_sha256': probe.digest(static / 'summary.json'),
                    'plan_sha256': probe.digest(plan), 'case_id': '044', 'cores': 5,
                    'budget': dict(probe.BUDGET)}
        path = static.parent / 'manifest.json'
        path.write_text(json.dumps(manifest))
        return source, manifest, path

    def test_prior_static_commit_reused_only_with_matching_source_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source, manifest, path = self.fixture(root)
            with patch.object(probe, 'ROOT', root), patch.object(probe, 'RESULT_ROOT', path.parent):
                value, _, _ = probe.load_manifest(path, probe.digest(path))
                self.assertEqual(value['source_commit'], 'b' * 40)
                source.write_text('changed source\n')
                with self.assertRaisesRegex(ValueError, 'source-input bytes differ'):
                    probe.load_manifest(path, probe.digest(path))

    def test_exact_budget_and_manifest_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            _, manifest, path = self.fixture(root)
            with patch.object(probe, 'ROOT', root), patch.object(probe, 'RESULT_ROOT', path.parent):
                with self.assertRaisesRegex(ValueError, 'manifest byte identity'):
                    probe.load_manifest(path, '0' * 64)
                manifest['budget']['workers'] = True
                path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'budget must be exact'):
                    probe.load_manifest(path, probe.digest(path))

    def test_resource_failure_stops_and_preserves_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            proc = Mock(pid=123, **{'poll.return_value': None})
            with (patch.object(probe.subprocess, 'Popen', return_value=proc),
                  patch.object(probe, 'observe', return_value={'pressure': 2, 'unused_mib': 2048, 'swapouts': 0}),
                  patch.object(probe, 'group_rss', return_value=0),
                  patch.object(probe, 'kill_owned', return_value=-9) as kill):
                result = probe.supervise(['fake'], Path(folder), 'prepare', time.monotonic() + 120, 0)
            kill.assert_called_once_with(proc)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['stop_reason'], 'resource gate closed')
            self.assertEqual(len(result['samples']), 1)

    def test_observation_fault_stops_owned_process(self):
        with tempfile.TemporaryDirectory() as folder:
            proc = Mock(pid=123)
            with (patch.object(probe.subprocess, 'Popen', return_value=proc),
                  patch.object(probe, 'observe', side_effect=RuntimeError('sensor unavailable')),
                  patch.object(probe, 'kill_owned', return_value=-9) as kill):
                result = probe.supervise(['fake'], Path(folder), 'prepare', time.monotonic() + 120, 0)
            kill.assert_called_once_with(proc)
            self.assertEqual(result['status'], 'failed')
            self.assertIn('sensor unavailable', result['stop_reason'])


if __name__ == '__main__':
    unittest.main()
