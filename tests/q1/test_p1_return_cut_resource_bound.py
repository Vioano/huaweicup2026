import itertools
import unittest
from fractions import Fraction

from src.review.p1_return_cut_resource_bound import relaxation


class ResourceRelaxationTests(unittest.TestCase):
    def test_integer_result_matches_independent_cut_enumeration(self):
        for a, b, c in [(1, 1, 1), (2, 7, 3), (5, 2, 4)]:
            for counts in [(0,), (1,), (2, 1), (3, 2, 1)]:
                for whole, extra in [(0, 0), (3, 0), (2, 1), (1, 6)]:
                    answer = relaxation(a, b, c, whole, extra, whole, counts)
                    costs = []
                    for cuts in itertools.product(*(range(n + 1) for n in counts)):
                        costs.append(max(max(n * (a + b + c) - b * x for n, x in zip(counts, cuts)),
                                         max(counts) * b, sum(counts) * whole + extra * sum(cuts)))
                    self.assertEqual(answer['integer_cut_lower_bound'], min(costs))
                    self.assertLessEqual(Fraction(answer['continuous_lower_bound']), min(costs))

    def test_fractional_resource_intersection(self):
        # T=3-x=1+3x gives x=1/2, T=5/2; integer cuts require T=3.
        result = relaxation(1, 1, 1, 2, 2, 1, [1])
        self.assertEqual(result['continuous_lower_bound'], '5/2')
        self.assertEqual(result['integer_cut_lower_bound'], 3)


if __name__ == '__main__':
    unittest.main()
