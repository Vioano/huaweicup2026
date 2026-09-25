"""Controller-only receipt reuse tests; never launch a supervised worker."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.review import p1_r6_pilot_once as controller


class ReuseTests(unittest.TestCase):
    def inputs(self, root):
        graph, reference = root / "graph.json", root / "reference.json"
        graph.write_text("{}\n")
        reference.write_text("{}\n")
        return graph, reference

    def prior(self, root):
        folder = root / "prior"
        folder.mkdir()
        artifacts = {}
        for name, raw in (("tests.stdout.raw", b""),
                          ("tests.stderr.raw", b"Ran 5 tests\nOK\n")):
            path = folder / name
            path.write_bytes(raw)
            artifacts[name] = {"bytes": len(raw), "sha256": controller.sha(raw)}
        receipt = {
            "source_head": "old-head", "calls": {"test_process": 1},
            "stages": [{"name": "tests", "reason": "complete",
                        "returncode": 0, "same_pgid_residual": []}],
            "source_sha256": {name: controller.file_sha(controller.ROOT / name)
                              for name in controller.STRUCTURE_TEST_SOURCES},
            "artifact_hashes": artifacts,
        }
        path = folder / "receipt.json"
        path.write_text(json.dumps(receipt) + "\n")
        return path, receipt

    def run_controller(self, graph, reference, output, prior=None):
        seen = []

        def fake_stage(name, argv, cap, folder, overall_start):
            seen.append(name)
            return {"name": name, "reason": "simulated stop",
                    "same_pgid_residual": [], "returncode": 1}

        with patch.object(controller, "preflight", return_value="current-head"), \
             patch.object(controller, "run_stage", side_effect=fake_stage):
            result = controller.pilot(graph, reference, output, "current-head", prior)
        return result, seen

    def test_default_still_starts_tests_stage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            graph, reference = self.inputs(root)
            result, seen = self.run_controller(graph, reference, root / "out")
            self.assertEqual(seen, ["tests"])
            self.assertNotIn("structure_tests_reused", result)

    def test_matching_prior_skips_only_tests_stage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            graph, reference = self.inputs(root)
            prior, _ = self.prior(root)
            result, seen = self.run_controller(graph, reference, root / "out", prior)
            self.assertEqual(seen, ["probe"])
            self.assertEqual(result["calls"]["test_process"], 0)
            self.assertEqual(result["structure_tests_reused"]["receipt_sha256"],
                             controller.file_sha(prior))
            self.assertIn("reused_scope", result["structure_tests_reused"])

    def test_changed_source_hash_rejects_before_any_child(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            graph, reference = self.inputs(root)
            prior, receipt = self.prior(root)
            receipt["source_sha256"]["src/q1/branch_aid.py"] = "0" * 64
            prior.write_text(json.dumps(receipt) + "\n")
            with patch.object(controller, "preflight", side_effect=AssertionError("git launched")), \
                 patch.object(controller, "run_stage", side_effect=AssertionError("worker launched")):
                result = controller.pilot(graph, reference, root / "out", "current-head", prior)
            self.assertEqual(result["status"], "stopped")
            self.assertIn("source hash", result["reason"])
            self.assertEqual(result["calls"]["test_process"], 0)

    def test_missing_residual_evidence_rejects_before_any_child(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            graph, reference = self.inputs(root)
            prior, receipt = self.prior(root)
            del receipt["stages"][0]["same_pgid_residual"]
            prior.write_text(json.dumps(receipt) + "\n")
            with patch.object(controller, "preflight", side_effect=AssertionError("git launched")), \
                 patch.object(controller, "run_stage", side_effect=AssertionError("worker launched")):
                result = controller.pilot(graph, reference, root / "out", "current-head", prior)
            self.assertEqual(result["status"], "stopped")
            self.assertIn("complete/rc0/empty-residual", result["reason"])
            self.assertEqual(result["calls"]["test_process"], 0)


if __name__ == "__main__":
    unittest.main()
