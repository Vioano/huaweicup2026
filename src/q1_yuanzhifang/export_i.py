"""Export Stage I original run bytes to board submission-v1; never score."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from src.q1_yuanzhifang.benchmark_i import CELLS, DEFAULT_OUTPUT, ROOT, SOLVER_SHA
from src.eval_exact._official import compute_official_code_hash

REPO = "huaweibei123/huaweicup2026"
SESSION = "yuanzhifang30-sudo/s-0e91469d5b284a0aaf7aca42c456233c"
E0_SOURCE = "1cc29d207ebad396d5a0bbfcabf2ef4b4c26ffed"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def artifact(path):
    relative = path.relative_to(ROOT).as_posix()
    return {"path": relative, "sha256": digest(path.read_bytes())}


def source(commit, path, entrypoint):
    return dict(repo=REPO, commit=commit, path=path, entrypoint=entrypoint)


def export(run_dir, feed_path):
    manifest = json.loads((run_dir / "batch_manifest.json").read_text(encoding="utf-8"))
    receipt = json.loads((run_dir / "batch_receipt.json").read_text(encoding="utf-8"))
    if manifest["solver_commit"] != SOLVER_SHA or manifest["official_e0_sha256"] != digest(
            (ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py").read_bytes()):
        raise ValueError("frozen source identity mismatch")
    if receipt["solver_attempts"] > 5 or receipt["online_e1_interface_budget_charge"] > 25 or receipt["external_e0_attempts"] > 5:
        raise ValueError("batch exceeded frozen calls")
    official_hash = compute_official_code_hash()
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
        success = run["status"] == "success"
        result = json.loads(gzip.decompress(result_path.read_bytes())) if success else None
        if success:
            if not all(path.is_file() for path in (plan, result_path, trace, log)):
                raise ValueError("successful cell missing original E0 artifact")
            if result["scene"] != "A" or result["num_cores"] != cores or type(result["makespan"]) is not int:
                raise ValueError("E0 result identity or makespan invalid")
            if run["e0_result_sha256"] != artifacts["result"]["sha256"]:
                raise ValueError("E0 result hash mismatch")
        status = "ok" if success else ("timeout" if run.get("solver", {}).get("timeout") or run.get("e0", {}).get("timeout") else "failed")
        movement = result["data_movement_bytes"] if success else {}
        solver = run.get("solver", {})
        e0 = run.get("e0", {})
        missing = {
            "provenance.environment.gpu": "GPU was not measured; this CPU solver does not request one.",
            "provenance.environment.ram_bytes": "Host RAM capacity was not measured by this runner.",
            "provenance.environment.threads": "OS thread count was not measured; batch processes limited to two.",
            "provenance.environment.peak_rss_bytes": "Child peak RSS was not instrumented.",
            "provenance.measurement.seed": "Deterministic fixed structural construction has no RNG parameter.",
        }
        failure = None if success else dict(stage="E0" if "e0" in run else "solver",
                                            reason=run["status"] + (": " + run["message"] if run.get("message") else ""),
                                            exit_code=(e0 or solver).get("returncode"),
                                            elapsed_seconds=(e0 or solver).get("wall_seconds"))
        if failure is not None:
            if failure["exit_code"] is None:
                missing["provenance.measurement.failure.exit_code"] = "No child exit code was observed."
            if failure["elapsed_seconds"] is None:
                missing["provenance.measurement.failure.elapsed_seconds"] = "No child process was started."
        e1_calls = run.get("e1_budget_charge", 5 if "solver" in run else 0)
        provenance = {
            "producer_session": SESSION,
            "task_url": "https://github.com/huaweibei123/huaweicup2026/issues/98",
            "solver": {"source": source(SOLVER_SHA, "src/q1_yuanzhifang/unified.py", "main"),
                       "authors": ["yuanzhifang30-sudo"],
                       "method": "Frozen captain candidate union plus one structure-gated H or private capacity-return candidate; E1 online ranking",
                       "references": ["https://github.com/huaweibei123/huaweicup2026/issues/98"],
                       "upstream": [], "selected_algorithm_id": None, "selected_solver_commit": None},
            "runner": {"source": source(manifest["runner_head"], "src/q1_yuanzhifang/benchmark_i.py", "main"),
                       "argv": solver.get("command", []), "working_directory": "."},
            "environment": {"os": manifest["platform"], "cpu": manifest["cpu"] or "unavailable",
                            "gpu": None, "ram_bytes": None, "python": manifest["python"],
                            "dependencies": "uv.lock sha256 " + digest((ROOT / "uv.lock").read_bytes()),
                            "threads": None, "workers": 2, "peak_rss_bytes": None},
            "measurement": {"started_at": run["started_at"], "finished_at": run["finished_at"],
                            "seed": None, "repeat_index": 0, "cold_start": True,
                            "solver_scope": "external perf_counter from process launch through Job close, outputs and descendant cleanup",
                            "evaluation_scope": "separate unchanged official E0 CLI through Job close",
                            "budget": {"wall_seconds": 1200, "candidate_limit": 5,
                                       "stop_reason": run["status"] + "; 0 retries"},
                            "calls": {"solver": int("solver" in run), "E0": int("e0" in run), "E1": e1_calls, "E2": 0},
                            "offline_costs": "Preparation and fixed earlier baselines separate; no current-case offline training or score selection.",
                            "failure": failure},
            "missing_reasons": missing,
        }
        records.append({
            "attempt_id": f"fang-q1-stage-i-20260925-{case}-k{cores}-r0", "revision": 1,
            "run_id": "fang-q1-stage-i-20260925", "algorithm_id": "q1-unified-prefetch-return",
            "algorithm_name": "Fang structural union with one additional candidate", "variant": "base-four-plus-one-v1",
            "solver_commit": SOLVER_SHA,
            "parameters": {"cores": cores, "candidate_limit": 5, "online_e1_worker_limit": 1,
                           "batch_budget": {"solver": 5, "E0": 5, "E1_attempts": 25, "E2": 0,
                                            "workers": 2, "wall_seconds": 1200, "retries": 0},
                           "batch_actual_calls": receipt},
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
            "artifacts": artifacts, "runtime_id": "fang-windows-q1-stage-i-20260925",
            "observed_at": run["finished_at"],
            "timing": {"solver_includes_evaluation": True,
                       "evaluation_precision": "perf_counter cold process wall; E1 online in solver and external E0 separate",
                       "utc": "UTC ISO8601 Z"},
            "provenance": provenance,
            "notes": ["Five exposed prospective pilot cells only; no full 100x5 mean or blind test.",
                      "E1 execution unknown attempts are charged conservatively; see original diagnostics/events."],
            "source_url": "https://github.com/huaweibei123/huaweicup2026/issues/98",
            "baseline": None, "cache_pair": None,
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
