"""Synthetic adapter checks; no official graph, solver, or evaluator."""
import copy
import unittest

from src.q2_nikolastarx.outside_slack_candidate import rebuild
from src.q2_nikolastarx.receiver_closure_exchange import _rows
from src.q2_nikolastarx.dag_direct import DAGIndex


def fixture():
    graph = {'ops': [
        {'id': u, 'op': 'CONV' if u in (1, 3) else 'RELU',
         'pipe': 'PIPE_M' if u in (1, 3) else 'PIPE_V', 'cycles': 1}
        for u in range(1, 5)], 'tensors': [], 'edges': []}
    baseline = {'node_to_subgraph': {str(u): u - 1 for u in range(1, 5)},
                'core_schedules': [[0, 2], [1, 3]]}
    c02 = {'plan': {'node_to_subgraph': dict(baseline['node_to_subgraph']),
                    'core_schedules': [[0, 1, 2], [3]]},
           'detail': {'region': {'ops': [1, 2], 'exit': 1, 'host': 0},
                      'priority': {'regional_word': [1, 2]}}}
    config = {'capacity': {'L1': 1000, 'UB': 1000}, 'bandwidth': 60,
              'cross_core_copy_delay_cycles': 500}
    starts = {1: 0, 2: 0, 3: 1, 4: 1}
    return graph, baseline, config, c02, starts


class OutsideSlackAdapterTests(unittest.TestCase):
    def test_success_preserves_identity_and_subsequences(self):
        graph, baseline, config, c02, starts = fixture()
        original = copy.deepcopy((graph, baseline, config, c02, starts))
        candidates, meta = rebuild(graph, baseline, config, [c02], starts,
                                   incumbent_makespan=100)
        self.assertEqual(meta['status'], 'candidates', meta)
        self.assertEqual(meta['recover_calls'], 1)
        self.assertEqual(len(candidates), 1)
        result = candidates[0]
        self.assertEqual(set(result['plan']), {'node_to_subgraph', 'core_schedules'})
        self.assertEqual(result['plan']['node_to_subgraph'], baseline['node_to_subgraph'])
        index = DAGIndex(graph)
        before = _rows(graph, baseline, index)
        c02_rows = _rows(graph, c02['plan'], index)
        after = _rows(graph, result['plan'], index)
        self.assertEqual({u: c for c, row in enumerate(after) for u in row},
                         {u: c for c, row in enumerate(c02_rows) for u in row})
        for old, new in zip(before, after):
            self.assertEqual([u for u in old if u not in (1, 2)],
                             [u for u in new if u not in (1, 2)])
        self.assertEqual([u for u in after[0] if u in (1, 2)], [1, 2])
        global_order = result['detail']['priority']['global_priority_order']
        for row in after:
            self.assertEqual([u for u in global_order if u in row], row)
        self.assertEqual(result['detail']['original_c02_priority'],
                         c02['detail']['priority'])
        self.assertTrue(result['detail']['witness_start'])
        self.assertTrue(result['detail']['exterior_reserved_start'])
        self.assertEqual(meta['calls'], {'prepare': 0, 'solver': 0,
                                         'E0': 0, 'E1': 0, 'E2': 0})
        self.assertEqual((graph, baseline, config, c02, starts), original)

    def test_owner_tampering_rejected_before_recovery(self):
        graph, baseline, config, c02, starts = fixture()
        c02['plan']['core_schedules'] = [[0, 1], [2, 3]]
        candidates, meta = rebuild(graph, baseline, config, [c02], starts,
                                   incumbent_makespan=100)
        self.assertEqual(candidates, [])
        self.assertEqual(meta['recover_calls'], 0)
        self.assertIn('owner', meta['rejections'][0]['reason'])

    def test_word_tampering_rejected_before_recovery(self):
        graph, baseline, config, c02, starts = fixture()
        c02['detail']['priority']['regional_word'] = [2, 1]
        candidates, meta = rebuild(graph, baseline, config, [c02], starts,
                                   incumbent_makespan=100)
        self.assertEqual(candidates, [])
        self.assertEqual(meta['recover_calls'], 0)
        self.assertIn('word', meta['rejections'][0]['reason'])

    def test_incomplete_start_rejected(self):
        graph, baseline, config, c02, starts = fixture()
        del starts[4]
        candidates, meta = rebuild(graph, baseline, config, [c02], starts,
                                   incumbent_makespan=100)
        self.assertEqual(candidates, [])
        self.assertEqual(meta['status'], 'unsupported')
        self.assertEqual(meta['recover_calls'], 0)

    def test_failed_recovery_keeps_reason_and_does_not_replace_candidate(self):
        graph, baseline, config, c02, starts = fixture()
        candidates, meta = rebuild(graph, baseline, config, [c02], starts,
                                   incumbent_makespan=1)
        self.assertEqual(candidates, [])
        self.assertEqual(meta['recover_calls'], 1)
        self.assertIn('exterior_reference_not_feasible',
                      meta['rejections'][0]['reason'])
        self.assertIn('original_c02_plan_sha256', meta['rejections'][0])


if __name__ == '__main__':
    unittest.main()
