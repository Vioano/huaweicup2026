"""Fixed P1 candidate union with one structure-gated addition per graph.

All construction and online E1 ranking are charged to the cold solver wall.
Final acceptance still requires an external, unchanged E0 run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
sys.path.insert(0, str(Path(__file__).parent))

from src.q1 import unified as captain

ALGORITHM_ID = "q1-unified-prefetch-return"
MAX_DISTINCT_CANDIDATES = 5
MANIFEST = Path(__file__).with_name("unified_sources.json")


def verify_sources():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    frozen = json.loads((ROOT / "src/q1/unified_sources.json").read_text(encoding="utf-8"))
    if frozen["e1_source"] != captain.E1_SOURCE or frozen["e1_source"] != manifest["e1_source"]:
        raise RuntimeError("E1 source commit mismatch")
    for relative, expected in {**frozen["e1_files_sha256"], **manifest["files_sha256"]}.items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"source hash mismatch: {relative}")


def generate_candidates(graph, cores, emit=None):
    """Keep every frozen captain candidate; add at most one new unique plan."""
    began = time.perf_counter()
    candidates, diagnostics = captain.generate_candidates(graph, cores, emit=emit)
    diagnostics = dict(diagnostics)
    diagnostics["base_candidates"] = [item["name"] for item in candidates]
    diagnostics["additional_route"] = "none"
    seen = {captain.plan_bytes(item["plan"]): item["name"] for item in candidates}
    if len(candidates) > 4:
        raise AssertionError("Frozen base candidate bound exceeded")
    if cores == 1:
        diagnostics["generation_seconds"] = time.perf_counter() - began
        return candidates, diagnostics

    # H and private M/V/M are structurally disjoint. The strict H guard has
    # twelve four-op PIPE_V chains and a binary join in every repeated round.
    from src.q1_yuanzhifang.star_frontier import guarded_stages
    guarded, guard_reason = guarded_stages(graph) if cores == 5 else (None, "five-core guard only")
    diagnostics["prefetch_guard"] = guard_reason
    if guarded is not None:
        route, name = "prefetch-frontier", "prefetch-frontier"
        from src.q1_yuanzhifang.prefetch_frontier import construct
        from src.q1_yuanzhifang.diagnose import read_scene_a_config
        make = lambda: construct(graph, cores, read_scene_a_config(str(captain.CONFIG)),
                                 startup_cores=4, fuse_reductions=True)
    else:
        route, name = "capacity-return", "capacity-return"
        from src.q1_yuanzhifang import capacity_return
        make = lambda: capacity_return.construct(graph, cores)
    diagnostics["additional_route"] = route
    start = time.perf_counter()
    captain.event(emit, "candidate_construction_started", name=name)
    try:
        plan, details = make()
    except Exception as error:
        # Unsupported is the one expected capacity mismatch. An unexpected
        # capacity implementation failure must surface rather than be hidden.
        if route == "capacity-return" and not isinstance(error, capacity_return.author.Unsupported):
            raise
        failure = dict(name=name, error_type=type(error).__name__, message=str(error),
                       construction_seconds=time.perf_counter() - start)
        diagnostics["construction_failures"].append(failure)
        captain.event(emit, "candidate_construction_failed", **failure)
    else:
        raw = captain.plan_bytes(plan)
        record = dict(name=name, plan_sha256=hashlib.sha256(raw).hexdigest(),
                      construction_seconds=time.perf_counter() - start, details=details)
        if raw in seen:
            duplicate = dict(record, duplicate_of=seen[raw])
            diagnostics["duplicates"].append(duplicate)
            captain.event(emit, "candidate_duplicate", name=name,
                          plan_sha256=record["plan_sha256"], duplicate_of=seen[raw])
        else:
            candidates.append(dict(record, plan=json.loads(raw)))
            captain.event(emit, "candidate_constructed", name=name,
                          plan_sha256=record["plan_sha256"],
                          construction_seconds=record["construction_seconds"])
    if len(candidates) > MAX_DISTINCT_CANDIDATES:
        raise AssertionError("Candidate bound exceeded")
    diagnostics["generation_seconds"] = time.perf_counter() - began
    return candidates, diagnostics


def solve(graph, cores, emit=None, score=None):
    """Optional score injection is solely for small controller tests."""
    verify_sources()
    began = time.perf_counter()
    candidates, diagnostics = generate_candidates(graph, cores, emit=emit)
    score_started = time.perf_counter()
    e1_interface_attempts = 0
    scoring_parameters = dict(workers=1, cache_bytes=16 << 20,
                              timeout_seconds=60, startup_timeout_seconds=10,
                              max_tasks_per_worker=5)
    if len(candidates) == 1:
        selected, records, reason = captain.choose(candidates, None, emit=emit)
    elif score is not None:
        selected, records, reason = captain.choose(candidates, score, emit=emit)
    else:
        from src.eval_exact import P1BatchEvaluator, read_config
        config = read_config(captain.CONFIG)
        with P1BatchEvaluator(graph, **scoring_parameters) as evaluator:
            def online_score(plan):
                nonlocal e1_interface_attempts
                e1_interface_attempts += 1
                captain.event(emit, "e1_interface_attempt_started", attempt=e1_interface_attempts)
                try:
                    result = next(evaluator.evaluate_batch([plan], full=False, **config))
                except Exception as error:
                    captain.event(emit, "e1_interface_attempt_failed", attempt=e1_interface_attempts,
                                  error_type=type(error).__name__, message=str(error))
                    raise
                captain.event(emit, "e1_interface_attempt_returned", attempt=e1_interface_attempts,
                              worker_pid=result.get("worker_pid"), status=result.get("status"))
                return result
            selected, records, reason = captain.choose(candidates, online_score, emit=emit)
    confirmed_worker_calls = sum(r.get("worker_pid") is not None for r in records) if score is None else 0
    unknown_worker_execution = e1_interface_attempts - confirmed_worker_calls
    diagnostics.update(algorithm_id=ALGORITHM_ID, variant="base-four-plus-one-v1",
                       selected=selected["name"], stop_reason=reason,
                       candidates=[{k: v for k, v in c.items() if k != "plan"} for c in candidates],
                       online_scores=records, online_score_attempts=len(records),
                       e1_interface_attempts=e1_interface_attempts,
                       actual_e1_calls=confirmed_worker_calls,
                       e1_worker_execution_unknown_attempts=unknown_worker_execution,
                       e1_call_accounting="actual_e1_calls counts returned worker_pid only; unknown attempts are charged to budget",
                       scoring_parameters=scoring_parameters,
                       e1_source_commit=captain.E1_SOURCE,
                       online_scoring_seconds=time.perf_counter() - score_started,
                       solve_function_seconds=time.perf_counter() - began,
                       scope="E1 online ranking is not external E0 acceptance")
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
    diagnostics["cli_body_through_plan_wall_seconds"] = time.perf_counter() - started
    diagnostics["cli_body_scope"] = "Starts after CLI parsing; ends after plan close; excludes imports, diagnostics write and process exit. External runner owns full cold wall."
    with args.diagnostics.open("x", encoding="utf-8") as out:
        json.dump(diagnostics, out, indent=2)
        out.write("\n")


if __name__ == "__main__":
    main()
