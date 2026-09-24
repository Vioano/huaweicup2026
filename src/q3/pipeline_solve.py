"""Calendar router plus one guarded shared-input pipeline construction.

The additional proposal solves a contiguous minimax partition directly, rather
than searching submitted schedules. The same invocation computes the calendar
incumbent. At most three E0 calls including that incumbent, all timed online.
"""
import hashlib

from . import calendar_solve
from .construct import ROOT, UnsupportedStructure
from .pipe_bound import UnsupportedBound, analyze
from .safe_solve import encoded, main as run_solver
from .shared_pipeline import construct
from evaluation_validation import EvaluationValidationError, read_required_settings


def evaluate_candidates(index, cores, evaluate, save):
    winner, calls, records, selection = calendar_solve.evaluate_candidates(
        index, cores, evaluate, save)
    if cores == 1:
        return winner, calls, records, selection
    try:
        proposal, metadata = construct(index, cores)
    except UnsupportedStructure:
        return winner, calls, records, selection
    if calls > 2:
        raise AssertionError("calendar incumbent exceeded its two-call contract")
    strategy = "shared_input_pipeline"
    metadata = {**metadata, "strategy": strategy}
    record = {"name": "shared_pipeline", "strategy": strategy,
              "metadata": metadata, "makespan": None}
    selection = {**selection, "shared_pipeline_policy": {
        "rule": "one_guarded_contiguous_minimax_partition",
        "candidate_e0_limit": 1, "total_e0_limit": 3,
        "acceptance": "strictly_lower_official_makespan_than_fresh_calendar",
        "previous_evaluation_calls": calls,
        "evaluation_calls": calls,
    }}
    if encoded(proposal) == encoded(winner[0]):
        return winner, calls, records + [{**record, "status": "duplicate"}], selection
    config = ROOT / "data/raw/a/official/data/config.txt"
    delay = read_required_settings(config, "multicore_scene_b",
                                  ("cross_core_copy_delay_cycles",))["cross_core_copy_delay_cycles"]
    try:
        lower = analyze(index.graph, proposal, delay)["with_cross_core_delay"]["lower_bound_cycles"]
        record["certified_lower_bound_cycles"] = lower
        if lower >= winner[1]["makespan"]:
            record.update(status="bound_pruned", unscored_plan=proposal,
                          unscored_plan_sha256=hashlib.sha256(encoded(proposal)).hexdigest())
            return winner, calls, records + [record], selection
    except UnsupportedBound as error:
        record["bound_unavailable"] = str(error)
    calls += 1
    selection["shared_pipeline_policy"]["evaluation_calls"] = calls
    try:
        result = evaluate(proposal)
    except EvaluationValidationError as error:
        return winner, calls, records + [{**record, "status": "rejected", "reason": str(error)}], selection
    artifacts = save("shared_pipeline", proposal, result) or {}
    records = records + [{**record, "status": "ok", "makespan": result["makespan"],
                          "artifacts": artifacts}]
    if result["makespan"] < winner[1]["makespan"]:
        winner = proposal, result, strategy
    return winner, calls, records, selection


def main():
    return run_solver(policy=evaluate_candidates, candidate_limit=3)


if __name__ == "__main__":
    main()
