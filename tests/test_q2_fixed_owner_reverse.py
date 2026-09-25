"""Synthetic-only checks for fixed-owner reverse retiming."""
import copy
import unittest

from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan, topo
from src.q2_nikolastarx.fixed_owner_reverse import retime
from tests.q2_nikolastarx.test_gap_candidate import CONFIG, diamond


def plan(rows):
    return {'node_to_subgraph': {str(u): u for row in rows for u in row},
            'core_schedules': rows}


def owners(candidate):
    return {u: core for core, row in enumerate(candidate['core_schedules'])
            for u in row}


def check_data_and_core_order(graph, candidate):
    index = DAGIndex(graph)
    reverse = {sg: int(u) for u, sg in candidate['node_to_subgraph'].items()}
    combined = {u: set(index.succ[u]) for u in index.ops}
    for row in candidate['core_schedules']:
        for a, b in zip(row, row[1:]):
            combined[reverse[a]].add(reverse[b])
    assert len(topo(index.ops, combined)) == len(index.ops)
    derive_multicore_plan(graph, candidate)


class FixedOwnerReverseTests(unittest.TestCase):
    def test_owner_partition_and_original_precedence_preserved(self):
        graph = diamond()
        incumbent = plan([[1, 4, 5], [2, 3]])
        original_graph, original_plan = copy.deepcopy(graph), copy.deepcopy(incumbent)
        revised, detail = retime(graph, incumbent, CONFIG)
        self.assertEqual(revised['node_to_subgraph'], incumbent['node_to_subgraph'])
        self.assertEqual(owners(revised), owners(incumbent))
        self.assertEqual(graph, original_graph)
        self.assertEqual(incumbent, original_plan)
        self.assertEqual(detail['online_E0_calls'], 0)
        check_data_and_core_order(graph, revised)

    def test_sink_first_changes_order_on_asymmetric_fork_join(self):
        graph = diamond()
        incumbent = plan([[1, 2, 3, 4, 5]])
        revised, _ = retime(graph, incumbent, CONFIG)
        self.assertNotEqual(revised['core_schedules'], incumbent['core_schedules'])
        check_data_and_core_order(graph, revised)

    def test_split_chain_at_owner_boundary(self):
        graph = diamond()
        graph['ops'].append({'id': 6, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 1})
        graph['edges'] = [edge for edge in graph['edges']
                          if (edge['source'], edge['target']) != (3, 4)]
        graph['edges'] += [{'source': 3, 'target': 6, 'data_size': 8},
                           {'source': 6, 'target': 4, 'data_size': 8}]
        incumbent = plan([[1, 4, 5], [2, 3, 6]])
        revised, detail = retime(graph, incumbent, CONFIG)
        self.assertEqual(owners(revised), owners(incumbent))
        self.assertGreater(detail['owner_split_count'], 0)
        # Original 6 -> 4 is a split maximal-chain edge across cores. In the
        # virtual reverse DAG, 4 must release 6 after the modeled COPY lag.
        lag = CONFIG['cross_core_copy_delay_cycles'] + 2 * 1
        self.assertEqual(detail['modeled_split_cross_core_lags']['6->4'], lag)
        starts = detail['modeled_reverse_op_starts']
        self.assertGreaterEqual(starts['6'], starts['4'] + 5 + lag)
        check_data_and_core_order(graph, revised)

    def test_integer_mapping_keys_remain_supported(self):
        incumbent = plan([[1, 2, 3, 4, 5]])
        incumbent['node_to_subgraph'] = {int(u): sg for u, sg in incumbent['node_to_subgraph'].items()}
        revised, _ = retime(diamond(), incumbent, CONFIG)
        self.assertEqual(revised['node_to_subgraph'], incumbent['node_to_subgraph'])
        check_data_and_core_order(diamond(), revised)

    def test_deterministic_across_input_order(self):
        graph = diamond()
        shuffled = copy.deepcopy(graph)
        for values in shuffled.values():
            values.reverse()
        incumbent = plan([[1, 2, 3, 4, 5]])
        self.assertEqual(retime(graph, incumbent, CONFIG), retime(shuffled, incumbent, CONFIG))

    def test_reject_non_singleton_and_physical_multi_producer(self):
        graph = diamond()
        merged = {'node_to_subgraph': {'1': 0, '2': 1, '3': 2, '4': 3, '5': 3},
                  'core_schedules': [[0, 1, 2, 3]]}
        with self.assertRaises(UnsupportedStructure):
            retime(graph, merged, CONFIG)
        graph['tensors'] = [{'id': 100, 'pos': 'UB', 'size': 8}]
        graph['edges'] += [{'source': 1, 'target': 100}, {'source': 2, 'target': 100}]
        with self.assertRaises(UnsupportedStructure):
            retime(graph, plan([[1, 2, 3, 4, 5]]), CONFIG)

    def test_reject_invalid_input_total_order(self):
        with self.assertRaisesRegex(UnsupportedStructure, 'cycle'):
            # Each local dependency is in order, but 4 -> 2 -> 3 -> 4
            # crosses core boundaries and forms a global cycle.
            retime(diamond(), plan([[1, 4, 2], [3, 5]]), CONFIG)


if __name__ == '__main__':
    unittest.main()
