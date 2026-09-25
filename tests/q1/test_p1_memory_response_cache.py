"""Pure fake-compiler checks; zero official Task compiles or model responses."""
import unittest
from unittest.mock import patch

from src.q1.response_oracle import PortOp, Task
from src.review.p1_memory_response_cache import DomainContract, MemoryResponseCache


class FakeFamily:
    capacity = {"L1": 80, "UB": 80}
    bandwidth = 60
    eligible = {1, 2, 3}
    family_certificate = {"private": True, "original_ids_unchanged": True}

    def __init__(self):
        self.view = type("View", (), {
            "in_t": {1: {10}, 2: {10}, 3: {12, 14}},
            "out_t": {1: {11}, 2: {11}, 3: {13}},
        })()

    def prekey(self, nodes):
        return ("same-ordered-shape",)


def prepared(nodes):
    return {"in_tids": {u: sorted(FakeFamily().view.in_t[u]) for u in nodes},
            "out_tids": {u: sorted(FakeFamily().view.out_t[u]) for u in nodes},
            "step3": {"execution_contract_validated": True}}


class CacheTests(unittest.TestCase):
    @patch("src.review.p1_memory_response_cache.source_scope", return_value=("fixed",))
    def test_hit_different_word_and_normalized_ids(self, _):
        calls = []
        def compiler(nodes):
            calls.append(nodes)
            task = Task(((PortOp(1, False, (0, 0, 0, 0), nodes[0]),), (), (), ()), 99)
            return task, {"spill_added_copy_bytes": 0, "scheduled_copy_bytes": 1}, prepared(nodes)
        cache = MemoryResponseCache(FakeFamily(), domain_contract=DomainContract(
            MemoryResponseCache.DOMAIN, True), compiler=compiler, max_task_compiles=2)
        first = cache.get((1,))
        again = cache.get((2,))  # same prekey and release word
        distinct = cache.get((3,))  # two inputs change the release word
        self.assertEqual(len(calls), 2)
        self.assertTrue(again["cache_hit"])
        self.assertFalse(distinct["cache_hit"])
        self.assertEqual(first["task"].task_id, -1)
        self.assertEqual(first["task"].ports[0][0].original_id, -1)

    @patch("src.review.p1_memory_response_cache.source_scope", return_value=("fixed",))
    def test_failure_and_preflight_budget(self, _):
        calls = []
        def compiler(nodes):
            calls.append(nodes)
            raise RuntimeError("fake compile failure")
        cache = MemoryResponseCache(FakeFamily(), domain_contract=DomainContract(
            MemoryResponseCache.DOMAIN, True), compiler=compiler, max_task_compiles=1)
        with self.assertRaisesRegex(RuntimeError, "fake compile failure"):
            cache.get((1,))
        self.assertEqual(cache.entries, {})
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            cache.get((1,))
        self.assertEqual(len(calls), 1)
        self.assertEqual(cache.compile_attempts, 1)


if __name__ == "__main__":
    unittest.main()
