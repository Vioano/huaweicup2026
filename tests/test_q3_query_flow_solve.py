"""Injected R8 selection tests; no real constructor or official evaluator runs."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.q3 import query_flow_solve as solver
from evaluation_validation import EvaluationValidationError
import evaluation_validation
import multicore_cut_evaluate_problem_2 as official_p2
import multicore_cut_evaluate_problem_3 as official_p3


OLD = {"node_to_subgraph": {"1": 0}, "core_schedules": [[0], []]}
NEW = {"node_to_subgraph": {"1": 0}, "core_schedules": [[], [0]]}
META = {"strategy": "query_flow_affinity_r8"}


class QueryFlowSelectionTests(unittest.TestCase):
    def run_policy(self, *, new_m3=70, old_m2=100, new_m2=90, lower=0,
                   p3_error=None):
        p3 = Mock(side_effect=[{"makespan": 80},
                               p3_error if p3_error else {"makespan": new_m3}])
        p2 = Mock(side_effect=[{"makespan": old_m2}, {"makespan": new_m2}])
        save = Mock(return_value={})
        constructor = Mock(return_value=(NEW, META))
        bound = Mock(return_value={"with_cross_core_delay":
                                   {"lower_bound_cycles": lower}})

        def fresh(index, cores, evaluate, save_fn):
            result = evaluate(OLD)
            return (OLD, result, "forest"), 1, [], {"fresh": True}

        with patch.object(solver.forest_solve, "evaluate_candidates", side_effect=fresh):
            outcome = solver.evaluate_candidates(
                SimpleNamespace(graph={}), 2, p3, p2, save,
                construct=constructor, bound=bound,
                cross_delay=500, capacity={"L1": 100, "UB": 200})
        return outcome, p3, p2, save, constructor, bound

    def test_m3_gain_but_g_loss_rejected(self):
        (winner, p3_calls, p2_calls, records, selection), p3, p2, _, _, _ = (
            self.run_policy(new_m3=75, old_m2=100, new_m2=90))
        self.assertIs(winner[0], OLD)
        self.assertEqual((p3_calls, p2_calls, p3.call_count, p2.call_count), (2, 2, 2, 2))
        self.assertTrue(records[-1]["m2_nonworse"])
        self.assertFalse(records[-1]["g_nonworse"])
        self.assertEqual(selection["query_flow_policy"]["status"], "paired_gate_rejected")

    def test_m2_worsens_even_when_g_rises(self):
        (winner, _, p2_calls, records, _), _, p2, _, _, _ = (
            self.run_policy(new_m3=70, old_m2=100, new_m2=120))
        self.assertIs(winner[0], OLD)
        self.assertEqual((p2_calls, p2.call_count), (2, 2))
        self.assertFalse(records[-1]["m2_nonworse"])
        self.assertTrue(records[-1]["g_nonworse"])

    def test_all_three_conditions_accept(self):
        (winner, p3_calls, p2_calls, records, selection), _, _, save, constructor, _ = (
            self.run_policy(new_m3=70, old_m2=100, new_m2=95))
        self.assertIs(winner[0], NEW)
        self.assertEqual((p3_calls, p2_calls), (2, 2))
        self.assertEqual(selection["query_flow_policy"]["status"], "accepted")
        self.assertEqual(records[-1]["status"], "accepted")
        self.assertEqual([c.args[:2] for c in save.call_args_list],
                         [("p3", "query_flow"), ("p2", "incumbent"),
                          ("p2", "query_flow")])
        constructor.assert_called_once_with(unittest.mock.ANY, 2, cross_delay=500,
                                            capacity={"L1": 100, "UB": 200})

    def test_bound_prunes_without_new_scoring(self):
        (winner, p3_calls, p2_calls, records, _), p3, p2, _, _, bound = (
            self.run_policy(lower=80))
        self.assertIs(winner[0], OLD)
        self.assertEqual((p3_calls, p2_calls, p3.call_count, p2.call_count), (1, 0, 1, 0))
        self.assertEqual(records[-1]["status"], "bound_pruned")
        bound.assert_called_once()

    def test_failed_p3_consumes_one_call_without_p2(self):
        (winner, p3_calls, p2_calls, records, _), p3, p2, _, _, _ = (
            self.run_policy(p3_error=EvaluationValidationError("invalid proposal")))
        self.assertIs(winner[0], OLD)
        self.assertEqual((p3_calls, p2_calls, p3.call_count, p2.call_count), (2, 0, 2, 0))
        self.assertEqual(records[-1]["status"], "p3_rejected")

    def test_adapter_keeps_p2_settings_separate_and_persists_policy_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = root / "graph.json"
            graph.write_text("{}")
            out, evidence = root / "out.json", root / "evidence"

            def fake_policy(index, cores, p3, p2, save, **kwargs):
                self.assertEqual(cores, 2)
                self.assertEqual(p3(OLD)["makespan"], 80)
                self.assertEqual(p2(OLD)["makespan"], 100)
                raise EvaluationValidationError("stopped after paired mock")

            with patch.object(sys, "argv", ["query_flow_solve", str(graph), "--cores", "2",
                                            "-o", str(out), "--evidence", str(evidence)]), \
                 patch.object(solver, "Index", return_value=SimpleNamespace(graph={})), \
                 patch.object(solver, "evaluate_candidates", side_effect=fake_policy), \
                 patch.object(evaluation_validation, "read_evaluation_config",
                              return_value={"capacity": {"L1": 10, "UB": 20}, "bandwidth": 4}), \
                 patch.object(official_p2, "read_scene_b_config",
                              return_value={"cross_core_copy_delay_cycles": 7}), \
                 patch.object(official_p3, "read_cache_config",
                              return_value={"cache_capacity_bytes": 32,
                                            "cache_bandwidth_bytes_per_cycle": 8}), \
                 patch.object(official_p3, "evaluate_problem_3",
                              return_value={"makespan": 80}) as p3, \
                 patch.object(official_p2, "evaluate_scene_b",
                              return_value={"makespan": 100}) as p2:
                with self.assertRaisesRegex(EvaluationValidationError, "paired mock"):
                    solver.main()
            self.assertEqual(p3.call_args.kwargs,
                             {"bandwidth": 4, "capacity": {"L1": 10, "UB": 20},
                              "cross_core_copy_delay": 7, "cache_capacity_bytes": 32,
                              "cache_bandwidth_bytes_per_cycle": 8})
            self.assertEqual(p2.call_args.kwargs,
                             {"bandwidth": 4, "capacity": {"L1": 10, "UB": 20},
                              "cross_core_copy_delay": 7})
            ledger = json.loads((evidence / "evaluations.json").read_text())
            self.assertEqual([e["phase"] for e in ledger], ["p3", "p2"])
            self.assertEqual([e["status"] for e in ledger], ["ok", "ok"])
            receipt = json.loads((evidence / "receipt.json").read_text())
            self.assertEqual((receipt["status"], receipt["official_e0_calls"]),
                             ("failed", 2))

    def test_adapter_charges_failed_official_call_before_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = root / "graph.json"
            graph.write_text("{}")
            evidence = root / "evidence"

            def fake_policy(index, cores, p3, p2, save, **kwargs):
                p3(OLD)

            with patch.object(sys, "argv", ["query_flow_solve", str(graph),
                                            "-o", str(root / "out.json"),
                                            "--evidence", str(evidence)]), \
                 patch.object(solver, "Index", return_value=SimpleNamespace(graph={})), \
                 patch.object(solver, "evaluate_candidates", side_effect=fake_policy), \
                 patch.object(evaluation_validation, "read_evaluation_config",
                              return_value={"capacity": {"L1": 10, "UB": 20}, "bandwidth": 4}), \
                 patch.object(official_p2, "read_scene_b_config",
                              return_value={"cross_core_copy_delay_cycles": 7}), \
                 patch.object(official_p3, "read_cache_config",
                              return_value={"cache_capacity_bytes": 32,
                                            "cache_bandwidth_bytes_per_cycle": 8}), \
                 patch.object(official_p3, "evaluate_problem_3",
                              side_effect=EvaluationValidationError("official failure")):
                with self.assertRaisesRegex(EvaluationValidationError, "official failure"):
                    solver.main()
            ledger = json.loads((evidence / "evaluations.json").read_text())
            self.assertEqual(len(ledger), 1)
            self.assertEqual((ledger[0]["phase"], ledger[0]["status"]),
                             ("p3", "failed"))
            self.assertTrue((evidence / "evaluated-plan-0-p3.json").exists())
            receipt = json.loads((evidence / "receipt.json").read_text())
            self.assertEqual(receipt["official_e0_calls"], 1)


if __name__ == "__main__":
    unittest.main()
