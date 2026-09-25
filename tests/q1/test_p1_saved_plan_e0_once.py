import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from src.review import p1_saved_plan_e0_once as runner


class SavedPlanE0OnceTests(unittest.TestCase):
    def temp_root(self, prefix):
        return tempfile.TemporaryDirectory(prefix=prefix, dir=runner.ROOT / "results/a")

    def test_bad_identity_refuses_before_output_or_dispatch(self):
        calls = []

        def bad_verify(*_):
            raise RuntimeError("frozen graph or plan SHA mismatch")

        with self.temp_root(".test-e0-bad-") as tmp, patch.object(runner, "_verify", bad_verify):
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "SHA mismatch"):
                runner.run_once(root / "graph", root / "plan", root / "out",
                                time.monotonic() + 20, execute=True,
                                process_fn=lambda *args: calls.append(args))
            self.assertEqual(calls, [])
            self.assertFalse((root / "out").exists())

    def test_expired_deadline_refuses_before_dispatch(self):
        calls = []
        with self.temp_root(".test-e0-expired-") as tmp, patch.object(
                runner, "_verify", lambda *_: {"verified": True}):
            root = Path(tmp)
            with self.assertRaisesRegex(TimeoutError, "expired"):
                runner.run_once(root / "graph", root / "plan", root / "out",
                                time.monotonic() - 1, execute=True,
                                process_fn=lambda *args: calls.append(args))
            self.assertEqual(calls, [])
            self.assertFalse((root / "out").exists())

    def test_failed_e0_keeps_logs_and_attempt_record(self):
        calls = []

        def failed(argv, folder, name, timeout, input_root):
            calls.append((argv, name, timeout, input_root))
            (folder / "E0.stdout.txt").write_bytes(b"raw stdout evidence\n")
            (folder / "E0.stderr.txt").write_bytes(b"raw stderr evidence\n")
            return {"status": "failed", "exit_code": 2, "cleanup_confirmed": True}

        with self.temp_root(".test-e0-failed-") as tmp, patch.object(
                runner, "_verify", lambda *_: {"verified": True}):
            root = Path(tmp)
            output = root / "out"
            with self.assertRaisesRegex(RuntimeError, "process status failed"):
                runner.run_once(root / "graph", root / "plan", output,
                                time.monotonic() + 30, execute=True, process_fn=failed)
            receipt = json.loads((output / "attempt.json").read_text())
            self.assertEqual(len(calls), 1)
            self.assertEqual(receipt["calls"],
                             {"constructor": 0, "E0": 1, "E1": 0, "E2": 0, "retry": 0})
            self.assertEqual(receipt["state"], "failed")
            self.assertEqual((output / "E0.stdout.txt").read_bytes(), b"raw stdout evidence\n")
            self.assertEqual((output / "E0.stderr.txt").read_bytes(), b"raw stderr evidence\n")

    def test_real_helper_facade_preserves_raw_logs_and_process_identity(self):
        fake_source = '''import json, pathlib, sys, time
time.sleep(0.05)
a=sys.argv
pathlib.Path(a[a.index("--output")+1]).write_text(json.dumps({"scene":"A","num_cores":5,"makespan":98932,"data_movement_bytes":{}}))
pathlib.Path(a[a.index("--trace-output")+1]).write_text("trace\\n")
pathlib.Path(a[a.index("--log-output")+1]).write_text("official log\\n")
print("stdout raw marker")
print("stderr raw marker", file=sys.stderr)
'''
        with self.temp_root(".test-e0-fake-") as tmp, patch.object(
                runner, "_verify", lambda *_: {"verified": True}):
            root = Path(tmp)
            fake = root / "fake-evaluator.py"
            fake.write_text(fake_source)
            with patch.object(runner, "EVALUATOR", fake):
                receipt = runner.run_once(root / "graph", root / "plan", root / "out",
                                          time.monotonic() + 30, execute=True)
            self.assertEqual(receipt["state"], "ok")
            self.assertEqual(receipt["calls"]["E0"], 1)
            self.assertEqual(receipt["process"]["cleanup_confirmed"], True)
            identity = receipt["process_identity"]
            self.assertGreater(identity["pid"], 0)
            self.assertEqual(identity["pgid"], identity["pid"])
            if Path("/proc/self/stat").is_file():
                self.assertIsInstance(identity["linux_proc_start_ticks"], int)
            else:
                self.assertIsNone(identity["linux_proc_start_ticks"])
            self.assertIn(b"stdout raw marker", (root / "out/E0.stdout.raw.txt").read_bytes())
            self.assertIn(b"stderr raw marker", (root / "out/E0.stderr.raw.txt").read_bytes())


if __name__ == "__main__":
    unittest.main()
