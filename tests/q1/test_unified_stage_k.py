"""Small injected controller checks; no real graph or evaluator invocation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_yuanzhifang_stage_k import unified as subject


def candidate(i):
    plan = {"node_to_subgraph": {str(i): 0}, "core_schedules": [[0]]}
    return dict(name=f"base-{i}", plan=plan, plan_sha256=str(i))


def base(n):
    return [candidate(i) for i in range(n)], dict(features={}, duplicates=[],
                                                    construction_failures=[])


class Controller(unittest.TestCase):
    def test_structural_route_is_core_exclusive(self):
        graph = {"ops": [{"id": "t", "op": "ADD", "pipe": "PIPE_V"}]}
        guarded = {"rounds": [{"tail": ["t"]} for _ in range(24)]}
        with patch("star_frontier.guarded_stages", return_value=(guarded, "strict")):
            self.assertEqual(subject._route(graph, 3)[0], "intact-pacing")
            self.assertEqual(subject._route(graph, 4)[0], "intact-pacing")
            self.assertEqual(subject._route(graph, 5)[0], "prefetch-frontier")
            self.assertIsNone(subject._route(graph, 1)[0])
        graph["ops"][0]["pipe"] = "PIPE_M"
        self.assertIsNone(subject._route(graph, 5)[0])

    def test_k1_preserves_base_and_zero_score(self):
        with patch.object(subject.captain, "generate_candidates", return_value=base(1)):
            plan, info = subject.solve({}, 1, score=lambda _: self.fail("scored k1"))
        self.assertEqual(plan, candidate(0)["plan"])
        self.assertEqual(info["online_score_attempts"], 0)
        self.assertEqual(info["stage_k_route"], "none")

    def test_h_j_mutually_exclusive_and_seven_cap(self):
        with patch.object(subject.captain, "generate_candidates", return_value=base(6)), \
             patch.object(subject, "_route", return_value=("prefetch-frontier", "strict")), \
             patch("prefetch_frontier.construct", return_value=(candidate(9)["plan"], {})):
            candidates, info = subject.generate_candidates({}, 5)
        self.assertEqual([c["name"] for c in candidates[:6]], [f"base-{i}" for i in range(6)])
        self.assertEqual(len(candidates), 7)
        self.assertEqual(candidates[-1]["name"], "prefetch-frontier")
        self.assertEqual(info["stage_k_route"], "prefetch-frontier")

    def test_duplicate_never_scores_twice(self):
        seen = []
        with patch.object(subject.captain, "generate_candidates", return_value=base(2)), \
             patch.object(subject, "_route", return_value=("intact-pacing", "strict")), \
             patch("intact_pacing.construct", return_value=(candidate(0)["plan"], {})):
            _, info = subject.solve({}, 3, score=lambda p: seen.append(p) or
                dict(status="ok", makespan=100, data_movement_bytes={"scheduled_copy_bytes": 0}))
        self.assertEqual(len(seen), 2)
        self.assertEqual(len(info["duplicates"]), 1)
        self.assertEqual(info["base_candidate_count"], 2)

    def test_extra_score_failure_retains_scored_base_winner(self):
        calls = []
        def score(plan):
            calls.append(plan)
            if len(calls) == 3:
                raise RuntimeError("injected evaluator failure")
            return dict(status="ok", makespan=100 - len(calls),
                        data_movement_bytes={"scheduled_copy_bytes": 0})
        with patch.object(subject.captain, "generate_candidates", return_value=base(2)), \
             patch.object(subject, "_route", return_value=("prefetch-frontier", "strict")), \
             patch("prefetch_frontier.construct", return_value=(candidate(9)["plan"], {})):
            selected, info = subject.solve({}, 5, score=score)
        self.assertEqual(selected, candidate(1)["plan"])
        self.assertEqual(info["stop_reason"], "first-score-failure")
        self.assertEqual(info["online_score_attempts"], 3)
        self.assertEqual(info["e1_interface_attempts"], 0)  # injected, no worker

    def test_manifest_detects_identity_change(self):
        subject.verify_sources()
        altered = json.loads(subject.MANIFEST.read_text(encoding="utf-8"))
        altered["base_commit"] = "wrong"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sources.json"
            path.write_text(json.dumps(altered), encoding="utf-8")
            with patch.object(subject, "MANIFEST", path):
                with self.assertRaisesRegex(RuntimeError, "source identity"):
                    subject.verify_sources()
            altered["base_commit"] = subject.BASE_COMMIT
            altered["files_sha256"]["src/q1/unified.py"] = "0" * 64
            path.write_text(json.dumps(altered), encoding="utf-8")
            with patch.object(subject, "MANIFEST", path):
                with self.assertRaisesRegex(RuntimeError, "source hash mismatch"):
                    subject.verify_sources()


if __name__ == "__main__":
    unittest.main()
