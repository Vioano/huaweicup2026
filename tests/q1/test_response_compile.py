"""Tiny static official Task-compilation fixtures; no evaluator or solver calls."""

import unittest

from src.q1.response_compile import UnsupportedResponse, compile_plan
from src.q1.response_oracle import PIPES


CAPACITY = {"L1": 1000, "UB": 1000}


def op(ident, pipe, cycles=1, kind="COMPUTE"):
    return {"id": ident, "op": kind, "pipe": pipe, "cycles": cycles}


def tensor(ident, size=60, pos="UB"):
    return {"id": ident, "size": size, "pos": pos}


def graph(ops, tensors=(), edges=()):
    return {"ops": list(ops), "tensors": list(tensors),
            "edges": [{"source": a, "target": b} for a, b in edges]}


def plan(mapping, *core_orders):
    return {"node_to_subgraph": {str(k): v for k, v in mapping.items()},
            "core_schedules": [list(order) for order in core_orders]}


class OfficialResponseCompileTests(unittest.TestCase):
    def test_direct_dependency_uses_completed_prefix_in_response_pipe_order(self):
        source = graph([op(1, "PIPE_M", 7), op(2, "PIPE_V", 3)],
                       edges=[(1, 2)])
        lines, certificate = compile_plan(source, plan({1: 0, 2: 0}, [0]), CAPACITY)
        self.assertEqual(PIPES, ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3"))
        task = lines[0][0]
        self.assertEqual(task.ports[0][0].work, 7)
        self.assertEqual(task.ports[1][0].need, (1, 0, 0, 0))
        self.assertEqual(task.ports[0][0].original_id, 1)
        self.assertEqual(certificate["tasks"][0]["op_count"], 2)
        self.assertEqual(certificate["calls"],
                         {"solver": 0, "E0": 0, "E1": 0, "E2": 0})
        source["edges"][0]["dependency"] = "MEMORY_REUSE"
        with self.assertRaisesRegex(UnsupportedResponse, "memory-reuse edge"):
            compile_plan(source, plan({1: 0, 2: 0}, [0]), CAPACITY)

    def test_task_boundary_copies_use_official_fifo_duration_and_ddr_flag(self):
        source = graph([op(1, "PIPE_M", 5)],
                       [tensor(100, 120), tensor(101, 120)],
                       [(100, 1), (1, 101)])
        lines, certificate = compile_plan(source, plan({1: 0}, [0]), CAPACITY)
        task = lines[0][0]
        self.assertEqual([len(port) for port in task.ports], [1, 0, 1, 1])
        read = task.ports[2][0]
        compute = task.ports[0][0]
        write = task.ports[3][0]
        self.assertEqual((read.work, read.ddr), (2, True))
        self.assertEqual((compute.work, compute.ddr), (5, False))
        self.assertEqual((write.work, write.ddr), (2, True))
        self.assertEqual(compute.need, (0, 0, 1, 0))
        self.assertEqual(write.need, (1, 0, 0, 0))
        self.assertEqual(certificate["tasks"][0]["footprint"]["UB"], 240)

    def test_same_core_task_dependency_preserves_order(self):
        source = graph([op(1, "PIPE_M"), op(2, "PIPE_V")],
                       edges=[(1, 2)])
        lines, _ = compile_plan(source, plan({1: 8, 2: 9}, [8, 9]), CAPACITY)
        self.assertEqual([task.task_id for task in lines[0]], [8, 9])

    def test_cross_core_dependency_rejected_before_compilation(self):
        source = graph([op(1, "PIPE_M"), op(2, "PIPE_V")],
                       edges=[(1, 2)])
        with self.assertRaisesRegex(UnsupportedResponse, "cross-core"):
            compile_plan(source, plan({1: 8, 2: 9}, [8], [9]), CAPACITY)

    def test_same_core_tensor_cut_is_not_cross_core_traffic(self):
        source = graph([op(1, "PIPE_M"), op(2, "PIPE_V")],
                       [tensor(100, 61)], [(1, 100), (100, 2)])
        lines, certificate = compile_plan(
            source, plan({1: 8, 2: 9}, [8, 9]), CAPACITY)
        self.assertEqual(certificate["cross_task_tensor_bytes"], 61)
        self.assertEqual(lines[0][0].ports[3][0].work, 2)
        self.assertEqual(lines[0][1].ports[2][0].work, 2)

    def test_multiple_producers_and_capacity_rejected(self):
        shared = graph([op(1, "PIPE_M"), op(2, "PIPE_V")],
                       [tensor(100)], [(1, 100), (2, 100)])
        with self.assertRaisesRegex(UnsupportedResponse, "multiple producers"):
            compile_plan(shared, plan({1: 0, 2: 0}, [0]), CAPACITY)
        oversized = graph([op(1, "PIPE_M")], [tensor(100, 1001)],
                          [(100, 1)])
        with self.assertRaisesRegex(UnsupportedResponse, "capacity"):
            compile_plan(oversized, plan({1: 0}, [0]), CAPACITY)


if __name__ == "__main__":
    unittest.main()
