"""Static bridge relocation tests; no Task compiler or evaluator calls."""
import unittest

from src.q1 import branch_aid
from src.q1.general_bridge_probe import construct


def op(ident, cycles, pipe="PIPE_M"):
    return {"id": ident, "op": "ADD", "pipe": pipe, "cycles": cycles}


def edge(a, b):
    return {"source": a, "target": b}


class GeneralBridgeTests(unittest.TestCase):
    def test_idle_helper_and_same_height_core_order(self):
        graph = {"ops": [op(1, 12), op(2, 12), op(3, 1, "PIPE_V"),
                         op(4, 1)], "tensors": [],
                 "edges": [edge(1, 3), edge(2, 3)]}
        base = {"node_to_subgraph": {1: 0, 2: 0, 3: 0, 4: 1},
                "core_schedules": [[0, 1], []]}
        old, old_info = branch_aid.construct(graph, 2, base)
        self.assertEqual(old, base)
        self.assertIn("strictly advance Task height", old_info["reason"])
        plan, info = construct(graph, 2, base)
        self.assertEqual(info["status"], "candidate-unscored")
        self.assertEqual(info["helper_core"], 1)
        self.assertEqual(info["helper_slot"], 0)
        self.assertEqual(info["census"]["old_tasks"], 2)
        self.assertEqual(info["scoring_calls"], {"E1": 0, "E0": 0, "E2": 0})
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        branch_aid.validate_task_order(branch_aid.derive_multicore_plan(graph, plan))
        self.assertEqual(base["core_schedules"], [[0, 1], []])

    def test_helper_slot_after_required_predecessor(self):
        # Task 1 -> donor Task 0; exported X contains op 1, so X cannot
        # precede Task 1 on its helper. Donor also has two same-height Tasks.
        graph = {"ops": [op(1, 4), op(2, 12), op(3, 1, "PIPE_V"),
                         op(4, 1), op(5, 1)], "tensors": [],
                 "edges": [edge(1, 3), edge(2, 3), edge(4, 1)]}
        base = {"node_to_subgraph": {1: 0, 2: 0, 3: 0, 4: 1, 5: 2},
                "core_schedules": [[0, 2], [1]]}
        plan, info = construct(graph, 2, base)
        self.assertEqual(info["status"], "candidate-unscored")
        self.assertEqual(info["export_pred"], 1)
        self.assertEqual(info["helper_slot"], 1)
        self.assertEqual(info["census"]["feasible_insertion_slots"], 1)
        branch_aid.validate_task_order(branch_aid.derive_multicore_plan(graph, plan))

    def test_no_witness_keeps_exact_baseline(self):
        graph = {"ops": [op(1, 2), op(2, 2)], "tensors": [], "edges": []}
        base = {"node_to_subgraph": {1: 0, 2: 1},
                "core_schedules": [[0], [1]]}
        plan, info = construct(graph, 2, base)
        self.assertEqual(plan, base)
        self.assertEqual(info["status"], "unsupported")
        self.assertEqual(info["census"]["bridge_witnessed_tasks"], 0)


if __name__ == "__main__":
    unittest.main()
