"""Injected budget/acceptance checks and archived-plan reproduction; no E0."""
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.q3 import band_lookahead_solve as solver
from src.q3.construct import Index
from src.q3.safe_solve import encoded
from evaluation_validation import EvaluationValidationError

ROOT = Path(__file__).resolve().parents[2]
ANCHOR = {'node_to_subgraph': {'1': 0}, 'core_schedules': [[0], []]}
PROPOSAL = {'node_to_subgraph': {'1': 0}, 'core_schedules': [[], [0]]}
META = {'strategy': 'band_pair_one_leaf_lookahead',
        'band_dp': {'strategy': 'forest_serpentine_band_quota_dp'},
        'leaf_lookahead': {'strategy': 'one_leaf_lookahead'}}


class BandLookaheadPolicyTests(unittest.TestCase):
    def run_policy(self, *, spent=2, candidate=None, proposal=PROPOSAL,
                   lower=1, bound_error=None, construct_error=None):
        responses = [{'makespan': 100}] * spent
        if candidate is not None:
            responses.append(candidate)
        evaluate = Mock(side_effect=responses)

        def incumbent(index, cores, evaluate_fn, save):
            for _ in range(spent):
                evaluate_fn(ANCHOR)
            return ((ANCHOR, {'makespan': 100}, 'fresh_forest'), spent, [],
                    {'forest_policy': {'status': 'fresh'}})

        with patch.object(solver.forest_solve, 'evaluate_candidates', side_effect=incumbent), \
             patch.object(solver, 'construct', side_effect=construct_error,
                          return_value=(proposal, META)) as make, \
             patch.object(solver, 'analyze',
                          side_effect=[bound_error] if bound_error else None,
                          return_value={'with_cross_core_delay':
                                        {'lower_bound_cycles': lower}}) as analyze, \
             patch.object(solver, 'read_required_settings',
                          return_value={'cross_core_copy_delay_cycles': 500}):
            outcome = solver.evaluate_candidates(SimpleNamespace(graph={}), 5,
                                                 evaluate, Mock(return_value={}))
        return outcome, evaluate, make, analyze

    def test_consumed_budget_does_not_construct(self):
        (winner, calls, records, selection), ev, make, _ = self.run_policy(spent=3)
        make.assert_not_called()
        self.assertEqual((winner[0], calls, ev.call_count), (ANCHOR, 3, 3))
        self.assertEqual(records, [])
        self.assertEqual(selection['band_lookahead_policy']['status'], 'skip')

    def test_duplicate_and_bound_skip_without_candidate_evaluation(self):
        (winner, calls, records, selection), ev, _, analyze = self.run_policy(proposal=ANCHOR)
        self.assertEqual((winner[0], calls, ev.call_count), (ANCHOR, 2, 2))
        self.assertEqual(records[-1]['status'], 'duplicate')
        analyze.assert_not_called()
        self.assertEqual(selection['band_lookahead_policy']['status'], 'duplicate')

        (winner, calls, records, selection), ev, _, _ = self.run_policy(lower=100)
        self.assertEqual((winner[0], calls, ev.call_count), (ANCHOR, 2, 2))
        self.assertEqual(records[-1]['status'], 'bound_pruned')
        self.assertEqual(selection['band_lookahead_policy']['status'], 'bound_pruned')

    def test_only_strictly_better_official_makespan_is_accepted(self):
        for score, accepted in ((99, True), (100, False), (101, False)):
            with self.subTest(score=score):
                (winner, calls, records, selection), ev, _, _ = self.run_policy(
                    candidate={'makespan': score}, spent=2)
                self.assertEqual((winner[0] == PROPOSAL, calls, ev.call_count),
                                 (accepted, 3, 3))
                self.assertEqual(records[-1]['makespan'], score)
                self.assertEqual(selection['band_lookahead_policy']['status'],
                                 'accepted' if accepted else 'evaluated')

    def test_validation_rejection_and_bound_unavailable(self):
        (winner, calls, records, selection), ev, _, _ = self.run_policy(
            candidate=EvaluationValidationError('invalid'), lower=1)
        self.assertEqual((winner[0], calls, ev.call_count), (ANCHOR, 3, 3))
        self.assertEqual(records[-1]['status'], 'rejected')
        self.assertEqual(selection['band_lookahead_policy']['status'], 'rejected')

        from src.q3.pipe_bound import UnsupportedBound
        (winner, calls, records, _), ev, _, _ = self.run_policy(
            candidate={'makespan': 100}, bound_error=UnsupportedBound('not covered'))
        self.assertEqual((winner[0], calls, ev.call_count), (ANCHOR, 3, 3))
        self.assertEqual(records[-1]['bound_unavailable'], 'not covered')

    def test_entrypoint_keeps_three_e0_limit(self):
        with patch.object(solver, 'run_solver') as runner:
            solver.main()
        runner.assert_called_once_with(policy=solver.evaluate_candidates, candidate_limit=3)

    def test_real_058_079_plans_match_archived_band_pair_lookahead_bytes(self):
        for case in (58, 79):
            graph = json.loads((ROOT / f'data/raw/a/official/data/case_{case:03}.json').read_text())
            index = Index(graph)
            plan, metadata = solver.construct(index, 5)
            archived = ROOT / f'results/a/q3-nikolastarx/leaf-lookahead-probe-20260925/{case:03}-band_pair/plan.json'
            self.assertEqual(encoded(plan), archived.read_bytes())
            self.assertEqual(metadata['band_dp']['tree_order_mode'], 'pair_cache_model')
            self.assertEqual(metadata['leaf_lookahead']['strategy'], 'one_leaf_lookahead')
            self.assertEqual(metadata['official_evaluations'], 0)


if __name__ == '__main__':
    unittest.main()
