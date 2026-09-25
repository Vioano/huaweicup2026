import unittest
from src.q3.static_task_bound import analyze, GuardFailure


def task(copy_id=1, compute_id=2, local=11, ddr=21, with_output=False):
    graph = {'ops': [{'id': copy_id, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2'},
                     {'id': compute_id, 'op': 'MATMUL', 'pipe': 'PIPE_M', 'cycles': 1}],
             'tensors': [{'id': local, 'pos': 'L1', 'size': 600},
                         {'id': ddr, 'pos': 'DDR', 'size': 600}],
             'edges': [{'source': ddr, 'target': copy_id}, {'source': copy_id, 'target': local},
                       {'source': local, 'target': compute_id}]}
    word = [copy_id, compute_id]
    if with_output:
        graph['ops'].append({'id': 3, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3'})
        graph['tensors'] += [{'id': 12, 'pos': 'L1', 'size': 600}, {'id': 22, 'pos': 'DDR', 'size': 600}]
        graph['edges'] += [{'source': compute_id, 'target': 12}, {'source': 12, 'target': 3}, {'source': 3, 'target': 22}]
        word.append(3)
    return {'graph': graph, 'pre_step2_word': word}


class BoundTests(unittest.TestCase):
    def run_bound(self, tasks, links=(), capacity=4096):
        return analyze(tasks, links, capacity={'L1': capacity, 'UB': 100},
                       ddr_bandwidth=60, cache_bandwidth=250, cross_core_delay_cycles=5)

    def test_unique_key_cold_but_repeated_key_optimistically_hot(self):
        self.assertEqual(self.run_bound({0: task()})['lower_bound_cycles'], 11)
        self.assertEqual(self.run_bound({0: task(), 1: task()})['lower_bound_cycles'], 4)

    def test_copy_out_does_not_warm_cache_and_cross_delay_is_counted(self):
        tasks = {0: task(with_output=True), 1: task(4, 5, 12, 23)}
        links = [{'source_core': 0, 'source_copy_out_id': 3, 'target_core': 1, 'target_copy_in_id': 4}]
        result = self.run_bound(tasks, links)
        self.assertEqual(result['lower_bound_cycles'], 37)  # 10+1+10+5+10+1
        self.assertEqual(result['sole_copy_in_key_count'], 2)

    def test_unproved_alias_and_multiport_copy_rejected(self):
        t = task()
        t['graph']['tensors'][0]['logical_tid'] = 99
        with self.assertRaisesRegex(GuardFailure, 'plain integer tensor'):
            self.run_bound({0: t})
        t = task()
        t['graph']['tensors'].append({'id': 13, 'pos': 'L1', 'size': 20})
        t['graph']['edges'].append({'source': 1, 'target': 13})
        with self.assertRaisesRegex(GuardFailure, 'one input and one output'):
            self.run_bound({0: t})

    def test_full_interval_must_fit_before_issuing_bound(self):
        with self.assertRaisesRegex(GuardFailure, 'closed-interval peak'):
            self.run_bound({0: task(with_output=True)}, capacity=1199)

    def test_cross_task_cycle_rejected(self):
        tasks = {0: task(with_output=True), 1: task(with_output=True)}
        links = [{'source_core': c, 'source_copy_out_id': 3,
                  'target_core': 1-c, 'target_copy_in_id': 1} for c in (0, 1)]
        with self.assertRaisesRegex(GuardFailure, 'contains a cycle'):
            self.run_bound(tasks, links)


if __name__ == '__main__':
    unittest.main()
