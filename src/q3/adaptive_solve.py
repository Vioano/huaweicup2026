"""One structural router: a direct stage plan, otherwise the unchanged guard policy.

Stage routing uses only the compute graph and core count. Exactly two heaviest
lane cores request rotation; all other lane-load patterns request fixed gather.
Only the full stage constructor can confirm that this interpretation is valid.
The stage route has one candidate and one online E0 call, with no old-anchor
non-regression promise. Non-stage inputs retain guarded_solve's own policy.
"""
from .construct import UnsupportedStructure
from .guarded_solve import evaluate_candidates as guarded_candidates
from .safe_solve import main as run_solver
from .stage_fork_join import construct as stage_construct


def stage_request(index, cores):
    """Cheap provisional lane counts; not a substitute for stage recognition."""
    if type(cores) is not int or cores < 1:
        raise ValueError("positive integer cores required")
    sources = sum(not index.pred[u] for u in index.ops)
    counts = [0] * cores
    for j in range(sources):
        counts[min(cores - 1, j * cores // sources)] += 1
    maximum = max(counts)
    heavy = [core for core, count in enumerate(counts) if count and count == maximum]
    return {
        "collector_policy": "rotate_heavy" if len(heavy) == 2 else "fixed",
        "source_count": sources,
        "lanes_by_core": counts,
        "heaviest_lane_cores": heavy,
        "feature_scope": "Provisional source-count partition; lane/load meaning is confirmed only by the strict stage guard.",
    }


def evaluate_candidates(index, cores, evaluate, save):
    request = stage_request(index, cores)
    try:
        # One construction attempt, not fixed-plan construction followed by a
        # second rotated-plan construction. The constructor performs its full
        # tensor-port / repeated-stage guard before emitting a plan.
        plan, metadata = stage_construct(index, cores, collector_policy=request["collector_policy"])
    except UnsupportedStructure as error:
        # Only a declared guard rejection changes routes. Constructor defects,
        # evaluator errors and save failures must not become silent fallbacks.
        winner, calls, records, selection = guarded_candidates(index, cores, evaluate, save)
        routing = {"route": "guarded", "stage_guard_reason": str(error),
                   "stage_request": request, "stage_construct_attempts": 1,
                   "stage_candidate_plans": 0, "guarded_policy_invocations": 1,
                   "route_e0_limit": 2, "evaluation_calls": calls,
                   "count_scope": "Router attempts only; guarded internal construction/decision records are preserved unchanged."}
        return winner, calls, records, {**selection, "router": routing}

    if metadata["lane_count"] != request["source_count"]:
        raise AssertionError("recognized stage lane count differs from provisional source count")
    policy = request["collector_policy"]
    routing = {"route": "stage", "stage_request": request,
               "stage_construct_attempts": 1, "stage_candidate_plans": 1,
               "guarded_policy_invocations": 0, "route_e0_limit": 1,
               "evaluation_calls": 1,
               "count_scope": "One successful stage construction and one injected online evaluation; no anchor comparison."}
    result = evaluate(plan)
    artifacts = save("seed", plan, result) or {}
    metadata = {**metadata, "route": "stage", "collector_policy": policy,
                "collector_cycle": metadata.get("collector_cycle", [metadata["collector_core"]]),
                "router": routing,
                "construction_note": "metadata.official_e0_calls=0 describes the static constructor only; this saved candidate received one online evaluation."}
    records = [{"name": "seed", "strategy": metadata["strategy"], "status": "ok",
                "makespan": result["makespan"], "metadata": metadata, "artifacts": artifacts}]
    selection = {"rule": "strict_stage_guard_then_lane_load_collector", "router": routing}
    return (plan, result, metadata["strategy"]), 1, records, selection


def main():
    return run_solver(policy=evaluate_candidates)


if __name__ == "__main__":
    main()
