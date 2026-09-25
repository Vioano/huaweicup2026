"""Pure resource-box comparisons; no Task/model/evaluator calls."""
import unittest

from src.review.p1_packet_edge_bound import Resources
from src.review.p1_packet_seed import choose_return_seed


class PacketSeedTests(unittest.TestCase):
    def check_against_all_s(self, resource):
        B = min(resource.counts)
        answer = choose_return_seed(resource, B)
        if B == 0:
            self.assertIsNone(answer["s"])
            self.assertEqual(answer["path"], ())
            return
        # Independently evaluate the resource inequalities at every integer;
        # do not use the selector's arrangement/minimization implementation.
        k, a, b, c = len(resource.counts), resource.a, resource.b, resource.c
        remain, total = max(resource.counts)-B, sum(resource.counts)-k*B
        def point(s):
            whole = (B-s)*(a+b+c)
            edge = max(whole+s*a, whole+s*b+(a if s else 0),
                       k*((B-s)*resource.d_whole+s*resource.d_prefix))
            tail = max(remain*(a+c)+s*c, remain*b,
                       total*resource.d_whole+k*s*resource.d_return)
            return edge+tail
        scores = {s: point(s) for s in range(B+1)}
        self.assertEqual((answer["resource_lower"], answer["s"]),
                         min((value, s) for s, value in scores.items()))
        self.assertEqual(answer["path"][0], ("normal", (0, 0), (B, answer["s"])))

    def test_zero_positive_plateau_and_b1(self):
        cases = [
            Resources(1, 1, 1, 4, 4, 4, (4, 5), 100),
            Resources(10, 20, 10, 1, 1, 1, (4, 6), 0),
            Resources(3, 3, 3, 2, 2, 2, (3, 3), 10),
            Resources(2, 2, 2, 2, 2, 2, (1, 2), 10),
            Resources(2, 2, 2, 2, 2, 2, (0, 2), 10),
        ]
        for resource in cases:
            with self.subTest(resource=resource):
                self.check_against_all_s(resource)
        self.assertEqual(choose_return_seed(cases[0], 4)["s"], 0)
        self.assertGreater(choose_return_seed(cases[1], 4)["s"], 0)
        self.assertEqual(cases[3].box(0, 0, (1, 1, 0, 0))["frontier_lower_bound"],
                         cases[3].box(0, 0, (1, 1, 1, 1))["frontier_lower_bound"])
        self.assertEqual(choose_return_seed(cases[3], 1)["s"], 0)  # B=1 plateau tie

    def test_varied_unequal_core_counts(self):
        for B in (1, 2, 3, 5):
            for b in (1, 4, 13):
                for extra in (0, 2, 9):
                    resource = Resources(2, b, 3, 1 + extra, 2 + extra,
                                         1 + extra, (B, B + 1, B + 3), 7)
                    self.check_against_all_s(resource)


if __name__ == "__main__":
    unittest.main()
