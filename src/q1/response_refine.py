"""Experimental one-shot response refinement around the frozen unified P1 solver.

This is a separate CLI, not the unified production entry. It uses one packet
DP child and at most one additional E1 score only for a scored capacity-return
winner. No full-matrix acceptance or E0 claim is made.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OFFICIAL = ROOT / "data/raw/a/official/code"
if str(OFFICIAL) not in sys.path:
    sys.path.insert(0, str(OFFICIAL))

from src.q1 import unified
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order

ALGORITHM_ID = "q1-response-refine-experimental"
VARIANT = "capacity-winner-ordered-graph-auto-once-v1"
# This starts termination; process cleanup is included in measured wall time.
CHILD_LIMIT_SECONDS = 120


def objective(record):
    return record["makespan"], record["data_movement_bytes"]["scheduled_copy_bytes"]


def scored_capacity_winner(plan, info):
    """Require the actual selected plan's own successful online score."""
    if info.get("selected") != "capacity-return":
        return None
    digest = hashlib.sha256(unified.plan_bytes(plan)).hexdigest()
    matches = [r for r in info.get("online_scores", [])
               if r.get("name") == "capacity-return" and
               r.get("plan_sha256") == digest and r.get("status") == "ok"]
    if len(matches) != 1:
        return None
    try:
        objective(matches[0])
    except (KeyError, TypeError):
        return None
    return matches[0]


def validate_candidate(graph, plan):
    if not isinstance(plan, dict) or set(plan) != {"node_to_subgraph", "core_schedules"}:
        raise ValueError("packet candidate requires exactly two plan keys")
    validate_task_order(derive_multicore_plan(graph, plan))


def packet_child(graph, cores):
    """Run one bounded direct child in the wrapper's process group.

    The DP path has no descendants. An external process-group cancellation can
    therefore reach this child; local timeout kills and reaps only this child.
    """
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="q1-response-refine-") as folder:
        root = Path(folder)
        source, plan_path, diag_path = (root / x for x in ("input.json", "plan.json", "diag.json"))
        source.write_bytes((json.dumps(graph, separators=(",", ":")) + "\n").encode())
        env = os.environ.copy()
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                     "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
            env[name] = "1"
        command = [sys.executable, "-B", str(ROOT / "src/q1/packet_dp.py"), str(source),
                   "--cores", str(cores), "--output", str(plan_path),
                   "--diagnostics", str(diag_path), "--profile-cache", "ordered-graph",
                   "--state-mode", "auto"]
        with (root / "stdout.txt").open("wb") as out, (root / "stderr.txt").open("wb") as err:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out,
                                     stderr=err, env=env)
            def reap_if_running():
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=10)
            try:
                returncode = child.wait(timeout=CHILD_LIMIT_SECONDS)
            except subprocess.TimeoutExpired as exc:
                reap_if_running()
                raise TimeoutError("packet DP child exceeded 120 seconds") from exc
            finally:
                reap_if_running()
        if returncode != 0:
            raise RuntimeError(f"packet DP child exited {returncode}")
        candidate = json.loads(plan_path.read_bytes())
        details = json.loads(diag_path.read_bytes())
        return candidate, {"child_returncode": returncode,
                           "child_wall_seconds": time.perf_counter() - started,
                           "details": details}


def score_once(graph, candidate):
    from src.eval_exact import P1BatchEvaluator, read_config
    config = read_config(unified.CONFIG)
    with P1BatchEvaluator(graph, workers=1, cache_bytes=16 << 20,
                          timeout_seconds=60, startup_timeout_seconds=10,
                          max_tasks_per_worker=1) as evaluator:
        return next(evaluator.evaluate_batch([candidate], full=False, **config))


