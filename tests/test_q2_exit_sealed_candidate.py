"""Small synthetic C02 adapter checks; no native/E0/real case."""
import copy
import unittest

from src.q2_nikolastarx.exit_sealed_candidate import propose
from src.q2_nikolastarx.direct import derive_multicore_plan


def fixture():
    ops = [{'id': u, 'op': 'CONV' if u in (1, 3, 5) else 'RELU',
            'pipe': 'PIPE_M' if u in (1, 3, 5) else 'PIPE_V', 'cycles': 1}
           for u in range(1, 6)]
    tensors = [{'id': tid, 'size': 4, 'pos': 'UB'} for tid in (10, 11, 12, 13)]
    edges = []
    for source, tid, target in ((1, 10, 2), (2, 11, 4),
                                (3, 12, 4), (4, 13, 5)):
        edges.extend(({'source': source, 'target': tid}, {'source': tid, 'target': target}))
    graph = {'ops': ops, 'tensors': tensors, 'edges': edges}
    plan = {'node_to_subgraph': {str(u): u - 1 for u in range(1, 6)},
            'core_schedules': [[0, 1], [2], [3, 4]]}
    config = {'capacity': {'L1': 1000, 'UB': 1000}, 'bandwidth': 60,
              'cross_core_copy_delay_cycles': 500}
    link = {'tensor_id': 11, 'source_core': 0, 'target_core': 2,
            'exposed_delay': 500}
    finish = {1: 1, 2: 2, 3: 1, 4: 3, 5: 4}
    return graph, plan, config, link, finish


class ExitSealedAdapterTests(unittest.TestCase):
    def test_full_join_and_singleton_coverage(self):
        graph, plan, config, link, finish = fixture()
        original = copy.deepcopy((graph, plan, config, link, finish))
        candidates, meta = propose(graph, plan, config, [link], finish,
                                   incumbent_makespan=10000)
        self.assertEqual(meta['status'], 'candidates', meta)
        self.assertEqual(len(candidates), 1)
        selected = candidates[0]
        self.assertEqual(set(selected['detail']['region']['ops']), {1, 2, 3, 4})
        self.assertEqual(selected['detail']['region']['exit'], 4)
        view = derive_multicore_plan(graph, selected['plan'])
        self.assertEqual(set(view['mapping']), {1, 2, 3, 4, 5})
        self.assertEqual(selected['plan']['node_to_subgraph'], plan['node_to_subgraph'])
        self.assertEqual(set(selected['plan']), {'node_to_subgraph', 'core_schedules'})
        self.assertEqual((graph, plan, config, link, finish), original)

    def test_hidden_consumer_uses_full_tensor_view(self):
        graph, plan, config, _, finish = fixture()
        graph['ops'].append({'id': 6, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 1})
        graph['edges'].append({'source': 10, 'target': 6})
        plan['node_to_subgraph']['6'] = 5
        plan['core_schedules'][0].append(5)
        finish[6] = 3
        # Witness names only one destination, but the original tensor also
        # feeds op 6. Its two arms do not have a real common postdominator.
        link = {'tensor_id': 10, 'source_core': 0, 'target_core': 0,
                'exposed_delay': 500}
        # Make op 6 remote so the witness is cross-core while retaining two arms.
        plan['core_schedules'][0].remove(5)
        plan['core_schedules'][1].append(5)
        link['target_core'] = 1
        candidates, meta = propose(graph, plan, config, [link], finish,
                                   incumbent_makespan=10000)
        self.assertEqual(candidates, [])
        self.assertEqual(meta['kernel_diagnostics']['rejections'][0]['reason'],
                         'no_real_common_postdominator')

    def test_alias_refused(self):
        graph, plan, config, link, finish = fixture()
        graph['tensors'][0]['logical_tid'] = 10
        candidates, meta = propose(graph, plan, config, [link], finish,
                                   incumbent_makespan=10000)
        self.assertEqual(candidates, [])
        self.assertEqual(meta['status'], 'unsupported')
        self.assertIn('logical_tensor_alias', str(meta['rejections']))

    def test_mandatory_output_escape_blocks_branch(self):
        graph, plan, config, link, finish = fixture()
        # The producer on the other branch now has an explicit mandatory OUT.
        graph['ops'].append({'id': 6, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1})
        graph['edges'].append({'source': 12, 'target': 6})
        candidates, meta = propose(graph, plan, config, [link], finish,
                                   incumbent_makespan=10000)
        self.assertTrue(candidates, meta)  # can still move the nonescaping arm
        self.assertNotIn(3, candidates[0]['detail']['region']['ops'])


if __name__ == '__main__':
    unittest.main()
