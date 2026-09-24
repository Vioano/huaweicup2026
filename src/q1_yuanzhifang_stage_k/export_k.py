"""Export Stage K 100/k4 originals to board submission-v1; never score."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from src.q1_yuanzhifang_stage_k.benchmark_k import (
    CELLS, DEFAULT_OUTPUT, ROOT, SOLVER_SHA, MAX_SOLVER, MAX_E1_ATTEMPTS,
    MAX_NEW_E0, git_original, load_reuse_feed,
)
from src.eval_exact._official import compute_official_code_hash

REPO = "huaweibei123/huaweicup2026"
E0_SOURCE = "a0537aeb72dc702af86d67d3194587d581ac207c"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def artifact(path):
    relative = path.relative_to(ROOT).as_posix()
    return {"path": relative, "sha256": digest(path.read_bytes())}


def source(commit, path, entrypoint):
    return dict(repo=REPO, commit=commit, path=path, entrypoint=entrypoint)


def baseline(case, source_row, manifest, official_hash, run_dir):
    reference = source_row["baseline"]
    if (reference["graph_sha256"] != manifest["graph_sha256"][case]
            or reference["config_sha256"] != manifest["config_sha256"]
            or reference["official_sha256"] != official_hash or reference["route"] != "E0"):
        raise ValueError(f"fixed baseline identity mismatch: {case}")
    item = reference["result"]
    raw = git_original(manifest["reuse_source"]["commit"], item["path"])
    if digest(raw) != item["sha256"]:
        raise ValueError(f"fixed baseline result hash mismatch: {case}")
    result = json.loads(gzip.decompress(raw))
    if result.get("scene") != "A" or result.get("num_cores") != 1 or type(result.get("makespan")) is not int:
        raise ValueError(f"fixed baseline result invalid: {case}")
    folder = run_dir / "baseline" / case
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "result.json.gz"
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError("existing baseline copy differs from original")
    else:
        target.write_bytes(raw)
    return dict(reference, result=artifact(target)), result["makespan"]


def export(run_dir, feed_path):
    manifest = json.loads((run_dir / "batch_manifest.json").read_text(encoding="utf-8"))
    receipt = json.loads((run_dir / "batch_receipt.json").read_text(encoding="utf-8"))
    if manifest["solver_commit"] != SOLVER_SHA or manifest["official_e0_sha256"] != digest(
            (ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py").read_bytes()):
        raise ValueError("frozen source identity mismatch")
    if not manifest.get("producer_session"):
        raise ValueError("actual supervising producer session missing")
    if (receipt["solver_attempts_charged"] > MAX_SOLVER
            or receipt["online_e1_interface_budget_charge"] > MAX_E1_ATTEMPTS
            or receipt["external_e0_attempts_charged"] > MAX_NEW_E0):
        raise ValueError("batch exceeded frozen calls")
    official_hash = compute_official_code_hash()
    source_path = ROOT / manifest["reuse_source"]["feed_path"]
    rows, identity = load_reuse_feed(source_path, manifest["reuse_source"]["commit"])
    if identity != manifest["reuse_source"]:
        raise ValueError("fixed reuse source changed")
    source_rows = {case: row for (case, _), row in rows.items()}
    if len(source_rows) != 100:
        raise ValueError("100 verified baseline source rows required")
    baselines = {case: baseline(case, source_rows[case], manifest, official_hash, run_dir)
                 for case, _ in CELLS}
    records = []
    for case, cores in CELLS:
        cell = run_dir / f"case_{case}_k{cores}"
        run = json.loads((cell / "run.json").read_text(encoding="utf-8"))
        if run["case"] != case or run["cores"] != cores or run["graph_sha256"] != manifest["graph_sha256"][case]:
            raise ValueError(f"cell identity mismatch {case}/k{cores}")
        plan = cell / f"case_{case}_multicore_res.json"
        result_path = cell / "e0_result.json.gz"
        trace = cell / "e0_trace.json.gz"
        log = cell / "e0_log.txt"
        artifacts = {"run": artifact(cell / "run.json"),
                     "manifest": artifact(run_dir / "batch_manifest.json")}
        if plan.is_file():
            artifacts["plan"] = artifact(plan)
            submitted = json.loads(plan.read_text(encoding="utf-8"))
            if set(submitted) != {"node_to_subgraph", "core_schedules"}:
                raise ValueError("plan must contain only official two keys")
            if run.get("plan_sha256") and run["plan_sha256"] != artifacts["plan"]["sha256"]:
                raise ValueError("plan hash mismatch")
        for key, path in (("result", result_path), ("trace", trace), ("log", log)):
            if path.is_file():
                artifacts[key] = artifact(path)
        success = run["status"] in {"success", "success-reused-e0"}
        reused = "e0_reuse" in run
        result = json.loads(gzip.decompress(result_path.read_bytes())) if success else None
        if success:
            if not all(path.is_file() for path in (plan, result_path, trace)) or (not reused and not log.is_file()):
                raise ValueError("successful cell missing original E0 artifact")
            if result["scene"] != "A" or result["num_cores"] != cores or type(result["makespan"]) is not int:
                raise ValueError("E0 result identity or makespan invalid")
            if run["e0_result_sha256"] != artifacts["result"]["sha256"]:
                raise ValueError("E0 result hash mismatch")
            if reused and (run["e0_reuse"]["source_commit"] != manifest["reuse_source"]["commit"]
                           or run["e0_reuse"]["trace_sha256"] != artifacts["trace"]["sha256"]):
                raise ValueError("fixed E0 reuse provenance mismatch")
            if reused:
                originals = run["e0_reuse"]["source_artifacts"]
                for key, path in (("plan", plan), ("result", result_path)):
                    source_item = originals[key]
                    source_raw = git_original(manifest["reuse_source"]["commit"], source_item["path"])
                    if digest(source_raw) != source_item["sha256"] or path.read_bytes() != source_raw:
                        raise ValueError(f"fixed E0 reuse bytes changed: {case}/{key}")
                source_trace = git_original(manifest["reuse_source"]["commit"],
                                            run["e0_reuse"]["trace_git_path"])
                if trace.read_bytes() != source_trace:
                    raise ValueError(f"fixed E0 reuse trace changed: {case}")
        status = ("ok" if success else "not_run" if run["status"] in
                  {"not-started-after-supervision-failure", "global-deadline-before-solver",
                   "global-deadline-before-e0", "unevaluated-e0-budget"}
                  else "timeout" if run.get("solver", {}).get("timeout") or run.get("e0", {}).get("timeout")
                  else "failed")
        movement = result["data_movement_bytes"] if success else {}
        verified_baseline, baseline_cycles = baselines[case]
        solver = run.get("solver", {})
        e0 = run.get("e0", {})
        missing = {
            "provenance.environment.gpu": "GPU was not measured; this CPU solver does not request one.",
            "provenance.environment.ram_bytes": "Host RAM capacity was not measured by this runner.",
            "provenance.environment.threads": "OS thread count was not measured; batch processes limited to two.",
            "provenance.environment.peak_rss_bytes": "Child peak RSS was not instrumented.",
            "provenance.measurement.seed": "Deterministic fixed structural construction has no RNG parameter.",
        }
        if reused:
            missing["metrics.evaluation_wall_seconds"] = "Reused E0; source run wall is recorded separately, no current E0 process wall exists."
            missing["artifacts.log"] = run["e0_reuse"]["missing_source_log"]
        if not success:
            for name in ("makespan_cycles", "ddr_bytes", "extra_ddr_bytes", "spill_bytes"):
                missing[f"metrics.{name}"] = f"No accepted external E0 result: {run['status']}"
        if "wall_seconds" not in solver:
            missing["metrics.solver_wall_seconds"] = "No completed owned solver process wall was recorded."
        if not reused and "wall_seconds" not in e0:
            missing["metrics.evaluation_wall_seconds"] = "No completed new external E0 process wall was recorded."
        failure = None if success else dict(stage="E0" if "e0" in run else "solver",
                                            reason=run["status"] + (": " + run["message"] if run.get("message") else ""),
                                            exit_code=(e0 or solver).get("returncode"),
                                            elapsed_seconds=(e0 or solver).get("wall_seconds"))
        if failure is not None:
            if failure["exit_code"] is None:
                missing["provenance.measurement.failure.exit_code"] = "No child exit code was observed."
            if failure["elapsed_seconds"] is None:
                missing["provenance.measurement.failure.elapsed_seconds"] = "No child process was started."
        e1_calls = run.get("e1_worker_confirmed_calls", 0)
        unknown_e1 = run.get("e1_worker_execution_unknown_attempts", run.get("e1_interface_attempts_observed", 0))
        provenance = {
            "producer_session": manifest["producer_session"],
            "task_url": "https://github.com/huaweibei123/huaweicup2026/issues/98",
            "solver": {"source": source(SOLVER_SHA, "src/q1_yuanzhifang_stage_k/unified.py", "main"),
                       "authors": ["NikolaStarx", "yuanzhifang30-sudo"],
                       "method": "Frozen a053 captain union plus at most one guarded H or J intact-chain candidate; E1 online ranking",
                       "references": ["https://github.com/huaweibei123/huaweicup2026/issues/98"],
                       "upstream": [
                           source("a0537aeb72dc702af86d67d3194587d581ac207c", "src/q1/unified.py", "generate_candidates"),
                           source("4f1b9f8be4bbcc98759a19451c108e62e80abb17", "src/q1_yuanzhifang/prefetch_frontier.py", "construct"),
                           source("aa3f18a71b117ebd0476c8d714c97d8d366d74d7", "src/q1_yuanzhifang/intact_pacing.py", "construct")],
                       "selected_algorithm_id": None, "selected_solver_commit": None},
            "runner": {"source": source(manifest["runner_head"], "src/q1_yuanzhifang_stage_k/benchmark_k.py", "main"),
                       "argv": solver.get("command", []), "working_directory": "."},
            "environment": {"os": manifest["platform"], "cpu": manifest["cpu"] or "unavailable",
                            "gpu": None, "ram_bytes": None, "python": manifest["python"],
                            "dependencies": "uv.lock sha256 " + digest((ROOT / "uv.lock").read_bytes()),
                            "threads": None, "workers": 2, "peak_rss_bytes": None},
            "measurement": {"started_at": run["started_at"], "finished_at": run["finished_at"],
                            "seed": None, "repeat_index": 0, "cold_start": True,
                            "solver_scope": "external perf_counter from process launch through Job close, outputs and descendant cleanup",
                            "evaluation_scope": "reused fixed Git E0 original, no new call" if reused else "separate unchanged official E0 CLI through Job close",
                            "budget": {"wall_seconds": 2400, "candidate_limit": 7,
                                       "stop_reason": run["status"] + "; 0 retries"},
                            "calls": {"solver": int("solver" in run),
                                      "E0": int("e0" in run), "E1": e1_calls, "E2": 0},
                            "offline_costs": "Preparation and fixed earlier baselines separate; no current-case offline training or score selection.",
                            "failure": failure},
            "missing_reasons": missing,
        }
        records.append({
            "attempt_id": f"fang-q1-stage-k-100k4-20260925-{case}-k{cores}-r0", "revision": 1,
            "run_id": "fang-q1-stage-k-100k4-20260925", "algorithm_id": "q1-unified-structural-hj-stage-k",
            "algorithm_name": "Captain a053 union with one guarded H/J candidate", "variant": "base-six-plus-one-v1",
            "solver_commit": SOLVER_SHA,
            "parameters": {"cores": cores, "candidate_limit": 7, "online_e1_worker_limit": 1,
                           "singlecore_baseline_commit": manifest["reuse_source"]["commit"],
                           "batch_budget": {"solver": 100, "E0_new": 8, "E1_attempts": 700, "E2": 0,
                                            "workers": 2, "wall_seconds": 2400, "retries": 0},
                           "batch_actual_calls": receipt,
                           "reused_e0": run.get("e0_reuse"),
                           "e1_unknown_execution_attempts": unknown_e1,
                           "e1_conservative_budget_charge": run.get("e1_budget_charge", 0)},
            "problem": "P1", "case_id": case, "cores": cores, "status": status,
            "metrics": {"makespan_cycles": result["makespan"] if success else None,
                        "solver_wall_seconds": solver.get("wall_seconds"),
                        "evaluation_wall_seconds": e0.get("wall_seconds"),
                        "ddr_bytes": movement.get("scheduled_copy_bytes"),
                        "extra_ddr_bytes": movement.get("added_copy_bytes"),
                        "spill_bytes": movement.get("spill_added_copy_bytes"), "cache_hit_rate": None},
            "evaluator": {"route": "E0", "commit": E0_SOURCE,
                          "entrypoint": "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"},
            "identity": {"graph_sha256": manifest["graph_sha256"][case],
                         "config_sha256": manifest["config_sha256"], "official_sha256": official_hash,
                         "plan_sha256": artifacts.get("plan", {}).get("sha256")},
            "artifacts": artifacts, "runtime_id": "fang-windows-q1-stage-k-100k4-20260925",
            "observed_at": run["finished_at"],
            "timing": {"solver_includes_evaluation": True,
                       "evaluation_precision": "new solver cold process wall; prior E0 wall only as separate reuse provenance" if reused else "perf_counter cold process wall; E1 online in solver and external E0 separate",
                       "utc": "UTC ISO8601 Z"},
            "provenance": provenance,
            "notes": ["Prospective 100/k4 validation against fixed a053 originals; unevaluated cells have no Makespan or mean contribution.",
                      f"Official singlecore denominator {baseline_cycles} cycles copied byte-for-byte from {manifest['reuse_source']['commit']}; 0 baseline reruns.",
                      "Reused E0 source wall, where present, is in parameters.reused_e0; current evaluation wall and call count remain empty/zero.",
                      "E1 execution unknown attempts are charged conservatively; see original diagnostics/events."],
            "source_url": "https://github.com/huaweibei123/huaweicup2026/issues/98",
            "baseline": verified_baseline, "cache_pair": None,
        })
    if feed_path.exists():
        raise FileExistsError(feed_path)
    feed_path.parent.mkdir(parents=True, exist_ok=True)
    feed_path.write_text(json.dumps({"schema_version": 1, "submission_version": 1,
                                     "records": records}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--feed", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"records": export(args.run_dir.resolve(), args.feed.resolve()),
                      "feed": str(args.feed.resolve())}))


if __name__ == "__main__":
    main()
