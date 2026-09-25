"""Pure injected policy tests; no official evaluator is imported or invoked."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.q3 import fifth_core_final_solve as solver
from src.q3.construct import UnsupportedStructure
from src.q3.pipe_bound import UnsupportedBound
from evaluation_validation import EvaluationValidationError


OLD = {"node_to_subgraph": {"1": 0}, "core_schedules": [[0]]}
NEW = {"node_to_subgraph": {"1": 0}, "core_schedules": [[], [], [], [], [0]]}
META = {"rule": "component_contiguous_extra_core"}


class FifthCorePolicyTests(unittest.TestCase):
    def run_policy(self, *, cores=5, forest_calls=3, proposal=NEW,
                   construct_error=None, lower=0, bound_error=None,
                   m3=90, m2_old=120, m2_new=110):
        p3 = Mock(side_effect=[m3 if isinstance(m3, Exception) else {"makespan": m3}])
        p2 = Mock(side_effect=[{"makespan": m2_old}, {"makespan": m2_new}])
        save = Mock(return_value={})
        construct = Mock(side_effect=construct_error, return_value=(proposal, META, {}))
        bound = Mock(side_effect=bound_error,
                     return_value={"with_cross_core_delay": {"lower_bound_cycles": lower}})

        def forest(index, count, evaluate, save_forest):
            self.assertEqual(count, cores)
            self.assertIs(evaluate, p3)
            return (OLD, {"makespan": 100}, "forest"), forest_calls, [], {"forest": True}

        with patch.object(solver.forest_solve, "evaluate_candidates", side_effect=forest):
            result = solver.evaluate_candidates(
                SimpleNamespace(graph={}), cores, p3, p2, save,
                construct=construct, bound=bound, cross_delay=7,
                capacity={"L1": 1, "UB": 2})
        return result, p3, p2, construct, bound, save

    def test_non_five_cores_preserve_forest_without_construction(self):
        for cores in (1, 2, 3, 4):
            (winner, p3_calls, p2_calls, records, selection), p3, p2, construct, _, _ = (
                self.run_policy(cores=cores))
            self.assertIs(winner[0], OLD)
            self.assertEqual((p3_calls, p2_calls, records), (3, 0, []))
            self.assertEqual(selection["fifth_core_policy"]["status"], "skip")
            p3.assert_not_called()
            p2.assert_not_called()
            construct.assert_not_called()

    def test_guard_duplicate_and_bound_prune_spend_no_extra_calls(self):
        scenarios = (
            ({"construct_error": UnsupportedStructure("guard")}, "unsupported"),
            ({"proposal": OLD}, "duplicate"),
            ({"lower": 100}, "bound_pruned"),
        )
        for kwargs, status in scenarios:
            (winner, p3_calls, p2_calls, records, _), p3, p2, _, _, _ = self.run_policy(**kwargs)
            self.assertIs(winner[0], OLD)
            self.assertEqual((p3_calls, p2_calls), (3, 0))
            self.assertEqual(records[-1]["status"], status)
            p3.assert_not_called()
            p2.assert_not_called()

    def test_fourth_p3_call_and_m3_gate(self):
        (winner, p3_calls, p2_calls, records, _), p3, p2, construct, bound, _ = (
            self.run_policy(m3=100))
        self.assertIs(winner[0], OLD)
        self.assertEqual((p3_calls, p2_calls), (4, 0))
        self.assertEqual(records[-1]["status"], "m3_not_better")
        construct.assert_called_once_with({}, 5, {"L1": 1, "UB": 2}, 7)
        bound.assert_called_once_with({}, NEW, 7)
        p3.assert_called_once_with(NEW)
        p2.assert_not_called()

    def test_paired_gate_uses_exact_integer_ratio(self):
        cases = (
            (120, 110, "accepted"),  # M2 lower; G also higher
            (1000, 1001, "paired_gate_rejected"),  # G rises, but M2 worsens
            (120, 100, "paired_gate_rejected"),  # M2 lower but G lower
            (120, 120, "accepted"),  # equal M2 and strict M3 improves G
        )
        for old, new, expected in cases:
            (winner, p3_calls, p2_calls, records, _), p3, p2, _, _, save = (
                self.run_policy(m2_old=old, m2_new=new))
            self.assertEqual((p3_calls, p2_calls), (4, 2))
            self.assertEqual(records[-1]["status"], expected)
            self.assertEqual(winner[0] is NEW, expected == "accepted")
            self.assertEqual([call.args[0] for call in p2.call_args_list], [OLD, NEW])
            self.assertEqual(p3.call_count, 1)
            self.assertEqual(sum(call.args[0] == "p2" for call in save.call_args_list), 2)

    def test_unsupported_bound_and_validation_failure(self):
        (winner, p3_calls, p2_calls, records, _), p3, _, _, _, _ = self.run_policy(
            bound_error=UnsupportedBound("unknown"), m3=EvaluationValidationError("bad"))
        self.assertIs(winner[0], OLD)
        self.assertEqual((p3_calls, p2_calls), (4, 0))
        self.assertEqual(records[-1]["status"], "p3_rejected")
        self.assertEqual(records[-1]["bound_unavailable"], "unknown")
        self.assertEqual(p3.call_count, 1)

    def test_forest_budget_and_failed_p2_call_are_counted(self):
        with self.assertRaisesRegex(RuntimeError, "forest incumbent exceeded"):
            self.run_policy(forest_calls=4)
        for forest_calls in (1, 2, 3):
            (_, p3_calls, p2_calls, _, _), p3, p2, _, _, _ = self.run_policy(
                forest_calls=forest_calls)
            self.assertEqual((p3_calls, p2_calls), (forest_calls + 1, 2))
            self.assertLessEqual(p3_calls, 4)
            self.assertEqual((p3.call_count, p2.call_count), (1, 2))
        # A P2 validation failure consumes its attempted call and retains M3 incumbent.
        p2_failure = Mock(side_effect=[{"makespan": 120}, EvaluationValidationError("bad P2")])
        with patch.object(solver.forest_solve, "evaluate_candidates", return_value=(
            (OLD, {"makespan": 100}, "forest"), 3, [], {})):
            winner, p3_calls, p2_calls, records, _ = solver.evaluate_candidates(
                SimpleNamespace(graph={}), 5, Mock(return_value={"makespan": 90}),
                p2_failure, Mock(return_value={}),
                construct=Mock(return_value=(NEW, META, {})),
                bound=Mock(return_value={"with_cross_core_delay": {"lower_bound_cycles": 0}}))
        self.assertIs(winner[0], OLD)
        self.assertEqual((p3_calls, p2_calls), (4, 2))
        self.assertEqual(records[-1]["status"], "p2_rejected")
        self.assertEqual(p2_failure.call_count, 2)


if __name__ == "__main__":
    unittest.main()
