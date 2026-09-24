"""Injected forest policy tests; no official evaluator processes."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.q3 import forest_solve as solver
from src.q3.construct import UnsupportedStructure
from evaluation_validation import EvaluationValidationError


ANCHOR = {"node_to_subgraph": {"1": 0}, "core_schedules": [[0]]}
PROPOSAL = {"node_to_subgraph": {"1": 0}, "core_schedules": [[], [0]]}
META = {"strategy": "forest_memory_order", "predicted_frontier": []}


class ForestPolicyTests(unittest.TestCase):
    def run_policy(self, *, incumbent_calls=1, candidate_result=None,
                   construct_error=None, proposal=PROPOSAL, lower=0,
                   bound_error=None):
        evaluate = Mock()
        responses = [{"makespan": 100}] * incumbent_calls
        if candidate_result is not None:
            responses.append(candidate_result)
        evaluate.side_effect = responses

        def incumbent(index, cores, evaluate_fn, save):
            for _ in range(incumbent_calls):
                evaluate_fn(ANCHOR)
            return ((ANCHOR, {"makespan": 100}, "witness"), incumbent_calls,
                    [], {"router": {"route": "forest_test"}})

        with patch.object(solver.witness_solve, "evaluate_candidates", side_effect=incumbent), \
             patch.object(solver, "construct", side_effect=construct_error,
                          return_value=(proposal, META)) as construct, \
             patch.object(solver, "analyze",
                          side_effect=[bound_error] if bound_error else None,
                          return_value={"with_cross_core_delay": {"lower_bound_cycles": lower}}), \
             patch.object(solver, "read_required_settings", return_value={"cross_core_copy_delay_cycles": 500}):
            outcome = solver.evaluate_candidates(SimpleNamespace(graph={}), 2,
                                                  evaluate, Mock(return_value={}))
        return outcome, evaluate, construct

    def test_fresh_incumbent_is_counted_and_candidate_stays_within_three(self):
        (winner, calls, records, selection), evaluate, _ = self.run_policy(
            incumbent_calls=2, candidate_result={"makespan": 99})
        self.assertEqual((winner[0], calls), (PROPOSAL, 3))
        self.assertEqual(evaluate.call_count, 3)
        self.assertEqual(records[-1]["status"], "ok")
        self.assertEqual(selection["forest_policy"]["status"], "accepted")

    def test_three_calls_skip_construction(self):
        (winner, calls, _, selection), evaluate, construct = self.run_policy(
            incumbent_calls=3)
        construct.assert_not_called()
        self.assertEqual((winner[0], calls, evaluate.call_count), (ANCHOR, 3, 3))
        self.assertEqual(selection["forest_policy"]["skip_reason"],
                         "three_call_budget_already_used")

    def test_duplicate_guard_and_safe_bound_skip(self):
        (winner, calls, records, selection), evaluate, _ = self.run_policy(
            proposal=ANCHOR)
        self.assertEqual((winner[0], calls, evaluate.call_count), (ANCHOR, 1, 1))
        self.assertEqual(records[-1]["status"], "duplicate")
        self.assertEqual(selection["forest_policy"]["status"], "duplicate")

        (winner, calls, records, selection), evaluate, _ = self.run_policy(
            construct_error=UnsupportedStructure("not a forest"))
        self.assertEqual((winner[0], calls, evaluate.call_count), (ANCHOR, 1, 1))
        self.assertEqual(selection["forest_policy"]["skip_reason"], "not a forest")
        self.assertEqual(records, [])

        (winner, calls, records, selection), evaluate, _ = self.run_policy(lower=100)
        self.assertEqual((winner[0], calls, evaluate.call_count), (ANCHOR, 1, 1))
        self.assertEqual(records[-1]["status"], "bound_pruned")
        self.assertEqual(selection["forest_policy"]["status"], "bound_pruned")

    def test_unsupported_bound_evaluates_but_tie_keeps_incumbent(self):
        from src.q3.pipe_bound import UnsupportedBound
        (winner, calls, records, _), evaluate, _ = self.run_policy(
            candidate_result={"makespan": 100},
            bound_error=UnsupportedBound("outside bound family"))
        self.assertEqual((winner[0], calls, evaluate.call_count), (ANCHOR, 2, 2))
        self.assertEqual(records[-1]["status"], "ok")
        self.assertEqual(records[-1]["bound_unavailable"], "outside bound family")

    def test_validation_failure_counts_call_and_unexpected_error_propagates(self):
        (winner, calls, records, selection), evaluate, _ = self.run_policy(
            candidate_result=EvaluationValidationError("bad plan"))
        self.assertEqual((winner[0], calls, evaluate.call_count), (ANCHOR, 2, 2))
        self.assertEqual(records[-1]["status"], "rejected")
        self.assertEqual(selection["forest_policy"]["status"], "rejected")
        with self.assertRaisesRegex(RuntimeError, "solver bug"):
            self.run_policy(candidate_result=RuntimeError("solver bug"))

    def test_entrypoint_declares_three_call_budget(self):
        with patch.object(solver, "run_solver") as runner:
            solver.main()
        runner.assert_called_once_with(policy=solver.evaluate_candidates, candidate_limit=3)


if __name__ == "__main__":
    unittest.main()
