"""Structural routing and saved records with injected scores; zero official E0."""
from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from src.q3 import adaptive_solve as adaptive
from src.q3.construct import Index, UnsupportedStructure
from src.q3.guarded_solve import evaluate_candidates as guarded
from src.q3.stage_fork_join import construct as stage_construct
from tests.q3.test_reduction_tree import graph as reduction_graph
from tests.q3.test_stage_fork_join import stage_graph
from evaluation_validation import EvaluationValidationError


class AdaptiveTests(unittest.TestCase):
    def test_stage_routes_and_saves_one_candidate(self):
        # Equal lane chains make lane count proportional to compute load. Two
        # heavy cores rotate; one, three or four heavy cores stay fixed.
        for lanes, cores, policy in ((8, 1, "fixed"), (8, 2, "rotate_heavy"),
                                     (8, 3, "rotate_heavy"), (8, 4, "fixed"),
                                     (8, 5, "fixed"), (2, 5, "rotate_heavy")):
            with self.subTest(lanes=lanes, cores=cores):
                graph, _ = stage_graph(lanes=lanes, stages=3)
                original = deepcopy(graph)
                index = Index(graph)
                expected, _ = stage_construct(index, cores, collector_policy=policy)
                result = {"makespan": 12.5, "full_result_field": {"untouched": True}}
                refs = {"plan": {"path": "seed-plan.json", "sha256": "plan-digest"},
                        "result": {"path": "seed-result.json.gz", "sha256": "result-digest"}}
                evaluate = Mock(return_value=result)
                save = Mock(return_value=refs)
                with patch.object(adaptive, "stage_construct", wraps=stage_construct) as construct, \
                     patch.object(adaptive, "guarded_candidates") as fallback:
                    winner, calls, records, selection = adaptive.evaluate_candidates(index, cores, evaluate, save)
                construct.assert_called_once_with(index, cores, collector_policy=policy)
                fallback.assert_not_called()
                evaluate.assert_called_once_with(expected)
                save.assert_called_once_with("seed", expected, result)
                self.assertIs(winner[1], result)
                self.assertEqual(winner[0], expected)
                self.assertEqual(calls, 1)
                self.assertEqual(len(records), 1)
                record = records[0]
                self.assertEqual((record["name"], record["status"], record["makespan"]), ("seed", "ok", 12.5))
                self.assertIs(record["artifacts"], refs)
                meta = record["metadata"]
                self.assertEqual(meta["collector_policy"], policy)
                self.assertEqual(meta["route"], "stage")
                self.assertEqual(meta["official_e0_calls"], 0)  # Static constructor scope.
                self.assertEqual(meta["router"]["evaluation_calls"], 1)
                self.assertEqual(meta["router"]["stage_construct_attempts"], 1)
                self.assertEqual(meta["router"]["stage_candidate_plans"], 1)
                self.assertEqual(meta["router"]["route_e0_limit"], 1)
                self.assertEqual(selection["router"], meta["router"])
                if policy == "rotate_heavy":
                    self.assertEqual(len(meta["collector_cycle"]), 2)
                else:
                    self.assertEqual(meta["collector_cycle"], [meta["collector_core"]])
                self.assertEqual(graph, original)

    def run_guarded_comparison(self, policy, graph, scores, lower=None):
        values = iter(scores)
        evaluated, saved = [], []

        def evaluate(plan):
            evaluated.append(deepcopy(plan))
            value = next(values)
            if isinstance(value, Exception):
                raise value
            return {"makespan": value}

        def save(name, plan, result):
            saved.append((name, deepcopy(plan), deepcopy(result)))
            return {"path": name}

        if lower is None:
            output = policy(Index(graph), 4, evaluate, save)
        else:
            bound = {"with_cross_core_delay": {"lower_bound_cycles": lower}}
            with patch("src.q3.guarded_solve.analyze", return_value=bound), \
                 patch("src.q3.guarded_solve.release", return_value=(
                     {"candidate": 1}, {"strategy": "release_place_forest"})):
                output = policy(Index(graph), 2, evaluate, save)
        return output, evaluated, saved

    def assert_same_guarded_policy(self, graph, scores, lower=None):
        direct, direct_evaluated, direct_saved = self.run_guarded_comparison(guarded, graph, scores, lower)
        with patch.object(adaptive, "guarded_candidates", wraps=guarded) as fallback:
            routed, evaluated, saved = self.run_guarded_comparison(adaptive.evaluate_candidates, graph, scores, lower)
        fallback.assert_called_once()
        self.assertEqual(routed[:3], direct[:3])
        self.assertEqual(evaluated, direct_evaluated)
        self.assertEqual(saved, direct_saved)
        self.assertEqual({k: v for k, v in routed[3].items() if k != "router"}, direct[3])
        route = routed[3]["router"]
        self.assertEqual(route["route"], "guarded")
        self.assertEqual(route["evaluation_calls"], len(evaluated))
        self.assertEqual(route["guarded_policy_invocations"], 1)
        self.assertEqual(route["stage_candidate_plans"], 0)
        self.assertLessEqual(len(evaluated), 2)
        return routed

    def test_nonstage_tree_preserves_guarded_choices_and_call_budget(self):
        for scores, lower in (([100, 90], 80), ([100, 100], 80),
                              ([100, 130], 80), ([100], 100),
                              ([100, EvaluationValidationError("capacity")], 80)):
            with self.subTest(scores=scores, lower=lower):
                self.assert_same_guarded_policy(reduction_graph(), scores, lower)

    def test_nonstage_forest_preserves_existing_overlap_policy(self):
        graph = {"ops": [], "tensors": [], "edges": []}
        for j in range(20):
            graph["ops"].extend({"id": 3*j+u, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": 1}
                                for u in range(3))
            graph["edges"].extend({"source": 3*j+u, "target": 3*j+2} for u in (0, 1))
        output = self.assert_same_guarded_policy(graph, [100])
        self.assertEqual(output[1], 1)
        self.assertEqual(output[2][-1]["status"], "unsupported")
        self.assertIn("uncut", output[2][-1]["reason"])

    def test_strict_tensor_guard_rejection_routes_to_guarded(self):
        graph, layout = stage_graph()
        graph["edges"].append({"source": layout["immutable"][1],
                               "target": layout["stages"][0]["chains"][0][-1]})
        index = Index(graph)
        sentinel = (({"fallback": 1}, {"makespan": 7}, "fallback"), 1, [], {"rule": "sentinel"})
        evaluate, save = Mock(), Mock()
        with patch.object(adaptive, "guarded_candidates", return_value=sentinel) as fallback:
            out = adaptive.evaluate_candidates(index, 2, evaluate, save)
        fallback.assert_called_once_with(index, 2, evaluate, save)
        self.assertEqual(out[:3], sentinel[:3])
        self.assertIn("lane-internal tensor input", out[3]["router"]["stage_guard_reason"])
        evaluate.assert_not_called()
        save.assert_not_called()

    def test_constructor_defects_do_not_silently_fallback(self):
        index = Index(stage_graph()[0])
        for failure in (RuntimeError("bug"), AssertionError("invariant"), ValueError("bad option")):
            with self.subTest(failure=type(failure).__name__):
                evaluate, save = Mock(), Mock()
                with patch.object(adaptive, "stage_construct", side_effect=failure), \
                     patch.object(adaptive, "guarded_candidates") as fallback:
                    with self.assertRaises(type(failure)):
                        adaptive.evaluate_candidates(index, 2, evaluate, save)
                fallback.assert_not_called()
                evaluate.assert_not_called()
                save.assert_not_called()

    def test_evaluation_failures_do_not_trigger_fallback_or_save(self):
        index = Index(stage_graph()[0])
        for failure in (EvaluationValidationError("capacity"), UnsupportedStructure("from evaluator"),
                        RuntimeError("runtime")):
            with self.subTest(failure=type(failure).__name__):
                evaluate, save = Mock(side_effect=failure), Mock()
                with patch.object(adaptive, "guarded_candidates") as fallback:
                    with self.assertRaises(type(failure)):
                        adaptive.evaluate_candidates(index, 2, evaluate, save)
                evaluate.assert_called_once()
                save.assert_not_called()
                fallback.assert_not_called()

    def test_save_failure_is_not_silently_fallback(self):
        evaluate = Mock(return_value={"makespan": 1})
        save = Mock(side_effect=OSError("disk"))
        with patch.object(adaptive, "guarded_candidates") as fallback:
            with self.assertRaises(OSError):
                adaptive.evaluate_candidates(Index(stage_graph()[0]), 2, evaluate, save)
        evaluate.assert_called_once()
        save.assert_called_once()
        fallback.assert_not_called()

    def test_fallback_exception_propagates(self):
        with patch.object(adaptive, "guarded_candidates", side_effect=RuntimeError("guarded bug")):
            with self.assertRaisesRegex(RuntimeError, "guarded bug"):
                adaptive.evaluate_candidates(Index(reduction_graph()), 2, Mock(), Mock())

    def test_main_injects_router_into_shared_cli(self):
        with patch.object(adaptive, "run_solver", return_value=17) as run:
            self.assertEqual(adaptive.main(), 17)
        run.assert_called_once_with(policy=adaptive.evaluate_candidates)

    def test_invalid_core_count_is_not_a_structure_fallback(self):
        index = Index(stage_graph()[0])
        for cores in (0, -1, True, 1.5):
            with self.subTest(cores=cores), \
                 patch.object(adaptive, "stage_construct") as construct, \
                 patch.object(adaptive, "guarded_candidates") as fallback:
                with self.assertRaises(ValueError):
                    adaptive.evaluate_candidates(index, cores, Mock(), Mock())
                construct.assert_not_called()
                fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
