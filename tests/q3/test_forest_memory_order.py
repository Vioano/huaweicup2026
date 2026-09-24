"""Guarded reduction-forest memory ordering; no official evaluator calls."""
import unittest

from src.q3.construct import Index, UnsupportedStructure, derive_multicore_plan
from src.q3.forest_memory_order import construct


def _tree_graph():
    # Tree 1 has an ID-adversarial large branch (30) and small branch (20).
    # Tree 2 ensures the multi-tree guard is exercised.
    nodes = [20, 21, 22, 30, 31, 32, 40, 80, 81, 82]
    edges, tensors = [], []

    def result(source, target, size):
        tid = 1000 + len(tensors)
        tensors.append({"id": tid, "pos": "L1", "size": size})
        edges.extend([{"source": source, "target": tid},
                      {"source": tid, "target": target}])

    # Large branch: 31,32 -> 30 -> 40.
    result(31, 30, 70)
    result(32, 30, 70)
    result(30, 40, 10)
    # Small branch: 21,22 -> 20 -> 40.
    result(21, 20, 1)
    result(22, 20, 1)
    result(20, 40, 2)
    # Root external output is part of retained bytes.
    tensors.append({"id": 1099, "pos": "L1", "size": 5})
    edges.append({"source": 40, "target": 1099})
    # Separate joined reduction tree.
    result(80, 82, 3)
    result(81, 82, 4)
    tensors.append({"id": 1199, "pos": "DDR", "size": 6})
    edges.append({"source": 82, "target": 1199})
    # Official boundary copies: input COPY_IN is external to the frontier;
    # the tree root's output is allowed to leave through COPY_OUT.
    ops = [{"id": u, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": 1}
           for u in nodes]
    ops.extend([{"id": 0, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
                {"id": 99, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0}])
    tensors.extend([{"id": 1200, "pos": "DDR", "size": 16},
                    {"id": 1201, "pos": "L1", "size": 16},
                    {"id": 1202, "pos": "DDR", "size": 5}])
    edges.extend([{"source": 1200, "target": 0}, {"source": 0, "target": 1201},
                  {"source": 1201, "target": 31}, {"source": 1099, "target": 99},
                  {"source": 99, "target": 1202}])
    return {
        "ops": ops,
        "tensors": tensors,
        "edges": edges,
    }


class ForestMemoryOrderTests(unittest.TestCase):
    def test_boundary_copies_are_accepted(self):
        plan, _ = construct(Index(_tree_graph()), 2)
        self.assertEqual(len(plan["core_schedules"]), 2)

    def test_diamond_with_fanout_is_rejected(self):
        graph = _tree_graph()
        # 31 now feeds two consumers, breaking the tree recurrence.
        tid = 2000
        graph["tensors"].append({"id": tid, "pos": "L1", "size": 8})
        graph["edges"].extend([{"source": 31, "target": tid},
                               {"source": tid, "target": 20}])
        with self.assertRaises(UnsupportedStructure):
            construct(Index(graph), 2)

    def test_coverage_ownership_and_fixed_singleton_ids(self):
        index = Index(_tree_graph())
        plan, metadata = construct(index, 2)
        reverse = {sg: int(op) for op, sg in plan["node_to_subgraph"].items()}
        self.assertEqual(plan["node_to_subgraph"],
                         {str(u): i for i, u in enumerate(index.order)})
        self.assertEqual(sorted(reverse[sg] for seq in plan["core_schedules"] for sg in seq),
                         sorted(index.ops))
        expected = {}
        for core, component_ids in enumerate(index.assignment(2)):
            for cid in component_ids:
                for u in index.components[cid]:
                    expected[u] = core
        actual = {reverse[sg]: core for core, seq in enumerate(plan["core_schedules"])
                  for sg in seq}
        self.assertEqual(actual, expected)
        derive_multicore_plan(index.graph, plan)
        self.assertEqual(metadata["strategy"], "forest_memory_order")
        self.assertIn("not official memory/spill certificate", metadata["prediction_scope"])

    def test_peak_minus_retained_orders_large_subtree_first(self):
        index = Index(_tree_graph())
        _, metadata = construct(index, 2)
        tree = next(item for item in metadata["predicted_frontier"]
                    if item["root_op"] == 40)
        order = tree["dfs_postorder"]
        # Despite lower IDs, the small branch (20) follows the high-frontier
        # branch (30), whose peak-minus-retained score is larger.
        self.assertLess(order.index(30), order.index(20))
        self.assertEqual(tree["retained_root_output_bytes"], 5)
        self.assertGreaterEqual(tree["peak_frontier_bytes"], 150)


if __name__ == "__main__":
    unittest.main()
