"""Injected comparisons, no evaluator processes or score claims."""
import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.q3 import pipeline_solve as solver
from src.q3.construct import UnsupportedStructure
from evaluation_validation import EvaluationValidationError
from src.q3.safe_solve import main as run_solver
from tests.q3.test_shared_pipeline import graph

ANCHOR = {"node_to_subgraph": {"1": 0, "2": 1}, "core_schedules": [[0, 1], []]}
PROPOSAL = {"node_to_subgraph": {"1": 0, "2": 1}, "core_schedules": [[0], [1]]}


class PipelinePolicyTests(unittest.TestCase):
    def execute(self, result, *, proposal=PROPOSAL, lower=0, unsupported=False, cores=2):
        def incumbent(index, cores, evaluate, save):
            evaluate(ANCHOR)
            value = evaluate(ANCHOR)
            return ((ANCHOR, value, "incumbent"), 2, [], {"router": {"route": "general_gap"}})
        evaluate = Mock(side_effect=[{"makespan": 101}, {"makespan": 100}, result])
        with patch.object(solver.calendar_solve, "evaluate_candidates", side_effect=incumbent), \
             patch.object(solver, "construct", side_effect=UnsupportedStructure("guard") if unsupported else None,
                          return_value=(proposal, {})) as construct, \
             patch.object(solver, "analyze", return_value={"with_cross_core_delay": {"lower_bound_cycles": lower}}):
            out = solver.evaluate_candidates(SimpleNamespace(graph={}), cores, evaluate, Mock(return_value={}))
            if cores == 1:
                construct.assert_not_called()
        self.assertEqual(out[1], evaluate.call_count)
        return out

    def test_fresh_incumbent_counted_and_strict_M_acceptance(self):
        for m in (99, 100, 101):
            winner, calls, records, selection = self.execute({"makespan": m})
            self.assertEqual(winner[0], PROPOSAL if m < 100 else ANCHOR)
            self.assertEqual(calls, 3)
            self.assertEqual(selection["shared_pipeline_policy"]["evaluation_calls"], 3)
            self.assertEqual(records[-1]["makespan"], m)

    def test_duplicate_bound_and_guard_avoid_third_call(self):
        for kwargs in ({"proposal": ANCHOR}, {"lower": 100}, {"unsupported": True}, {"cores": 1}):
            winner, calls, _, _ = self.execute(RuntimeError("must not run"), **kwargs)
            self.assertEqual(winner[0], ANCHOR)
            self.assertEqual(calls, 2)

    def test_validation_rejection_keeps_incumbent_and_programming_bug_propagates(self):
        winner, calls, records, _ = self.execute(EvaluationValidationError("bad proposal"))
        self.assertEqual((winner[0], calls, records[-1]["status"]), (ANCHOR, 3, "rejected"))
        with self.assertRaisesRegex(RuntimeError, "unexpected"):
            self.execute(RuntimeError("unexpected"))

    def test_online_limit_stops_before_extra_evaluator_dispatch(self):
        def runaway(index, cores, evaluate, save):
            for _ in range(4):
                evaluate(ANCHOR)
            self.fail("fourth evaluator call must not dispatch")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "graph.json").write_text(json.dumps(graph()))
            argv = ["solver", str(root / "graph.json"), "--cores", "2", "-o",
                    str(root / "plan.json"), "--evidence", str(root / "evidence")]
            with patch("sys.argv", argv), \
                 patch("multicore_cut_evaluate_problem_3.evaluate_problem_3", return_value={}) as evaluate:
                with self.assertRaisesRegex(RuntimeError, "declared online E0"):
                    run_solver(policy=runaway, candidate_limit=3)
                self.assertEqual(evaluate.call_count, 3)
            ledger = json.loads((root / "evidence/evaluations.json").read_text())
            self.assertEqual(len(ledger), 3)

    def test_entrypoint_declares_three_call_budget(self):
        with patch.object(solver, "run_solver") as runner:
            solver.main()
        runner.assert_called_once_with(policy=solver.evaluate_candidates, candidate_limit=3)
