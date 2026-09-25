"""Small structural R6 tests; each test makes at most one candidate call.

No solver, Task compiler, response simulator, E1, E0, or E2 is invoked.
"""
import unittest

from src.q1.branch_aid import construct


def op(ident, cycles, pipe="PIPE_M"):
    return {"id": ident, "op": "ADD", "pipe": pipe, "cycles": cycles}


def edge(source, target):
    return {"source": source, "target": target}


def fork_graph(helper_cycles=6, shared_input=False):
    graph = {"ops": [op(1, 12), op(2, 12), op(3, 1, "PIPE_V"),
                     op(4, helper_cycles)],
             "tensors": [], "edges": [edge(1, 3), edge(2, 3)]}
    if shared_input:
        graph["tensors"].append({"id": 100, "size": 128, "pos": "DDR"})
        graph["edges"].extend([edge(100, node) for node in (1, 2, 3)])
    return graph


def fork_base():
    return {"node_to_subgraph": {1: 0, 2: 0, 3: 0, 4: 1},
            "core_schedules": [[0], [1]]}


class BranchAidTests(unittest.TestCase):
    def test_independent_bridge_join_and_exact_repeated_read(self):
        graph, base = fork_graph(shared_input=True), fork_base()
        candidate, info = construct(graph, 2, base)
        self.assertEqual(info["status"], "candidate-unscored")
        self.assertEqual(info["split_tasks"], 1)
        # Equal branch work exports the larger predecessor ID (2).
        mapping = candidate["node_to_subgraph"]
        self.assertEqual(mapping[1], 0)
        self.assertNotEqual(mapping[2], mapping[1])
        self.assertNotEqual(mapping[3], mapping[1])
        self.assertNotEqual(mapping[2], mapping[3])
        self.assertEqual(candidate["core_schedules"][0], [0, mapping[3]])
        self.assertEqual(candidate["core_schedules"][1], [mapping[2], 1])
        self.assertEqual(set(mapping), {1, 2, 3, 4})
        # The original shared DDR tensor is read once by the old Task and
        # separately by X, Y, J after splitting: two extra 128-byte COPY_INs.
        self.assertEqual(info["boundary_delta"]["copy_in_instances"], 2)
        self.assertEqual(info["boundary_delta"]["bytes"], 256)
        self.assertEqual(info["boundary_delta"]["service_cycles"], 6)
        self.assertEqual(info["scoring_calls"], {"E1": 0, "E0": 0, "E2": 0})

    def test_same_height_core_order_is_unsupported(self):
        graph = fork_graph()
        graph["ops"].append(op(5, 1))
        base = fork_base()
        base["node_to_subgraph"][5] = 2
        base["core_schedules"][0].append(2)
        candidate, info = construct(graph, 2, base)
        self.assertEqual(candidate, base)
        self.assertEqual(info["status"], "unsupported")
        self.assertIn("strictly advance Task height", info["reason"])

    def test_augmented_core_order_cycle_is_rejected(self):
        # The op graph is acyclic: 2 -> 3 and 4 -> 1. Core order would add
        # 1 -> 2 and 3 -> 4, closing a Task-level ring.
        graph = {"ops": [op(i, 1) for i in range(1, 5)],
                 "tensors": [], "edges": [edge(2, 3), edge(4, 1)]}
        base = {"node_to_subgraph": {1: 0, 2: 1, 3: 2, 4: 3},
                "core_schedules": [[0, 1], [2, 3]]}
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            construct(graph, 2, base)

    def test_copy_contracted_hidden_edge_rejects_packet(self):
        graph = fork_graph()
        graph["ops"].extend([
            {"id": 5, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 1},
            {"id": 6, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 1},
        ])
        graph["tensors"] = [{"id": i, "size": 16, "pos": "UB"}
                            for i in (100, 101, 102)]
        graph["edges"].extend([edge(1, 100), edge(100, 5),
                               edge(5, 101), edge(101, 6),
                               edge(6, 102), edge(102, 2)])
        base = fork_base()
        candidate, info = construct(graph, 2, base)
        self.assertEqual(candidate, base)
        self.assertEqual(info["status"], "unsupported")
        self.assertIn("no wave passed", info["reason"])

    def test_batch_work_does_not_improve_and_falls_back(self):
        graph, base = fork_graph(helper_cycles=15), fork_base()
        candidate, info = construct(graph, 2, base)
        self.assertEqual(candidate, base)
        self.assertEqual(info["status"], "unsupported")
        self.assertIn("no wave passed", info["reason"])


if __name__ == "__main__":
    unittest.main()
