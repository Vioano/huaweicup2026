"""Preserve an attention placement witness when ready reranking worsens its proxy.

Exactly one deterministic word is proposed, only after a fresh incumbent and
strict proxy-gap screen. Real acceptance uses official M; at most three online
E0 calls total, including any shared-input pipeline comparison.
"""
import hashlib

from . import pipeline_solve
from .attention_rows import construct
from .pipe_bound import UnsupportedBound, analyze
from .safe_solve import encoded, main as run_solver
from evaluation_validation import EvaluationValidationError


def evaluate_candidates(index, cores, evaluate, save):
    winner, calls, records, selection = pipeline_solve.evaluate_candidates(
        index, cores, evaluate, save)
    route = selection.get("router", {})
    if route.get("route") != "attention" or cores == 1:
        return winner, calls, records, selection
    if calls >= 3:
        return winner, calls, records, {**selection, "witness_skip": "three_call_budget_already_used"}
    gap = next((r["metadata"] for r in records if r["name"] == "attention_gap"), None)
    if gap is None:
        raise AssertionError("multi-core attention route lacks its gap construction record")
    if gap["placement_proxy_makespan_cycles"] >= gap["proxy_makespan_cycles"]:
        return winner, calls, records, {**selection, "witness_skip": "placement_witness_not_strictly_better_proxy"}
    delay = route["attention_cross_delay_cycles"]
    proposal, metadata = construct(index, cores, cross_delay=delay, pack_ffn=True,
                                   placement_mode="gap", final_order="placement")
    if metadata["placement_proxy_makespan_cycles"] != gap["placement_proxy_makespan_cycles"]:
        raise AssertionError("witness construction changed the frozen placement")
    record = {"name": "attention_witness", "strategy": metadata["strategy"],
              "metadata": metadata, "makespan": None}
    selection = {**selection, "witness_policy": {
        "screen": "committed_placement_proxy_strictly_below_ready_proxy",
        "total_e0_limit": 3, "evaluation_calls": calls,
        "acceptance": "strictly_lower_official_makespan_than_fresh_incumbent"}}
    if encoded(proposal) == encoded(winner[0]):
        return winner, calls, records + [{**record, "status": "duplicate"}], selection
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
    selection["witness_policy"]["evaluation_calls"] = calls
    try:
        result = evaluate(proposal)
    except EvaluationValidationError as error:
        return winner, calls, records + [{**record, "status": "rejected", "reason": str(error)}], selection
    refs = save("attention_witness", proposal, result) or {}
    records = records + [{**record, "status": "ok", "makespan": result["makespan"], "artifacts": refs}]
    if result["makespan"] < winner[1]["makespan"]:
        winner = proposal, result, metadata["strategy"]
    return winner, calls, records, selection


def main():
    return run_solver(policy=evaluate_candidates, candidate_limit=3)


if __name__ == "__main__":
    main()
