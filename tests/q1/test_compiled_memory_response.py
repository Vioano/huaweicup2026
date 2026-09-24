"""At most three tiny static Task compilations; never invoke E0/E1/E2."""

import unittest

from src.q1.compiled_memory_response import compile_plan
from src.q1.response_compile import compile_plan as conservative_compile
from src.q1.response_oracle import PIPES


def op(ident, pipe):
    return {"id": ident, "op": "COMPUTE", "pipe": pipe, "cycles": 1}


def tensor(ident):
    return {"id": ident, "pos": "UB", "size": 80}


def graph(ops, tensors=(), edges=()):
    return {"ops": list(ops), "tensors": list(tensors),
            "edges": [{"source": source, "target": target}
                      for source, target in edges]}


PLAN = {"node_to_subgraph": {"1": 0, "2": 0}, "core_schedules": [[0]]}
CAPACITY = {"L1": 80, "UB": 80}


class CompiledMemoryResponseTests(unittest.TestCase):
    def test_step3_memory_reuse_predecessor_reaches_prefix(self):
        source = graph([op(1, "PIPE_M"), op(2, "PIPE_V")],
                       [tensor(100), tensor(101)], [(1, 100), (2, 101)])
        lines, certificate = compile_plan(source, PLAN, CAPACITY)
        detail = certificate["tasks"][0]
        self.assertEqual(detail["footprint"]["UB"], 160)
        self.assertEqual(detail["memory_peak"]["UB"], 80)
        self.assertTrue(detail["execution_contract_validated"])
        self.assertTrue(detail["memory_dependencies"])
        task = lines[0][0]
        by_id = {port_op.original_id: port_op
                 for port in task.ports for port_op in port}
        ranks = {port_op.original_id: (p, rank)
                 for p, port in enumerate(task.ports)
                 for rank, port_op in enumerate(port, 1)}
        for predecessor, successor in detail["memory_edge_pairs"]:
            pipe, rank = ranks[predecessor]
            self.assertGreaterEqual(by_id[successor].need[pipe], rank)
        self.assertEqual(certificate["calls"],
                         {"solver": 0, "E0": 0, "E1": 0, "E2": 0})

    def test_old_accepted_task_has_identical_signature(self):
        source = graph([op(1, "PIPE_M"), op(2, "PIPE_V")],
                       edges=[(1, 2)])
        old, _ = conservative_compile(source, PLAN, CAPACITY)
        new, certificate = compile_plan(source, PLAN, CAPACITY)
        self.assertEqual(new[0][0].signature(), old[0][0].signature())
        self.assertEqual(PIPES, ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3"))
        self.assertEqual(certificate["tasks"][0]["memory_dependencies"], [])


if __name__ == "__main__":
    unittest.main()
