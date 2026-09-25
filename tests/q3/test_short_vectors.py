"""Structural failure guards and independent tiny timing examples; zero E0."""
import itertools
from types import SimpleNamespace
import unittest

from src.q3.attention_rows import _capsules
from src.q3.construct import UnsupportedStructure
from src.q3.short_vectors import regions


def graph(pipes, edges, durations):
    nodes = list(range(len(pipes)))
    pred, succ = {u: set() for u in nodes}, {u: set() for u in nodes}
    for u, v in edges:
        pred[v].add(u)
        succ[u].add(v)
    return SimpleNamespace(ops={u: {"pipe": pipes[u]} for u in nodes},
                           order=nodes, pred=pred, succ=succ,
                           duration=lambda u: durations[u])


class ShortVectorTests(unittest.TestCase):
    def test_connected_fork_join_packs_beyond_exclusive_chain(self):
        g = graph(["PIPE_V"] * 4, [(0, 1), (0, 2), (1, 3), (2, 3)], [10] * 4)
        blocks, *_ = _capsules(g, [], vector_work_limit=50)
        self.assertEqual(blocks, [{"kind": "short_vector_region", "nodes": (0, 1, 2, 3)}])
        self.assertEqual(regions(g, g.ops, 39), [])
        self.assertEqual(regions(g, g.ops, 0), [])

    def test_protected_region_is_not_absorbed(self):
        g = graph(["PIPE_V"] * 4, [(0, 1), (1, 2), (2, 3)], [1] * 4)
        self.assertEqual(regions(g, {0, 1, 3}, 50), [(0, 1)])

    def test_nonconvex_V_component_fails_quotient_guard(self):
        g = graph(["PIPE_V", "PIPE_M", "PIPE_V"], [(0, 1), (1, 2), (0, 2)], [1] * 3)
        self.assertEqual(regions(g, g.ops, 50), [(0, 2)])
        with self.assertRaisesRegex(UnsupportedStructure, "quotient contains a cycle"):
            _capsules(g, [], vector_work_limit=50)

    def test_isolated_short_fork_join_locality_by_independent_timing(self):
        # In the original diamond, every nonconstant ownership has a crossing.
        # Enumerate just 16 assignments and their two possible middle orders.
        edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
        best_local, best_split = float("inf"), float("inf")
        for owner in itertools.product(range(2), repeat=4):
            for order in ((0, 1, 2, 3), (0, 2, 1, 3)):
                finish, free = {}, [0, 0]
                for v in order:
                    release = max([finish[u] + (50 if owner[u] != owner[v] else 0)
                                   for u, w in edges if w == v] or [0])
                    finish[v] = max(free[owner[v]], release) + 10
                    free[owner[v]] = finish[v]
                m = max(finish.values())
                if len(set(owner)) == 1:
                    best_local = min(best_local, m)
                else:
                    best_split = min(best_split, m)
        self.assertEqual(best_local, 40)
        self.assertGreater(best_split, best_local)

    def test_external_calendar_can_reverse_locality(self):
        # A 10+10 chain with delta=50. First op's external input releases at
        # t=0 on core0 and t=1000 on core1; core0 is occupied from10 to1000.
        # Joint placement cannot use a single core cheaply; moving the tail
        # finishes at70. This invalidates an unconditional whole-graph claim.
        local0 = 1010
        local1 = 1020
        split = 10 + 50 + 10
        self.assertLess(split, min(local0, local1))


if __name__ == "__main__":
    unittest.main()
