"""Independent interval-oracle checks for persistent calendar release."""
import random
import unittest
from math import inf

from src.q3.gap_calendar import earliest, empty, release, reserve


def inspect_tree(root):
    """Recompute AVL metadata and return in-order free intervals."""
    def visit(node):
        if node is None:
            return 0, 0, []
        lh, lm, left = visit(node.left)
        rh, rm, right = visit(node.right)
        assert abs(lh - rh) <= 1
        assert node.height == max(lh, rh) + 1
        assert node.maximum == max(node.stop - node.key, lm, rm)
        if left:
            assert left[-1][0] < node.key
        if right:
            assert node.key < right[0][0]
        assert node.stop >= node.key
        return node.height, node.maximum, left + [(node.key, node.stop)] + right

    intervals = visit(root)[2]
    for (_, end), (start, _) in zip(intervals, intervals[1:]):
        assert end <= start
    return intervals


def oracle_earliest(busy, release_time, duration):
    start = release_time
    while any(t < len(busy) and busy[t] for t in range(start, start + duration)):
        start += 1
    return start


class GapCalendarReleaseTests(unittest.TestCase):
    def test_boundary_merges_and_rejects_double_release(self):
        root = reserve(empty(), 5, 10)
        old = inspect_tree(root)
        root = release(root, 8, 3)
        self.assertEqual(earliest(root, 8, 3), 8)
        with self.assertRaises(ValueError):
            release(root, 9, 3)
        root = release(root, 5, 3)
        self.assertEqual(earliest(root, 0, 11), 0)
        root = release(root, 11, 4)
        self.assertEqual(inspect_tree(root), [(0, inf)])
        self.assertEqual(old, [(0, 5), (15, inf)])

        # Old reserve creates zero-length intervals at exact boundaries.
        root = reserve(empty(), 0, 4)
        root = reserve(root, 4, 6)
        self.assertEqual(inspect_tree(release(root, 0, 10)), [(0, inf)])
        with self.assertRaises(ValueError):
            release(empty(), 0, 1)

    def test_invalid_arguments(self):
        for start, duration in [(-1, 1), (0, 0), (0, -1), (True, 1),
                                (0, True), (1.0, 1), (0, 1.0)]:
            with self.subTest(start=start, duration=duration), self.assertRaises(ValueError):
                release(empty(), start, duration)

    def test_random_bitmap_oracle_and_old_roots(self):
        rng = random.Random(20260925)
        horizon = 70
        for _ in range(8):
            root = empty()
            busy = [False] * horizon
            for _ in range(250):
                old_root = root
                old_intervals = inspect_tree(root)
                candidates = [(s, d) for s in range(horizon) for d in range(1, 7)
                              if s + d <= horizon and not any(busy[s:s + d])]
                occupied = [(s, d) for s in range(horizon) for d in range(1, 7)
                            if s + d <= horizon and all(busy[s:s + d])]
                if occupied and (not candidates or rng.randrange(2) == 0):
                    start, duration = rng.choice(occupied)
                    root = release(root, start, duration)
                    busy[start:start + duration] = [False] * duration
                else:
                    start, duration = rng.choice(candidates)
                    root = reserve(root, start, duration)
                    busy[start:start + duration] = [True] * duration
                self.assertEqual(inspect_tree(old_root), old_intervals)
                intervals = inspect_tree(root)
                for t in range(horizon):
                    self.assertEqual(any(a <= t < b for a, b in intervals), not busy[t])
                for _ in range(4):
                    t = rng.randrange(horizon + 1)
                    d = rng.randrange(1, 9)
                    self.assertEqual(earliest(root, t, d), oracle_earliest(busy, t, d))


if __name__ == '__main__':
    unittest.main()
