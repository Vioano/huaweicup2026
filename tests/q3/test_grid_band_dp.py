"""Bounded checks for the archived R4 Cartesian band-DP proposal.

No official evaluator is called. Raw cases exercise only recognition, plan
construction, and the existing static legal-plan derivation guard.
"""
from __future__ import annotations

from itertools import accumulate
import json
from pathlib import Path
import unittest

from src.q3.construct import Index, derive_multicore_plan
from src.q3.forest_memory_order import construct as memory_order
from src.q3.forest_reuse_grid import recognize
from src.q3.grid_band_dp import (
    _one_axis, construct_grid, coverage, quotas, support_hall_checks,
    verify_partition,
)
from src.q3.forest_band_dp import construct

ROOT = Path(__file__).resolve().parents[2]


def _compositions(total):
    if total == 0:
        yield []
    else:
        for first in range(1, total + 1):
            for rest in _compositions(total - first):
                yield [first, *rest]


def _band_word(a, b, k, bands, first_direction):
    m, n = len(a), len(b)
    word, x, direction = [], 0, first_direction
    for h in bands:
        columns = range(n) if direction == 0 else range(n - 1, -1, -1)
        word.extend((i, j) for j in columns for i in range(x, x + h))
        x += h
        direction = 1 - direction
    ends = [0, *accumulate(quotas(m, n, k))]
    return [word[ends[c]:ends[c + 1]] for c in range(k)]


class GridBandDPTests(unittest.TestCase):
    def test_dp_matches_exhaustive_band_compositions(self):
        a, b, k = [2, 5, 3], [4, 1, 3], 2
        for direction in (0, 1):
            expected = min(
                sum(rec['a_bytes'] + rec['b_bytes']
                    for rec in coverage(_band_word(a, b, k, bands, direction), a, b))
                for bands in _compositions(len(a))
            )
            actual = _one_axis(a, b, k, direction)['coverage_bytes']
            self.assertEqual(actual, expected)

    def test_partition_and_hall_certificate(self):
        sol = construct_grid([3, 5, 2], [4, 1, 6], 3)
        verify_partition(sol['parts'], 3, 3, 3)
        checks = support_hall_checks(sol['parts'], 3, 3)
        self.assertEqual(len(checks), 7)
        self.assertTrue(all(x['neighbor_cells'] >= x['demand'] for x in checks))

    def test_weighted_coordinate_certificates(self):
        cases = [
            (17, 15, 270336, 135168, 15003648, [51] * 5),
            (18, 16, 202752, 135168, 13246464, [58, 58, 58, 57, 57]),
        ]
        for m, n, a, b, expected_d, expected_q in cases:
            with self.subTest(m=m, n=n):
                sol = construct_grid([a] * m, [b] * n, 5)
                verify_partition(sol['parts'], m, n, 5)
                self.assertEqual(sol['coverage_bytes'], expected_d)
                self.assertEqual([len(p) for p in sol['parts']], expected_q)

    def test_real_case_construct_guards_both_tree_orders(self):
        expected_stats = {
            58: (15003648, [51, 51, 51, 51, 51]),
            79: (13246464, [58, 58, 58, 57, 57]),
        }
        for case in (58, 79):
            graph = json.loads((ROOT / f'data/raw/a/official/data/case_{case:03}.json').read_text())
            index = Index(graph)
            model = recognize(index)
            for mode in ('component_id', 'pair_cache_model'):
                with self.subTest(case=case, mode=mode):
                    plan, metadata = construct(index, 5, order_mode=mode)
                    derived = derive_multicore_plan(graph, plan)
                    self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})
                    self.assertEqual(plan['node_to_subgraph'],
                                     {str(u): i for i, u in enumerate(index.order)})
                    self.assertEqual(len(plan['core_schedules']), 5)
                    flat = [sg for schedule in plan['core_schedules'] for sg in schedule]
                    self.assertEqual(sorted(flat), list(range(len(index.ops))))
                    self.assertEqual(len(flat), len(set(flat)))
                    # Every component remains wholly on one core and retains its
                    # original-tree DFS postorder, irrespective of inter-tree order.
                    sg_to_op = {sg: int(op) for op, sg in plan['node_to_subgraph'].items()}
                    owner = {sg: core for core, seq in enumerate(plan['core_schedules']) for sg in seq}
                    tree_meta = {x['min_op_id']: x['dfs_postorder']
                                 for x in memory_order(index, 5)[1]['predicted_frontier']}
                    for component in index.components:
                        expected = tree_meta[min(component)]
                        owners = {owner[plan['node_to_subgraph'][str(u)]] for u in component}
                        self.assertEqual(len(owners), 1)
                        scheduled = [sg_to_op[sg] for seq in plan['core_schedules'] for sg in seq
                                     if sg_to_op[sg] in set(component)]
                        self.assertEqual(scheduled, expected)
                    self.assertEqual(metadata['component_counts'],
                                     [len(x) for x in metadata['components_by_core']])
                    self.assertEqual(metadata['coverage_bytes'], expected_stats[case][0])
                    self.assertEqual(metadata['component_counts'], expected_stats[case][1])
                    self.assertEqual(metadata['official_evaluations'], 0)
                    self.assertEqual(len(model['cells']), len(index.components))
                    if mode == 'pair_cache_model':
                        self.assertIsNotNone(metadata['pair_cache_model_input_bytes'])


if __name__ == '__main__':
    unittest.main()
