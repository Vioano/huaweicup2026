"""Controller-only tests; all solver, child, validator and scorer calls are fakes."""
import hashlib
import subprocess
import unittest
from unittest.mock import patch

from src.q1 import response_refine as target


BASE = {"node_to_subgraph": {"1": 0}, "core_schedules": [[0], []]}
OTHER = {"node_to_subgraph": {"1": 1}, "core_schedules": [[], [1]]}


def diagnostics(plan=BASE, selected="capacity-return", status="ok"):
    digest = hashlib.sha256(target.unified.plan_bytes(plan)).hexdigest()
    return {"selected": selected, "actual_e1_calls": 2, "online_score_attempts": 2,
            "online_scores": [{"name": "capacity-return", "plan_sha256": digest,
                               "status": status, "makespan": 100,
                               "data_movement_bytes": {"scheduled_copy_bytes": 1000}}]}


def baseline(info):
    return lambda graph, cores, emit=None: (BASE, info)


def ok_validator(graph, plan):
    assert set(plan) == {"node_to_subgraph", "core_schedules"}


class ResponseControllerTests(unittest.TestCase):
    def test_refiner_command_and_diagnostics_are_explicit(self):
        fixed = target.child_command("fixed", "in.json", 5, "plan.json", "diag.json")
        variable = target.child_command("variable", "in.json", 5, "plan.json", "diag.json")
        self.assertTrue(fixed[2].endswith("/packet_dp.py"))
        self.assertEqual(fixed[-4:], ["--profile-cache", "ordered-graph",
                                      "--state-mode", "auto"])
        self.assertTrue(variable[2].endswith("/variable_packet.py"))
        self.assertNotIn("--profile-cache", variable)
        self.assertNotIn("--state-mode", variable)
        with self.assertRaises(ValueError):
            target.child_command("unknown", "in.json", 5, "plan.json", "diag.json")
        plan, out = target.solve({}, 2, baseline_solve=baseline(diagnostics()),
                                 constructor=lambda *_: (OTHER, {}),
                                 scorer=lambda *_: {"status": "ok", "worker_pid": 7,
                                                    "makespan": 99,
                                                    "data_movement_bytes": {"scheduled_copy_bytes": 999}},
                                 validator=ok_validator, refiner="variable")
        self.assertEqual(plan, OTHER)
        self.assertEqual(out["selected"], "variable-packet-refinement")
        self.assertEqual(out["variant"], target.VARIANTS["variable"])
        self.assertEqual(out["refinement"]["refiner"], "variable")
        self.assertEqual(out["refinement"]["construction_parameters"],
                         target.VARIABLE_COMPILE_BUDGETS)
        self.assertEqual(out["refinement"]["score_attempts"], 1)

    def test_child_timeout_reaps_direct_process_without_new_session(self):
        class FakeChild:
            def __init__(self):
                self.kills = 0
                self.waits = []
            def wait(self, timeout):
                self.waits.append(timeout)
                if self.kills == 0:
                    raise subprocess.TimeoutExpired("fake packet DP", timeout)
                return -9
            def poll(self):
                return None if self.kills == 0 else -9
            def kill(self):
                self.kills += 1
        child = FakeChild()
        with patch.object(target.subprocess, "Popen", return_value=child) as popen:
            with self.assertRaises(TimeoutError):
                target.packet_child({}, 2)
        self.assertNotIn("start_new_session", popen.call_args.kwargs)
        self.assertEqual(child.waits, [120, 10])
        self.assertEqual(child.kills, 1)

    def test_guard_skips_every_unscored_or_other_winner(self):
        for info in (diagnostics(selected="bounded"), diagnostics(status="error"),
                     {**diagnostics(), "online_scores": []}):
            def forbidden(*args, **kwargs):
                self.fail("guard must prevent expensive calls")
            plan, out = target.solve({}, 2, baseline_solve=baseline(info),
                                     constructor=forbidden, scorer=forbidden,
                                     validator=forbidden)
            self.assertEqual(plan, BASE)
            self.assertEqual(out["refinement"]["child_attempts"], 0)
            self.assertEqual(out["refinement"]["score_attempts"], 0)
            self.assertEqual(out["baseline"]["actual_e1_calls"], 2)

    def test_child_or_score_failure_retains_baseline(self):
        def failed_child(graph, cores):
            raise TimeoutError("synthetic timeout")
        plan, out = target.solve({}, 2, baseline_solve=baseline(diagnostics()),
                                 constructor=failed_child, scorer=lambda *_: self.fail("scored"),
                                 validator=ok_validator)
        self.assertEqual(plan, BASE)
        self.assertEqual(out["refinement"]["score_attempts"], 0)
        self.assertEqual(out["refinement"]["child_attempts"], 1)
        plan, out = target.solve({}, 2, baseline_solve=baseline(diagnostics()),
                                 constructor=lambda *_: (OTHER, {}),
                                 scorer=lambda *_: {"status": "error", "worker_pid": 42},
                                 validator=ok_validator)
        self.assertEqual(plan, BASE)
        self.assertEqual(out["refinement"]["score_attempts"], 1)
        self.assertEqual(out["refinement"]["actual_e1_calls"], 1)

    def test_identical_bytes_skip_score(self):
        plan, out = target.solve({}, 2, baseline_solve=baseline(diagnostics()),
                                 constructor=lambda *_: (BASE, {}),
                                 scorer=lambda *_: self.fail("identical plan scored"),
                                 validator=ok_validator)
        self.assertEqual(plan, BASE)
        self.assertEqual(out["refinement"]["stop_reason"], "byte-identical-plan")
        self.assertEqual(out["refinement"]["score_attempts"], 0)

    def test_score_exception_keeps_baseline_and_unknown_call_count(self):
        def interrupted_score(graph, plan):
            raise RuntimeError("synthetic failure after possible dispatch")
        plan, out = target.solve({}, 2, baseline_solve=baseline(diagnostics()),
                                 constructor=lambda *_: (OTHER, {}),
                                 scorer=interrupted_score, validator=ok_validator)
        self.assertEqual(plan, BASE)
        self.assertEqual(out["selected"], "capacity-return")
        self.assertEqual(out["refinement"]["score_attempts"], 1)
        self.assertIsNone(out["refinement"]["actual_e1_calls"])
        self.assertEqual(out["refinement"]["actual_e1_calls_range"], [0, 1])
        self.assertEqual(out["refinement"]["stop_reason"], "refinement-score-failed")

    def test_only_strict_lexicographic_improvement_promotes(self):
        for score, promoted in (({"makespan": 100, "data_movement_bytes":
                                  {"scheduled_copy_bytes": 999}}, True),
                                ({"makespan": 100, "data_movement_bytes":
                                  {"scheduled_copy_bytes": 1000}}, False),
                                ({"makespan": 101, "data_movement_bytes":
                                  {"scheduled_copy_bytes": 0}}, False)):
            calls = []
            def scorer(graph, plan):
                calls.append(plan)
                return {"status": "ok", "worker_pid": 7, **score}
            plan, out = target.solve({}, 2, baseline_solve=baseline(diagnostics()),
                                     constructor=lambda *_: (OTHER, {}), scorer=scorer,
                                     validator=ok_validator)
            self.assertEqual(plan, OTHER if promoted else BASE)
            self.assertEqual(out["selected"] == "packet-dp-refinement", promoted)
            self.assertEqual(out["refinement"]["score_attempts"], 1)
            self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
