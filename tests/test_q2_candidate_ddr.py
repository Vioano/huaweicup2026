"""Compare the static counter with frozen P2 COPY construction, without scheduling."""
import unittest
from unittest.mock import patch

from src.q2_nikolastarx.candidate_ddr import UnknownMandatoryDDR, mandatory_copy_work
from src.q2_nikolastarx import direct  # installs frozen code path

import multicore_cut_evaluate_problem_2 as official
from stub_multicore_cut_and_schedule import MulticoreCutError


def op(ident, kind='ADD'):
    return {'id': ident, 'op': kind, 'pipe': 'PIPE_V', 'cycles': 0}


def tensor(ident, size):
    return {'id': ident, 'size': size, 'pos': 'UB'}


def edge(source, target, **extra):
    return {'source': source, 'target': target, **extra}


def plan(core_rows):
    return {'node_to_subgraph': {str(node): node for row in core_rows for node in row},
            'core_schedules': core_rows}


def built_copy_totals(graph, candidate, bandwidth=60):
    """Run only frozen COPY insertion; stub every scheduling/spilling stage."""
    with (patch.object(official, 'step1_schedule', side_effect=lambda g: [o['id'] for o in g['ops']]),
          patch.object(official, '_prioritize_task_seq', side_effect=lambda g, seq, *_: seq),
          patch.object(official, 'step2_spill_insertion', return_value={
              'new_ops': [], 'new_tensors': [], 'new_edges': [],
              'spill_records': [], 'seq_ext': []}),
          patch.object(official, '_build_extended_graph', side_effect=lambda g, _: g),
          patch.object(official, 'prepare_step3_execution',
                       side_effect=lambda g, **_: {'graph': g})):
        tasks, _, _, _, _ = official._build_scene_b_tasks(
            graph, candidate, bandwidth, {'L1': 10**9, 'UB': 10**9})
    totals = {'copy_count': 0, 'transfer_bytes': 0, 'service_work': 0}
    for task in tasks.values():
        local = task['graph']
        sizes = {t['id']: t['size'] for t in local['tensors']}
        for item in local['ops']:
            if item['op'] not in ('COPY_IN', 'COPY_OUT'):
                continue
            endpoints = [e['target'] if item['op'] == 'COPY_IN' else e['source']
                         for e in local['edges']
                         if (e['source'] == item['id'] if item['op'] == 'COPY_IN'
                             else e['target'] == item['id'])]
            size = sum(sizes[t] for t in endpoints if t in sizes)
            totals['copy_count'] += 1
            totals['transfer_bytes'] += size
            totals['service_work'] += max(1, (size + bandwidth - 1) // bandwidth)
    return totals


class MandatoryCopyTests(unittest.TestCase):
    def check(self, graph, candidate, expected):
        result = mandatory_copy_work(graph, candidate, 60)
        self.assertEqual({k: result[k] for k in ('copy_count', 'transfer_bytes', 'service_work')},
                         built_copy_totals(graph, candidate))
        self.assertEqual({k: result['categories'][k]['copy_count'] for k in expected}, expected)

    def test_shared_boundary_input_one_per_consuming_core(self):
        graph = {'ops': [op(1), op(2), op(3)], 'tensors': [tensor(10, 61)],
                 'edges': [edge(10, 1), edge(10, 2), edge(10, 3)]}
        self.check(graph, plan([[1, 2], [3]]), {'boundary_input': 2})

    def test_multiple_source_destination_cores_deduplicate_tensor_pairs(self):
        graph = {'ops': [op(i) for i in range(1, 7)], 'tensors': [tensor(10, 60)],
                 'edges': [edge(1, 10), edge(2, 10), edge(10, 3), edge(10, 4),
                           edge(10, 5), edge(10, 6)]}
        self.check(graph, plan([[1], [2], [3, 4], [5, 6]]), {'cross_tensor': 8})

    def test_boundary_output_and_cross_transfer_are_distinct(self):
        graph = {'ops': [op(1), op(2), op(3, 'COPY_OUT')],
                 'tensors': [tensor(10, 1)],
                 'edges': [edge(1, 10), edge(10, 2), edge(10, 3)]}
        self.check(graph, plan([[1], [2]]),
                   {'boundary_output': 1, 'cross_tensor': 2})

    def test_terminal_output_without_consumer(self):
        graph = {'ops': [op(1), op(2)], 'tensors': [tensor(10, 121)],
                 'edges': [edge(1, 10), edge(2, 10)]}
        self.check(graph, plan([[1], [2]]), {'boundary_output': 2})

    def test_direct_zero_byte_edge_still_has_two_units_of_work(self):
        graph = {'ops': [op(1), op(2)], 'tensors': [],
                 'edges': [edge(1, 2, data_size=0)]}
        self.check(graph, plan([[1], [2]]), {'cross_direct': 2})
        self.assertEqual(mandatory_copy_work(graph, plan([[1], [2]]), 60)['service_work'], 2)
        graph['edges'][0]['data_size'] = 61
        self.check(graph, plan([[1], [2]]), {'cross_direct': 2})
        self.assertEqual(mandatory_copy_work(graph, plan([[1], [2]]), 60)['service_work'], 4)

    def test_unsupported_values_fail_closed(self):
        graph = {'ops': [op(1), op(2)], 'tensors': [],
                 'edges': [edge(1, 2, data_size='4')]}
        with self.assertRaises(UnknownMandatoryDDR):
            mandatory_copy_work(graph, plan([[1], [2]]), 60)
        with self.assertRaises(UnknownMandatoryDDR):
            mandatory_copy_work(graph, plan([[1], [2]]), 0)
        with self.assertRaises(MulticoreCutError):
            mandatory_copy_work(graph, plan([[1]]), 60)
        valid = {**graph, 'edges': [edge(1, 2, data_size=0)]}
        self.assertEqual(mandatory_copy_work(valid, plan([[1], [2]]), 60.0)['service_work'], 2)
        for bandwidth in (float('nan'), float('inf'), 10**1000, True, 0.0):
            with self.subTest(bandwidth=bandwidth), self.assertRaises(UnknownMandatoryDDR):
                mandatory_copy_work(valid, plan([[1], [2]]), bandwidth)


if __name__ == '__main__':
    unittest.main()
