"""Fixed P2 portfolio of complete, structurally distinct plans.

The old guarded route is the incumbent. Construction proxies never decide the
winner: only the injected complete-plan oracle supplies (Makespan, added DDR).
"""
from __future__ import annotations

from . import (adaptive_hypergap_guarded, fixed_owner_reverse, gap_candidate,
               latency_hyperrefine, reverse_gap_candidate)
from .adaptive_guarded import main as guarded_main
from .guarded_component import _score


_LIMIT = 6


def build(graph, cores, config, oracle):
    cache = []  # valid results only: (plan, score, raw response)
    requests = cache_hits = 0

    def find(plan):
        return next((i for i, (prior, _, _) in enumerate(cache) if plan == prior), None)

    def recorded_oracle(plan):
        nonlocal requests, cache_hits
        index = find(plan)
        if index is not None:
            cache_hits += 1
            return cache[index][2]
        if requests >= _LIMIT:
            raise RuntimeError('six distinct complete-plan oracle starts exhausted')
        requests += 1
        response = oracle(plan)
        score = _score(lambda _: response, plan)
        cache.append((plan, score, response))
        return response

    incumbent, old_detail = adaptive_hypergap_guarded.build(
        graph, cores, config, recorded_oracle)
    detail = {
        'selected': 'incumbent', 'selected_strategy': old_detail.get('selected_strategy'),
        'selected_score_id': None, 'reason': 'incumbent_retained',
        'score_evidence': old_detail.get('score_evidence', 'unknown'),
        'score_scope': 'complete final constructor plans; no downstream repair',
        'incumbent_detail': old_detail, 'candidates': {}, 'scores': {},
        'oracle_requests': requests, 'oracle_request_limit': _LIMIT,
        'cache_hits': cache_hits, 'unique_scored_plans': len(cache),
        'constructed_plans': old_detail.get('constructed_plans', 1),
    }

    def finish(plan):
        detail['oracle_requests'] = requests
        detail['cache_hits'] = cache_hits
        detail['unique_scored_plans'] = len(cache)
        return plan, detail

    if cores < 2:
        detail['reason'] = 'single_core_no_portfolio'
        return finish(incumbent)
    if old_detail.get('score_evidence', 'unknown') == 'unknown':
        detail['reason'] = 'incumbent_score_evidence_unknown'
        return finish(incumbent)

    best_plan, best_label, best_score = incumbent, 'incumbent', None
    constructed = [('incumbent', incumbent)]
    candidates = (
        ('fixed_owner', lambda: fixed_owner_reverse.retime(graph, incumbent, config)),
        ('reverse_gap', lambda: reverse_gap_candidate.build(graph, cores, config)),
        ('latency_hyperrefine', lambda: latency_hyperrefine.build(
            graph, gap_candidate.build(graph, cores, config)[0], config,
            region_width=16)),
    )
    for label, constructor in candidates:
        record = detail['candidates'][label] = {'status': 'not_started'}
        try:
            plan, construction_detail = constructor()
        except Exception as error:
            record.update(status='construction_unavailable', error=repr(error))
            continue
        detail['constructed_plans'] += 1
        record['construction_detail'] = construction_detail
        duplicate = next((prior_label for prior_label, prior in constructed if plan == prior), None)
        if duplicate is not None:
            record.update(status='duplicate', duplicate_of=duplicate)
            continue
        constructed.append((label, plan))
        if best_score is None:
            try:
                best_score = _score(recorded_oracle, incumbent)
            except Exception as error:
                record.update(status='incumbent_score_unavailable', error=repr(error))
                detail.update(reason='score_unavailable', score_evidence='unknown')
                return finish(incumbent)
            index = find(incumbent)
            detail['scores']['incumbent'] = list(best_score)
            detail['selected_score_id'] = index + 1
        try:
            candidate_score = _score(recorded_oracle, plan)
        except Exception as error:
            record.update(status='candidate_score_unavailable', error=repr(error))
            detail.update(reason='score_unavailable', score_evidence='unknown',
                          selected='incumbent', selected_strategy=old_detail.get('selected_strategy'),
                          selected_score_id=find(incumbent) + 1 if find(incumbent) is not None else None)
            return finish(incumbent)
        index = find(plan)
        record.update(status='scored', score=list(candidate_score), score_id=index + 1)
        detail['scores'][label] = list(candidate_score)
        if candidate_score < best_score:
            best_plan, best_label, best_score = plan, label, candidate_score
            detail.update(selected=label, selected_strategy=label,
                          selected_score_id=index + 1,
                          reason='strict_lexicographic_improvement')
    if best_label == 'incumbent':
        detail['reason'] = 'incumbent_wins_or_ties'
    if best_score is not None:
        detail['score_evidence'] = 'injected_oracle_complete_plan_scores'
    return finish(best_plan)


def main(argv=None):
    guarded_main(argv, constructor=build, oracle_request_limit=_LIMIT)


if __name__ == '__main__':
    main()
