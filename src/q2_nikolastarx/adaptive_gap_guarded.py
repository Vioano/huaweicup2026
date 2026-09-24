"""Bounded P2 full-plan comparison of adaptive_budget and join/gap candidate.

The candidate is selected only on strict native E2 (Makespan, added DDR) gain.
No heuristic DDR lower-bound pruning or downstream plan repair is performed.
"""
from __future__ import annotations

from . import adaptive_budget, gap_candidate, guarded_component


def build(graph, cores, config, oracle):
    baseline, base_detail = adaptive_budget.build(graph, cores, config)
    detail = {
        'selected_strategy': 'adaptive_budget',
        'baseline_detail': base_detail,
        'candidate_detail': None,
        'constructed_plans': 1,
        'oracle_requests': 0,
        'selected': 'baseline',
        'score_scope': 'complete final plans returned by both constructors; no downstream repair',
        'score_evidence': 'not_requested',
    }
    try:
        candidate, candidate_detail = gap_candidate.build(graph, cores, config)
    except Exception as error:
        detail.update(reason='candidate_construction_failed', candidate_error=repr(error))
        return baseline, detail
    detail.update(candidate_detail=candidate_detail, constructed_plans=2)
    if candidate == baseline:
        detail['reason'] = 'identical_complete_plans'
        return baseline, detail
    detail['oracle_requests'] += 1
    try:
        base_score = guarded_component._score(oracle, baseline)
    except Exception as error:
        detail.update(reason='baseline_score_unavailable', score_evidence='unknown',
                      baseline_error=repr(error))
        return baseline, detail
    detail['baseline_score'] = list(base_score)
    detail['oracle_requests'] += 1
    try:
        candidate_score = guarded_component._score(oracle, candidate)
    except Exception as error:
        detail.update(reason='candidate_score_unavailable', score_evidence='unknown',
                      candidate_error=repr(error))
        return baseline, detail
    detail['candidate_score'] = list(candidate_score)
    detail['score_evidence'] = 'injected_oracle_complete_plan_scores'
    if candidate_score < base_score:
        detail.update(selected='candidate', selected_strategy='join_gap_candidate',
                      reason='strict_lexicographic_improvement')
        return candidate, detail
    detail['reason'] = 'baseline_wins_or_ties'
    return baseline, detail


def main(argv=None):
    from .adaptive_guarded import main as guarded_main
    guarded_main(argv, constructor=build)


if __name__ == '__main__':
    main()
