"""Small exhaustive arithmetic reference; no graph or evaluator is invoked."""
from itertools import product
import unittest

from src.review.p1_two_task_resource_bound import solve


def brute(counts, a, b, c, whole, delta, gate):
    width = a + b + c
    values = []
    for cuts in product(*(range(n + 1) for n in counts)):
        compute = max((n * width if x == 0 else n * width - a * (x - 1) + gate
                       for n, x in zip(counts, cuts)), default=0)
        values.append(max(compute, sum(counts) * whole + delta * sum(cuts)))
    return min(values)


class TwoTaskResourceBoundTests(unittest.TestCase):
    def test_exhaustive_small_integer_optimum(self):
        for counts in product(range(4), repeat=3):
            for a, b, c, whole, delta, gate in product(
                    (1, 2), (2, 3), (1, 2), (0, 3), (0, 2), (0, 4)):
                if b < a:
                    continue
                result = solve(counts, a=a, b=b, c=c,
                               d_prefix=whole + delta, d_return=0,
                               d_whole=whole, gate=gate)
                self.assertEqual(result["objective"],
                                 brute(counts, a, b, c, whole, delta, gate))
                self.assertEqual(result["infeasible_T_minus_1"], result["objective"] - 1)

    def test_empty_cores_and_discontinuous_gate(self):
        self.assertEqual(solve([0, 0], a=1, b=1, c=1,
                               d_prefix=0, d_return=0, d_whole=0)["cuts"], [0, 0])
        result = solve([1, 0], a=1, b=1, c=1, d_prefix=0,
                       d_return=0, d_whole=0, gate=4)
        self.assertEqual((result["objective"], result["cuts"]), (3, [0, 0]))

    def test_domain_rejection(self):
        with self.assertRaises(ValueError):
            solve([1], a=2, b=1, c=1, d_prefix=0, d_return=0, d_whole=0)
        with self.assertRaises(ValueError):
            solve([1], a=1, b=1, c=1, d_prefix=0, d_return=0, d_whole=1)


if __name__ == "__main__": unittest.main()
