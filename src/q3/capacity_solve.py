"""Fresh forest incumbent plus one guarded L1-capacity pipeline proposal.

All construction, bounds and official evaluations run inside one timed solver
invocation. The proposal is evaluated only when it could strictly improve the
incumbent Makespan; at most four online E0 calls occur in total.
"""
import hashlib

from . import forest_solve
from .construct import ROOT, UnsupportedStructure
from .pipe_bound import UnsupportedBound, analyze
from .safe_solve import encoded, main as run_solver
from .shared_pipeline_capacity import construct
from evaluation_validation import EvaluationValidationError, read_required_settings


STRATEGY = "capacity_shared_pipeline"


def evaluate_candidates(index, cores, evaluate, save):
    """One structure-derived proposal after the complete fresh forest policy."""
    previously_evaluated = set()
    prior_calls = 0

    def count_evaluation(plan):
        nonlocal prior_calls
        if prior_calls >= 3:
            raise AssertionError("fresh forest exceeded its three-call contract")
        prior_calls += 1
        previously_evaluated.add(encoded(plan))
        return evaluate(plan)

    winner, calls, records, selection = forest_solve.evaluate_candidates(
        index, cores, count_evaluation, save)
    if calls != prior_calls:
        raise AssertionError("fresh forest E0 call count differs from submitted calls")
    if calls > 3:
        raise AssertionError("fresh forest exceeded its three-call contract")
    policy = {
        "rule": "one_guarded_l1_capacity_contiguous_partition_after_fresh_forest",
        "strategy": STRATEGY, "candidate_e0_limit": 1, "total_e0_limit": 4,
        "previous_evaluation_calls": calls, "evaluation_calls": calls,
        "acceptance": "strictly_lower_official_makespan_than_fresh_forest",
    }
    selection = {**selection, "capacity_pipeline_policy": policy}
    try:
        proposal, metadata = construct(index, cores)
    except UnsupportedStructure as error:
        policy.update(status="skip", skip_reason=str(error))
        return winner, calls, records, selection
    metadata = {**metadata, "strategy": STRATEGY}
    record = {"name": STRATEGY, "strategy": STRATEGY,
              "metadata": metadata, "makespan": None}
    policy["status"] = "constructed"
    payload = encoded(proposal)
    if payload in previously_evaluated:
        policy["status"] = "duplicate"
        return winner, calls, records + [{**record, "status": "duplicate"}], selection

    config = ROOT / "data/raw/a/official/data/config.txt"
    delay = read_required_settings(
        config, "multicore_scene_b", ("cross_core_copy_delay_cycles",)
    )["cross_core_copy_delay_cycles"]
    try:
        lower = analyze(index.graph, proposal, delay)["with_cross_core_delay"]["lower_bound_cycles"]
        record["certified_lower_bound_cycles"] = lower
        if lower >= winner[1]["makespan"]:
            record.update(status="bound_pruned", unscored_plan=proposal,
                          unscored_plan_sha256=hashlib.sha256(payload).hexdigest())
            policy.update(status="bound_pruned", lower_bound_cycles=lower)
            return winner, calls, records + [record], selection
    except UnsupportedBound as error:
        record["bound_unavailable"] = str(error)

    calls += 1
    policy.update(status="evaluating", evaluation_calls=calls)
    try:
        result = evaluate(proposal)
    except EvaluationValidationError as error:
        record.update(status="rejected", reason=str(error))
        policy["status"] = "rejected"
        return winner, calls, records + [record], selection
    artifacts = save(STRATEGY, proposal, result) or {}
    record.update(status="ok", makespan=result["makespan"], artifacts=artifacts)
    policy["status"] = "evaluated"
    if result["makespan"] < winner[1]["makespan"]:
        winner = proposal, result, STRATEGY
        policy["status"] = "accepted"
    return winner, calls, records + [record], selection


def main():
    return run_solver(policy=evaluate_candidates, candidate_limit=4)


if __name__ == "__main__":
    main()
