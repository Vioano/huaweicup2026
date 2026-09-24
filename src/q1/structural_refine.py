"""Experimental structural refinement of the variable response wrapper.

One frozen parent solve, then at most two distinct guarded intact candidates.
E1 is online selection only; no E0 or general quality certificate is implied.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import time

from src.q1 import intact_frontier, response_refine, unified
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order

MODES = ("paced", "root-heavy-fused")


def _digest(plan):
    return hashlib.sha256(unified.plan_bytes(plan)).hexdigest()


def _scored_parent(plan, info):
    digest = _digest(plan)
    if info.get("selected") == "variable-packet-refinement":
        r = info.get("refinement", {})
        score = r.get("score", {})
        if r.get("candidate_plan_sha256") == digest and score.get("status") == "ok":
            try:
                response_refine.objective(score)
                return score, "variable-refinement-score"
            except (KeyError, TypeError):
                pass
        return None, "variable-refinement-score-missing"
    base = info.get("baseline", {}).get("diagnostics", {})
    matches = [r for r in base.get("online_scores", [])
               if r.get("name") == info.get("selected") and
               r.get("plan_sha256") == digest and r.get("status") == "ok"]
    if len(matches) == 1:
        try:
            response_refine.objective(matches[0])
            return matches[0], "baseline-online-score"
        except (KeyError, TypeError):
            pass
    return None, "baseline-online-score-missing"


def _total_calls(base, extra):
    parts = [base.get("baseline", {}).get("actual_e1_calls"),
             base.get("refinement", {}).get("actual_e1_calls"), extra]
    return sum(parts) if all(type(x) is int for x in parts) else None


def solve(graph, cores, *, parent_solve=None, recognizer=None,
          constructor=None, validator=None, scorer=None):
    started = time.perf_counter()
    parent_solve = parent_solve or (lambda g, k: response_refine.solve(g, k, refiner="variable"))
    recognizer = recognizer or intact_frontier.recognize
    constructor = constructor or intact_frontier.construct
    validator = validator or (lambda g, p: validate_task_order(derive_multicore_plan(g, p)))
    plan, parent = parent_solve(graph, cores)
    parent_finished = time.perf_counter()
    score, source = _scored_parent(plan, parent)
    info = dict(algorithm_id="q1-structural-refine-experimental",
                variant="variable-parent-then-intact-two-v1", parent=parent,
                parent_score_source=source, parent_objective=(
                    list(response_refine.objective(score)) if score else None),
                selected=parent.get("selected"), extra=[],
                budget=dict(max_additional_e1_calls=2, workers=1,
                            per_item_timeout_seconds=60),
                extra_score_attempts=0, extra_actual_e1_calls=0,
                scope="Research entry; E1 selection is not official E0 acceptance")
    if score is None:
        info["stop_reason"] = "no-matching-parent-score"
    elif type(cores) is not int or cores < 2:
        info["stop_reason"] = "single-core-or-invalid"
    else:
        try:
            recognizer(graph)
        except intact_frontier.UnsupportedStructure as exc:
            info.update(stop_reason="outside-strict-intact-family", guard_reason=str(exc))
        except Exception as exc:
            info.update(stop_reason="guard-failed", guard_error_type=type(exc).__name__,
                        guard_reason=str(exc))
        else:
            seen = {_digest(plan)}
            with ExitStack() as stack:
                if scorer is None:
                    from src.eval_exact import P1BatchEvaluator, read_config
                    config = read_config(unified.CONFIG)
                    evaluator = None

                    def score_candidate(g, candidate):
                        nonlocal evaluator
                        if evaluator is None:
                            evaluator = stack.enter_context(P1BatchEvaluator(
                                g, workers=1, cache_bytes=16 << 20,
                                timeout_seconds=60, startup_timeout_seconds=10,
                                max_tasks_per_worker=2))
                        return next(evaluator.evaluate_batch([candidate], full=False, **config))
                else:
                    score_candidate = scorer
                for mode in MODES:
                    row = dict(mode=mode, constructor_attempted=True)
                    info["extra"].append(row)
                    begun = time.perf_counter()
                    try:
                        candidate, details = constructor(graph, cores, mode)
                        if set(candidate) != {"node_to_subgraph", "core_schedules"} or len(candidate["core_schedules"]) != cores:
                            raise ValueError("candidate must have two plan keys and requested core count")
                        validator(graph, candidate)
                        row["constructor_diagnostics"] = details
                        digest = _digest(candidate)
                        row["plan_sha256"] = digest
                        row["construction_validation_seconds"] = time.perf_counter() - begun
                    except Exception as exc:
                        row.update(status="construction-or-validation-failed",
                                   error_type=type(exc).__name__, error_message=str(exc),
                                   construction_validation_seconds=time.perf_counter() - begun)
                        info["stop_reason"] = "candidate-failed"
                        break
                    if digest in seen:
                        row["status"] = "duplicate-plan"
                        continue
                    seen.add(digest)
                    row["score_attempted"] = True
                    info["extra_score_attempts"] += 1
                    info["extra_actual_e1_calls"] = None
                    score_start = time.perf_counter()
                    try:
                        tested = score_candidate(graph, candidate)
                        row["score"] = tested
                        row["score_wall_seconds"] = time.perf_counter() - score_start
                        if all(r.get("score", {}).get("worker_pid") is not None
                               for r in info["extra"] if r.get("score_attempted")):
                            info["extra_actual_e1_calls"] = sum(
                                int(r.get("score", {}).get("worker_pid") is not None)
                                for r in info["extra"] if r.get("score_attempted"))
                        if tested.get("status") != "ok":
                            row["status"] = "score-failed"
                            info["stop_reason"] = "score-failed"
                            break
                        objective = response_refine.objective(tested)
                    except Exception as exc:
                        row.update(status="score-failed", error_type=type(exc).__name__,
                                   error_message=str(exc),
                                   score_wall_seconds=time.perf_counter() - score_start)
                        info["stop_reason"] = "score-failed"
                        break
                    if objective < response_refine.objective(score):
                        plan, score = candidate, tested
                        info["selected"] = f"intact-{mode}"
                        row["status"] = "strict-improvement"
                    else:
                        row["status"] = "no-strict-improvement"
                else:
                    info["stop_reason"] = "both-modes-considered"
    info["selected_plan_sha256"] = _digest(plan)
    info["selected_objective"] = list(response_refine.objective(score)) if score else None
    info["actual_e1_calls_total"] = _total_calls(parent, info["extra_actual_e1_calls"])
    info["known_e1_calls_lower_bound"] = sum(
        x for x in (parent.get("baseline", {}).get("actual_e1_calls"),
                    parent.get("refinement", {}).get("actual_e1_calls"),
                    info["extra_actual_e1_calls"]) if type(x) is int)
    info["parent_wall_seconds"] = parent_finished - started
    info["extra_wall_seconds"] = time.perf_counter() - parent_finished
    info["solve_function_seconds"] = time.perf_counter() - started
    return plan, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("refuse to overwrite solver artifacts")
    started = time.perf_counter()
    plan, info = solve(json.loads(args.graph.read_bytes()), args.cores)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as out:
        out.write(unified.plan_bytes(plan))
        out.flush()
        os.fsync(out.fileno())
    info["cli_before_diagnostics_write_seconds"] = time.perf_counter() - started
    with args.diagnostics.open("x", encoding="utf-8") as out:
        json.dump(info, out, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    print(json.dumps(dict(event="solver_completed", selected=info["selected"],
                          cli_read_to_outputs_fsync_seconds=time.perf_counter() - started)), flush=True)


if __name__ == "__main__":
    main()
