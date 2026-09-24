"""Synthetic structure and calendar tests; no original graphs or evaluator."""
import copy
import unittest

from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from src.q2_nikolastarx.gap_calendar import empty, earliest, reserve
from src.q2_nikolastarx.gap_candidate import build


def diamond():
    return {'ops': [
        {'id': u, 'op': 'COMPUTE', 'pipe': pipe, 'cycles': cycles}
        for u, pipe, cycles in [(1, 'PIPE_MTE2', 10), (2, 'PIPE_MTE3', 30),
                                (3, 'PIPE_V', 10), (4, 'PIPE_M', 5), (5, 'PIPE_V', 5)]],
        'tensors': [], 'edges': [{'source': u, 'target': v, 'data_size': 8}
                                 for u, v in [(1, 3), (2, 3), (3, 4), (3, 5)]]}


CONFIG = {'bandwidth': 60, 'cross_core_copy_delay_cycles': 500}


class GapCandidateTests(unittest.TestCase):
    def test_join_pairing_all_pipes_coverage_and_order(self):
        graph = diamond()
        for cores in (1, 2, 5):
            plan, meta = build(graph, cores, CONFIG)
            view = derive_multicore_plan(graph, plan)
            self.assertEqual(set(view['mapping']), {1, 2, 3, 4, 5})
            self.assertGreater(meta['paired_joins'], 0)
            self.assertEqual(meta['online_E0_calls'], 0)
            self.assertLessEqual(meta['arithmetic_placement_choices'], meta['choice_bound'])
            self.assertEqual(len(plan['core_schedules']), cores)

    def test_persistent_calendar_inserts_in_gap(self):
        original = empty()
        booked = reserve(original, 10, 20)
        self.assertEqual(earliest(original, 0, 15), 0)
        self.assertEqual(earliest(booked, 0, 5), 0)
        self.assertEqual(earliest(booked, 6, 5), 30)
        filled = reserve(booked, 0, 5)
        self.assertEqual(earliest(filled, 0, 6), 30)
        self.assertEqual(earliest(booked, 0, 6), 0)

    def test_structural_guard_no_fallback(self):
        graph = diamond()
        graph['edges'].pop()  # no fork
        with self.assertRaises(UnsupportedStructure):
            build(graph, 2, CONFIG)
        graph = diamond()
        graph['tensors'] = [{'id': 100, 'pos': 'L1', 'size': 8, 'logical_tid': 100}]
        with self.assertRaises(UnsupportedStructure):
            build(graph, 2, CONFIG)
        graph = diamond()
        graph['edges'] = [e for e in graph['edges'] if (e['source'], e['target']) != (1, 3)]
        graph['ops'].append({'id': 90, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1})
        graph['tensors'] = [{'id': 100, 'pos': 'L1', 'size': 8}, {'id': 101, 'pos': 'DDR', 'size': 8}]
        graph['edges'] += [{'source': u, 'target': v} for u, v in
                           [(1, 100), (100, 90), (90, 101), (101, 3)]]
        with self.assertRaises(UnsupportedStructure):
            build(graph, 2, CONFIG)
        graph = diamond()
        graph['tensors'] = [{'id': 100, 'pos': 'UB', 'size': 8}]
        graph['edges'] += [{'source': u, 'target': 100} for u in (1, 2)]
        with self.assertRaises(UnsupportedStructure):
            build(graph, 2, CONFIG)

    def test_export_is_deterministic(self):
        graph = diamond()
        shuffled = copy.deepcopy(graph)
        for key in shuffled:
            shuffled[key].reverse()
        self.assertEqual(build(graph, 2, CONFIG), build(shuffled, 2, CONFIG))


if __name__ == '__main__':
    unittest.main()
