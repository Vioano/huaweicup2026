"""Small structural and static-compiler checks; no real case or evaluator."""
import unittest

from src.q1.variable_packet import Family, Unsupported, construct
from tests.q1.test_capacity_return import chains


CAPACITY = {"L1": 1024, "UB": 160}


class VariablePacketTests(unittest.TestCase):
    def test_ordered_family_rejects_interleaved_original_ids(self):
        graph = chains(3)
        exchange = {2: 3, 3: 2}
        for op in graph["ops"]:
            op["id"] = exchange.get(op["id"], op["id"])
        for edge in graph["edges"]:
            edge["source"] = exchange.get(edge["source"], edge["source"])
            edge["target"] = exchange.get(edge["target"], edge["target"])
        with self.assertRaisesRegex(Unsupported, "interleaved compute-ID blocks"):
            Family(graph, 2, CAPACITY, 60)

    def test_ordered_family_rejects_interleaved_tensor_ids(self):
        graph = chains(3)
        exchange = {1003: 1004, 1004: 1003}
        for tensor in graph["tensors"]:
            tensor["id"] = exchange.get(tensor["id"], tensor["id"])
        for edge in graph["edges"]:
            edge["source"] = exchange.get(edge["source"], edge["source"])
            edge["target"] = exchange.get(edge["target"], edge["target"])
        with self.assertRaisesRegex(Unsupported, "interleaved tensor-ID blocks"):
            Family(graph, 2, CAPACITY, 60)

    def test_small_variable_width_path_and_explicit_tail(self):
        graph = chains(5)  # B=2 per core; one core has a true remainder.
        plan, info = construct(graph, 2, CAPACITY, 60, 100,
                               compile_limit=20, final_limit=12)
        self.assertEqual(info["B"], 2)
        self.assertEqual(info["Qmax"], 2)
        self.assertIn(info["terminal_policy"], ("merge", "separate"))
        self.assertTrue(info["terminals"])
        self.assertEqual(info["model_makespan"], info["response"]["makespan"])
        self.assertEqual(set(map(int, plan["node_to_subgraph"])), set(range(15)))
        self.assertLessEqual(info["total_static_task_compiles"], 40)
        n = 0
        for before, pending, q, following in info["actions"]:
            self.assertEqual(before, n)
            self.assertLessEqual(following, q)
            self.assertTrue(q > 0 or pending > 0)
            n += q
        self.assertEqual(n, info["B"])


if __name__ == "__main__":
    unittest.main()
