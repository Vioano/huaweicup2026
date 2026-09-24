import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/q1_yuanzhifang"))
from diagnose import lower_bounds


class BoundTests(unittest.TestCase):
    def graph(self):
        return {"ops": [{"id": 0, "op": "X", "pipe": "PIPE_M", "cycles": 3},
                        {"id": 1, "op": "X", "pipe": "PIPE_V", "cycles": 4}],
                "tensors": [{"id": 10, "pos": "UB", "size": 1}],
                "edges": [{"source": 0, "target": 10}, {"source": 10, "target": 1}]}

    def test_same_core_and_cross_core_gates(self):
        waits = {"task_same_core_wait_cycles": 100, "task_cross_core_wait_cycles": 1000}
        for schedules, expected in (([[0, 1], []], 107), ([[0], [1]], 1007)):
            b = lower_bounds(self.graph(), {"node_to_subgraph": {0: 0, 1: 1}, "core_schedules": schedules}, waits)
            self.assertEqual(b["task_gate_lower_bound_cycles"], expected)
            self.assertEqual(b["witness_compute_cycles"] + b["witness_gate_cycles"], expected)

    def test_internal_dependency_cannot_overlap_different_pipes(self):
        b = lower_bounds(self.graph(), {"node_to_subgraph": {0: 0, 1: 0}, "core_schedules": [[0]]},
                         {"task_same_core_wait_cycles": 100, "task_cross_core_wait_cycles": 1000})
        self.assertEqual(b["task_gate_lower_bound_cycles"], 7)
        self.assertEqual(b["global_pipe_work_lower_bound_cycles"], 4)


if __name__ == "__main__":
    unittest.main()
