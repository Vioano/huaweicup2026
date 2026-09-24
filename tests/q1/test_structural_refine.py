"""Injected controller checks: no real graph construction or E1 calls."""
import unittest

from src.q1 import structural_refine as target

BASE = {"node_to_subgraph": {1: 0}, "core_schedules": [[0], []]}
A = {"node_to_subgraph": {1: 1}, "core_schedules": [[], [1]]}
B = {"node_to_subgraph": {1: 2}, "core_schedules": [[2], []]}


def score(m, pid=7, status="ok"):
    return {"status": status, "worker_pid": pid, "makespan": m,
            "data_movement_bytes": {"scheduled_copy_bytes": 100}}


def parent(plan=BASE, selected="capacity-return", matching=True):
    record = {"name": selected, "plan_sha256": target._digest(plan) if matching else "bad",
              **score(100)}
    return plan, {"selected": selected,
                  "baseline": {"actual_e1_calls": 2, "diagnostics": {"online_scores": [record]}},
                  "refinement": {"actual_e1_calls": 0}}


def run_case(parent_result=None, candidates=(A, B), scores=(score(90), score(80))):
    calls = []
    choices = iter(candidates)
    scored = iter(scores)

    def scorer(g, p):
        calls.append(p)
        value = next(scored)
        if isinstance(value, Exception):
            raise value
        return value

    plan, info = target.solve({}, 2, parent_solve=lambda *_: parent_result or parent(),
                              recognizer=lambda _: None,
                              constructor=lambda *_: (next(choices), {}),
                              validator=lambda *_: None, scorer=scorer)
    return plan, info, calls


class StructuralRefineTests(unittest.TestCase):
    def test_unexpected_guard_error_keeps_parent_without_candidates(self):
        def failed_guard(_):
            raise RuntimeError("synthetic recognizer failure")

        def forbidden(*_):
            self.fail("guard failure must prevent construction and scoring")

        p, d = target.solve({}, 2, parent_solve=lambda *_: parent(),
                            recognizer=failed_guard, constructor=forbidden,
                            validator=forbidden, scorer=forbidden)
        self.assertEqual(p, BASE)
        self.assertEqual(d["stop_reason"], "guard-failed")
        self.assertEqual(d["guard_error_type"], "RuntimeError")
        self.assertEqual(d["extra"], [])
        self.assertEqual(d["extra_score_attempts"], 0)

    def test_retains_parent_without_matching_score(self):
        p, d, calls = run_case(parent_result=parent(matching=False))
        self.assertEqual(p, BASE)
        self.assertEqual(calls, [])
        self.assertEqual(d["stop_reason"], "no-matching-parent-score")

    def test_strict_improvement_and_total_calls(self):
        p, d, calls = run_case()
        self.assertEqual(p, B)
        self.assertEqual(len(calls), 2)
        self.assertEqual(d["actual_e1_calls_total"], 4)

    def test_no_strict_improvement(self):
        p, d, _ = run_case(scores=(score(100), score(101)))
        self.assertEqual(p, BASE)
        self.assertEqual(d["selected"], "capacity-return")

    def test_failure_retains_last_verified_winner(self):
        p, d, calls = run_case(scores=(score(90), RuntimeError("after dispatch")))
        self.assertEqual(p, A)
        self.assertEqual(len(calls), 2)
        self.assertIsNone(d["actual_e1_calls_total"])
        self.assertEqual(d["stop_reason"], "score-failed")

    def test_duplicate_skips_score(self):
        p, d, calls = run_case(candidates=(BASE, A), scores=(score(90),))
        self.assertEqual(p, A)
        self.assertEqual(len(calls), 1)
        self.assertEqual(d["extra"][0]["status"], "duplicate-plan")

    def test_variable_parent_uses_refinement_score_and_hash(self):
        p, info = parent()
        info["selected"] = "variable-packet-refinement"
        info["refinement"] = {"actual_e1_calls": 1,
                              "candidate_plan_sha256": target._digest(p), "score": score(95)}
        result, d, _ = run_case(parent_result=(p, info), scores=(score(96), score(94)))
        self.assertEqual(result, B)
        self.assertEqual(d["parent_score_source"], "variable-refinement-score")
        self.assertEqual(d["actual_e1_calls_total"], 5)


if __name__ == "__main__":
    unittest.main()
