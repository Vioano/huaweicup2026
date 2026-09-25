"""Mock-only controller tests: no graph construction or E1/E0 execution."""
import unittest
from unittest.mock import Mock

from src.q1 import branch_refine


BASE = {"node_to_subgraph": {1: 0}, "core_schedules": [[0], []]}
CANDIDATE = {"node_to_subgraph": {1: 1}, "core_schedules": [[], [1]]}


def parent(objective=(100, 200), digest=None):
    return {"selected_plan_sha256": digest or branch_refine.digest(BASE),
            "selected_objective": list(objective), "selected": "structural-parent",
            "actual_e1_calls_total": 4}


def score(makespan, copy_bytes, status="ok", worker_pid=123):
    return {"status": status, "makespan": makespan,
            "data_movement_bytes": {"scheduled_copy_bytes": copy_bytes},
            "worker_pid": worker_pid}


class BranchRefineControllerTests(unittest.TestCase):
    def run_case(self, *, parent_info=None, candidate=CANDIDATE,
                 candidate_info=None, scored=None, scorer=None):
        constructor = Mock(return_value=(candidate, candidate_info or {"status": "candidate-unscored"}))
        validator = Mock()
        scorer = scorer or Mock(return_value=scored or score(90, 300))
        result, info = branch_refine.solve(
            {}, 2, parent_solve=Mock(return_value=(BASE, parent_info or parent())),
            constructor=constructor, validator=validator, scorer=scorer)
        return result, info, constructor, validator, scorer

    def test_parent_hash_or_objective_mismatch_prevents_construction(self):
        for invalid in (parent(digest="0" * 64), parent(objective=(100, -1))):
            result, info, constructor, _, scorer = self.run_case(parent_info=invalid)
            self.assertEqual(result, BASE)
            constructor.assert_not_called()
            scorer.assert_not_called()
            self.assertEqual(info["attempt"]["score_attempts"], 0)

    def test_unsupported_and_identical_candidate_never_score(self):
        for candidate, diag in ((BASE, {"status": "unsupported", "reason": "no bridge"}),
                                (BASE, {"status": "candidate-unscored"})):
            result, info, constructor, _, scorer = self.run_case(
                candidate=candidate, candidate_info=diag)
            self.assertEqual(result, BASE)
            self.assertEqual(constructor.call_count, 1)
            scorer.assert_not_called()
            self.assertEqual(info["attempt"]["score_attempts"], 0)

    def test_failed_score_and_worse_objective_keep_parent(self):
        for tested in (score(80, 100, status="failed"), score(101, 0)):
            result, info, constructor, validator, scorer = self.run_case(scored=tested)
            self.assertEqual(result, BASE)
            self.assertEqual(constructor.call_count, 1)
            self.assertEqual(validator.call_count, 1)
            self.assertEqual(scorer.call_count, 1)
            self.assertEqual(info["attempt"]["score_attempts"], 1)

    def test_makespan_first_then_copy_bytes_on_tie(self):
        for tested in (score(99, 9999), score(100, 199)):
            result, info, _, _, scorer = self.run_case(scored=tested)
            self.assertEqual(result, CANDIDATE)
            self.assertEqual(info["selected_objective"],
                             [tested["makespan"], tested["data_movement_bytes"]["scheduled_copy_bytes"]])
            self.assertEqual(info["selected_plan_sha256"], branch_refine.digest(CANDIDATE))
            self.assertEqual(scorer.call_count, 1)

    def test_dispatch_exception_preserves_unknown_worker_count(self):
        scorer = Mock(side_effect=RuntimeError("lost after dispatch"))
        result, info, _, _, scorer = self.run_case(scorer=scorer)
        self.assertEqual(result, BASE)
        self.assertEqual(scorer.call_count, 1)
        self.assertIsNone(info["attempt"]["actual_e1_worker_calls"])
        self.assertEqual(info["attempt"]["actual_e1_worker_calls_range"], [0, 1])
        self.assertIsNone(info["actual_e1_calls_total"])
        self.assertEqual(info["known_e1_calls_lower_bound"], 4)

    def test_parent_unknown_exact_count_preserves_known_subtotal(self):
        info = parent()
        info.update(actual_e1_calls_total=None, known_e1_calls_lower_bound=3)
        _, result, _, _, _ = self.run_case(parent_info=info)
        self.assertIsNone(result["actual_e1_calls_total"])
        self.assertEqual(result["known_e1_calls_lower_bound"], 4)


if __name__ == "__main__":
    unittest.main()
