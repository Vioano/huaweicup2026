"""Tiny private-chain construction checks; no evaluator or Task compiler."""
import unittest

from src.review.p1_resource_cut_candidate import construct


def chains(count, cycles=(10, 20, 10), size=16):
    graph = {"ops": [], "tensors": [], "edges": []}
    for i in range(count):
        ops = [i * 3 + j for j in range(3)]
        tids = [1000 + i * 4 + j for j in range(4)]
        graph["ops"].extend({"id": u, "op": "COMPUTE", "pipe": pipe, "cycles": work}
                            for u, pipe, work in zip(ops, ("PIPE_M", "PIPE_V", "PIPE_M"), cycles))
        graph["tensors"].extend({"id": t, "size": size, "pos": "UB"} for t in tids)
        for j, u in enumerate(ops):
            graph["edges"].extend(({"source": tids[j], "target": u},
                                   {"source": u, "target": tids[j + 1]}))
    return graph


class ResourceCutTests(unittest.TestCase):
    def check_plan(self, graph, plan):
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        self.assertEqual(set(map(int, plan["node_to_subgraph"])),
                         {op["id"] for op in graph["ops"]})

    def test_cut_and_uncut_graphs(self):
        for cycles, size, bandwidth, expect_cut in (
                ((10, 20, 10), 16, 60, True),
                ((1, 1, 1), 100, 1, False)):
            graph = chains(4, cycles, size)
            plan, info = construct(graph, 2, bandwidth)
            self.check_plan(graph, plan)
            self.assertTrue(all(0 <= x <= n for x, n in zip(
                info["cut_counts"], info["per_core_chain_counts"])))
            self.assertEqual(any(info["cut_counts"]), expect_cut)

    def test_empty_cores_have_no_task(self):
        graph = chains(2)
        plan, info = construct(graph, 5, 60)
        self.check_plan(graph, plan)
        self.assertEqual(len(plan["core_schedules"]), 5)
        self.assertEqual(sum(not line for line in plan["core_schedules"]), 3)
        self.assertEqual(info["calls"]["E0"], 0)


if __name__ == "__main__":
    unittest.main()
