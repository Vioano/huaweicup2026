"""C04 adapter structure and static-guard tests; no evaluator calls."""
from copy import deepcopy
import unittest

from src.q2_nikolastarx.port_packet_adapter import (
    UnsupportedPortPacket, build, to_ir,
)


CONFIG = {'capacity': {'L1': 100, 'UB': 100}, 'bandwidth': 60,
          'cross_core_copy_delay_cycles': 500}


def fixture():
    return {
        'ops': [
            {'id': 3, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 1},
            {'id': 7, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2},
            {'id': 11, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 3},
            {'id': 90, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1},
        ],
        'tensors': [
            {'id': 99, 'size': 8, 'pos': 'DDR'},
            {'id': 100, 'size': 8, 'pos': 'L1'},
            {'id': 101, 'size': 5, 'pos': 'UB'},
            {'id': 102, 'size': 5, 'pos': 'DDR'},
        ],
        'edges': [
            {'source': 99, 'target': 3}, {'source': 3, 'target': 100},
            {'source': 100, 'target': 7}, {'source': 7, 'target': 101},
            {'source': 101, 'target': 11}, {'source': 101, 'target': 90},
            {'source': 90, 'target': 102},
        ],
    }


class PortPacketAdapterTests(unittest.TestCase):
    def test_independent_copy_input_and_exact_original_singletons(self):
        graph = fixture()
        ir = to_ir(graph)
        self.assertEqual(set(ir.pipe), {7, 11})
        self.assertEqual([(t.id, t.producer, t.required_output)
                          for t in ir.tensors], [(100, None, False), (101, 7, True)])
        plan, detail = build(graph, 2, CONFIG, width=2)
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})
        self.assertEqual(plan['node_to_subgraph'], {'7': 7, '11': 11})
        self.assertEqual(sorted(sum(plan['core_schedules'], [])), [7, 11])
        self.assertTrue(detail['zero_spill']['zero_spill_certificate'])
        self.assertEqual(detail['physical_pre_step2_copy_bytes'],
                         detail['constructor']['pre_step2_copy_bytes'])
        self.assertEqual(graph, fixture())

    def test_alias_multi_producer_and_direct_edge_abstain(self):
        graph = fixture()
        graph['tensors'][1]['logical_tid'] = 100
        with self.assertRaisesRegex(UnsupportedPortPacket, 'alias'):
            to_ir(graph)
        graph = fixture()
        graph['ops'].append({'id': 5, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 1})
        graph['edges'].append({'source': 5, 'target': 100})
        with self.assertRaisesRegex(UnsupportedPortPacket, 'multiple original producers'):
            to_ir(graph)
        graph = fixture()
        graph['edges'].append({'source': 7, 'target': 11, 'data_size': 5})
        with self.assertRaisesRegex(UnsupportedPortPacket, 'direct eligible'):
            to_ir(graph)

    def test_copy_path_and_nonindependent_copy_input_abstain(self):
        graph = fixture()
        # A COPY_OUT-to-COPY_IN path adds a dependency absent from tensor IR.
        graph['edges'].append({'source': 90, 'target': 3})
        with self.assertRaises(UnsupportedPortPacket):
            to_ir(graph)
        graph = fixture()
        graph['edges'].remove({'source': 99, 'target': 3})
        graph['edges'].append({'source': 101, 'target': 3})
        with self.assertRaises(UnsupportedPortPacket):
            to_ir(graph)

    def test_no_numeric_defaults_or_low_capacity_claim(self):
        graph = fixture()
        for config in ({'capacity': {'L1': 100, 'UB': 100}, 'bandwidth': 60},
                       {'capacity': {'L1': 100, 'UB': 100}, 'bandwidth': True,
                        'cross_core_copy_delay_cycles': 500},
                       {'capacity': {'L1': 100, 'UB': 100}, 'bandwidth': 60,
                        'cross_core_copy_delay_cycles': -1}):
            with self.assertRaises(UnsupportedPortPacket):
                build(graph, 2, config)
        small = deepcopy(CONFIG)
        small['capacity']['L1'] = 1
        with self.assertRaises(UnsupportedPortPacket):
            build(graph, 2, small)


if __name__ == '__main__':
    unittest.main()
