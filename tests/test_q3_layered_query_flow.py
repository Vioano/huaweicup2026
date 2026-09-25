"""Small synthetic checks for the guarded R9 port; no official graph runs."""
import itertools
from types import SimpleNamespace
import unittest

from src.q3.layered_query_flow import (
    GuardError, RawIndex, construct_layered, decompose, partition_tracks,
)


class LayeredQueryFlowTests(unittest.TestCase):
    def test_invalid_graph_is_typed_rejection(self):
        graph = {'ops': [{'id': 1, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 1}],
                 'tensors': [], 'edges': [{'source': 1, 'target': 999}]}
        with self.assertRaisesRegex(GuardError, 'invalid original graph'):
            RawIndex.build(graph)

    def test_public_interface_rejects_invalid_capacity(self):
        with self.assertRaisesRegex(GuardError, 'capacity'):
            construct_layered({}, 2, capacity={'L1': 1}, cross_delay_cycles=0)

    def test_subset_dp_matches_exhaustive_two_core_proxy(self):
        pairs = [(9, 1), (3, 7), (4, 4), (1, 8)]
        ops = {}
        private = {}
        for track, (m, v) in enumerate(pairs):
            ops[2*track] = {'pipe': 'PIPE_M', 'cycles': m}
            ops[2*track+1] = {'pipe': 'PIPE_V', 'cycles': v}
            private[2*track] = private[2*track+1] = track
        index = SimpleNamespace(ops=ops, duration=lambda u: ops[u]['cycles'])
        groups, info = partition_tracks(index, private, len(pairs), 2)
        measured = []
        for group in groups:
            measured.append(tuple(sum(pairs[i][axis] for i in group) for axis in (0, 1)))
        got = (max(max(pair) for pair in measured),
               sum(m*m+v*v for m, v in measured))
        all_scores = []
        for mask in range(1, (1 << len(pairs))-1):
            if not mask & 1:
                continue
            a = [i for i in range(len(pairs)) if mask & (1 << i)]
            b = [i for i in range(len(pairs)) if not mask & (1 << i)]
            ab = [tuple(sum(pairs[i][axis] for i in group) for axis in (0, 1))
                  for group in (a, b)]
            all_scores.append((max(max(pair) for pair in ab),
                               sum(m*m+v*v for m, v in ab)))
        self.assertEqual(got, min(all_scores))
        self.assertEqual(info['bottleneck_private_pipe_work'], got[0])

    def test_subset_dp_rejects_too_many_cores(self):
        ops = {0: {'pipe': 'PIPE_M', 'cycles': 1}}
        index = SimpleNamespace(ops=ops, duration=lambda u: 1)
        with self.assertRaisesRegex(GuardError, 'bounded subset DP'):
            partition_tracks(index, {0: 0}, 1, 2)

    def test_same_depth_dynamic_join_rejected(self):
        index = SimpleNamespace(
            order=[0, 1, 2], ops={u: {'pipe': 'PIPE_M', 'cycles': 1} for u in range(3)},
            pred={0: set(), 1: set(), 2: {0, 1}},
            succ={0: {2}, 1: {2}, 2: set()},
        )
        with self.assertRaisesRegex(GuardError, 'two keys of one depth'):
            decompose(index, {0: ('P', 0, 10), 1: ('P', 0, 20)}, set())


if __name__ == '__main__':
    unittest.main()
