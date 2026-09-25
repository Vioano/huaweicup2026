"""Pure arithmetic and a compute-only precedence model; zero official calls."""
from fractions import Fraction
from itertools import permutations, product
import unittest

from src.review.p1_packet_edge_bound import Resources, exact_box_minimum


def compute_finish(w, word, a, b, c):
    # Independent two-Pipe earliest-start calculation. All W spines are first;
    # arbitrary P/R interleavings follow. Copies/MEM are absent, never simulated.
    m = v = 0
    for _ in range(w):
        m += a
        v = max(v, m) + b
        m = max(m, v) + c
    for role in word:
        if role == 'P':
            m += a
            v = max(v, m) + b
        else:
            m += c
    return max(m, v)


class PacketEdgeBoundTests(unittest.TestCase):
    def test_compute_bound_with_every_small_PR_interleaving(self):
        for a, b, c in ((1, 1, 1), (2, 5, 3), (5, 2, 4)):
            for w, r, s in product(range(3), repeat=3):
                if w+s == 0:
                    continue
                obj = Resources(a, b, c, 0, 0, 0, (10,), 0)
                forms, _ = obj.forms(r, r, positive_s=s > 0)
                lower = max(x*(w+s)+y*s+z for x, y, z in forms)
                for word in set(permutations('P'*s + 'R'*r)):
                    self.assertLessEqual(lower, compute_finish(w, word, a, b, c))

    def test_arrangement_bound_below_all_integer_points_and_old_envelope(self):
        obj = Resources(2, 7, 3, 4, 3, 5, (6, 7), 2)
        for n in range(5):
            for r in range(n+1):
                for sl in (0, 1):
                    box = (1, 6-n, sl, 6-n)
                    result = obj.box(n, r, box, 10)
                    left, right = obj.forms(n, r, positive_s=sl > 0)
                    old = (left[0], (obj.b, 0, 0), left[2])
                    old_min = exact_box_minimum(old, right, box)['integer_lower_bound']
                    self.assertGreaterEqual(result['integer_lower_bound'], old_min)
                    for q in range(box[0], box[1]+1):
                        for s in range(sl, q+1):
                            point = sum(max(a*q+b*s+c for a, b, c in fs) for fs in (left, right))
                            self.assertLessEqual(result['integer_lower_bound'], point)

    def test_zero_prefix_count_does_not_charge_fill(self):
        obj = Resources(2, 7, 3, 0, 0, 0, (1,), 0)
        self.assertEqual(obj.box(0, 0, (1, 1, 0, 0))['integer_lower_bound'], 12)

    def test_fractional_vertex_and_degenerate_region(self):
        result = exact_box_minimum(((1, 0, 0), (-1, 0, 1)), ((0, 0, 0),), (0, 1, 0, 0))
        self.assertEqual(Fraction(result['real_minimum']), Fraction(1, 2))
        self.assertEqual(result['integer_lower_bound'], 1)


if __name__ == '__main__':
    unittest.main()
