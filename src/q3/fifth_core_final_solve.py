"""One guarded contiguous fifth-core proposal after a fresh forest incumbent.

The constructor, all scoring, and both paired comparisons run online. No
case-number dispatch or historical plan is used by this entrypoint.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from . import fifth_core_contiguous, forest_solve
from .construct import Index, ROOT, UnsupportedStructure
from .pipe_bound import UnsupportedBound, analyze
from .safe_solve import encoded
from .solve import publish_new
from evaluation_validation import EvaluationValidationError


def evaluate_candidates(index, cores, evaluate_p3, evaluate_p2, save,
                        *, construct=None, bound=None, save_unscored=None,
                        cross_delay=0, capacity=None):
    """Return winner, P3/P2 call counts, records, selection; callbacks count first.

    Injecting construct/bound/evaluators permits policy tests without a graph
    construction or official scoring call. An unexpected exception propagates;
    the adapter's pre-dispatch ledger retains the failed call.
    """
    construct = fifth_core_contiguous.construct if construct is None else construct
    bound = analyze if bound is None else bound
    winner, p3_calls, records, selection = forest_solve.evaluate_candidates(
        index, cores, evaluate_p3, lambda name, plan, result: save("p3", name, plan, result))
    if not 1 <= p3_calls <= 3:
        raise RuntimeError("forest incumbent exceeded or omitted P3 calls")
    old_plan, old_p3, _ = winner
    policy = {"strategy": "component_contiguous_extra_core", "p3_calls": p3_calls,
              "p2_calls": 0, "acceptance": "M3 strict, M2 nonworse, G nonworse"}
    selection = {**selection, "fifth_core_policy": policy}
    if cores != 5:
        policy.update(status="skip", reason="requires_five_cores")
        return winner, p3_calls, 0, records, selection
    record = {"name": "component_contiguous_extra_core", "status": "unstarted"}
    try:
        proposal, meta, _ = construct(index.graph, cores, capacity, cross_delay)
    except UnsupportedStructure as error:
        policy.update(status="unsupported", reason=str(error))
        return winner, p3_calls, 0, records + [{**record, "status": "unsupported",
                                                 "reason": str(error)}], selection
    record["metadata"] = meta
    if save_unscored is not None:
        record["proposal_plan"] = save_unscored(proposal)
    if encoded(proposal) == encoded(old_plan):
        policy["status"] = record["status"] = "duplicate"
        return winner, p3_calls, 0, records + [record], selection
    try:
        lower = bound(index.graph, proposal, cross_delay)[
            "with_cross_core_delay"]["lower_bound_cycles"]
        record["certified_lower_bound_cycles"] = lower
        if lower >= old_p3["makespan"]:
            policy["status"] = record["status"] = "bound_pruned"
            record["unscored_plan_sha256"] = hashlib.sha256(encoded(proposal)).hexdigest()
            return winner, p3_calls, 0, records + [record], selection
    except UnsupportedBound as error:
        record["bound_unavailable"] = str(error)

    p3_calls += 1
    policy["p3_calls"] = p3_calls
    try:
        new_p3 = evaluate_p3(proposal)
    except EvaluationValidationError as error:
        policy["status"] = record["status"] = "p3_rejected"
        record["reason"] = str(error)
        return winner, p3_calls, 0, records + [record], selection
    record["p3"] = {"makespan": new_p3["makespan"],
                    "artifacts": save("p3", "fifth_core", proposal, new_p3) or {}}
    if new_p3["makespan"] >= old_p3["makespan"]:
        policy["status"] = record["status"] = "m3_not_better"
        return winner, p3_calls, 0, records + [record], selection

    # Only a strict M3 gain authorizes the two same-plan P2 calls.
    p2_calls = 0
    for label, plan in (("incumbent", old_plan), ("fifth_core", proposal)):
        p2_calls += 1
        policy["p2_calls"] = p2_calls
        try:
            p2_result = evaluate_p2(plan)
        except EvaluationValidationError as error:
            policy["status"] = record["status"] = "p2_rejected"
            record["reason"] = str(error)
            return winner, p3_calls, p2_calls, records + [record], selection
        record[label + "_p2"] = {"makespan": p2_result["makespan"],
                                "artifacts": save("p2", label, plan, p2_result) or {}}
    m20, m21 = (record[key + "_p2"]["makespan"] for key in ("incumbent", "fifth_core"))
    m30, m31 = old_p3["makespan"], new_p3["makespan"]
    if any(type(value) is not int or value <= 0 for value in (m20, m21, m30, m31)):
        raise ValueError("official paired Makespan must be positive integer cycles")
    record["m2_nonworse"] = m21 <= m20
    record["g_nonworse"] = m21 * m30 >= m20 * m31
    if record["m2_nonworse"] and record["g_nonworse"]:
        winner = proposal, new_p3, meta["rule"]
        policy["status"] = record["status"] = "accepted"
    else:
        policy["status"] = record["status"] = "paired_gate_rejected"
    return winner, p3_calls, p2_calls, records + [record], selection


def main():
    start = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.evidence.exists():
        raise FileExistsError("output and evidence must be new paths")
    raw_graph = args.graph.read_bytes()
    index = Index(json.loads(raw_graph))
    config = ROOT / "data/raw/a/official/data/config.txt"
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config
    base = read_evaluation_config(config)
    delay = read_scene_b_config(config)["cross_core_copy_delay_cycles"]
    p2_settings = {**base, "cross_core_copy_delay": delay}
    p3_settings = {**p2_settings, **read_cache_config(config)}
    args.evidence.mkdir(parents=True, exist_ok=False)
    ledger = []

    def record_ledger():
        (args.evidence / "evaluations.json").write_bytes(encoded(ledger))

    def evaluate(phase, plan):
        if sum(item["phase"] == phase for item in ledger) >= (4 if phase == "p3" else 2):
            raise RuntimeError("declared online E0 budget exceeded")
        ordinal = len(ledger)
        plan_bytes = encoded(plan)
        (args.evidence / f"evaluated-plan-{ordinal}-{phase}.json").write_bytes(plan_bytes)
        entry = {"ordinal": ordinal, "phase": phase, "status": "started",
                 "plan_sha256": hashlib.sha256(plan_bytes).hexdigest()}
        ledger.append(entry)
        record_ledger()  # Reserve before any official call, including failures.
        t0 = time.perf_counter()
        try:
            result = (evaluate_problem_3(index.graph, plan, **p3_settings) if phase == "p3"
                      else evaluate_scene_b(index.graph, plan, **p2_settings))
        except BaseException as error:
            entry.update(status="failed", error_type=type(error).__name__,
                         reason=str(error), seconds=time.perf_counter() - t0)
            record_ledger()
            raise
        entry.update(status="ok", seconds=time.perf_counter() - t0)
        record_ledger()
        return result

    def save(phase, name, plan, result):
        folder = args.evidence / f"{phase}-{name}"
        folder.mkdir(exist_ok=False)
        plan_bytes = encoded(plan)
        result_bytes = gzip.compress(encoded(result), mtime=0)
        (folder / "plan.json").write_bytes(plan_bytes)
        (folder / "result.json.gz").write_bytes(result_bytes)
        return {"plan": {"path": f"{folder.name}/plan.json",
                         "sha256": hashlib.sha256(plan_bytes).hexdigest()},
                "result": {"path": f"{folder.name}/result.json.gz",
                           "sha256": hashlib.sha256(result_bytes).hexdigest()}}

    def save_unscored(plan):
        plan_bytes = encoded(plan)
        path = args.evidence / "fifth-core-proposal.json"
        path.write_bytes(plan_bytes)
        return {"path": path.name, "sha256": hashlib.sha256(plan_bytes).hexdigest()}

    try:
        winner, p3_calls, p2_calls, candidates, selection = evaluate_candidates(
            index, args.cores, lambda plan: evaluate("p3", plan),
            lambda plan: evaluate("p2", plan), save,
            save_unscored=save_unscored, cross_delay=delay, capacity=base["capacity"])
        plan, result, strategy = winner
        if set(plan) != {"node_to_subgraph", "core_schedules"}:
            raise ValueError("selected plan must contain only the two submission fields")
        payload = encoded(plan)
        result_bytes = gzip.compress(encoded(result), mtime=0)
        receipt = {"status": "complete", "strategy": strategy, "selection": selection,
                   "candidates": candidates, "official_p3_calls": p3_calls,
                   "official_p2_calls": p2_calls, "official_e0_calls": len(ledger),
                   "limits": {"p3": 4, "p2": 2, "total_e0": 6},
                   "makespan": result["makespan"],
                   "graph_sha256": hashlib.sha256(raw_graph).hexdigest(),
                   "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
                   "plan_sha256": hashlib.sha256(payload).hexdigest(),
                   "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
                   "evaluation_seconds": sum(e["seconds"] for e in ledger),
                   "main_until_evidence_seconds": time.perf_counter() - start,
                   "timing_note": "Use outer subprocess wall for full solver time; cold/warm cache state must be measured separately. All construction and E0 calls are online."}
        (args.evidence / "result.json.gz").write_bytes(result_bytes)
        (args.evidence / "receipt.json").write_bytes(encoded(receipt))
        publish_new(args.output, payload)
        print(json.dumps(receipt))
    except BaseException as error:
        (args.evidence / "receipt.json").write_bytes(encoded({
            "status": "failed", "error_type": type(error).__name__,
            "reason": str(error), "official_e0_calls": len(ledger),
            "main_until_evidence_seconds": time.perf_counter() - start}))
        raise


if __name__ == "__main__":
    main()
