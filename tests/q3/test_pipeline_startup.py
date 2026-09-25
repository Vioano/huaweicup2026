"""Static Pareto DP checks; no official evaluator, Task or Step3 calls."""
from itertools import combinations, product
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from src.q3.construct import Index, ROOT, UnsupportedStructure, derive_multicore_plan
from src.q3 import pipeline_startup as solver


def brute(weights, reads, sizes, capacity, k, jobs, bandwidth):
    n = len(weights)
    choices = []
    for interior in combinations(range(1, n), k - 1):
        cuts = [0, *interior, n]
        computes = [sum(weights[left:right]) for left, right in zip(cuts, cuts[1:])]
        byte_counts = [sum(sizes[t] for t in set().union(*reads[left:right]))
                       for left, right in zip(cuts, cuts[1:])]
        if all(size <= capacity for size in byte_counts):
            objective = (sum(max(bandwidth * c, b) for c, b in zip(computes, byte_counts))
                         + bandwidth * (jobs - 1) * max(computes))
            choices.append((objective, cuts))
    return choices


class PipelineStartupTests(unittest.TestCase):
    def test_small_exhaustive_exact_objective_and_feasibility(self):
        sizes = {1: 2, 2: 3}
        for n in range(1, 5):
            for weights in product((1, 3), repeat=n):
                for pattern in product((set(), {1}, {2}, {1, 2}), repeat=n):
                    reads = [set(v) for v in pattern]
                    for k in range(1, n + 1):
                        capacity, jobs, bandwidth = 4, 3, 2
                        truth = brute(weights, reads, sizes, capacity, k, jobs, bandwidth)
                        if not truth:
                            with self.assertRaises(UnsupportedStructure):
                                solver.partition(weights, reads, sizes, capacity,
                                                 k, jobs, bandwidth)
                            continue
                        cuts, value, computes, bytes_by_stage, _ = solver.partition(
                            weights, reads, sizes, capacity, k, jobs, bandwidth)
                        self.assertEqual(value, min(v for v, _ in truth))
                        self.assertIn((value, cuts), truth)
                        self.assertTrue(all(b <= capacity for b in bytes_by_stage))
                        self.assertEqual(computes,
                                         [sum(weights[a:b]) for a, b in zip(cuts, cuts[1:])])

    def test_union_bytes_and_jobs_one_determinism(self):
        args = ([1, 1, 1], [{1}, {1}, {2}], {1: 6, 2: 5}, 6, 2, 2, 2)
        outcome = solver.partition(*args)
        self.assertEqual(outcome[0], [0, 2, 3])
        self.assertEqual(outcome[3], [6, 5])
        self.assertEqual(outcome, solver.partition(*args))
        # For jobs=1 and no bytes, all cuts have the same F. Pure (A,h)
        # dominance may choose [0,2,3], not globally lex-first [0,1,3].
        cuts, objective, _, _, _ = solver.partition(
            [1, 1, 3], [set(), set(), set()], {}, 1, 2, 1, 1)
        self.assertEqual(objective, 5)
        self.assertEqual(cuts, [0, 2, 3])

    def test_explicit_resource_guard(self):
        with patch.object(solver, "MAX_TRANSITIONS", 0):
            with self.assertRaisesRegex(UnsupportedStructure, "resource guard"):
                solver.partition([1], [set()], {}, 1, 1, 1, 1)

    def test_original_044_046_static_single_construction(self):
        for number in (44, 46):
            path = ROOT / f"data/raw/a/official/data/case_{number:03}.json"
            graph = json.loads(path.read_text())
            original_bytes = path.read_bytes()
            index = Index(graph)
            plan, meta = solver.construct(index, 5)
            self.assertEqual(path.read_bytes(), original_bytes)
            self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
            self.assertEqual(len(plan["core_schedules"]), 5)
            self.assertEqual(set(map(int, plan["node_to_subgraph"])), set(index.ops))
            self.assertEqual(len(set(s for word in plan["core_schedules"] for s in word)),
                             len(index.ops))
            self.assertTrue(all(b <= meta["shared_input_capacity_bytes"]
                                for b in meta["shared_input_bytes_by_stage"]))
            derive_multicore_plan(graph, plan)
            print(f"case_{number:03} " + json.dumps({k: meta[k] for k in (
                "cuts", "stage_compute_cycles", "shared_input_bytes_by_stage",
                "proxy_scaled_objective", "pareto_dp")}), flush=True)


if __name__ == "__main__":
    unittest.main()
