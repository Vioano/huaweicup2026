"""Small controller checks; no real graph, Task compile or evaluator call."""
import hashlib
import unittest
from unittest.mock import patch

from src.q1_yuanzhifang import unified


def candidate(name, value):
    plan = {"node_to_subgraph": {"n": value}, "core_schedules": [[value]]}
    return {"name": name, "plan": plan,
            "plan_sha256": hashlib.sha256(unified.captain.plan_bytes(plan)).hexdigest()}


def base(count):
    return [candidate(f"base-{i}", i) for i in range(count)], {
        "features": {}, "duplicates": [], "construction_failures": [],
        "generation_seconds": 0.0}


class UnifiedControllerTest(unittest.TestCase):
    def test_h_guard_adds_only_fifth_and_retains_four_base_candidates(self):
        with patch.object(unified.captain, "generate_candidates", return_value=base(4)), \
             patch("src.q1_yuanzhifang.star_frontier.guarded_stages", return_value=({"rounds": []}, "guard passed")), \
             patch("src.q1_yuanzhifang.prefetch_frontier.construct", return_value=(candidate("h", 9)["plan"], {})), \
             patch("src.q1_yuanzhifang.capacity_return.construct") as capacity:
            found, info = unified.generate_candidates({}, 5)
        self.assertEqual([item["name"] for item in found],
                         ["base-0", "base-1", "base-2", "base-3", "prefetch-frontier"])
        self.assertEqual(info["additional_route"], "prefetch-frontier")
        capacity.assert_not_called()

    def test_capacity_route_is_mutually_exclusive_and_duplicate_not_scored(self):
        with patch.object(unified.captain, "generate_candidates", return_value=base(2)), \
             patch("src.q1_yuanzhifang.star_frontier.guarded_stages", return_value=(None, "unsupported")), \
             patch("src.q1_yuanzhifang.capacity_return.construct", return_value=(candidate("duplicate", 0)["plan"], {})), \
             patch("src.q1_yuanzhifang.prefetch_frontier.construct") as prefetch:
            scores = []
            def score(plan):
                scores.append(plan)
                return {"status": "ok", "makespan": len(scores),
                        "data_movement_bytes": {"scheduled_copy_bytes": 0}}
            _, info = unified.solve({}, 5, score=score)
        self.assertEqual(len(scores), 2)
        self.assertEqual(len(info["duplicates"]), 1)
        self.assertEqual(info["additional_route"], "capacity-return")
        self.assertEqual(info["actual_e1_calls"], 0)
        prefetch.assert_not_called()

    def test_scoring_failure_keeps_checked_winner(self):
        with patch.object(unified.captain, "generate_candidates", return_value=base(2)), \
             patch("src.q1_yuanzhifang.capacity_return.construct", return_value=(candidate("new", 8)["plan"], {})):
            def score(plan):
                value = plan["node_to_subgraph"]["n"]
                if value == 0:
                    return {"status": "ok", "makespan": 10,
                            "data_movement_bytes": {"scheduled_copy_bytes": 0}}
                if value == 1:
                    return {"status": "ok", "makespan": 5,
                            "data_movement_bytes": {"scheduled_copy_bytes": 0}}
                raise RuntimeError("injected failure")
            selected, info = unified.solve({}, 2, score=score)
        self.assertEqual(selected, candidate("winner", 1)["plan"])
        self.assertEqual(info["stop_reason"], "first-score-failure")
        self.assertEqual(info["online_score_attempts"], 3)

    def test_one_core_has_no_extra_candidate_or_scoring(self):
        with patch.object(unified.captain, "generate_candidates", return_value=base(1)), \
             patch("src.q1_yuanzhifang.capacity_return.construct") as capacity:
            selected, info = unified.solve({}, 1, score=lambda _: self.fail("score called"))
        self.assertEqual(selected, candidate("base", 0)["plan"])
        self.assertEqual(info["online_score_attempts"], 0)
        capacity.assert_not_called()


if __name__ == "__main__":
    unittest.main()
