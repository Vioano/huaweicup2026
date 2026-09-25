"""Static controller fixtures; no graph construction or evaluator process."""
from datetime import datetime, timedelta, timezone
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.q1_benchmarks import s6607_branch_full500 as runner


def single_core_diag(plan_sha):
    return {"selected_plan_sha256": plan_sha, "selected_objective": None,
            "stop_reason": "single-core-or-invalid", "actual_e1_calls_total": 0,
            "known_e1_calls_lower_bound": 0,
            "attempt": {"score_attempts": 0, "constructor_attempts": 0,
                        "actual_e1_worker_calls": 0},
            "parent": {"actual_e1_calls_total": 0, "known_e1_calls_lower_bound": 0,
                       "extra": [], "extra_score_attempts": 0,
                       "extra_actual_e1_calls": 0,
                       "parent": {"baseline": {"actual_e1_calls": 0,
                                               "diagnostics": {"actual_e1_calls": 0,
                                                               "online_scores": [],
                                                               "online_score_attempts": 0}},
                                  "refinement": {"actual_e1_calls": 0,
                                                 "score_attempts": 0}}}}


class BranchFull500Tests(unittest.TestCase):
    def test_prelaunch_resource_rejection_is_zero_dispatch(self):
        row = {"calls": {"solver": 1, "E1": None, "E0": 0},
               "solver": {"supervision": {"reason": "resource guard before Popen: pressure"}}}
        runner.reconcile_process_calls(row)
        self.assertEqual(row["calls"], {"solver": 0, "E1": 0, "E0": 0})
        row["solver"]["supervision"] = {"pid": 123, "reason": "identity acquisition failed"}
        runner.reconcile_process_calls(row)
        self.assertEqual(row["calls"]["solver"], 1)

    def test_single_core_no_selected_objective_needs_zero_e1(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp) / "plan.json"
            plan.write_text(json.dumps({"node_to_subgraph": {}, "core_schedules": [[]]}))
            diag = single_core_diag(runner.sha(plan))
            self.assertEqual(runner.checked_diagnostics(diag, runner.sha(plan)), 0)
            runner.checked_plan(plan, diag, 1)
            diag["actual_e1_calls_total"] = 1
            with self.assertRaises((RuntimeError, ValueError)):
                runner.checked_diagnostics(diag, runner.sha(plan))

    def test_formal_gate_rejects_budget_drift_and_expiry(self):
        with tempfile.TemporaryDirectory() as temp:
            gate_path = Path(temp) / "gate.json"
            output = runner.ROOT / "output" / "not-created-full500-mock-run"
            self.assertFalse(output.exists())
            gate = {"status": "admitted", "scope": "p1-branch-refine-full500",
                    "owner_session": "nikolastarx/s-6607cb2735304751b36662035723372b",
                    "source_head": "head", "solver_commit": runner.SOLVER,
                    "runner_sha256": runner.sha(Path(runner.__file__)),
                    "output_dir": str(output), "budget": dict(runner.BUDGET),
                    "expires_at_utc": (datetime.now(timezone.utc)
                                       + timedelta(hours=1)).isoformat()}
            with patch.object(runner.subprocess, "check_output", return_value="head\n"):
                gate_path.write_text(json.dumps(gate))
                self.assertEqual(runner.check_gate(gate_path, output, "head")["source_head"], "head")
                gate["budget"]["E1_max"] = True
                gate_path.write_text(json.dumps(gate))
                with self.assertRaises(ValueError):
                    runner.check_gate(gate_path, output, "head")
                gate["budget"] = dict(runner.BUDGET)
                gate["expires_at_utc"] = "2000-01-01T00:00:00Z"
                gate_path.write_text(json.dumps(gate))
                with self.assertRaises(ValueError):
                    runner.check_gate(gate_path, output, "head")
            self.assertFalse(output.exists())

    def test_preflight_binds_new_wrapper_file_and_git_tree(self):
        old = runner.old
        previous = (old.__file__, old.RUNNER_PATH, old.SOLVER, old.checked_diagnostics,
                    old.maybe_reuse, old.process_cell, old.h.process)
        try:
            runner.install_checks()
            self.assertEqual(Path(old.__file__).resolve(), Path(runner.__file__).resolve())
            self.assertEqual(old.RUNNER_PATH, runner.RUNNER_PATH)
            paths = sorted(p.relative_to(runner.ROOT).as_posix()
                           for folder in (runner.ROOT / "src/q1", runner.ROOT / "src/eval_exact")
                           for p in folder.rglob("*.py"))
            listing = "\n".join(paths) + "\n"
            def git(cmd, **kwargs):
                if "rev-parse" in cmd:
                    return b"head\n"
                if "ls-tree" in cmd or "ls-files" in cmd:
                    return listing.encode()
                if "diff" in cmd:
                    return b""
                raise AssertionError(cmd)
            mini = {"files": [], "official_code_hash": hashlib.sha256(b"").hexdigest(),
                    "case_archive": {"path": "unused", "sha256": "archive"}}
            with (patch.object(old.subprocess, "check_output", side_effect=git),
                  patch.object(old, "frozen", side_effect=lambda commit, path:
                               (b"multicore_cut_evaluate_problem_1.py"
                                if path == "src/q1_benchmarks/s59ee_v4_full500_e0900.py"
                                else (runner.ROOT / path).read_bytes())),
                  patch.object(old.h, "read", return_value=mini),
                  patch.object(old.h, "sha", return_value="archive")):
                head, _, _ = old.preflight()
            self.assertEqual(head, "head")
        finally:
            (old.__file__, old.RUNNER_PATH, old.SOLVER, old.checked_diagnostics,
             old.maybe_reuse, old.process_cell, old.h.process) = previous

    def test_official_mismatch_marks_failed_and_preserves_calls(self):
        old = runner.old
        previous = (old.__file__, old.RUNNER_PATH, old.SOLVER, old.checked_diagnostics,
                    old.maybe_reuse, old.process_cell, old.h.process)
        with tempfile.TemporaryDirectory() as temp:
            batch = Path(temp)
            folder = batch / "cells" / "085" / "k5"
            folder.mkdir(parents=True)
            (folder / "diagnostics.json").write_text(json.dumps({
                "selected_objective": [100, 20]}))
            def fake_cell(*args):
                return {"status": "ok", "makespan_cycles": 101,
                        "scheduled_copy_bytes": 20,
                        "calls": {"solver": 1, "E1": 3, "E0": 1, "E2": 0}}
            try:
                old.process_cell = fake_cell
                runner.install_checks()
                row = old.process_cell(("085", 5), batch, None, None, None, None, None)
                self.assertEqual(row["status"], "failed")
                self.assertEqual(row["calls"]["E1"], 3)
                self.assertEqual(row["calls"]["E0"], 1)
                self.assertEqual(old.h.read(folder / "run.json")["status"], "failed")
            finally:
                (old.__file__, old.RUNNER_PATH, old.SOLVER, old.checked_diagnostics,
                 old.maybe_reuse, old.process_cell, old.h.process) = previous


if __name__ == "__main__":
    unittest.main()
