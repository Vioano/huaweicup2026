"""C02 external-input guard regressions; no evaluator calls."""
import importlib.util
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.q2_nikolastarx.dag_direct import DAGIndex
from tests.test_q2_exit_sealed_candidate import fixture

from src.q2_nikolastarx import exit_sealed_candidate as adapter


def with_standard_copyin():
    graph, plan, config, link, finish = fixture()
    graph['ops'].append({'id': 7, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 1})
    graph['tensors'].extend([{'id': 20, 'size': 4, 'pos': 'DDR'},
                             {'id': 21, 'size': 4, 'pos': 'UB'}])
    graph['edges'].extend([{'source': 20, 'target': 7},
                           {'source': 7, 'target': 21},
                           {'source': 21, 'target': 2}])
    return graph, plan, config, link, finish


class CopyInGuardTests(unittest.TestCase):
    def test_independent_ddr_copyin_is_graph_input(self):
        graph, plan, config, link, finish = with_standard_copyin()
        problem = adapter._problem_and_tensor_guard(graph, DAGIndex(graph))
        self.assertEqual(set(problem.pipe), set(finish))
        self.assertNotIn(7, problem.pipe)
        candidates, meta = adapter.propose(graph, plan, config, [link], finish,
                                            incumbent_makespan=10000)
        self.assertEqual(meta['status'], 'candidates', meta)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(set(candidates[0]['plan']), {'node_to_subgraph', 'core_schedules'})

    def test_eligible_producer_into_copyin_is_rejected(self):
        graph, *_ = with_standard_copyin()
        graph['edges'].append({'source': 1, 'target': 20})
        with self.assertRaisesRegex(ValueError, 'COPY_IN_not_independent_graph_input'):
            adapter._problem_and_tensor_guard(graph, DAGIndex(graph))

    def test_excluded_relay_into_copyin_is_rejected(self):
        graph, *_ = with_standard_copyin()
        graph['ops'].append({'id': 8, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1})
        graph['edges'].append({'source': 8, 'target': 20})
        with self.assertRaisesRegex(ValueError, 'COPY_IN_not_independent_graph_input'):
            adapter._problem_and_tensor_guard(graph, DAGIndex(graph))

    def test_hidden_excluded_consumer_remains_rejected(self):
        graph, *_ = with_standard_copyin()
        graph['ops'].append({'id': 9, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 1})
        graph['tensors'].extend([{'id': 22, 'size': 4, 'pos': 'DDR'},
                                 {'id': 23, 'size': 4, 'pos': 'UB'}])
        graph['edges'].extend([{'source': 22, 'target': 9},
                               {'source': 9, 'target': 23},
                               {'source': 10, 'target': 9},
                               {'source': 23, 'target': 3}])
        with self.assertRaisesRegex(ValueError, 'nonstandard_COPY_IN_incidence'):
            adapter._problem_and_tensor_guard(graph, DAGIndex(graph))

    def test_copyin_size_mismatch_is_outside_sufficient_guard(self):
        graph, *_ = with_standard_copyin()
        next(t for t in graph['tensors'] if t['id'] == 21)['size'] = 8
        with self.assertRaisesRegex(ValueError, 'COPY_IN_not_independent_graph_input'):
            adapter._problem_and_tensor_guard(graph, DAGIndex(graph))

    def test_copyin_direct_output_is_rejected(self):
        graph, *_ = with_standard_copyin()
        graph['edges'].append({'source': 7, 'target': 3, 'data_size': 4})
        with self.assertRaisesRegex(ValueError, 'nonstandard_COPY_IN_incidence'):
            adapter._problem_and_tensor_guard(graph, DAGIndex(graph))


if __name__ == '__main__':
    unittest.main(verbosity=2)
