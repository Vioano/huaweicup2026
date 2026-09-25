"""Pure frozen-timeout record checks; no solver or evaluator."""
import json
import unittest
from pathlib import Path

from src.review import p1_colab_timeout_export as x


class TimeoutExportTests(unittest.TestCase):
    def test_timeout_is_not_a_success_score(self):
        public = x.PUBLIC
        run = json.loads((public / "failures/014/k4/run.json").read_text())
        template = json.loads(next(public.glob("board-feed-*.json")).read_text())["records"][0]
        record = x.build_record(template, run, {"path": "results/plan", "sha256": "a" * 64},
                                {"path": "results/run", "sha256": "b" * 64})
        self.assertEqual(record["status"], "timeout")
        self.assertIsNone(record["metrics"]["makespan_cycles"])
        self.assertNotIn("result", record["artifacts"])
        self.assertEqual(record["provenance"]["measurement"]["calls"],
                         {"solver": 1, "E1": 3, "E0": 1, "E2": 0})
        self.assertEqual(record["provenance"]["measurement"]["failure"]["elapsed_seconds"], 900.065508997)


if __name__ == "__main__": unittest.main()
