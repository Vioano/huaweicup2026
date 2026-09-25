"""Synthetic structural tests; no official evaluator is called."""
import copy
import unittest

from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from src.q2_nikolastarx.shared_stationary_pipeline import build
from tests.test_q2_shared_input_wave import graph


CONFIG = {'capacity': {'L1': 1000, 'UB': 1000}}


class SharedStationaryPipelineTests(unittest.TestCase):
    def test_job_major_order_and_structural_legality(self):
        data = graph(4)
        index = DAGIndex(data)
        plan, detail = build(data, 2, CONFIG)
        view = derive_multicore_plan(data, plan)
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})
        self.assertEqual(set(view['mapping']), set(index.ops))
        inverse = {i: int(u) for u, i in plan['node_to_subgraph'].items()}
        rows = [[inverse[i] for i in row] for row in plan['core_schedules']]
        # On core 1 the second-stage work of job 0 precedes first-stage
        # work of job 1; stage-major order would reverse this pair.
        self.assertLess(rows[1].index(21), rows[1].index(111))
        owner = {u: c for c, row in enumerate(rows) for u in row}
        self.assertEqual(len(owner), len(index.ops))
        for row in rows:
            jobs = [next(j for j, component in enumerate(index.components) if u in component)
                    for u in row]
            self.assertEqual(jobs, sorted(jobs))
        for u in index.ops:
            for pred in index.pred[u]:
                self.assertLessEqual(owner[pred], owner[u])
                if owner[pred] == owner[u]:
                    self.assertLess(rows[owner[u]].index(pred), rows[owner[u]].index(u))
        self.assertEqual(detail['shared_input_owner_count_max'], 1)
        self.assertEqual(detail['jobs'], 4)
        self.assertFalse(detail['official_score_available'])
        self.assertFalse(detail['zero_spill_claim'])

    def test_data_derived_reserve_and_rejection(self):
        data = graph(4)
        _, detail = build(data, 2, CONFIG)
        self.assertGreater(detail['two_job_produced_reserve_bytes']['L1'], 0)
        for ext in detail['core_external_input_bytes']:
            self.assertLessEqual(ext['L1'] + detail['two_job_produced_reserve_bytes']['L1'],
                                 CONFIG['capacity']['L1'])
        with self.assertRaises(UnsupportedStructure):
            build(data, 2, {'capacity': {'L1': 100, 'UB': 1000}})

    def test_renamed_private_ids_and_unsupported_template(self):
        data = graph(3)
        renamed = copy.deepcopy(data)
        remap = {op['id']: op['id'] + 10000 for op in renamed['ops']}
        remap.update({t['id']: t['id'] + 20000 for t in renamed['tensors'] if t['id'] >= 2000})
        for op in renamed['ops']:
            op['id'] = remap[op['id']]
        for tensor in renamed['tensors']:
            tensor['id'] = remap.get(tensor['id'], tensor['id'])
        for edge in renamed['edges']:
            edge['source'] = remap.get(edge['source'], edge['source'])
            edge['target'] = remap.get(edge['target'], edge['target'])
        _, first = build(data, 2, CONFIG)
        plan, second = build(renamed, 2, CONFIG)
        self.assertEqual(first['core_stage_bounds'], second['core_stage_bounds'])
        self.assertEqual(first['estimated_transfer_bytes_without_spill'],
                         second['estimated_transfer_bytes_without_spill'])
        derive_multicore_plan(renamed, plan)
        data['ops'][-1]['cycles'] += 1
        with self.assertRaises(UnsupportedStructure):
            build(data, 2, CONFIG)


if __name__ == '__main__':
    unittest.main()
