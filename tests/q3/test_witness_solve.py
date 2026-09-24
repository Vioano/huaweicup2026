"""Verify the witness policy's exact incumbent and budget; injected scoring."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from src.q3 import witness_solve as solver
from evaluation_validation import EvaluationValidationError

ANCHOR = {"node_to_subgraph": {"1": 0, "2": 1}, "core_schedules": [[0, 1], []]}
PROPOSAL = {"node_to_subgraph": {"1": 0, "2": 1}, "core_schedules": [[0], [1]]}


class WitnessPolicyTests(unittest.TestCase):
    def run_policy(self, result, *, placement=70, ready=80, lower=0,
                   incumbent_calls=2, proposal=PROPOSAL, reconstructed=70):
        def incumbent(index, cores, evaluate, save):
            for _ in range(incumbent_calls):
                score = evaluate(ANCHOR)
            return ((ANCHOR, score, "current"), incumbent_calls,
                    [{"name": "attention_gap", "metadata": {
                        "placement_proxy_makespan_cycles": placement,
                        "proxy_makespan_cycles": ready}}],
                    {"router": {"route": "attention", "attention_cross_delay_cycles": 500}})
        evaluator = Mock(side_effect=[{"makespan": 100}] * incumbent_calls + [result])
        with patch.object(solver.pipeline_solve, "evaluate_candidates", side_effect=incumbent), \
             patch.object(solver, "construct", return_value=(proposal, {
                 "strategy": "witness", "placement_proxy_makespan_cycles": reconstructed})) as builder, \
             patch.object(solver, "analyze", return_value={"with_cross_core_delay": {"lower_bound_cycles": lower}}):
            answer = solver.evaluate_candidates(SimpleNamespace(graph={}), 2, evaluator, Mock(return_value={}))
        self.assertEqual(answer[1], evaluator.call_count)
        return answer, builder

    def test_official_M_acceptance_is_independent_of_proxy(self):
        for m in (90, 100, 110):
            (winner, calls, records, selection), _ = self.run_policy({"makespan": m})
            self.assertEqual(winner[0], PROPOSAL if m < 100 else ANCHOR)
            self.assertEqual(calls, 3)
            self.assertEqual(selection["witness_policy"]["evaluation_calls"], 3)
            self.assertEqual(records[-1]["makespan"], m)

    def test_proxy_screen_and_shared_pipeline_budget_avoid_dispatch(self):
        for kwargs in ({"placement": 80}, {"incumbent_calls": 3}):
            (winner, calls, _, selection), builder = self.run_policy(RuntimeError("unexpected E0"), **kwargs)
            self.assertEqual(winner[0], ANCHOR)
            self.assertEqual(calls, kwargs.get("incumbent_calls", 2))
            self.assertIn("witness_skip", selection)
            builder.assert_not_called()

    def test_duplicate_and_certified_bound_keep_incumbent(self):
        for kwargs in ({"proposal": ANCHOR}, {"lower": 100}):
            (winner, calls, _, _), _ = self.run_policy(RuntimeError("unexpected E0"), **kwargs)
            self.assertEqual((winner[0], calls), (ANCHOR, 2))

    def test_validation_rejection_and_construction_bug_distinct(self):
        (winner, calls, records, _), _ = self.run_policy(EvaluationValidationError("invalid"))
        self.assertEqual((winner[0], calls, records[-1]["status"]), (ANCHOR, 3, "rejected"))
        with self.assertRaisesRegex(AssertionError, "changed the frozen placement"):
            self.run_policy({"makespan": 90}, reconstructed=69)
        with self.assertRaisesRegex(RuntimeError, "bug"):
            self.run_policy(RuntimeError("bug"))

    def test_other_routes_unchanged(self):
        existing=((ANCHOR,{"makespan":100},"stage"),1,[],{"router":{"route":"stage"}})
        with patch.object(solver.pipeline_solve,"evaluate_candidates",return_value=existing), \
             patch.object(solver,"construct") as builder:
            self.assertEqual(solver.evaluate_candidates(None,5,Mock(),Mock()),existing)
        builder.assert_not_called()
