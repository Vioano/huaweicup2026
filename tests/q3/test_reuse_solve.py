"""Acceptance/budget regression cases for a proxy with an observed reversal."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.q3 import reuse_solve as solver
from evaluation_validation import EvaluationValidationError


BASE = {"node_to_subgraph": {"1": 0}, "core_schedules": [[0], []]}
NEW = {"node_to_subgraph": {"1": 0}, "core_schedules": [[], [0]]}


class ReuseAcceptanceTests(unittest.TestCase):
    def run_case(self, old_m, new_m=None, spent=2, failure=None):
        evaluate = Mock(side_effect=[{"makespan": old_m}] * spent +
                        ([failure or {"makespan": new_m}] if new_m is not None else []))

        def upstream(index, cores, ev, save):
            for _ in range(spent):
                ev(BASE)
            return ((BASE, {"makespan": old_m}, "fresh_forest"), spent, [],
                    {"forest_policy": {"status": "accepted"}})

        with patch.object(solver.forest_solve, "evaluate_candidates", side_effect=upstream), \
             patch.object(solver, "construct", return_value=(NEW, {"strategy": "forest_reuse_grid"})) as construct, \
             patch.object(solver, "analyze", return_value={"with_cross_core_delay": {"lower_bound_cycles": 1}}), \
             patch.object(solver, "read_required_settings", return_value={"cross_core_copy_delay_cycles": 500}):
            result = solver.evaluate_candidates(SimpleNamespace(graph={}), 2, evaluate, Mock(return_value={}))
        return result, evaluate, construct

    def test_observed_improvement_and_reversal_are_decided_by_makespan(self):
        # Recorded values exercise the decision, not a new E0 reproduction.
        for old, new, expected in [(1004819, 948039, NEW), (6075472, 6215466, BASE),
                                   (1004819, 1004819, BASE)]:
            with self.subTest(old=old, new=new):
                (winner, calls, records, selection), evaluate, _ = self.run_case(old, new)
                self.assertEqual((winner[0], calls, evaluate.call_count), (expected, 3, 3))
                self.assertEqual(selection["forest_policy"]["status"], "accepted")
                self.assertEqual(records[-1]["makespan"], new)

    def test_consumed_budget_never_constructs_a_fourth_candidate(self):
        (winner, calls, records, selection), evaluate, construct = self.run_case(10, spent=3)
        construct.assert_not_called()
        self.assertEqual((winner[0], calls, evaluate.call_count), (BASE, 3, 3))
        self.assertEqual(records, [])
        self.assertEqual(selection["reuse_policy"]["status"], "skip")

    def test_invalid_candidate_keeps_fresh_incumbent_and_counts_attempt(self):
        (winner, calls, records, selection), evaluate, _ = self.run_case(
            10, 9, failure=EvaluationValidationError("invalid plan"))
        self.assertEqual((winner[0], calls, evaluate.call_count), (BASE, 3, 3))
        self.assertEqual(records[-1]["status"], "rejected")
        self.assertEqual(selection["reuse_policy"]["status"], "rejected")

    def test_entrypoint_enforces_same_overall_limit(self):
        with patch.object(solver, "run_solver") as run:
            solver.main()
        run.assert_called_once_with(policy=solver.evaluate_candidates, candidate_limit=3)


if __name__ == "__main__":
    unittest.main()
