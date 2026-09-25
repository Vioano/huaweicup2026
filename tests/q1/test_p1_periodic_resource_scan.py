"""Small arithmetic checks; no graph compiler or response model."""
import unittest

from src.review.p1_packet_edge_bound import Resources
from src.review.p1_periodic_resource_scan import periodic_cost, scan


class PeriodicResourceTests(unittest.TestCase):
    def test_two_segments_and_terminal_by_hand(self):
        resource = Resources(2, 3, 2, 1, 1, 1, (3, 4), 5)
        row = periodic_cost(resource, 3, 2, 1)
        # Edge resource maxima 12 and 5; one inter-normal gate 5;
        # terminal max(M=6,V=3,DDR=3) plus its gate 5.
        self.assertEqual(row["resource_lower"], 12 + 5 + 5 + 6 + 5)
        self.assertEqual((row["normal_count"], row["pending"]), (2, 1))

    def test_full_packet_and_empty_terminal(self):
        resource = Resources(2, 3, 2, 1, 1, 1, (3, 3), 5)
        row = periodic_cost(resource, 3, 3, 0)
        self.assertEqual((row["normal_count"], row["pending"], row["terminal_gate"]),
                         (1, 0, 0))
        diagnostic = scan(resource)
        self.assertEqual(diagnostic["candidate_count"], sum(q + 1 for q in range(1, 4)))
        self.assertEqual(len(diagnostic["s0_comparison"]), 3)
        self.assertLessEqual(len(diagnostic["top_five"]), 5)


if __name__ == "__main__":
    unittest.main()
