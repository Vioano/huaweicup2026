import itertools
import unittest

from src.q3.reuse_projection_bound import lower_bound


class ProjectionBoundTests(unittest.TestCase):
    def test_bound_against_exhaustive_small_edge_partitions(self):
        # Independent edge-coloring enumerator checks all load vectors, including
        # empty cores; it does not reuse the support DP's constraints.
        for m, n, k in [(1, 3, 2), (2, 3, 2), (2, 3, 3), (3, 3, 2)]:
            optima = {}
            for owners in itertools.product(range(k), repeat=m * n):
                loads = tuple(owners.count(core) for core in range(k))
                cost = sum(2 * len({i // n for i, c in enumerate(owners) if c == core}) +
                           3 * len({i % n for i, c in enumerate(owners) if c == core})
                           for core in range(k))
                optima[loads] = min(cost, optima.get(loads, cost))
            for loads, optimum in optima.items():
                value = lower_bound(m, n, 2, 3, loads)
                self.assertLessEqual(value['lower_bound_bytes'], optimum, (m, n, loads))
                self.assertGreaterEqual(value['lower_bound_bytes'], value['individual_support_bound_bytes'])

    def test_current_uniform_input_groups_have_stricter_bounds(self):
        a = lower_bound(17, 15, 270336, 135168, [51] * 5)
        b = lower_bound(18, 16, 202752, 135168, [58, 58, 58, 57, 57])
        self.assertEqual((a['individual_support_bound_bytes'], a['lower_bound_bytes']),
                         (14192640, 14733312))
        self.assertEqual((b['individual_support_bound_bytes'], b['lower_bound_bytes']),
                         (12840960, 13246464))


if __name__ == '__main__':
    unittest.main()
