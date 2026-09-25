"""Pure guard tests; no solver or evaluator calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.q3.fifth_core_final_export import export, percent95, strict_batch, study_segments


class FinalExportGuards(unittest.TestCase):
    def test_running_batch_is_rejected_before_reading_control(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "batch.json").write_text(json.dumps({"status": "running", "records": []}))
            with self.assertRaisesRegex(ValueError, "not a stopped fixed-solver segment"):
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

    def test_two_segments_require_disjoint_fixed_identity_and_combined_cap(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for file in ("a.json", "b.json"):
                (root / file).write_text("{}")
            def record(n, k):
                return {"case_id": f"{n:03d}", "cores": k,
                    "identity": {"graph_sha256": f"graph{n}", "config_sha256": "config", "official_sha256": "official"}}
            all_rows = [record(n, k) for n in range(1, 101) for k in range(1, 6)]
            common = {"solver_commit": "fixed", "solver_module": "solver", "runtime_id": "host",
                "official_sha256": "official", "algorithm": {"id": "fixed"},
                "environment": {"os": "same"}, "offline_costs": "none"}
            a = {**common, "run_id": "a", "e0_budget_used": 800, "records": all_rows[:400]}
            b = {**common, "run_id": "b", "e0_budget_used": 300, "records": all_rows[400:]}
            sources = {"a.json": a, "b.json": b}
            def loaded(_, path):
                return sources[path], root, {}
            with patch("src.q3.fifth_core_final_export.strict_batch", side_effect=loaded):
                segments, _ = study_segments(root, ["a.json", "b.json"])
                self.assertEqual(sum(len(item[1]["records"]) for item in segments), 500)
                b["records"] = all_rows[399:499]
                with self.assertRaisesRegex(ValueError, "overlapping"):
                    study_segments(root, ["a.json", "b.json"])
                b["records"] = all_rows[400:]
                b["solver_commit"] = "changed"
                with self.assertRaisesRegex(ValueError, "fixed algorithm"):
                    study_segments(root, ["a.json", "b.json"])
                b["solver_commit"] = "fixed"
                b["e0_budget_used"] = 1001
                with self.assertRaisesRegex(ValueError, "combined study E0"):
                    study_segments(root, ["a.json", "b.json"])


if __name__ == "__main__":
    unittest.main()
