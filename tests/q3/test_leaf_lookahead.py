"""Structural tests for one-leaf lookahead; no E0 or Step3 invocation."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from src.q3.construct import Index, UnsupportedStructure, derive_multicore_plan
from src.q3.leaf_lookahead import transform

ROOT = Path(__file__).resolve().parents[2]


def _independent_graph():
    # V prefix, then M/VV/M/VV/M/VV. M roots use only external inputs; they have
    # no contracted compute predecessors.
    ops = [
        {'id': 20, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 2},
        {'id': 10, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 3},
        {'id': 21, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 4},
        {'id': 24, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 1},
        {'id': 11, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 3},
        {'id': 22, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 5},
        {'id': 25, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 1},
        {'id': 12, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 3},
        {'id': 23, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 6},
        {'id': 26, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 1},
    ]
    return {'ops': ops, 'tensors': [], 'edges': []}


def _plan(index, core_words):
    mapping = {str(u): i for i, u in enumerate(index.order)}
    by_op = {int(u): sg for u, sg in mapping.items()}
    return {'node_to_subgraph': mapping,
            'core_schedules': [[by_op[u] for u in word] for word in core_words]}


class LeafLookaheadTests(unittest.TestCase):
    def test_one_block_only_and_pipe_order_owner_preserved(self):
        index = Index(_independent_graph())
        original = _plan(index, [[20, 10, 21, 24, 11, 22, 25, 12, 23, 26]])
        transformed, meta = transform(index, original)
        inv = {sg: int(u) for u, sg in transformed['node_to_subgraph'].items()}
        word = [inv[sg] for sg in transformed['core_schedules'][0]]
        self.assertEqual(word, [20, 10, 11, 21, 24, 12, 22, 25, 23, 26])
        before = derive_multicore_plan(index.graph, original)
        after = derive_multicore_plan(index.graph, transformed)
        self.assertEqual(before['core_by_subgraph'], after['core_by_subgraph'])
        for core in range(1):
            def projection(plan, pipe):
                return [sg for sg in plan['core_orders'][core]
                        if index.ops[before['nodes_by_subgraph'][sg][0]]['pipe'] == pipe]
            self.assertEqual(projection(before, 'PIPE_M'), projection(after, 'PIPE_M'))
            self.assertEqual(projection(before, 'PIPE_V'), projection(after, 'PIPE_V'))
        self.assertEqual(meta['v_operations_delayed_by_one_m_by_core'], [4])

    def test_guard_rejects_m_with_compute_predecessor(self):
        graph = _independent_graph()
        # Add a real compute dependency into one M op.
        graph['ops'].append({'id': 30, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 1})
        graph['edges'] = [{'source': 30, 'target': 10}]
        index = Index(graph)
        plan = _plan(index, [[20, 30, 10, 21, 24, 11, 22, 25, 12, 23, 26]])
        with self.assertRaisesRegex(UnsupportedStructure, 'no compute predecessor'):
            transform(index, plan)

    def test_guard_rejects_non_singleton_or_other_pipe(self):
        index = Index(_independent_graph())
        plan = _plan(index, [[20, 10, 21, 24, 11, 22, 25, 12, 23, 26]])
        bad = dict(plan)
        bad['node_to_subgraph'] = dict(plan['node_to_subgraph'])
        bad['node_to_subgraph']['11'] = bad['node_to_subgraph']['10']
        # Make schedules valid for merged subgraph before reaching singleton guard.
        sg_old = plan['node_to_subgraph']['11']
        for core, seq in enumerate(plan['core_schedules']):
            bad['core_schedules'][core] = [x for x in seq if x != sg_old]
        with self.assertRaisesRegex(UnsupportedStructure, 'singleton'):
            transform(index, bad)

        graph = _independent_graph()
        graph['ops'][0]['pipe'] = 'PIPE_MTE2'
        idx = Index(graph)
        pl = _plan(idx, [[20, 10, 21, 24, 11, 22, 25, 12, 23, 26]])
        with self.assertRaisesRegex(UnsupportedStructure, 'PIPE_M/PIPE_V'):
            transform(idx, pl)

    def test_archived_band_plans_on_058_079(self):
        for case in (58, 79):
            graph = json.loads((ROOT / f'data/raw/a/official/data/case_{case:03}.json').read_text())
            index = Index(graph)
            for mode in ('component_id', 'pair_cache_model'):
                with self.subTest(case=case, mode=mode):
                    plan_path = ROOT / f'results/a/q3-nikolastarx/band-mechanism-20260925/{case:03}-k5-{mode}/plan.json'
                    original = json.loads(plan_path.read_text())
                    transformed, meta = transform(index, original)
                    before = derive_multicore_plan(graph, original)
                    after = derive_multicore_plan(graph, transformed)
                    self.assertEqual(set(transformed), {'node_to_subgraph', 'core_schedules'})
                    self.assertEqual(transformed['node_to_subgraph'], original['node_to_subgraph'])
                    self.assertEqual(before['core_by_subgraph'], after['core_by_subgraph'])
                    self.assertEqual(before['num_cores'], 5)
                    for core in range(5):
                        for pipe in ('PIPE_M', 'PIPE_V'):
                            project = lambda view: [sg for sg in view['core_orders'][core]
                                if index.ops[view['nodes_by_subgraph'][sg][0]]['pipe'] == pipe]
                            self.assertEqual(project(before), project(after))
                    self.assertEqual(meta['official_evaluations'], 0)
                    self.assertTrue(meta['plan_guard_validated'])


if __name__ == '__main__':
    unittest.main()
