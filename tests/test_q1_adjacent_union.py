"""Small structural tests only; never call Task compilation or evaluators."""
import unittest

from src.q1_yuanzhifang_stage_m.adjacent_union import construct, merge_plan
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


CAP = {"L1": 524288, "UB": 131072}


def op(ident, kind="ADD"):
    return {"id": ident, "op": kind, "pipe": "PIPE_V", "cycles": 1}


def tensor(ident, size=128, pos="L1"):
    return {"id": ident, "size": size, "pos": pos}


def edge(a, b):
    return {"source": a, "target": b}


def plan(schedules):
    return {"node_to_subgraph": {u: u for order in schedules for u in order},
            "core_schedules": schedules}


def task_output_boundary_for(graph, proposal, producer, tensor_id):
    """The official output predicate for a tensor without original COPY_OUT."""
    producer_task = proposal["node_to_subgraph"][producer]
    consumers = {e["target"] for e in graph["edges"] if e["source"] == tensor_id
                 and e["target"] in proposal["node_to_subgraph"]}
    return not consumers or any(proposal["node_to_subgraph"][u] != producer_task
                                for u in consumers)


class AdjacentUnionTests(unittest.TestCase):
    def test_internal_boundary_and_third_consumer(self):
        # A produces t; B and later C consume t. Merge A+B, keep C external.
        graph = {"ops": [op(1), op(2), op(3)],
                 "tensors": [tensor(11)],
                 "edges": [edge(1, 11), edge(11, 2), edge(11, 3)]}
        base = plan([[1, 2, 3]])
        result, d = merge_plan(graph, base, CAP)
        self.assertEqual(result["core_schedules"], [[1, 3]])
        self.assertEqual(result["node_to_subgraph"], {1: 1, 2: 1, 3: 3})
        self.assertEqual(d["merged_pairs"][0]["resident_union_bytes"], {"L1": 128, "UB": 0})
        # B's input disappears, while A's output remains for third Task C.
        self.assertTrue(task_output_boundary_for(graph, base, 1, 11))
        self.assertTrue(task_output_boundary_for(graph, result, 1, 11))
        self.assertNotEqual(result["node_to_subgraph"][3], result["node_to_subgraph"][1])
        validate_task_order(derive_multicore_plan(graph, result))

    def test_external_reuse_is_not_required(self):
        graph = {"ops": [op(1), op(2)],
                 "tensors": [tensor(10), tensor(11)],
                 "edges": [edge(10, 1), edge(11, 2)]}
        result, d = merge_plan(graph, plan([[1, 2]]), CAP)
        self.assertEqual(result["core_schedules"], [[1]])
        self.assertEqual(len(d["merged_pairs"]), 1)

    def test_l1_and_ub_union_limits(self):
        for pos, size in (("L1", 300000), ("UB", 80000), ("DDR", 80000)):
            with self.subTest(pos=pos):
                graph = {"ops": [op(1), op(2)],
                         "tensors": [tensor(10, size, pos), tensor(11, size, pos)],
                         "edges": [edge(10, 1), edge(11, 2)]}
                base = plan([[1, 2]])
                result, d = merge_plan(graph, base, CAP)
                self.assertIs(result, base)
                self.assertEqual(d["reason"], "no_adjacent_pair_within_resident_union_capacity")

    def test_original_oversize_task_falls_back(self):
        graph = {"ops": [op(1), op(2)],
                 "tensors": [tensor(10, 530000)],
                 "edges": [edge(10, 1)]}
        base = plan([[1, 2]])
        result, d = merge_plan(graph, base, CAP)
        self.assertIs(result, base)
        self.assertIn("exceeds_resident_union_capacity", d["reason"])

    def test_remote_path_and_copy_bridge_fall_back(self):
        remote = {"ops": [op(1), op(2), op(3)],
                  "tensors": [tensor(10), tensor(11)],
                  "edges": [edge(1, 10), edge(10, 3), edge(3, 11), edge(11, 2)]}
        base = plan([[1, 2], [3]])
        result, d = merge_plan(remote, base, CAP)
        self.assertIs(result, base)
        self.assertEqual(d["reason"], "remote_task_dependency")

        bridge = {"ops": [op(1), op(2), op(3, "COPY_OUT")],
                  "tensors": [tensor(10), tensor(11)],
                  "edges": [edge(1, 10), edge(10, 3), edge(3, 11), edge(11, 2)]}
        base = plan([[1, 2]])
        result, d = merge_plan(bridge, base, CAP)
        self.assertIs(result, base)
        self.assertEqual(d["reason"], "excluded_copy_bridge_between_compute_ops")

    def test_construct_includes_base_and_returns_only_plan_fields(self):
        graph = {"ops": [op(1), op(2)], "tensors": [tensor(10)],
                 "edges": [edge(10, 1), edge(10, 2)]}
        calls = []

        def frozen_stub(actual_graph, cores):
            calls.append((actual_graph, cores))
            return plan([[1, 2]]), {"algorithm_id": "injected-base"}

        result, d = construct(graph, 1, base_constructor=frozen_stub)
        self.assertEqual(len(calls), 1)
        self.assertEqual(set(result), {"node_to_subgraph", "core_schedules"})
        self.assertEqual(d["selected"], "adjacent-union")
        self.assertEqual(d["base_algorithm"]["algorithm_id"], "injected-base")


if __name__ == "__main__":
    unittest.main()
