"""Pure guard tests; no solver or evaluator calls."""
import json
from pathlib import Path
import tempfile
import unittest

from src.q3.fifth_core_final_export import export, percent95, strict_batch


class FinalExportGuards(unittest.TestCase):
    def test_running_batch_is_rejected_before_reading_control(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "batch.json").write_text(json.dumps({"status": "running", "records": []}))
            with self.assertRaisesRegex(ValueError, "not the fixed completed"):
                strict_batch(root, "batch.json")

    def test_existing_export_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            area = root / "results/a/q3-nikolastarx"
            area.mkdir(parents=True)
            output = area / "final-export"
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("original")
            with self.assertRaisesRegex(ValueError, "new repository-relative"):
                export(root, "batch.json", output.relative_to(root).as_posix())
            self.assertEqual(sentinel.read_text(), "original")

    def test_p95_uses_linear_order_statistic(self):
        self.assertAlmostEqual(percent95([1, 2, 3, 4, 5]), 4.8)

    def test_completed_batch_rejects_invalid_process_and_call_totals(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            records = [{"case_id": f"{n:03d}", "cores": k, "status": "ok",
                "calls": {"solver": 1, "E0": 1, "E1": 0, "E2": 0}, "failure": None,
                "solver_process": {"status": "ok", "exit_code": 0, "wall_seconds": 1.0}}
                for n in range(1, 101) for k in range(1, 6)]
            batch = {"status": "stage_complete", "records": records,
                "solver_commit": "f6fd8153375a7fb64f9af2c8f36c35356fb7d878",
                "solver_module": "src.q3.fifth_core_final_solve", "full500_verified": {"cells": 500},
                "e0_budget_used": 500, "budget": {"max_e0_calls": 1800}, "stages": []}
            path = root / "batch.json"
            records[0]["solver_process"]["wall_seconds"] = float("nan")
            path.write_text(json.dumps(batch))
            with self.assertRaisesRegex(ValueError, "invalid call, process or timing"):
                strict_batch(root, "batch.json")
            records[0]["solver_process"]["wall_seconds"] = 1.0
            batch["e0_budget_used"] = 499
            path.write_text(json.dumps(batch))
            with self.assertRaisesRegex(ValueError, "E0 call total"):
                strict_batch(root, "batch.json")


if __name__ == "__main__":
    unittest.main()
