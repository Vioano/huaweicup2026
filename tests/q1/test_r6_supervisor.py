"""Zero-scoring regression for three real, tiny supervised Python children."""
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

from src.review import p1_r6_pilot_once as supervisor


class SupervisorRaceTests(unittest.TestCase):
    stages = []

    @classmethod
    def setUpClass(cls):
        cls.output = Path(os.environ["R6_REGRESSION_OUT"])
        cls.output.mkdir(parents=True, exist_ok=False)

    @classmethod
    def tearDownClass(cls):
        receipt = {"scope": "three tiny Python children; no construct or scoring",
                   "child_processes": len(cls.stages), "stages": cls.stages,
                   "all_same_pgid_residual_empty": all(
                       stage.get("same_pgid_residual") == [] for stage in cls.stages)}
        (cls.output / "receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    def stage(self, name, code, cap):
        stage = supervisor.run_stage(
            name, [sys.executable, "-B", "-c", code], cap,
            self.output, time.monotonic())
        self.stages.append(stage)
        return stage

    def test_1_fast_success_after_delayed_identity_read(self):
        real_ps_value = supervisor.ps_value

        def delayed_ps_value(pid, field):
            if field == "lstart":
                time.sleep(0.15)
                # A transient ps lookup miss after the real short-lived
                # child exits. Do not replace Popen, poll, rc, or PGID data.
                return None
            return real_ps_value(pid, field)

        # Delay only the identity observation. The child, exit code, Popen
        # handle, actual PGID query, and cleanup paths are real.
        with patch.object(supervisor, "ps_value", delayed_ps_value):
            stage = self.stage("fast", "pass", 2.0)
        self.assertEqual(stage["reason"], "complete")
        self.assertEqual(stage["returncode"], 0)
        self.assertEqual(stage["same_pgid_residual"], [])
        self.assertTrue(stage.get("fast_exit_after_identity_failure"))

    def test_2_nonzero_exit_stops_without_signal(self):
        stage = self.stage("nonzero", "import sys; sys.exit(3)", 2.0)
        self.assertEqual(stage["reason"], "child returned 3")
        self.assertEqual(stage["returncode"], 3)
        self.assertEqual(stage["same_pgid_residual"], [])
        self.assertEqual(stage["cleanup"]["signals"], [])

    def test_3_timeout_terminates_confirmed_group(self):
        stage = self.stage("timeout", "import time; time.sleep(3)", 0.4)
        self.assertEqual(stage["reason"], "stage timeout")
        self.assertEqual(stage["same_pgid_residual"], [])
        self.assertTrue(stage["cleanup"]["confirmed"])
        self.assertIn("SIGTERM", stage["cleanup"]["signals"])


if __name__ == "__main__":
    unittest.main()
