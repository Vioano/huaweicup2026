"""Synthetic structural checks only; no official case or evaluator."""
import unittest

from src.q1.intact_frontier import construct, recognize, UnsupportedStructure
from stub_multicore_cut_and_schedule import derive_multicore_plan, _build_op_adjacency
from evaluation_validation import validate_task_order


def graph(widths, depths, shape="balanced"):
    g = {"ops": [], "tensors": [], "edges": []}
    nid, tid, previous = 0, 10000, None

    def op(kind="MUL"):
        nonlocal nid
        u = nid
        nid += 1
        g["ops"].append({"id": u, "op": kind, "pipe": "PIPE_V", "cycles": 3})
        return u

    def edge(a, b):
        nonlocal tid
        t = tid
        tid += 1
        g["tensors"].append({"id": t, "pos": "UB", "size": 8})
        g["edges"].extend([{"source": a, "target": t}, {"source": t, "target": b}])

    for width, depth in zip(widths, depths):
        leaves = []
        for _ in range(width):
            chain = [op() for _ in range(depth)]
            if previous is not None:
                edge(previous, chain[0])
            for a, b in zip(chain, chain[1:]):
                edge(a, b)
            leaves.append(chain[-1])
        if shape == "comb":
            while len(leaves) > 1:
                a, b = leaves[:2]
                parent = op("ADD")
                edge(a, parent)
                edge(b, parent)
                leaves = [parent] + leaves[2:]
        else:
            while len(leaves) > 1:
                nxt = []
                for i in range(0, len(leaves), 2):
                    if i + 1 == len(leaves):
                        nxt.append(leaves[i])
                    else:
                        parent = op("ADD")
                        edge(leaves[i], parent)
                        edge(leaves[i + 1], parent)
                        nxt.append(parent)
                leaves = nxt
        previous = leaves[0]
    return g


class IntactFrontierTests(unittest.TestCase):
    def test_construct_shapes(self):
        cases = [([8], [2], 4, "balanced"),
                 ([12, 12], [4, 4], 3, "comb"),
                 ([3], [1], 5, "balanced"),
                 ([2, 3], [1, 2], 5, "balanced")]
        for widths, depths, cores, shape in cases:
            g = graph(widths, depths, shape)
            for mode in ("paced", "root-heavy-fused"):
                with self.subTest(widths=widths, mode=mode):
                    plan, info = construct(g, cores, mode)
                    self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
                    self.assertEqual(len(plan["node_to_subgraph"]), len(g["ops"]))
                    self.assertEqual(info["rounds"], len(widths))
                    validate_task_order(derive_multicore_plan(g, plan))
                    pred, _ = _build_op_adjacency(g)
                    for task in info["tasks"]:
                        members = {u for u, tid in plan["node_to_subgraph"].items()
                                   if tid == task["id"]}
                        for u in task["fused_reductions"]:
                            self.assertEqual(len(pred[u]), 2)
                            self.assertTrue(pred[u] <= members)

    def test_single_core_fuses_entire_tail(self):
        # W<K in a later round forces root core to own all chains and reductions.
        g = graph([3, 2], [1, 1])
        _, info = construct(g, 5, "root-heavy-fused")
        last = [t for t in info["tasks"] if t["stage"] == 1]
        self.assertEqual(len(last), 1)
        self.assertEqual(len(last[0]["fused_reductions"]), 1)

    def test_cross_chain_edge_rejected(self):
        g = graph([3], [2])
        t = 99999
        g["tensors"].append({"id": t, "pos": "UB", "size": 8})
        g["edges"].extend([{"source": 0, "target": t}, {"source": t, "target": 2}])
        with self.assertRaises(UnsupportedStructure):
            recognize(g)

    def test_hidden_copy_path_rejected(self):
        g = graph([2], [1])
        g["ops"].append({"id": 99, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 1})
        for t, a, b in [(99991, 0, 99), (99992, 99, 1)]:
            g["tensors"].append({"id": t, "pos": "UB", "size": 8})
            g["edges"].extend([{"source": a, "target": t}, {"source": t, "target": b}])
        with self.assertRaises(UnsupportedStructure):
            recognize(g)


if __name__ == "__main__":
    unittest.main()
