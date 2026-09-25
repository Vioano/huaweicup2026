"""Static construction checks; no solver, Task, Step2/3, or E0 calls."""
import copy
from itertools import combinations
import json
from pathlib import Path
import unittest

from src.q3.construct import Index, ROOT, UnsupportedStructure, derive_multicore_plan

from src.q3 import shared_pipeline_capacity as prototype


def synthetic(jobs=3, cycles=(2, 3, 4), reads=((1001,), (1001,), (1002,))):
    graph = {"ops": [], "tensors": [
        {"id": 1001, "pos": "L1", "size": 6},
        {"id": 1002, "pos": "L1", "size": 5}], "edges": []}
    for j in range(jobs):
        ids = [10 * j + p for p in range(len(cycles))]
        for p, u in enumerate(ids):
            graph["ops"].append({"id": u, "op": "RELU", "pipe": "PIPE_V",
                                 "cycles": cycles[p]})
            graph["edges"].extend({"source": t, "target": u} for t in reads[p])
        graph["edges"].extend({"source": u, "target": v}
                              for u, v in zip(ids, ids[1:]))
    return graph


class CapacityPipelineTests(unittest.TestCase):
    def test_partition_against_exhaustive_feasible_partitions(self):
        weights = [2, 3, 4, 5, 1]
        reads = [{1}, {1, 2}, {2}, {3}, {1, 3}]
        sizes = {1: 3, 2: 4, 3: 5}
        for capacity in range(3, 13):
            for stages in range(1, 6):
                feasible = []
                for inside in combinations(range(1, len(weights)), stages - 1):
                    cuts = [0, *inside, len(weights)]
                    by_segment = [sum(sizes[t] for t in set().union(*reads[a:b]))
                                  for a, b in zip(cuts, cuts[1:])]
                    if all(size <= capacity for size in by_segment):
                        feasible.append((max(sum(weights[a:b])
                                             for a, b in zip(cuts, cuts[1:])), cuts))
                if not feasible:
                    with self.assertRaises(UnsupportedStructure):
                        prototype.partition(weights, reads, sizes, capacity, stages)
                else:
                    cuts, cost, actual_bytes = prototype.partition(
                        weights, reads, sizes, capacity, stages)
                    self.assertEqual(cost, min(v for v, _ in feasible))
                    self.assertIn(cuts, [c for v, c in feasible if v == cost])
                    self.assertEqual(actual_bytes,
                                     [sum(sizes[t] for t in set().union(*reads[a:b]))
                                      for a, b in zip(cuts, cuts[1:])])

    def test_repeated_tensor_counted_once_and_impossible(self):
        cuts, _, bytes_by_stage = prototype.partition(
            [2, 3, 4], [{1}, {1}, {2}], {1: 6, 2: 5}, 6, 2)
        self.assertEqual(cuts, [0, 2, 3])
        self.assertEqual(bytes_by_stage, [6, 5])
        with self.assertRaises(UnsupportedStructure):
            prototype.partition([1, 1], [{1}, {2}], {1: 7, 2: 1}, 6, 2)

    def test_constructor_synthetic_plan_and_guard(self):
        graph = synthetic()
        before = copy.deepcopy(graph)
        index = Index(graph)
        plan, meta = prototype.construct(index, 2)
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        self.assertEqual(meta["shared_input_bytes_by_stage"], [6, 5])
        self.assertEqual(graph, before)
        self.assertEqual(len(plan["core_schedules"]), 2)
        self.assertEqual(set(map(int, plan["node_to_subgraph"])), set(index.ops))
        derive_multicore_plan(graph, plan)
        with self.assertRaises(UnsupportedStructure):
            prototype.construct(Index(synthetic(jobs=1)), 2)
        bad = synthetic()
        bad["tensors"][0]["pos"] = "UB"
        with self.assertRaises(UnsupportedStructure):
            prototype.construct(Index(bad), 2)

    def test_original_cases_044_046_five_cores(self):
        for number in (44, 46):
            path = ROOT / f"data/raw/a/official/data/case_{number:03}.json"
            graph = json.loads(path.read_text())
            before = copy.deepcopy(graph)
            index = Index(graph)
            plan, meta = prototype.construct(index, 5)
            self.assertEqual(graph, before)
            self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
            self.assertEqual(len(plan["core_schedules"]), 5)
            self.assertEqual(len(set(s for word in plan["core_schedules"] for s in word)),
                             len(index.ops))
            self.assertEqual(set(map(int, plan["node_to_subgraph"])), set(index.ops))
            self.assertTrue(all(x <= meta["shared_input_capacity_bytes"]
                                for x in meta["shared_input_bytes_by_stage"]))
            derive_multicore_plan(graph, plan)
            print(f"case_{number:03} " + json.dumps({k: meta[k] for k in (
                "cuts", "stage_compute_cycles", "shared_input_bytes_by_stage")}),
                flush=True)


if __name__ == "__main__":
    unittest.main()
