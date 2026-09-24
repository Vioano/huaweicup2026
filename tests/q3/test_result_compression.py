"""CLI evidence compression checks with a fake E0; no official evaluations."""
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.q3 import safe_solve
from tests.q3.test_shared_pipeline import graph


class ResultCompressionTests(unittest.TestCase):
    def run_case(self, selected):
        first = {"node_to_subgraph": {"1": 0}, "core_schedules": [[0]]}
        second = {"node_to_subgraph": {"1": 1}, "core_schedules": [[], [1]]}
        results = [
            {"makespan": 10, "data_movement_bytes": 1, "cache_stats": {"hits": 1}},
            {"makespan": 20, "data_movement_bytes": 2, "cache_stats": {"hits": 2}},
        ]

        def policy(index, cores, evaluate, save):
            for name, plan in (("first", first), ("second", second)):
                save(name, plan, evaluate(plan))
            if selected == "mutated":
                results[0]["cache_stats"]["hits"] = 99
            choice = 1 if selected == "nonminimum" else 0
            return ((first, second)[choice], results[choice], "test"), 2, [], {}

        real_compress = gzip.compress
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "graph.json"
            source.write_text(json.dumps(graph()))
            argv = ["safe_solve", str(source), "--cores", "2", "-o",
                    str(root / "plan.json"), "--evidence", str(root / "evidence")]
            with patch("sys.argv", argv), \
                 patch("multicore_cut_evaluate_problem_3.evaluate_problem_3", side_effect=results) as fake_e0, \
                 patch.object(safe_solve.gzip, "compress", wraps=real_compress) as compress:
                safe_solve.main(policy=policy)
            evidence = root / "evidence"
            full = (evidence / "result.json.gz").read_bytes()
            expected = real_compress(safe_solve.encoded(results[1 if selected == "nonminimum" else 0]), mtime=0)
            self.assertEqual(full, expected)
            self.assertEqual(gzip.decompress(full), safe_solve.encoded(results[1 if selected == "nonminimum" else 0]))
            receipt = json.loads((evidence / "receipt.json").read_bytes())
            self.assertEqual(receipt["result_sha256"], hashlib.sha256(full).hexdigest())
            self.assertEqual(fake_e0.call_count, 2)
            self.assertEqual(receipt["candidate_limit"], 2)
            self.assertEqual(compress.call_count, 2 if selected == "minimum" else 3)
            if selected == "minimum":
                self.assertEqual(full, (evidence / "first/result.json.gz").read_bytes())
            else:
                self.assertNotEqual(full, (evidence / "first/result.json.gz").read_bytes())

    def test_minimum_reuses_exact_gzip_bytes(self):
        self.run_case("minimum")

    def test_mutated_result_falls_back_to_compress(self):
        self.run_case("mutated")

    def test_nonminimum_choice_falls_back_to_compress(self):
        self.run_case("nonminimum")


if __name__ == "__main__":
    unittest.main()
