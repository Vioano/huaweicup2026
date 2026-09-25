"""Synthetic structure tests only; no official scoring calls."""
import copy
import unittest

from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from src.q2_nikolastarx.shared_stationary_wave import build
from tests.test_q2_shared_input_wave import graph


CONFIG = {'capacity': {'L1': 300, 'UB': 300}}


class SharedStationaryWaveTests(unittest.TestCase):
    def test_shared_inputs_one_owner_and_global_topology(self):
        data = graph(4)
        plan, detail = build(data, 3, CONFIG)
        index = DAGIndex(data)
        view = derive_multicore_plan(data, plan)
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})
        self.assertEqual(set(view['mapping']), set(index.ops))
        self.assertEqual(len(set().union(*map(set, plan['core_schedules']))), len(index.ops))
        owner = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
        for tid in (1000, 1001, 1002):
            self.assertEqual(len({owner[u] for u in index.ops if tid in index.inputs[u]}), 1)
        # A single common sequence exists: concatenate contiguous core stages.
        inverse = {sg: u for u, sg in view['mapping'].items()}
        order = [inverse[sg] for row in plan['core_schedules'] for sg in row]
        positions = {u: i for i, u in enumerate(order)}
        for u in index.ops:
            self.assertTrue(all(positions[v] < positions[u] for v in index.pred[u]))
        self.assertEqual(detail['shared_input_owner_count_max'], 1)
        self.assertEqual(detail['stage_count'], 4)  # 3 shared waves plus residual.
        self.assertFalse(detail['official_score_available'])

    def test_renamed_private_ids_and_unsupported_template(self):
        data = graph(3)
        renamed = copy.deepcopy(data)
        remap = {op['id']: op['id'] + 10000 for op in renamed['ops']}
        remap.update({t['id']: t['id'] + 20000 for t in renamed['tensors']
                      if t['id'] >= 2000})
        for op in renamed['ops']:
            op['id'] = remap[op['id']]
        for tensor in renamed['tensors']:
            tensor['id'] = remap.get(tensor['id'], tensor['id'])
        for edge in renamed['edges']:
            edge['source'] = remap.get(edge['source'], edge['source'])
            edge['target'] = remap.get(edge['target'], edge['target'])
        first, first_detail = build(data, 2, CONFIG)
        second, second_detail = build(renamed, 2, CONFIG)
        self.assertEqual(first_detail['core_stage_bounds'], second_detail['core_stage_bounds'])
        self.assertEqual(first_detail['estimated_transfer_bytes_without_spill'],
                         second_detail['estimated_transfer_bytes_without_spill'])
        derive_multicore_plan(renamed, second)
        self.assertEqual(len(first['core_schedules']), 2)
        data['ops'][-1]['cycles'] += 1
        with self.assertRaises(UnsupportedStructure):
            build(data, 2, CONFIG)


if __name__ == '__main__':
    unittest.main()
