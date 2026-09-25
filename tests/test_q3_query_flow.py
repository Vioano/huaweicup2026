"""Tiny in-memory R8 topology checks; motif rows are injected, no evaluator."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from src.q3 import query_flow
from src.q3.construct import UnsupportedStructure


class ToyIndex:
    def __init__(self, graph):
        self.graph = graph
        self.ops = {op["id"]: op for op in graph["ops"]}
        op_ids = set(self.ops)
        producer = {e["target"]: e["source"] for e in graph["edges"]
                    if e["source"] in op_ids and e["target"] not in op_ids}
        self.pred = {u: set() for u in op_ids}
        self.succ = {u: set() for u in op_ids}
        for edge in graph["edges"]:
            if edge["source"] not in op_ids and edge["target"] in op_ids:
                source = producer.get(edge["source"])
                if source is not None:
                    self.pred[edge["target"]].add(source)
                    self.succ[source].add(edge["target"])
        degree = {u: len(self.pred[u]) for u in op_ids}
        ready = sorted(u for u in degree if not degree[u])
        self.order = []
        while ready:
            u = ready.pop(0)
            self.order.append(u)
            for v in sorted(self.succ[u]):
                degree[v] -= 1
                if not degree[v]:
                    ready.append(v)
                    ready.sort()
        if len(self.order) != len(op_ids):
            raise ValueError("toy cycle")

    def duration(self, u):
        return self.ops[u]["cycles"]


def toy(flows=3):
    graph = {"ops": [], "tensors": [], "edges": []}
    next_op, next_tensor = 1, 1001

    def tensor(size=8, pos="UB"):
        nonlocal next_tensor
        t = next_tensor
        next_tensor += 1
        graph["tensors"].append({"id": t, "size": size, "pos": pos})
        return t

    def op(kind, pipe, inputs, cycles=3):
        nonlocal next_op
        u = next_op
        next_op += 1
        t = tensor()
        graph["ops"].append({"id": u, "op": kind, "pipe": pipe, "cycles": cycles})
        graph["edges"].extend({"source": x, "target": u} for x in inputs)
        graph["edges"].append({"source": u, "target": t})
        return u, t

    parameter = tensor(pos="DDR")
    shared = op("MATMUL", "PIPE_M", [parameter])
    streams = []
    for i in range(flows):
        query = tensor(pos="DDR")
        weights = [tensor(pos="DDR") for _ in range(2)]
        q = op("MATMUL", "PIPE_M", [query, shared[1]])
        k = op("MATMUL", "PIPE_M", [query, weights[0]])
        v = op("MATMUL", "PIPE_M", [query, weights[1]])
        streams.append((q, k, v))
    rows = []
    for i in range(flows):
        source = streams[(i + 1) % flows]
        a = op("DIV", "PIPE_V", [streams[i][0][1], source[1][1], source[2][1]])
        op("ADD", "PIPE_V", [a[1]])
        rows.append({"q": streams[i][0][0], "k": (source[1][0],),
                     "v": (source[2][0],), "nodes": (a[0],), "sink": a[0]})
    return ToyIndex(graph), rows


class QueryFlowTests(unittest.TestCase):
    def test_canonical_pair_singletons_and_two_crossing_bound(self):
        index, rows = toy(3)
        with patch.object(query_flow, "_recognize", return_value=rows):
            plan, info = query_flow.construct(
                index, 2, cross_delay=7, capacity={"L1": 128, "UB": 512})
            self.assertEqual((plan, info), query_flow.construct(
                index, 2, cross_delay=7, capacity={"L1": 128, "UB": 512}))
        self.assertEqual(info["canonical_states"], 3)
        self.assertEqual(info["flow_count"], 3)
        self.assertLessEqual(info["max_remote_edges_on_path"], 2)
        self.assertLessEqual(info["Ldelta_compute_fifo"], info["L0_compute_fifo"] + 14)
        self.assertEqual(len(plan["node_to_subgraph"]), len(index.ops))
        self.assertEqual(sorted(sg for word in plan["core_schedules"] for sg in word),
                         list(range(len(index.ops))))
        op_of = {sg: int(op) for op, sg in plan["node_to_subgraph"].items()}
        stage = query_flow._decompose(index, query_flow._ports(index), rows)[0]
        for word in plan["core_schedules"]:
            for pipe in query_flow.PIPES:
                ranks = [query_flow.STAGES.index(stage[op_of[sg]][0]) for sg in word
                         if index.ops[op_of[sg]]["pipe"] == pipe]
                self.assertEqual(ranks, sorted(ranks))

    def test_capacity_and_direct_bridge_fail_closed(self):
        index, rows = toy(2)
        with patch.object(query_flow, "_recognize", return_value=rows):
            with self.assertRaisesRegex(UnsupportedStructure, "support capacity"):
                query_flow.construct(index, 2, capacity={"L1": 128, "UB": 8})
            index.graph["edges"].append({"source": rows[0]["q"], "target": rows[0]["sink"]})
            with self.assertRaisesRegex(UnsupportedStructure, "direct edges unsupported"):
                query_flow.construct(index, 2, capacity={"L1": 128, "UB": 512})


if __name__ == "__main__":
    unittest.main()
