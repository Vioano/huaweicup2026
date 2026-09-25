"""No-score regression checks for the tail3 wrapper."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import json
from datetime import datetime, timezone, timedelta

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('holdout_tail3_runner', HERE / 'run_tail3.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class PreparationTests(unittest.TestCase):
    def test_absolute_result_crosses_child_cwd(self):
        from src.q2_nikolastarx import evaluate_feedback as feedback
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            parent = Path(temp) / 'parent'
            child = Path(temp) / 'fixed-checkout'
            parent.mkdir()
            child.mkdir()
            prior_cwd, prior_root = Path.cwd(), feedback.ROOT
            try:
                os.chdir(parent)
                feedback.ROOT = child
                target = runner.absolute_output(Path('deliver/result.json'))
                target.parent.mkdir()
                command = [sys.executable, '-B', '-c',
                           'from pathlib import Path; import sys; Path(sys.argv[1]).write_text("received")',
                           str(target)]
                receipt = feedback.monitored(command, parent / 'fake-process',
                                             time.perf_counter() + 5, 2 << 30)
                self.assertEqual(receipt['status'], 'ok', receipt)
                self.assertEqual(target.read_text(), 'received')
                self.assertFalse((child / 'deliver/result.json').exists())
            finally:
                feedback.ROOT = prior_root
                os.chdir(prior_cwd)

    def test_pending_gate_dispatches_nothing(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            output = Path(temp) / 'forbidden-run'
            command = [sys.executable, '-B', str(HERE / 'run_tail3.py'),
                       '--gate', str(HERE / 'gate-template.json'), '--output', str(output)]
            proc = subprocess.run(command, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('unadmitted_or_unpinned_gate', proc.stderr)
            self.assertFalse(output.exists())

    def test_admitted_gate_wrong_output_dispatches_nothing(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            gate_path = Path(temp) / 'wrong-output-gate.json'
            gate = {'scope': runner.SCOPE, 'status': 'admitted',
                    'manifest_sha256': runner.sha(HERE / 'manifest.json'),
                    'runner_sha256': runner.sha(HERE / 'run_tail3.py'),
                    'output_dir': str(Path(temp) / 'wrong-output'),
                    'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
            gate_path.write_text(json.dumps(gate))
            target = Path(runner.OUTPUT_DIR)
            existed = target.exists()
            with mock.patch.object(sys, 'argv', ['run_tail3.py', '--gate', str(gate_path),
                                                '--output', str(target)]), \
                 mock.patch.object(runner.holdout, 'preflight') as preflight:
                with self.assertRaisesRegex(ValueError, 'unadmitted_or_unpinned_gate'):
                    runner.main()
                preflight.assert_not_called()
            self.assertEqual(target.exists(), existed)


if __name__ == '__main__':
    unittest.main()
