import unittest
from unittest.mock import patch

from src.q1.packet_dp import UnsupportedResponse, construct, shortest_packet_path
from tests.q1.test_capacity_return import chains


class PacketDPTests(unittest.TestCase):
    def test_drain_closure_can_beat_direct_transition(self):
        normal = [
            {(0, 0): (20, 0, 1), (0, 1): (5, 1, 1)},
            {(0, 0): (2, 0, 1), (1, 0): (20, 0, 1), (1, 1): (1, 0, 1)},
        ]
        cost, path = shortest_packet_path(
            (0, 1), normal, [{}, {1: (1, 1, 1)}, {1: (9, 0, 1)}])
        self.assertEqual(cost, (8, 2, 3))
        self.assertEqual(path, [('normal', 0, 0, 1), ('drain', 1, 1, 0),
                                ('normal', 1, 0, 0)])

    def test_two_core_multiple_rounds(self):
        graph = chains(12)
        plan, info = construct(graph, 2, {'L1': 1024, 'UB': 160})
        self.assertEqual(info['packet'], 2)
        self.assertEqual(info['complete_rounds'], 3)
        self.assertEqual(set(map(int, plan['node_to_subgraph'])), set(range(36)))
        self.assertEqual(info['model_makespan'], info['response']['makespan'])
        self.assertEqual(info['official_scoring_calls'], dict(E0=0, E1=0, E2=0))

    def test_three_core_remainder_uses_explicit_tail(self):
        plan, info = construct(chains(7), 3, {'L1': 1024, 'UB': 160})
        self.assertEqual(info['packet'], 2)
        self.assertEqual(info['complete_rounds'], 1)
        self.assertEqual(set(map(int, plan['node_to_subgraph'])), set(range(21)))
        self.assertEqual(len(plan['core_schedules'][0]),
                         len(plan['core_schedules'][1]) + 1)
        self.assertEqual(info['model_makespan'], info['response']['makespan'])

    def test_full_auto_and_preflight_budget_on_tiny_packet_three(self):
        graph = chains(6)
        kwargs = dict(cores=2, capacity={'L1': 1024, 'UB': 240})
        _, full = construct(graph, state_mode='full', **kwargs)
        self.assertEqual(full['packet'], 3)
        self.assertEqual(full['states'], (0, 1, 2, 3))
        self.assertEqual(full['state_mode_chosen'], 'full')
        self.assertLessEqual(full['static_task_compiles'],
                             full['state_compile_estimates']['full']['total_task_compiles_bound'])
        full_bound = full['state_compile_estimates']['full']['total_task_compiles_bound']
        three_bound = full['state_compile_estimates']['three']['total_task_compiles_bound']
        self.assertLess(three_bound, full_bound)
        _, automatic_full = construct(graph, max_task_compiles=full_bound, **kwargs)
        self.assertEqual(automatic_full['state_mode_chosen'], 'full')
        _, automatic_three = construct(graph, max_task_compiles=three_bound, **kwargs)
        self.assertEqual(automatic_three['state_mode_chosen'], 'three')
        self.assertEqual(automatic_three['states'], (0, 2, 3))
        # Forced full must reject before even the first static Task compile.
        with patch('src.q1.packet_dp.compile_plan', side_effect=AssertionError('compiled')):
            with self.assertRaisesRegex(UnsupportedResponse, 'before compilation'):
                construct(graph, max_task_compiles=full_bound - 1,
                          state_mode='full', **kwargs)


if __name__ == '__main__':
    unittest.main()
