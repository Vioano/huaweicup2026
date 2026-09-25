"""Synthetic integration tests; no real solver case or evaluator request."""
import json
import tempfile
import unittest
from pathlib import Path

from src.q2_nikolastarx import adaptive_guarded, adaptive_semantic, adaptive_budget
from src.q2_nikolastarx.dag_direct import DAGIndex
from tests.q2_nikolastarx.test_component_envelope import config, jobs


def ledger():
    return {'calls': {'E0': 0, 'E1': 0, 'E2': 0, 'E2_api_attempted': 0,
                      'native_returns': 0, 'E0_fallback': 0},
            'request_in_flight': False, 'possible_E0_fallback_calls': 0}


def imbalanced():
    graph = jobs(6)
    graph['ops'][0]['cycles'] = 10000
    return graph


class AdaptiveGuardedTests(unittest.TestCase):
    def test_cli_zero_score_does_not_require_e2_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            graph_path = root/'graph.json'
            graph_path.write_text(json.dumps(jobs(6)))
            adaptive_guarded.main([
                str(graph_path), '--cores', '2', '--e2-root', str(root/'absent-e2'),
                '--output', str(root/'plan.json'), '--evidence', str(root/'evidence')])
            result = json.loads((root/'evidence/solver.json').read_text())
            self.assertEqual(result['status'], 'ok')
            self.assertFalse(result['source_checked'])
            self.assertEqual(result['calls']['E2'], 0)
            self.assertEqual(set(json.loads((root/'plan.json').read_text())),
                             {'node_to_subgraph', 'core_schedules'})

    def test_no_pressure_never_invokes_oracle(self):
        graph = jobs(6)
        plan, detail = adaptive_guarded.build_guarded(
            graph, 2, config(), lambda _: self.fail('no score expected'))
        expected, _ = adaptive_semantic.build(graph, 2, config())
        self.assertEqual(plan, expected)
        self.assertEqual(detail['guarded_component']['oracle_requests'], 0)

    def test_candidate_win_with_native_score_and_two_requests(self):
        graph = imbalanced()
        index = DAGIndex(graph)
        baseline, _ = adaptive_budget.component_route(index, 2, config())
        candidate, _ = index.build(2, bandwidth=60, cross_core_delay=500)
        self.assertNotEqual(baseline, candidate)
        with tempfile.TemporaryDirectory() as folder:
            state = ledger()
            path = Path(folder)/'ledger.json'
            def fake(plan):
                score = (22000, 900) if plan == baseline else (21000, 2000)
                return {'route': 'native', 'status': 'ok', 'problem': 2,
                        'makespan': score[0],
                        'data_movement_bytes': {'added_copy_bytes': score[1]}}
            plan, detail = adaptive_guarded.build_guarded(
                graph, 2, config(), adaptive_guarded.score_adapter(fake, state, path))
            self.assertEqual(plan, candidate)
            self.assertEqual(detail['guarded_component']['selected'], 'dag')
            self.assertEqual(state['calls']['E2_api_attempted'], 2)
            self.assertEqual(state['calls']['E2'], 2)
            self.assertEqual(state['calls']['native_returns'], 2)
            self.assertEqual(state['calls']['E0'], 0)
            self.assertEqual(len(state['attempts']), 2)
            self.assertTrue(all('record' in row and 'plan_sha256' in row
                                and 'wall_seconds' in row for row in state['attempts']))
            self.assertFalse(json.loads(path.read_text())['request_in_flight'])

    def test_fallback_and_exception_preserve_baseline_and_budget(self):
        graph = imbalanced()
        baseline, _ = adaptive_budget.component_route(DAGIndex(graph), 2, config())
        for response, expected in [
            ({'route': 'e0_fallback', 'status': 'ok', 'problem': 2}, (1, 0, 1, False)),
            (RuntimeError('unknown after call'), (1, 0, 0, True)),
        ]:
            with tempfile.TemporaryDirectory() as folder:
                state = ledger()
                path = Path(folder)/'ledger.json'
                def fake(_):
                    if isinstance(response, Exception):
                        raise response
                    return response
                plan, detail = adaptive_guarded.build_guarded(
                    graph, 2, config(), adaptive_guarded.score_adapter(fake, state, path))
                self.assertEqual(plan, baseline)
                self.assertEqual(detail['guarded_component']['reason'], 'baseline_score_unavailable')
                calls = state['calls']
                self.assertEqual((calls['E2_api_attempted'], calls['native_returns'],
                                  calls['E0_fallback'], state['request_in_flight']), expected)
                self.assertEqual(state['possible_E0_fallback_calls'], 1)
                self.assertEqual(state['calls']['E0'], 1)
                self.assertEqual(json.loads(path.read_text())['request_in_flight'], expected[3])

    def test_wrong_problem_and_request_cap_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            state = ledger()
            scorer = adaptive_guarded.score_adapter(
                lambda _: {'route': 'native', 'status': 'ok', 'problem': 3,
                           'makespan': 1, 'data_movement_bytes': {'added_copy_bytes': 0}},
                state, Path(folder)/'ledger.json')
            with self.assertRaises(ValueError):
                scorer({})
            self.assertEqual(state['calls']['native_returns'], 1)
            state['calls']['E2_api_attempted'] = 2
            with self.assertRaises(RuntimeError):
                scorer({})
            self.assertEqual(state['calls']['E2_api_attempted'], 2)

    def test_six_request_portfolio_cap_is_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            state = ledger()
            scorer = adaptive_guarded.score_adapter(
                lambda _: {'route': 'native', 'status': 'ok', 'problem': 2,
                           'makespan': 100,
                           'data_movement_bytes': {'added_copy_bytes': 0}},
                state, Path(folder)/'ledger.json', max_requests=6)
            for number in range(6):
                self.assertEqual(scorer({'candidate': number})['makespan'], 100)
            with self.assertRaisesRegex(RuntimeError, '6-request E2 cap'):
                scorer({'candidate': 6})
            self.assertEqual(state['calls']['E2_api_attempted'], 6)
            self.assertEqual(state['calls']['native_returns'], 6)
            self.assertEqual(len(state['attempts']), 6)
            self.assertFalse(state['request_in_flight'])

    def test_preparation_and_wall_failure_do_not_reserve_request(self):
        with tempfile.TemporaryDirectory() as folder:
            state = ledger()
            path = Path(folder)/'ledger.json'
            def fail_prepare():
                raise ValueError('source drift')
            scorer = adaptive_guarded.score_adapter(
                lambda _: self.fail('no E2'), state, path, prepare=fail_prepare)
            with self.assertRaises(ValueError):
                scorer({})
            self.assertEqual(state['calls']['E2'], 0)
            scorer = adaptive_guarded.score_adapter(
                lambda _: self.fail('no E2'), state, path, remaining_wall=lambda: 0)
            with self.assertRaises(TimeoutError):
                scorer({})
            self.assertEqual(state['calls']['E2'], 0)


if __name__ == '__main__':
    unittest.main()
