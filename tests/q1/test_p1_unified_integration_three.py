"""Pure mock control tests: no constructor, Task, scorer, or child process."""
import json
from pathlib import Path
import tempfile
import unittest

from src.review import p1_unified_integration_three as runner


def diagnostics(plan_sha):
    return {"actual_e1_calls_total": 3,
            "selected_plan_sha256": plan_sha,
            "selected_objective": [100, 20],
            "attempt": {"actual_e1_worker_calls": 1},
            "parent": {"actual_e1_calls_total": 2,
                       "extra_actual_e1_calls": 1,
                       "parent": {"baseline": {
                           "actual_e1_calls": 1,
                           "diagnostics": {"actual_e1_calls": 1,
                                           "online_score_attempts": 1,
                                           "online_scores": [{"worker_pid": 22}]}},
                           "refinement": {"actual_e1_calls": 0}}}}


class Guard:
    def __init__(self):
        self.samples = []
    def check(self):
        sample = {"ok": True}
        self.samples.append(sample)
        return sample


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.manifest = self.base / "manifest.json"
        self.manifest.write_text("{}")
        self.admission = self.base / "admission.json"
        self.admission.write_text("{}")
        self.graphs = []
        for case in runner.ORDER:
            graph = self.base / f"{case}.json"
            graph.write_text("{}")
            self.graphs.append({"case": case, "graph": graph,
                                "sha256": runner.file_sha(graph), "bytes": 2})
        self.stages = []

    def checked(self, *_):
        return {"head": "head", "graphs": self.graphs,
                "manifest_sha256": "test", "admission_sha256": "test"}

    def stage(self, name, argv, cap, out, check):
        self.stages.append((out.name, name, cap))
        self.assertTrue(check()["ok"])
        if name == "solver":
            plan = out / "plan.json"
            plan.write_text(json.dumps({"node_to_subgraph": {},
                                        "core_schedules": [[], [], [], [], []]}))
            (out / "diagnostics.json").write_text(json.dumps(diagnostics(runner.file_sha(plan))))
        else:
            (out / "e0" / "result.json").write_text("{}")
            (out / "e0" / "trace.json").write_text("{}")
            (out / "e0" / "official.log").write_text("")
        (out / f"{name}.stdout.raw").write_bytes(b"stdout")
        (out / f"{name}.stderr.raw").write_bytes(b"")
        return {"pid": 9, "reason": "complete", "returncode": 0,
                "same_pgid_residual": []}

    def execute(self, stage=None, clock=None):
        return runner.run(self.manifest, self.base / "out", "head", self.admission,
                          manifest_check=self.checked, stage_fn=stage or self.stage,
                          guard=Guard(), clock=clock or (lambda: 0.0))

    def test_three_cells_and_separate_e0(self):
        result = self.execute()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(self.stages, [(case, stage, cap)
                                       for case in runner.ORDER
                                       for stage, cap in (("solver", 300.0), ("E0", 120.0))])
        self.assertEqual(result["calls"], {"solver_process": 3,
                                           "online_E1_exact": 9,
                                           "E0_process": 3, "E2": 0, "retry": 0})

    def test_unknown_e1_stops_with_null(self):
        def missing_diag(name, argv, cap, out, check):
            stage = self.stage(name, argv, cap, out, check)
            if name == "solver":
                (out / "diagnostics.json").write_text("{}")
            return stage
        result = self.execute(stage=missing_diag)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["calls"]["solver_process"], 1)
        self.assertIsNone(result["calls"]["online_E1_exact"])
        self.assertEqual(result["cells"][1]["status"], "not-run")
        self.assertEqual(self.stages, [("085", "solver", 300.0)])

    def test_insufficient_batch_budget_does_not_launch(self):
        now = [0.0]
        def advancing(name, argv, cap, out, check):
            stage = self.stage(name, argv, cap, out, check)
            if out.name == "085" and name == "E0":
                now[0] = 901.0
            return stage
        result = self.execute(stage=advancing, clock=lambda: now[0])
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["cells"][1]["status"], "not-run")
        self.assertEqual(len(self.stages), 2)

    def test_unified_score_without_worker_identity_blocks_e0(self):
        def bad_score(name, argv, cap, out, check):
            stage = self.stage(name, argv, cap, out, check)
            if name == "solver":
                path = out / "diagnostics.json"
                data = json.loads(path.read_text())
                data["parent"]["parent"]["baseline"]["diagnostics"]["online_scores"][0].pop("worker_pid")
                path.write_text(json.dumps(data))
            return stage
        result = self.execute(stage=bad_score)
        self.assertEqual(result["status"], "stopped")
        self.assertIsNone(result["calls"]["online_E1_exact"])
        self.assertEqual(self.stages, [("085", "solver", 300.0)])

    def test_plan_hash_mismatch_blocks_e0(self):
        def bad_plan(name, argv, cap, out, check):
            stage = self.stage(name, argv, cap, out, check)
            if name == "solver":
                path = out / "diagnostics.json"
                data = json.loads(path.read_text())
                data["selected_plan_sha256"] = "wrong"
                path.write_text(json.dumps(data))
            return stage
        result = self.execute(stage=bad_plan)
        self.assertEqual(result["status"], "stopped")
        self.assertIn("selected plan bytes", result["reason"])
        self.assertEqual(result["calls"]["E0_process"], 0)


if __name__ == "__main__":
    unittest.main()
