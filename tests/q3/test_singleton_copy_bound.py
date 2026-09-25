"""Small mathematical relaxation checks; no official Task or simulation."""
import unittest
from functools import partial

from src.q3.pipe_bound import UnsupportedBound
from src.q3.singleton_copy_bound import analyze as analyze_with_settings
from tests.q3.test_pipe_bound import graph, plan

analyze = partial(analyze_with_settings, ddr_bandwidth=60, cache_bandwidth=250,
                  cross_core_delay_cycles=500)


class SingletonCopyBoundTests(unittest.TestCase):
    def test_private_external_input_is_cold(self):
        g = graph([(1, "PIPE_M", 10)], [(100, 1)],
                  [{"id": 100, "pos": "L1", "size": 600}])
        b = analyze(g, plan([[1]]))
        self.assertEqual(b["lower_bound_cycles"], 20)
        self.assertEqual(b["proved_cold_first_input_count"], 1)

    def test_shared_external_input_may_hit(self):
        g = graph([(1, "PIPE_M", 10), (2, "PIPE_M", 10)], [(100, 1), (100, 2)],
                  [{"id": 100, "pos": "L1", "size": 600}])
        b = analyze(g, plan([[1], [2]]))
        self.assertEqual(b["lower_bound_cycles"], 13)
        self.assertEqual(b["proved_cold_first_input_count"], 0)

    def test_later_input_bucket_cannot_bypass_activation(self):
        g = graph([(1, "PIPE_M", 10), (2, "PIPE_M", 1), (3, "PIPE_M", 1)],
                  [(1, 100), (100, 2), (2, 3), (101, 3)],
                  [{"id": 100, "pos": "L1", "size": 250},
                   {"id": 101, "pos": "L1", "size": 600}])
        b = analyze(g, plan([[1], [2, 3]]))
        self.assertEqual(b["compute_only_lower_bound_cycles"], 512)
        self.assertEqual(b["lower_bound_cycles"], 522)

    def test_same_bucket_does_not_charge_input_after_activation_release(self):
        g = graph([(1, "PIPE_M", 10), (2, "PIPE_M", 1)],
                  [(1, 100), (100, 2), (101, 2)],
                  [{"id": 100, "pos": "L1", "size": 250},
                   {"id": 101, "pos": "L1", "size": 600}])
        # They may run in either FIFO order. A relaxation must permit input
        # preloading before the activation; sum after latest release is unsafe.
        self.assertEqual(analyze(g, plan([[1], [2]]))["lower_bound_cycles"], 512)

    def test_unproved_alias_and_direct_cross_edge_rejected(self):
        g = graph([(1, "PIPE_M", 1)], [(100, 1)],
                  [{"id": 100, "pos": "L1", "size": 600, "logical_tid": 200}])
        with self.assertRaisesRegex(UnsupportedBound, "alias"):
            analyze(g, plan([[1]]))
        # An alias on a DIFFERENT tensor can prefill this input's key. The
        # guard must inspect the complete original tensor set, not just T.
        g = graph([(1, "PIPE_M", 1), (2, "PIPE_M", 1)], [(100, 1), (101, 2)],
                  [{"id": 100, "pos": "L1", "size": 600},
                   {"id": 101, "pos": "L1", "size": 600, "logical_tid": 100}])
        with self.assertRaisesRegex(UnsupportedBound, "alias"):
            analyze(g, plan([[1], [2]]))
        g = graph([(1, "PIPE_M", 1), (2, "PIPE_M", 1)], [(1, 2)])
        with self.assertRaisesRegex(UnsupportedBound, "direct op"):
            analyze(g, plan([[1], [2]]))


if __name__ == "__main__":
    unittest.main()
