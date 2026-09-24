"""Injected-score mechanism tests; no official evaluation or real case runs."""
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import adaptive_budget, guarded_component
from src.q2_nikolastarx.dag_direct import DAGIndex
from tests.q2_nikolastarx.test_component_envelope import config, jobs


def imbalanced(count=6):
    graph = jobs(count)
    graph['ops'][0]['cycles'] = 10000
    return DAGIndex(graph)


class GuardedComponentTests(unittest.TestCase):
    def test_candidate_can_win_and_tied_makespan_saves_ddr(self):
        index = imbalanced()
        base, _ = adaptive_budget.component_route(index, 2, config())
        dag, _ = index.build(2, bandwidth=60, cross_core_delay=500)
        self.assertNotEqual(base, dag)
        for scores in [((22000, 900), (21000, 2000)),
                       ((22000, 900), (22000, 800))]:
            calls = []
            def oracle(plan):
                calls.append(plan)
                makespan, added = scores[0] if plan == base else scores[1]
                return {'status': 'ok', 'makespan': makespan, 'added_copy_bytes': added}
            plan, detail = guarded_component.guarded_component_route(
                index, 2, config(), oracle=oracle)
            self.assertEqual(plan, dag)
            self.assertEqual(calls, [base, dag])
            self.assertEqual(detail['guarded_component']['oracle_requests'], 2)

    def test_no_trigger_and_identical_plan_request_no_score(self):
        for index in [DAGIndex(jobs(6)), imbalanced(3)]:
            plan, detail = guarded_component.guarded_component_route(
                index, 2, config(), oracle=lambda _: self.fail('unexpected score'))
            base, _ = adaptive_budget.component_route(index, 2, config())
            self.assertEqual(plan, base)
            self.assertEqual(detail['guarded_component']['oracle_requests'], 0)
        index = DAGIndex(jobs(6))
        _, detail = guarded_component.guarded_component_route(
            index, 1, config(), oracle=lambda _: self.fail('unexpected score'))
        self.assertEqual(detail['guarded_component']['constructed_plans'], 1)

    def test_invalid_or_failed_oracle_preserves_baseline(self):
        index = imbalanced()
        base, _ = adaptive_budget.component_route(index, 2, config())
        invalid = [None, {'status': 'ok', 'makespan': 0},
                   {'status': 'error', 'makespan': 1, 'added_copy_bytes': 0},
                   {'status': 'ok', 'makespan': True, 'added_copy_bytes': 0},
                   {'status': 'ok', 'makespan': -1, 'added_copy_bytes': 0},
                   {'status': 'ok', 'makespan': float('nan'), 'added_copy_bytes': 0}]
        for response in invalid:
            plan, detail = guarded_component.guarded_component_route(
                index, 2, config(), oracle=lambda _: response)
            self.assertEqual(plan, base)
            self.assertEqual(detail['guarded_component']['evidence'], 'unknown')
            self.assertEqual(detail['guarded_component']['oracle_requests'], 1)
        calls = 0
        def candidate_fails(_):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('unavailable')
            return {'status': 'ok', 'makespan': 22000, 'added_copy_bytes': 0}
        plan, detail = guarded_component.guarded_component_route(
            index, 2, config(), oracle=candidate_fails)
        self.assertEqual(plan, base)
        self.assertEqual(detail['guarded_component']['oracle_requests'], 2)
        self.assertEqual(detail['guarded_component']['evidence'], 'unknown')

    def test_strict_actual_pipe_work_lower_bound(self):
        index = imbalanced()
        base, _ = adaptive_budget.component_route(index, 2, config())
        calls = []
        def oracle(plan):
            calls.append(plan)
            return {'status': 'ok', 'makespan': 9999, 'added_copy_bytes': 100}
        plan, detail = guarded_component.guarded_component_route(
            index, 2, config(), oracle=oracle)
        self.assertEqual(plan, base)
        self.assertEqual(calls, [base])
        guard = detail['guarded_component']
        self.assertGreater(guard['candidate_pipe_work_lower_bound'], 9999)
        self.assertEqual(guard['reason'], 'candidate_lower_bound_strictly_worse')
        self.assertEqual(guard['oracle_requests'], 1)

    def test_candidate_construction_failure_and_callback(self):
        index = imbalanced()
        base, _ = adaptive_budget.component_route(index, 2, config())
        with patch.object(index, 'build', side_effect=RuntimeError('construction')):
            plan, detail = guarded_component.make_component_builder(
                lambda _: self.fail('unexpected score'))(index, 2, config())
        self.assertEqual(plan, base)
        self.assertEqual(detail['guarded_component']['evidence'], 'unknown')
        self.assertEqual(detail['guarded_component']['oracle_requests'], 0)

    def test_recognized_vector_defers_to_semantic_repair(self):
        index = imbalanced()
        base, _ = adaptive_budget.component_route(index, 2, config())
        with patch('src.q2_nikolastarx.guarded_component.vector_lanes.recognize',
                   return_value={'template': 'synthetic'}):
            plan, detail = guarded_component.guarded_component_route(
                index, 2, config(), oracle=lambda _: self.fail('unexpected score'))
        self.assertEqual(plan, base)
        self.assertEqual(detail['guarded_component']['constructed_plans'], 1)
        self.assertEqual(detail['guarded_component']['oracle_requests'], 0)


if __name__ == '__main__':
    unittest.main()
