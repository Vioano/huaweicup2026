"""Mocked complete-plan portfolio contracts; no official evaluator is invoked."""
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import adaptive_structural_portfolio as route


def plan(number):
    return {'node_to_subgraph': {'1': number}, 'core_schedules': [[number]]}


BASE, GAP, INCUMBENT = (plan(number) for number in range(3))
FIXED, REVERSE, LATENCY = (plan(number) for number in range(3, 6))


def exercise(*, scores=None, old_plans=(BASE, GAP, INCUMBENT),
             candidates=(FIXED, REVERSE, LATENCY), cores=2,
             evidence='injected_oracle_complete_plan_scores'):
    scores = scores or {number: (100 + number, 10) for number in range(6)}
    calls = []

    def oracle(candidate):
        number = candidate['node_to_subgraph']['1']
        calls.append(number)
        result = scores[number]
        if isinstance(result, Exception):
            raise result
        if isinstance(result, dict):
            return result
        return {'status': 'ok', 'makespan': result[0],
                'added_copy_bytes': result[1]}

    def old_build(graph, count, config, scored_oracle):
        for candidate in old_plans:
            scored_oracle(candidate)
        return INCUMBENT, {'selected_strategy': 'hypergap_retime',
                           'score_evidence': evidence,
                           'constructed_plans': len(old_plans)}

    with patch.object(route.adaptive_hypergap_guarded, 'build', side_effect=old_build), \
         patch.object(route.fixed_owner_reverse, 'retime',
                      return_value=(candidates[0], {'method': 'fixed'})) as fixed, \
         patch.object(route.reverse_gap_candidate, 'build',
                      return_value=(candidates[1], {'method': 'reverse'})) as reverse, \
         patch.object(route.gap_candidate, 'build',
                      return_value=(GAP, {'method': 'gap'})) as gap, \
         patch.object(route.latency_hyperrefine, 'build',
                      return_value=(candidates[2], {'method': 'latency'})) as latency:
        chosen, detail = route.build({}, cores, {}, oracle)
    return chosen, detail, calls, (fixed, reverse, gap, latency)


class StructuralPortfolioTests(unittest.TestCase):
    def test_each_structural_candidate_can_win_on_complete_plan_makespan(self):
        for winner, expected in ((3, FIXED), (4, REVERSE), (5, LATENCY)):
            with self.subTest(winner=winner):
                scores = {number: (110 + number, 10) for number in range(6)}
                scores[2] = (100, 10)
                scores[winner] = (90, 100)
                chosen, detail, calls, _ = exercise(scores=scores)
                self.assertEqual(chosen, expected)
                self.assertEqual(detail['selected'],
                                 {3: 'fixed_owner', 4: 'reverse_gap',
                                  5: 'latency_hyperrefine'}[winner])
                self.assertEqual(detail['selected_score_id'], winner + 1)
                self.assertEqual(calls, list(range(6)))

    def test_regressions_ties_and_ddr_tiebreak(self):
        for candidate_score, expected in (((101, 0), INCUMBENT),
                                          ((100, 10), INCUMBENT),
                                          ((100, 11), INCUMBENT),
                                          ((100, 9), FIXED)):
            with self.subTest(score=candidate_score):
                scores = {number: (120 + number, 10) for number in range(6)}
                scores[2] = (100, 10)
                scores[3] = candidate_score
                chosen, detail, _, _ = exercise(scores=scores)
                self.assertEqual(chosen, expected)
                self.assertEqual(detail['reason'], 'strict_lexicographic_improvement'
                                 if expected == FIXED else 'incumbent_wins_or_ties')

    def test_duplicate_constructors_do_not_request_or_score_again(self):
        chosen, detail, calls, _ = exercise(candidates=(INCUMBENT, FIXED, FIXED))
        self.assertEqual(chosen, INCUMBENT)
        self.assertEqual(calls, [0, 1, 2, 3])
        self.assertEqual(detail['oracle_requests'], 4)
        self.assertEqual(detail['unique_scored_plans'], 4)
        self.assertEqual(detail['candidates']['fixed_owner']['status'], 'duplicate')
        self.assertEqual(detail['candidates']['latency_hyperrefine']['status'], 'duplicate')
        self.assertEqual(detail['candidates']['latency_hyperrefine']['duplicate_of'],
                         'reverse_gap')

    def test_six_distinct_oracle_starts_are_hard_capped(self):
        fourth = plan(6)
        scores = {number: (100 + number, 10) for number in range(7)}
        scores[2] = (90, 10)
        chosen, detail, calls, _ = exercise(scores=scores,
                                            old_plans=(BASE, GAP, INCUMBENT, fourth))
        self.assertEqual(chosen, INCUMBENT)
        self.assertEqual(calls, [0, 1, 2, 6, 3, 4])
        self.assertEqual(detail['oracle_requests'], 6)
        self.assertEqual(detail['unique_scored_plans'], 6)
        self.assertEqual(detail['candidates']['latency_hyperrefine']['status'],
                         'candidate_score_unavailable')
        self.assertEqual(detail['score_evidence'], 'unknown')

    def test_single_core_and_unknown_evidence_skip_constructors(self):
        for options, reason in (({'cores': 1}, 'single_core_no_portfolio'),
                                ({'evidence': 'unknown'},
                                 'incumbent_score_evidence_unknown')):
            with self.subTest(reason=reason):
                chosen, detail, calls, constructors = exercise(**options)
                self.assertEqual(chosen, INCUMBENT)
                self.assertEqual(detail['reason'], reason)
                self.assertEqual(calls, [0, 1, 2])
                for constructor in constructors:
                    constructor.assert_not_called()

    def test_invalid_or_missing_candidate_score_fails_closed(self):
        for result in (RuntimeError('oracle unavailable'),
                       {'status': 'error'},
                       {'status': 'ok', 'makespan': -1,
                        'added_copy_bytes': 0}):
            with self.subTest(result=result):
                scores = {number: (100 + number, 10) for number in range(6)}
                scores[3] = (80, 1)
                scores[4] = result
                chosen, detail, calls, _ = exercise(scores=scores)
                self.assertEqual(chosen, INCUMBENT)
                self.assertEqual(calls, [0, 1, 2, 3, 4])
                self.assertEqual(detail['reason'], 'score_unavailable')
                self.assertEqual(detail['score_evidence'], 'unknown')
                self.assertEqual(detail['selected'], 'incumbent')

    def test_unscored_incumbent_requires_valid_oracle_score(self):
        scores = {number: (100 + number, 10) for number in range(6)}
        scores[2] = {'status': 'unknown'}
        chosen, detail, calls, _ = exercise(scores=scores, old_plans=(),
                                            evidence='not_requested')
        self.assertEqual(chosen, INCUMBENT)
        self.assertEqual(calls, [2])
        self.assertEqual(detail['candidates']['fixed_owner']['status'],
                         'incumbent_score_unavailable')
        self.assertEqual(detail['score_evidence'], 'unknown')

    def test_cli_uses_six_request_limit(self):
        with patch.object(route, 'guarded_main') as main:
            route.main(['--example'])
        main.assert_called_once_with(['--example'], constructor=route.build,
                                     oracle_request_limit=6)


if __name__ == '__main__':
    unittest.main()
