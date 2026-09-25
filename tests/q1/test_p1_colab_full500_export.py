"""Pure receipt/schema identity refusals; no export or scoring."""
import json
from pathlib import Path
import tempfile
import unittest

from src.review import p1_colab_full500_export as x


class ExportGuardTests(unittest.TestCase):
    def test_unrecorded_seed_has_protocol_reason(self):
        evidence = {"missing_reasons": {"provenance.environment.cpu": "not measured"}}
        reasons = x.submission_missing_reasons(evidence)
        self.assertEqual(reasons["provenance.environment.cpu"], "not measured")
        self.assertIn("provenance.measurement.seed", reasons)
        self.assertIn("specified or recorded", reasons["provenance.measurement.seed"])
        self.assertIn("not independently timed", reasons["provenance.measurement.offline_costs"])

    def test_success_record_requires_board_structure(self):
        with self.assertRaisesRegex(ValueError, "required structure"):
            x.validate_record_shape({"status": "ok", "artifacts": {"plan": {}}})

    def test_reused_e0_and_tampered_plan_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "cells/001/k2"
            folder.mkdir(parents=True)
            plan = b'{"node_to_subgraph":{},"core_schedules":[[],[]]}\n'
            result = b'{"scene":"A","num_cores":2,"makespan":7,"data_movement_bytes":{"scheduled_copy_bytes":9}}\n'
            (folder / "plan.json").write_bytes(plan)
            (folder / "result.json").write_bytes(result)
            (folder / "run.json").write_text('{}')
            row = dict(status="ok", case_id="001", cores=2, calls=dict(solver=1,E0=1,E1=0),
                       artifacts=dict(plan=dict(sha256=x.digest(plan)),result=dict(sha256=x.digest(result))),
                       graph_sha256="graph", makespan_cycles=7, scheduled_copy_bytes=9,
                       model_source=dict(solver_commit=x.SOLVER),
                       solver=dict(status="ok",cleanup_confirmed=True),
                       evaluation=dict(status="ok",cleanup_confirmed=True,
                                       argv=["python","multicore_cut_evaluate_problem_1.py"]))
            row["calls"]["E2"] = 0
            batch = dict(download_root=root,download_file_hashes={p.relative_to(root).as_posix():x.digest(p.read_bytes())
                         for p in folder.iterdir()},input_hashes={"001":"graph"},
                         solver_commit=x.SOLVER,run_id=x.RUN_ID,config_sha256="config",
                         official_config_sha256="config",official_code_hash="official",
                         official_expected_hash="official")
            self.assertEqual(x.validate_success(row,folder,batch)["makespan"],7)
            row["reused_e0"] = {"old": True}
            with self.assertRaisesRegex(ValueError, "new-E0"):
                x.validate_success(row,folder,batch)
            row.pop("reused_e0")
            (folder / "plan.json").write_bytes(plan+b' ')
            with self.assertRaisesRegex(ValueError, "plan receipt hash"):
                x.validate_success(row,folder,batch)


if __name__ == "__main__": unittest.main()
