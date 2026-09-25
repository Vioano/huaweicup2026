"""Pure-controller tests; no Popen, construction, Task, or evaluator."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.review import p1_r6_transfer_batch as batch
from src.review import p1_r6_pilot_once as supervisor


class FakeGuard:
    def __init__(self, fail_at=None):
        self.samples = []
        self.fail_at = fail_at

    def check(self):
        result = {"ok": len(self.samples) != self.fail_at,
                  "reason": "pressure not normal" if len(self.samples) == self.fail_at else None}
        self.samples.append(result)
        return result


def fake_stage(name, reason, rc):
    return {"name": name, "reason": reason, "returncode": rc,
            "same_pgid_residual": [], "cleanup": {"confirmed": True}}


class TransferBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.manifest = self.base / "manifest.json"
        self.manifest.write_text(json.dumps({"prior_test_receipt": "ignored"}))
        self.inputs = self.base / "inputs"
        self.admission = self.base / "freshps.json"
        self.admission.write_text("{}")
        self.prior = batch.ROOT / "ignored"
        self.calls = []

    def pilot(self, graph, reference, output, expected_head, **kwargs):
        self.calls.append(output.name)
        output.mkdir()
        (output / "probe").mkdir()
        probe_calls = {"heavy_construct": 1, "branch_construct": 1,
                       "solver": 0, "E0": 0, "E1": 0, "E2": 0}
        (output / "probe" / "receipt.json").write_text(json.dumps({
            "status": "structural-unsupported", "calls": probe_calls}))
        receipt = {"status": "stopped", "reason": "probe: child returned 1",
                   "stages": [fake_stage("probe", "child returned 1", 1)],
                   "calls": {"test_process": 0, "probe_process": 1,
                             "E0_process": 0, "E1": 0, "E2": 0, "retry": 0,
                             "baseline_E0": 0}, "probe_calls": probe_calls}
        (output / "receipt.json").write_text(json.dumps(receipt))
        return receipt

    def execute(self, *, pilot=None, guard=None, clock=None):
        with patch.object(batch, "file_sha", return_value="fixture"):
            return batch.run_batch(self.manifest, self.inputs, self.base / "out",
                                   "head", self.admission, pilot_fn=pilot or self.pilot,
                                   verify_fn=lambda *args: {"source_head": "head"},
                                   guard=guard or FakeGuard(), clock=clock or (lambda: 0.0),
                                   sleep=lambda _: None)

    def test_normal_no_candidate_continues_all_four(self):
        result = self.execute()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(self.calls, list(batch.ORDER))
        self.assertEqual([c["status"] for c in result["cells"]],
                         ["normal-no-candidate"] * 4)
        self.assertEqual(result["overall_exact_calls"],
                         {"heavy_construct": 4, "branch_construct": 4, "E0": 0})

    def test_identity_or_timeout_stops_without_next_cell(self):
        for reason in ("leader identity changed during execution", "stage timeout"):
            with self.subTest(reason=reason):
                self.calls = []
                output = self.base / "out"
                if output.exists():
                    import shutil
                    shutil.rmtree(output)
                def bad_pilot(*args, **kwargs):
                    receipt = self.pilot(*args, **kwargs)
                    receipt["stages"][0]["reason"] = reason
                    receipt["reason"] = f"probe: {reason}"
                    return receipt
                result = self.execute(pilot=bad_pilot)
                self.assertEqual(self.calls, ["082"])
                self.assertEqual(result["cells"][1]["status"], "not-run")
                self.assertEqual(result["status"], "stopped")

    def test_call_cap_and_missing_evidence_fail_closed(self):
        def extra_calls(*args, **kwargs):
            receipt = self.pilot(*args, **kwargs)
            receipt["probe_calls"]["heavy_construct"] = 2
            args[2].joinpath("receipt.json").write_text(json.dumps(receipt))
            return receipt
        result = self.execute(pilot=extra_calls)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(self.calls, ["082"])
        self.assertIn("constructor counts", result["reason"])
        self.assertEqual(result["successful_cell_subtotal"]["heavy_construct"], 0)
        self.assertIsNone(result["overall_exact_calls"]["heavy_construct"])
        self.assertEqual(result["cells"][0]["raw_pilot_calls"]["probe_process"], 1)

    def test_remaining_budget_and_resource_guard(self):
        result = self.execute(clock=lambda: 541.0)
        self.assertEqual(result["status"], "complete")
        # A separate monotonic clock advances only after the first pilot.
        import shutil
        shutil.rmtree(self.base / "out")
        now = [0.0]
        def advancing(*args, **kwargs):
            receipt = self.pilot(*args, **kwargs)
            now[0] = 541.0
            return receipt
        result = self.execute(pilot=advancing, clock=lambda: now[0])
        self.assertEqual(self.calls[-1], "082")
        self.assertEqual(result["cells"][1]["status"], "not-run")
        self.assertIn("less than 180", result["reason"])
        shutil.rmtree(self.base / "out")
        self.calls = []
        result = self.execute(guard=FakeGuard(fail_at=2))
        self.assertEqual(self.calls, [])
        self.assertIn("resource guard", result["reason"])

    def test_prelaunch_resource_rejection_never_calls_popen(self):
        out = self.base / "stage"
        out.mkdir()
        with patch.object(supervisor.subprocess, "Popen") as popen:
            stage = supervisor.run_stage("probe", ["unused"], 30, out, 0,
                                         resource_check=lambda: {"ok": False,
                                                                 "reason": "pressure"})
        popen.assert_not_called()
        self.assertNotIn("pid", stage)
        self.assertIn("before Popen", stage["reason"])

    def test_stage_resource_failure_uses_existing_cleanup(self):
        out = self.base / "stage"
        out.mkdir()
        class Child:
            pid = 12345
            def poll(self):
                return None
        child = Child()
        ticks = iter(i * 0.6 for i in range(100))
        samples = iter(({"ok": True}, {"ok": False, "reason": "swapouts increased"}))
        with (patch.object(supervisor.subprocess, "Popen", return_value=child),
              patch.object(supervisor.os, "getpgid", return_value=child.pid),
              patch.object(supervisor, "ps_value", return_value="start"),
              patch.object(supervisor, "leader_identity", return_value=True),
              patch.object(supervisor, "group_table", return_value=[]),
              patch.object(supervisor, "settled_exit", return_value=(False, None)),
              patch.object(supervisor, "cleanup_group", return_value={
                  "confirmed": True, "signals": ["SIGTERM"], "reason": None}) as cleanup,
              patch.object(supervisor.time, "monotonic", side_effect=lambda: next(ticks)),
              patch.object(supervisor.time, "sleep", return_value=None)):
            stage = supervisor.run_stage("probe", ["unused"], 30, out, 0,
                                         resource_check=lambda: next(samples))
        self.assertIn("swapouts increased", stage["reason"])
        cleanup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
