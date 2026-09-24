"""Candidate-preserving structural H/J extension of the frozen captain solver.

Only a guarded all-V repeated fork/join graph can gain one candidate. External
unchanged E0 acceptance and full cold-wall measurement belong to the runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
sys.path.insert(0, str(HERE))  # Frozen H/J source imports its sibling modules by name.

from src.q1 import unified as captain

ALGORITHM_ID = "q1-unified-structural-hj-stage-k"
BASE_COMMIT = "a0537aeb72dc702af86d67d3194587d581ac207c"
H_SOURCE = "4f1b9f8be4bbcc98759a19451c108e62e80abb17"
J_SOURCE = "aa3f18a71b117ebd0476c8d714c97d8d366d74d7"
MAX_DISTINCT_CANDIDATES = captain.MAX_DISTINCT_CANDIDATES + 1
MANIFEST = HERE / "sources.json"


def verify_sources():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (manifest["base_commit"] != BASE_COMMIT or manifest["h_source"] != H_SOURCE
            or manifest["j_source"] != J_SOURCE or manifest["e1_source"] != captain.E1_SOURCE):
        raise RuntimeError("source identity mismatch")
    frozen = json.loads((ROOT / "src/q1/unified_sources.json").read_text(encoding="utf-8"))
    if frozen["e1_source"] != captain.E1_SOURCE:
        raise RuntimeError("captain E1 source mismatch")
    for relative, expected in {**frozen["e1_files_sha256"], **manifest["files_sha256"]}.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"source hash mismatch: {relative}")


def _route(graph, cores):
    if cores not in (3, 4, 5):
        return None, "core count outside guarded H/J domain"
    # Cheap shape exclusion prevents the expensive strict recognizer on the
    # many M/V, M-only, and mixed-pipe captain cases.
    compute = [op for op in graph["ops"] if op["op"] not in ("COPY_IN", "COPY_OUT")]
    if not compute or any(op["pipe"] != "PIPE_V" for op in compute):
        return None, "not an all-PIPE_V compute graph"
    from star_frontier import guarded_stages
    guarded, reason = guarded_stages(graph)
    if guarded is None:
        return None, reason
    if len(guarded["rounds"]) != 24:
        return None, "requires exactly 24 repeated fork/join rounds"
    if cores in (3, 4):
        ops = {op["id"]: op for op in graph["ops"]}
        if any(ops[u]["op"] != "ADD" for row in guarded["rounds"] for u in row["tail"]):
            return None, "J requires ADD-only reduction tails"
        return "intact-pacing", reason
    return "prefetch-frontier", reason


def generate_candidates(graph, cores, emit=None):
    began = time.perf_counter()
    candidates, diagnostics = captain.generate_candidates(graph, cores, emit=emit)
    diagnostics = dict(diagnostics)
    diagnostics["base_candidates"] = [c["name"] for c in candidates]
    diagnostics["base_candidate_count"] = len(candidates)
    if len(candidates) > captain.MAX_DISTINCT_CANDIDATES:
        raise AssertionError("captain base candidate bound exceeded")
    route, reason = _route(graph, cores)
    diagnostics["stage_k_route"] = route or "none"
    diagnostics["stage_k_guard"] = reason
    if route is None:
        diagnostics["generation_seconds"] = time.perf_counter() - began
        return candidates, diagnostics
    name = route
    started = time.perf_counter()
    captain.event(emit, "candidate_construction_started", name=name)
    try:
        if route == "prefetch-frontier":
            from prefetch_frontier import construct
            from diagnose import read_scene_a_config
            plan, details = construct(graph, cores, read_scene_a_config(str(captain.CONFIG)),
                                      startup_cores=4, fuse_reductions=True)
        else:
            from intact_pacing import construct
            plan, details = construct(graph, cores, "paced")
    except Exception as error:
        # Expected structural non-applicability is observable. A constructor
        # bug or validation failure surfaces; it must not silently alter the
        # candidate pool or masquerade as an inapplicable graph.
        if route != "intact-pacing":
            raise
        from intact_pacing import Unsupported
        if not isinstance(error, Unsupported):
            raise
        failure = dict(name=name, error_type=type(error).__name__, message=str(error),
                       construction_seconds=time.perf_counter()-started)
        diagnostics["construction_failures"].append(failure)
        captain.event(emit, "candidate_construction_failed", **failure)
    else:
        raw = captain.plan_bytes(plan)
        record = dict(name=name, plan_sha256=hashlib.sha256(raw).hexdigest(),
                      construction_seconds=time.perf_counter()-started, details=details)
        prior = next((c["name"] for c in candidates if captain.plan_bytes(c["plan"]) == raw), None)
        if prior is not None:
            diagnostics["duplicates"].append(dict(record, duplicate_of=prior))
            captain.event(emit, "candidate_duplicate", name=name,
                          plan_sha256=record["plan_sha256"], duplicate_of=prior)
        else:
            candidates.append(dict(record, plan=json.loads(raw)))
            captain.event(emit, "candidate_constructed", name=name,
                          plan_sha256=record["plan_sha256"],
                          construction_seconds=record["construction_seconds"])
    if len(candidates) > MAX_DISTINCT_CANDIDATES:
        raise AssertionError("Stage K candidate bound exceeded")
    diagnostics["generation_seconds"] = time.perf_counter()-began
    return candidates, diagnostics


def solve(graph, cores, emit=None, score=None):
    """The injected scorer exists only for small controller tests."""
    verify_sources()
    began = time.perf_counter()
    candidates, diagnostics = generate_candidates(graph, cores, emit=emit)
    score_started = time.perf_counter()
    attempts = 0
    scoring_parameters = dict(workers=1, cache_bytes=16 << 20,
                              timeout_seconds=60, startup_timeout_seconds=10,
                              max_tasks_per_worker=MAX_DISTINCT_CANDIDATES)
    if len(candidates) == 1:
        selected, records, reason = captain.choose(candidates, None, emit=emit)
    elif score is not None:
        selected, records, reason = captain.choose(candidates, score, emit=emit)
    else:
        from src.eval_exact import P1BatchEvaluator, read_config
        config = read_config(captain.CONFIG)
        with P1BatchEvaluator(graph, **scoring_parameters) as evaluator:
            def online_score(plan):
                nonlocal attempts
                attempts += 1
                captain.event(emit, "e1_interface_attempt_started", attempt=attempts)
                try:
                    result = next(evaluator.evaluate_batch([plan], full=False, **config))
                except Exception as error:
                    captain.event(emit, "e1_interface_attempt_failed", attempt=attempts,
                                  error_type=type(error).__name__, message=str(error))
                    raise
                captain.event(emit, "e1_interface_attempt_returned", attempt=attempts,
                              worker_pid=result.get("worker_pid"), status=result.get("status"))
                return result
            selected, records, reason = captain.choose(candidates, online_score, emit=emit)
    confirmed = sum(r.get("worker_pid") is not None for r in records) if score is None else 0
    diagnostics.update(algorithm_id=ALGORITHM_ID, selected=selected["name"],
                       stop_reason=reason,
                       candidates=[{k:v for k,v in c.items() if k != "plan"} for c in candidates],
                       online_scores=records, online_score_attempts=len(records),
                       e1_interface_attempts=attempts, actual_e1_calls=confirmed,
                       e1_worker_execution_unknown_attempts=attempts-confirmed,
                       e1_call_accounting="worker_pid confirms calls; unknown attempts charged to budget",
                       scoring_parameters=scoring_parameters, e1_source_commit=captain.E1_SOURCE,
                       online_scoring_seconds=time.perf_counter()-score_started,
                       solve_function_seconds=time.perf_counter()-began,
                       scope="E1 ranking is not unchanged external E0 acceptance")
    return selected["plan"], diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("Refuse to overwrite solver artifacts")
    started = time.perf_counter()
    def emit(row):
        print(json.dumps(row), flush=True)
    captain.event(emit, "solver_input_started", cores=args.cores)
    plan, diagnostics = solve(json.loads(args.graph.read_bytes()), args.cores, emit=emit)
    for path in (args.output, args.diagnostics):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as out:
        out.write(captain.plan_bytes(plan))
    diagnostics["cli_body_through_plan_wall_seconds"] = time.perf_counter()-started
    diagnostics["cli_body_scope"] = "After CLI parsing through plan close; excludes imports, diagnostics write and process exit. External runner measures full cold wall."
    with args.diagnostics.open("x", encoding="utf-8") as out:
        json.dump(diagnostics, out, indent=2)
        out.write("\n")


if __name__ == "__main__":
    main()
