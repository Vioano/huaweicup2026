"""Injected capacity policy checks; no official simulation is imported or run."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.q3 import capacity_solve as solver
from src.q3.construct import UnsupportedStructure
from src.q3.pipe_bound import UnsupportedBound
from evaluation_validation import EvaluationValidationError


def plan(core):
    return {"node_to_subgraph": {"1": 0},
            "core_schedules": [[] for _ in range(core)] + [[0]]}


META = {"selected": "pipeline_l1_capacity", "cuts": [0, 1]}


class CapacityPolicyTests(unittest.TestCase):
    def run_policy(self, *, prior=1, proposal=None, result=None, lower=0,
                   construct_error=None, bound_error=None, cores=5):
        previous = [plan(i) for i in range(prior)]
        proposal = plan(8) if proposal is None else proposal
        responses = [{"makespan": 100, "data_movement_bytes": 10} for _ in previous]
        if result is not None:
            responses.append(result)
        evaluate = Mock(side_effect=responses)
        save = Mock(return_value={"plan": {"sha256": "fixture"}})

        def incumbent(index, requested_cores, evaluate_fn, save_fn):
            self.assertEqual(requested_cores, cores)
            for old in previous:
                evaluate_fn(old)
            return ((previous[-1], responses[prior - 1], "forest_memory_order"),
                    prior, [], {"forest_policy": {"status": "fixture"}})

        with patch.object(solver.forest_solve, "evaluate_candidates", side_effect=incumbent), \
             patch.object(solver, "construct", side_effect=construct_error,
                          return_value=(proposal, META)) as construct, \
             patch.object(solver, "analyze",
                          side_effect=bound_error,
                          return_value={"with_cross_core_delay": {"lower_bound_cycles": lower}}) as bound, \
             patch.object(solver, "read_required_settings",
                          return_value={"cross_core_copy_delay_cycles": 500}):
            outcome = solver.evaluate_candidates(SimpleNamespace(graph={}), cores,
                                                  evaluate, save)
        return outcome, evaluate, save, construct, bound

    def test_four_call_ceiling_and_entrypoint(self):
        outcome, evaluate, save, _, _ = self.run_policy(
            prior=3, result={"makespan": 99, "data_movement_bytes": 99})
        winner, calls, records, selection = outcome
        self.assertEqual((winner[2], calls, evaluate.call_count), (solver.STRATEGY, 4, 4))
        self.assertEqual(records[-1]["status"], "ok")
        self.assertEqual(selection["capacity_pipeline_policy"]["evaluation_calls"], 4)
        save.assert_called_once()
        with patch.object(solver, "run_solver") as runner:
            solver.main()
        runner.assert_called_once_with(policy=solver.evaluate_candidates, candidate_limit=4)
        with self.assertRaisesRegex(AssertionError, "three-call contract"):
            self.run_policy(prior=4)

    def test_unsupported_keeps_fresh_forest(self):
        outcome, evaluate, _, construct, bound = self.run_policy(
            construct_error=UnsupportedStructure("not shared L1"))
        winner, calls, records, selection = outcome
        self.assertEqual((winner[2], calls, evaluate.call_count), ("forest_memory_order", 1, 1))
        self.assertEqual(records, [])
        self.assertEqual(selection["capacity_pipeline_policy"]["skip_reason"], "not shared L1")
        construct.assert_called_once()
        bound.assert_not_called()

    def test_duplicate_of_any_previously_evaluated_plan(self):
        outcome, evaluate, _, _, bound = self.run_policy(prior=2, proposal=plan(0))
        winner, calls, records, selection = outcome
        self.assertEqual((winner[0], calls, evaluate.call_count), (plan(1), 2, 2))
        self.assertEqual(records[-1]["status"], "duplicate")
        self.assertEqual(selection["capacity_pipeline_policy"]["status"], "duplicate")
        bound.assert_not_called()

    def test_certified_bound_prunes_and_unavailable_bound_does_not(self):
        outcome, evaluate, _, _, _ = self.run_policy(lower=100)
        winner, calls, records, selection = outcome
        self.assertEqual((winner[2], calls, evaluate.call_count), ("forest_memory_order", 1, 1))
        self.assertEqual(records[-1]["status"], "bound_pruned")
        self.assertEqual(selection["capacity_pipeline_policy"]["lower_bound_cycles"], 100)
        self.assertEqual(records[-1]["unscored_plan_sha256"],
                         __import__("hashlib").sha256(solver.encoded(plan(8))).hexdigest())
        outcome, evaluate, _, _, _ = self.run_policy(
            bound_error=UnsupportedBound("outside proof"),
            result={"makespan": 101, "data_movement_bytes": 5})
        self.assertEqual((outcome[1], evaluate.call_count), (2, 2))
        self.assertEqual(outcome[2][-1]["bound_unavailable"], "outside proof")

    def test_strict_makespan_only_even_if_secondary_regresses_and_one_core(self):
        outcome, evaluate, _, _, _ = self.run_policy(
            cores=1, result={"makespan": 99, "data_movement_bytes": 999})
        self.assertEqual((outcome[0][2], outcome[1], evaluate.call_count),
                         (solver.STRATEGY, 2, 2))
        self.assertEqual(outcome[3]["capacity_pipeline_policy"]["status"], "accepted")
        self.assertEqual(outcome[2][-1]["metadata"]["strategy"], solver.STRATEGY)
        outcome, evaluate, _, _, _ = self.run_policy(
            result={"makespan": 100, "data_movement_bytes": 1})
        self.assertEqual((outcome[0][2], outcome[1], evaluate.call_count),
                         ("forest_memory_order", 2, 2))

    def test_validation_failure_charges_call_unexpected_error_propagates(self):
        outcome, evaluate, save, _, _ = self.run_policy(
            result=EvaluationValidationError("bad candidate"))
        winner, calls, records, selection = outcome
        self.assertEqual((winner[2], calls, evaluate.call_count), ("forest_memory_order", 2, 2))
        self.assertEqual(records[-1]["status"], "rejected")
        self.assertEqual(selection["capacity_pipeline_policy"]["status"], "rejected")
        save.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, "bug"):
            self.run_policy(result=RuntimeError("bug"))


if __name__ == "__main__":
    unittest.main()
