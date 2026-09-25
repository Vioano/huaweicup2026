"""Structural Stage N tests; no Task compiler or evaluator calls."""
import unittest

from src.q1_yuanzhifang_stage_n.adjacent_spill_invariant import construct, merge_plan

CAP = {"L1": 524288, "UB": 131072}


def graph(ops, tensors, edges):
    return {"ops": [{"id": u, "op": kind, "pipe": "PIPE_V", "cycles": 1}
                    for u, kind in ops],
            "tensors": [{"id": t, "size": size, "pos": pos}
                        for t, size, pos in tensors],
            "edges": [{"source": u, "target": v} for u, v in edges]}


def plan(*orders):
    return {"node_to_subgraph": {u: u for order in orders for u in order},
            "core_schedules": [list(order) for order in orders]}


class AdjacentSpillInvariantTests(unittest.TestCase):
    def test_unrelated_oversize_task_does_not_block_fit_pair(self):
        g = graph([(1, "ADD"), (2, "ADD"), (3, "ADD")],
                  [(10, 530000, "L1"), (11, 128, "L1")],
                  [(10, 1), (2, 11), (11, 3)])
        result, d = merge_plan(g, plan([1, 2, 3]), CAP)
        self.assertEqual(result["core_schedules"], [[1, 2]])
        self.assertEqual(result["node_to_subgraph"], {1: 1, 2: 2, 3: 2})
        self.assertEqual([x["task"] for x in d["oversize_original_tasks"]], [1])
        self.assertEqual([(x["left"], x["right"]) for x in d["merged_pairs"]], [(2, 3)])

    def test_merged_union_still_must_fit(self):
        g = graph([(1, "ADD"), (2, "ADD")],
                  [(10, 300000, "L1"), (11, 300000, "L1")],
                  [(10, 1), (11, 2)])
        base = plan([1, 2])
        result, d = merge_plan(g, base, CAP)
        self.assertIs(result, base)
        self.assertEqual(d["reason"], "no_adjacent_pair_within_resident_union_capacity")

    def test_remote_path_and_copy_bridge_fall_back(self):
        remote = graph([(1, "ADD"), (2, "ADD"), (3, "ADD")],
                       [(10, 128, "L1"), (11, 128, "L1")],
                       [(1, 10), (10, 3), (3, 11), (11, 2)])
        base = plan([1, 2], [3])
        self.assertEqual(merge_plan(remote, base, CAP)[1]["reason"], "remote_task_dependency")
        bridge = graph([(1, "ADD"), (2, "ADD"), (3, "COPY_OUT")],
                       [(10, 128, "L1"), (11, 128, "L1")],
                       [(1, 10), (10, 3), (3, 11), (11, 2)])
        self.assertEqual(merge_plan(bridge, plan([1, 2]), CAP)[1]["reason"],
                         "excluded_copy_bridge_between_compute_ops")

    def test_base_once_and_exact_plan_fields(self):
        g = graph([(1, "ADD"), (2, "ADD")], [(10, 128, "L1")],
                  [(1, 10), (10, 2)])
        calls = []

        def base(actual, cores):
            calls.append((actual, cores))
            return plan([1, 2]), {"algorithm_id": "synthetic-base"}

        result, d = construct(g, 1, base_constructor=base)
        self.assertEqual(calls, [(g, 1)])
        self.assertEqual(set(result), {"node_to_subgraph", "core_schedules"})
        self.assertEqual(d["algorithm_id"], "q1-adjacent-spill-invariant-stage-n")


if __name__ == "__main__":
    unittest.main()