def solve(graph, cores, *, baseline_solve=None, constructor=None, scorer=None,
          validator=None, emit=None):
    """Pure one-shot controller with injectable expensive boundaries for tests."""
    started = time.perf_counter()
    baseline_solve = unified.solve if baseline_solve is None else baseline_solve
    constructor = packet_child if constructor is None else constructor
    scorer = score_once if scorer is None else scorer
    validator = validate_candidate if validator is None else validator
    base_plan, base_info = baseline_solve(graph, cores, emit=emit)
    baseline = scored_capacity_winner(base_plan, base_info)
    result = dict(algorithm_id=ALGORITHM_ID, variant=VARIANT,
                  baseline=dict(selected=base_info.get("selected"),
                                actual_e1_calls=base_info.get("actual_e1_calls"),
                                online_score_attempts=base_info.get("online_score_attempts"),
                                diagnostics=base_info),
                  refinement=dict(eligible=baseline is not None, child_attempts=0,
                                  child_wall_seconds=0.0, score_attempts=0,
                                  actual_e1_calls=0, score_wall_seconds=0.0,
                                  child_limit_seconds=CHILD_LIMIT_SECONDS,
                                  child_limit_scope="termination trigger; cleanup adds to wall time",
                                  maximum_additional_e1_calls=1),
                  selected=base_info.get("selected"),
                  scope="Experimental one-shot refinement; no full-matrix or E0 acceptance")
    refinement = result["refinement"]
    if baseline is None:
        refinement["stop_reason"] = "no-scored-capacity-winner"
        result["solve_function_seconds"] = time.perf_counter() - started
        return base_plan, result
    refinement["baseline_winner_objective"] = list(objective(baseline))
    construction_start = time.perf_counter()
    refinement["child_attempts"] = 1
    try:
        candidate, child_info = constructor(graph, cores)
        refinement["child"] = child_info
        validator(graph, candidate)
        if len(candidate["core_schedules"]) != cores:
            raise ValueError("packet candidate core count differs from request")
    except Exception as exc:
        refinement.update(stop_reason="construction-or-validation-failed",
                          error_type=type(exc).__name__, error_message=str(exc))
        refinement["child_wall_seconds"] = time.perf_counter() - construction_start
        result["solve_function_seconds"] = time.perf_counter() - started
        return base_plan, result
    refinement["child_wall_seconds"] = time.perf_counter() - construction_start
    base_bytes, candidate_bytes = unified.plan_bytes(base_plan), unified.plan_bytes(candidate)
    refinement["candidate_plan_sha256"] = hashlib.sha256(candidate_bytes).hexdigest()
    if candidate_bytes == base_bytes:
        refinement["stop_reason"] = "byte-identical-plan"
        result["solve_function_seconds"] = time.perf_counter() - started
        return base_plan, result
    score_start = time.perf_counter()
    refinement["score_attempts"] = 1
    # An exception can occur after dispatch. Until a worker PID is returned,
    # the actual count cannot be inferred from the Python call boundary.
    refinement["actual_e1_calls"] = None
    refinement["actual_e1_calls_range"] = [0, 1]
    try:
        scored = scorer(graph, candidate)
        refinement["score"] = scored
        if scored.get("worker_pid") is not None:
            refinement["actual_e1_calls"] = 1
            refinement["actual_e1_calls_range"] = [1, 1]
        if scored.get("status") != "ok":
            refinement["stop_reason"] = "refinement-score-failed"
        elif objective(scored) < objective(baseline):
            result["selected"] = "packet-dp-refinement"
            refinement["stop_reason"] = "strict-objective-improvement"
            refinement["score_wall_seconds"] = time.perf_counter() - score_start
            result["solve_function_seconds"] = time.perf_counter() - started
            return candidate, result
        else:
            refinement["stop_reason"] = "no-strict-improvement"
    except Exception as exc:
        refinement.update(stop_reason="refinement-score-failed",
                          score_error_type=type(exc).__name__, score_error_message=str(exc))
    refinement["score_wall_seconds"] = time.perf_counter() - score_start
    result["solve_function_seconds"] = time.perf_counter() - started
    return base_plan, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("refuse to overwrite solver artifacts")
    started = time.perf_counter()  # before input read, through final diagnostics write
    graph = json.loads(args.graph.read_bytes())
    plan, info = solve(graph, args.cores)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(unified.plan_bytes(plan))
        stream.flush()
        os.fsync(stream.fileno())
    info["cli_before_diagnostics_write_seconds"] = time.perf_counter() - started
    with args.diagnostics.open("x") as stream:
        json.dump(info, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"event": "solver_completed", "algorithm_id": ALGORITHM_ID,
                      "selected": info["selected"],
                      "cli_read_to_outputs_fsync_seconds": time.perf_counter() - started}), flush=True)


if __name__ == "__main__":
    main()
