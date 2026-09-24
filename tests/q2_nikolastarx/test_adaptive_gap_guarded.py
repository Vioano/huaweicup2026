"""Synthetic complete-plan routing tests; no E2 or official graph execution."""
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import adaptive_gap_guarded
from src.q2_nikolastarx.direct import UnsupportedStructure


BASE = {'node_to_subgraph': {'1': 0}, 'core_schedules': [[0]]}
CANDIDATE = {'node_to_subgraph': {'1': 1}, 'core_schedules': [[1]]}


def compare(candidate=CANDIDATE, scores=((100, 50), (90, 100)), candidate_error=None):
    observed = []
    def oracle(plan):
        observed.append(plan)
        score = scores[0] if plan == BASE else scores[1]
        if isinstance(score, Exception):
            raise score
        if isinstance(score, dict):
            return score
        return {'status': 'ok', 'makespan': score[0], 'added_copy_bytes': score[1]}
    with patch.object(adaptive_gap_guarded.adaptive_budget, 'build',
                      return_value=(BASE, {'final_repair': 'already_applied'})) as base_build:
        if candidate_error is None:
            replacement = {'return_value': (candidate, {'gap': 'final'})}
        else:
            replacement = {'side_effect': candidate_error}
        with patch.object(adaptive_gap_guarded.gap_candidate, 'build', **replacement) as gap_build:
            plan, detail = adaptive_gap_guarded.build({'synthetic': True}, 2, {'x': 1}, oracle)
    base_build.assert_called_once()
    gap_build.assert_called_once()
    return plan, detail, observed


class AdaptiveGapGuardedTests(unittest.TestCase):
    def test_scores_complete_returned_plans_and_makespan_gain(self):
        plan, detail, observed = compare()
        self.assertIs(plan, CANDIDATE)
        self.assertEqual(observed, [BASE, CANDIDATE])
        self.assertEqual(detail['baseline_detail']['final_repair'], 'already_applied')
        self.assertEqual(detail['candidate_detail']['gap'], 'final')
        self.assertIn('complete final plans', detail['score_scope'])
        self.assertEqual(detail['oracle_requests'], 2)

    def test_same_makespan_lower_ddr_wins(self):
        plan, detail, observed = compare(scores=((100, 50), (100, 49)))
        self.assertIs(plan, CANDIDATE)
        self.assertEqual(detail['candidate_score'], [100, 49])
        self.assertEqual(len(observed), 2)

    def test_loser_and_tie_keep_baseline(self):
        for scores in (((101, 0), (102, 0)), ((100, 50), (100, 50)),
                       ((100, 50), (100, 51))):
            plan, detail, observed = compare(scores=scores)
            self.assertIs(plan, BASE)
            self.assertEqual(detail['reason'], 'baseline_wins_or_ties')
            self.assertEqual(len(observed), 2)

    def test_same_plan_and_failed_construction_do_not_score(self):
        plan, detail, observed = compare(candidate=BASE)
        self.assertIs(plan, BASE)
        self.assertEqual(detail['oracle_requests'], 0)
        self.assertEqual(observed, [])
        for error in (UnsupportedStructure('guard'), RuntimeError('construction')):
            plan, detail, observed = compare(candidate_error=error)
            self.assertIs(plan, BASE)
            self.assertEqual(detail['oracle_requests'], 0)
            self.assertEqual(detail['reason'], 'candidate_construction_failed')
            self.assertEqual(observed, [])

    def test_invalid_or_missing_score_is_unknown_and_keeps_baseline(self):
        bad = (None, {'status': 'ok', 'makespan': True, 'added_copy_bytes': 0},
               {'status': 'ok', 'makespan': 10, 'added_copy_bytes': -1},
               {'status': 'error', 'makespan': 10, 'added_copy_bytes': 0},
               RuntimeError('score unavailable'))
        for invalid in bad:
            for scores, request_count in (((invalid, (1, 0)), 1),
                                          (((100, 50), invalid), 2)):
                plan, detail, observed = compare(scores=scores)
                self.assertIs(plan, BASE)
                self.assertEqual(detail['score_evidence'], 'unknown')
                self.assertEqual(detail['oracle_requests'], request_count)
                self.assertEqual(len(observed), request_count)


if __name__ == '__main__':
    unittest.main()
