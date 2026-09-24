"""Chain packet structure and placement tests; no scheduler or evaluator calls."""
import copy
import unittest

from src.q2_nikolastarx.chain_packets import construct, packetize
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import derive_multicore_plan


def op(ident, pipe='PIPE_V', cycles=10):
    return {'id': ident, 'op': 'ADD', 'pipe': pipe, 'cycles': cycles}


def edge(source, target):
    return {'source': source, 'target': target}


def fork_join():
    return {'ops': [op(i) for i in range(1, 8)], 'tensors': [],
            'edges': [edge(a, b) for a, b in
                      ((1, 2), (2, 3), (3, 4), (3, 5), (4, 6), (5, 6), (6, 7))]}


def build(graph, cores=2, delay=0):
    return construct(graph, cores, bandwidth=60, cross_core_delay=delay)


class ChainPacketTests(unittest.TestCase):
    def test_partition_cover_contraction_acyclic_and_fork_join_boundaries(self):
        graph = fork_join()
        index = DAGIndex(graph)
        packets, owner, preds, succs = packetize(index)
        self.assertEqual(packets, [(1, 2, 3), (4,), (5,), (6, 7)])
        self.assertEqual(set(owner), set(index.ops))
        self.assertEqual(sum(map(len, packets)), len(index.ops))
        self.assertEqual(succs, [{1, 2}, {3}, {3}, set()])
        self.assertEqual(preds, [set(), {0}, {0}, {1, 2}])
        for source, targets in enumerate(succs):
            self.assertTrue(all(source < target for target in targets))
        plan, detail = build(graph)
        view = derive_multicore_plan(graph, plan)
        self.assertEqual(set(view['mapping']), set(index.ops))
        self.assertEqual(detail['packet_count'], 4)
        self.assertEqual(detail['max_packet_length'], 3)
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})

    def test_mixed_pipe_chain_preserves_actual_operation_work(self):
        graph = {'ops': [op(1, 'PIPE_M', 3), op(2, 'PIPE_V', 5),
                         op(3, 'PIPE_M', 7)], 'tensors': [],
                 'edges': [edge(1, 2), edge(2, 3)]}
        plan, detail = build(graph, 2)
        self.assertEqual(len(set(plan['node_to_subgraph'].values())), 3)
        sequence = [next(u for u, sg in plan['node_to_subgraph'].items() if sg == item)
                    for row in plan['core_schedules'] for item in row]
        self.assertEqual(sequence, ['1', '2', '3'])
        self.assertEqual(sum(bool(row) for row in plan['core_schedules']), 1)
        self.assertEqual(detail['packet_count'], 1)
        work = detail['compute_work_by_core_pipe']
        self.assertEqual(sum(row['PIPE_M'] for row in work), 10)
        self.assertEqual(sum(row['PIPE_V'] for row in work), 5)
        derive_multicore_plan(graph, plan)

    def test_one_core_packet_construction(self):
        graph = fork_join()
        plan, detail = build(graph, 1)
        self.assertEqual(len(plan['core_schedules']), 1)
        self.assertEqual(len(plan['core_schedules'][0]), len(graph['ops']))
        self.assertEqual(detail['packet_count'], 4)
        derive_multicore_plan(graph, plan)

    def test_shared_tensor_copy_deduplicates_consumers_on_one_target_core(self):
        consumers = range(2, 6)
        graph = {'ops': [op(1, cycles=1)] + [op(u, 'PIPE_M', 1000) for u in consumers],
                 'tensors': [{'id': 101, 'size': 60, 'pos': 'L1'}],
                 'edges': [edge(1, 101)] + [edge(101, u) for u in consumers]}
        plan, detail = build(graph)
        view = derive_multicore_plan(graph, plan)
        cores = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
        source = cores[1]
        target_consumers = [u for u in consumers if cores[u] != source]
        self.assertGreaterEqual(len(target_consumers), 2)
        self.assertEqual(len({cores[u] for u in target_consumers}), 1)
        self.assertEqual(detail['predicted_cross_core_pairs'], 1)
        self.assertEqual(detail['predicted_ddr_bytes_without_spill']['cross_core_bytes'], 120)

    def test_singletons_and_input_order_invariance(self):
        graph = {'ops': [op(1), op(2), op(3)], 'tensors': [],
                 'edges': [edge(1, 2), edge(1, 3)]}
        self.assertTrue(all(len(p) == 1 for p in packetize(DAGIndex(graph))[0]))
        original = build(graph)
        shuffled = copy.deepcopy(graph)
        for key in ('ops', 'tensors', 'edges'):
            shuffled[key].reverse()
        self.assertEqual(build(shuffled), original)
        self.assertEqual(original[1]['packet_count'], 3)


if __name__ == '__main__':
    unittest.main()
