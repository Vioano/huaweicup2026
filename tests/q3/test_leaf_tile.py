"""Small structural tests and one read-only 097 plan-construction check."""
import copy
import json
from pathlib import Path
import unittest

from src.q3.construct import Index, UnsupportedStructure, derive_multicore_plan
from src.q3.forest_memory_order import construct as forest_order
from src.q3.leaf_tile import construct, transform


ROOT = Path(__file__).resolve().parents[2]


def grid_graph(m=3, n=4, leaves=3, a=1000, b=10, s=3):
    graph = {"ops": [], "tensors": [], "edges": []}
    next_op, next_tensor = 1, 10000

    def op(kind, pipe, cycles=1):
        nonlocal next_op
        u = next_op
        next_op += 1
        graph["ops"].append({"id": u, "op": kind, "pipe": pipe, "cycles": cycles})
        return u

    def tensor(size, pos="L1"):
        nonlocal next_tensor
        tid = next_tensor
        next_tensor += 1
        graph["tensors"].append({"id": tid, "size": size, "pos": pos})
        return tid

    def edge(u, v):
        graph["edges"].append({"source": u, "target": v})

    def input_tensor(size):
        raw, local = tensor(size, "DDR"), tensor(size)
        copy_in = op("COPY_IN", "PIPE_MTE2", 0)
        edge(raw, copy_in)
        edge(copy_in, local)
        return local

    row = [[input_tensor(a) for _ in range(leaves)] for _ in range(m)]
    col = [[input_tensor(b) for _ in range(leaves)] for _ in range(n)]
    matmuls = {}
    for i in range(m):
        for j in range(n):
            leaf_outputs = []
            for t in range(leaves):
                u, output = op("MATMUL", "PIPE_M", 10), tensor(s)
                edge(row[i][t], u)
                edge(col[j][t], u)
                edge(u, output)
                leaf_outputs.append(output)
                matmuls[i, j, t] = u
            acc = leaf_outputs[0]
            for t in range(1, leaves):
                u, output = op("ADD", "PIPE_V", 2), tensor(s)
                edge(acc, u)
                edge(leaf_outputs[t], u)
                edge(u, output)
                acc = output
            out, raw = op("COPY_OUT", "PIPE_MTE3", 0), tensor(s, "DDR")
            edge(acc, out)
            edge(out, raw)
    return graph, matmuls, col


class LeafTileTests(unittest.TestCase):
    def test_general_algebra_and_ownership(self):
        graph, _, _ = grid_graph()
        index = Index(graph)
        base, _ = forest_order(index, 1)
        plan, meta = transform(index, base, 2200)
        self.assertEqual(meta["axis_sizes"], [3, 4])
        self.assertEqual(meta["leaf_count"], 3)
        self.assertEqual(meta["tile_shape"], [2, 4])
        self.assertEqual(meta["ideal_input_bytes_per_leaf_round"], 3080)
        self.assertEqual(meta["ideal_max_layer_frontier_bytes"], 2091)
        self.assertEqual(plan["node_to_subgraph"], base["node_to_subgraph"])
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        derive_multicore_plan(graph, plan)

    def test_two_cores_keep_each_original_op_owner(self):
        graph, _, _ = grid_graph()
        index = Index(graph)
        base, _ = forest_order(index, 2)
        plan, meta = transform(index, base, {"L1": 2200})
        def owners(p):
            return {u: core for core, seq in enumerate(p["core_schedules"])
                    for sg in seq for u, x in p["node_to_subgraph"].items() if x == sg}
        self.assertEqual(owners(plan), owners(base))
        self.assertEqual(len(meta["tiles_by_core"]), 2)
        self.assertGreaterEqual(sum(meta["tiles_by_core"]), 2)
        derive_multicore_plan(graph, plan)

    def test_leaf_ordinal_must_match_original_shared_tensor(self):
        graph, matmuls, col = grid_graph()
        bad = copy.deepcopy(graph)
        u0, u1 = matmuls[0, 0, 0], matmuls[0, 0, 1]
        for edge in bad["edges"]:
            if edge["target"] == u0 and edge["source"] == col[0][0]:
                edge["source"] = col[0][1]
            elif edge["target"] == u1 and edge["source"] == col[0][1]:
                edge["source"] = col[0][0]
        index = Index(bad)
        base, _ = forest_order(index, 1)
        with self.assertRaisesRegex(UnsupportedStructure, "shared input"):
            transform(index, base, 2200)

    def test_bottom_pair_op_ids_need_not_align_between_cells(self):
        graph, matmuls, _ = grid_graph()
        u0, u1 = matmuls[0, 1, 0], matmuls[0, 1, 1]
        for op in graph["ops"]:
            if op["id"] == u0:
                op["id"] = u1
            elif op["id"] == u1:
                op["id"] = u0
        for edge in graph["edges"]:
            for key in ("source", "target"):
                if edge[key] == u0:
                    edge[key] = u1
                elif edge[key] == u1:
                    edge[key] = u0
        index = Index(graph)
        base, _ = forest_order(index, 1)
        plan, _ = transform(index, base, 2200)
        derive_multicore_plan(graph, plan)

    def test_balanced_reduction_is_rejected(self):
        graph, matmuls, _ = grid_graph(leaves=4)
        index = Index(graph)
        adds = sorted(u for u in index.components[0]
                      if index.ops[u]["op"] == "ADD")
        first_result = next(e["target"] for e in graph["edges"]
                            if e["source"] == adds[0] and e["target"] >= 10000)
        last_leaf_result = next(e["target"] for e in graph["edges"]
                                if e["source"] == matmuls[0, 0, 3]
                                and e["target"] >= 10000)
        for edge in graph["edges"]:
            if edge["source"] == first_result and edge["target"] == adds[1]:
                edge["target"] = adds[2]
            elif edge["source"] == last_leaf_result and edge["target"] == adds[2]:
                edge["target"] = adds[1]
        index = Index(graph)
        base, _ = forest_order(index, 1)
        with self.assertRaisesRegex(UnsupportedStructure, "strict left-deep"):
            transform(index, base, 2200)

    def test_097_construct_is_static_legal_and_selects_four_by_four(self):
        graph = json.loads((ROOT / "data/raw/a/official/data/case_097.json").read_text())
        index = Index(graph)
        plan, meta = construct(index, 1, 524288)
        self.assertEqual(meta["tile_shape"], [4, 4])
        self.assertEqual(meta["ideal_max_layer_frontier_bytes"], 446464)
        self.assertEqual(meta["ideal_input_bytes_per_leaf_round"], 163840)
        self.assertEqual(plan["node_to_subgraph"],
                         {str(u): i for i, u in enumerate(index.order)})
        self.assertEqual(len(plan["core_schedules"][0]), len(index.ops))
        derive_multicore_plan(graph, plan)


if __name__ == "__main__":
    unittest.main()
