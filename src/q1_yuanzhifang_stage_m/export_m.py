"""Export one Stage M raw cell to a submission-v1 feed; never score."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from src.q1_yuanzhifang_stage_m.benchmark_m import (
    BASELINE_COMMIT, BASELINE_DIR, CASE, CORES, OUT, ROOT, SOURCE_COMMIT,
    V4_COMMIT, V4_K2_RESULT, sha,
)

REPO = "huaweibei123/huaweicup2026"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def artifact(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}


def export(run_dir: Path, feed: Path) -> dict:
    manifest = json.loads((run_dir / "batch_manifest.json").read_bytes())
    receipt = json.loads((run_dir / "batch_receipt.json").read_bytes())
    if manifest.get("method_source_commit") != SOURCE_COMMIT or not manifest.get("producer_session"):
        raise ValueError("frozen solver/session identity mismatch")
    calls = receipt["calls"]
    upper = receipt.get("calls_upper_bound", calls)
    if (upper["solver"] > 1 or upper["E0"] > 1 or upper["E1"] or upper["E2"]
            or receipt["retries"]):
        raise ValueError("Stage M execution budget exceeded")
    if not receipt.get("calls_exact", True):
        calls = dict(solver=None, E0=None, E1=0, E2=0)

    baseline_folder = run_dir.parent / "baseline" / CASE
    baseline_folder.mkdir(parents=True, exist_ok=True)
    baseline_raw = {name: git("show", f"{BASELINE_COMMIT}:{BASELINE_DIR}/{name}")
                    for name in ("run.json", "result.json.gz")}
    for name, raw in baseline_raw.items():
        target = baseline_folder / name
        if target.exists() and target.read_bytes() != raw:
            raise ValueError("baseline copy conflicts with fixed Git original")
        if not target.exists():
            target.write_bytes(raw)
    base_run = json.loads(baseline_raw["run.json"])
    base_result = json.loads(gzip.decompress(baseline_raw["result.json.gz"]))
    if (base_run.get("status") != "ok" or base_run.get("case_id") != CASE
            or base_result.get("scene") != "A" or base_result.get("num_cores") != 1
            or base_result.get("makespan") != base_run.get("makespan_cycles")
            or base_run.get("graph_sha256") != manifest["source_closure"]["graph_sha256"]
            or base_run.get("config_sha256") != manifest["source_closure"]["config_sha256"]
            or base_run.get("official_code_hash") != manifest["source_closure"]["official_code_hash"]):
        raise ValueError("fixed single-core baseline identity mismatch")
    baseline_ref = dict(
        graph_sha256=base_run["graph_sha256"], config_sha256=base_run["config_sha256"],
        official_sha256=base_run["official_code_hash"], route="E0",
        entrypoint="singlecore_evaluate.evaluate_singlecore",
        result=artifact(baseline_folder / "result.json.gz"))

    cell = run_dir / f"case_{CASE}_k{CORES}"
    run_path = cell / "run.json"
    row = json.loads(run_path.read_bytes())
    artifacts = {"run": artifact(run_path), "manifest": artifact(run_dir / "batch_manifest.json")}
    pathmap = {"plan": cell / f"case_{CASE}_multicore_res.json",
               "result": cell / "e0_result.json", "trace": cell / "e0_trace.json",
               "log": cell / "e0_log.txt", "diagnostics": cell / "diagnostics.json"}
    for name, path in pathmap.items():
        if name != "diagnostics" and path.is_file():
            artifacts[name] = artifact(path)
    success = row.get("status") == "success"
    result = movement = None
    diagnostic = None
    if success:
        if not all(path.is_file() for path in pathmap.values()):
            raise ValueError("success missing plan, diagnostics, or original E0 artifacts")
        plan = json.loads(pathmap["plan"].read_bytes())
        diagnostic = json.loads(pathmap["diagnostics"].read_bytes())
        result = json.loads(pathmap["result"].read_bytes())
        if (set(plan) != {"node_to_subgraph", "core_schedules"}
                or diagnostic.get("algorithm_id") != "q1-adjacent-union-stage-m"
                or diagnostic.get("selected") != "adjacent-union"
                or not diagnostic.get("merged_pairs")
                or diagnostic.get("graph_sha256") != manifest["source_closure"]["graph_sha256"]
                or result.get("scene") != "A" or result.get("num_cores") != CORES
                or result.get("makespan") != row.get("makespan_cycles")
                or row.get("plan_sha256") != artifacts["plan"]["sha256"]):
            raise ValueError("successful raw artifacts or mechanism evidence mismatch")
        for name in ("result", "trace", "log"):
            if row.get(f"e0_{name}_sha256") != artifacts[name]["sha256"]:
                raise ValueError(f"E0 {name} original SHA differs from run receipt")
        movement = result.get("data_movement_bytes", {})

    solver, e0 = row.get("solver", {}), row.get("e0", {})
    status = "ok" if success else ("unsupported" if row.get("status") == "mechanism-not-triggered"
                                    else "timeout" if solver.get("timeout") or e0.get("timeout")
                                    else "not_run" if row.get("status", "").startswith("deadline")
                                    else "failed")
    missing = {
        "provenance.environment.gpu": "GPU was not measured.",
        "provenance.environment.ram_bytes": "Only available RAM gate was recorded; installed RAM was not measured.",
        "provenance.environment.threads": "OS thread count was not instrumented.",
        "provenance.environment.peak_rss_bytes": "Peak RSS was not instrumented.",
        "provenance.measurement.seed": "Deterministic constructor has no RNG seed.",
    }
    if not success:
        for metric in ("makespan_cycles", "ddr_bytes", "extra_ddr_bytes", "spill_bytes"):
            missing[f"metrics.{metric}"] = f"No accepted E0 result: {row.get('status')}"
    failure = None if success else dict(stage="runner" if calls["solver"] is None else "E0" if calls["E0"] else "solver",
        reason=row.get("status", "unknown") + (": " + row["message"] if row.get("message") else ""),
        exit_code=(e0 or solver).get("returncode"), elapsed_seconds=(e0 or solver).get("wall_seconds"))
    for key, obj in (("solver_wall_seconds", solver), ("evaluation_wall_seconds", e0)):
        if obj.get("wall_seconds") is None:
            missing[f"metrics.{key}"] = "No completed owned-process wall was recorded."
    if failure:
        if failure["exit_code"] is None:
            missing["provenance.measurement.failure.exit_code"] = "No process exit code was observed."
        if failure["elapsed_seconds"] is None:
            missing["provenance.measurement.failure.elapsed_seconds"] = "No completed child wall was observed."

    source_ref = dict(repo=REPO, commit=SOURCE_COMMIT,
                      path="src/q1_yuanzhifang_stage_m/adjacent_union.py", entrypoint="construct")
    runner_ref = dict(repo=REPO, commit=manifest["runner_head"],
                      path="src/q1_yuanzhifang_stage_m/benchmark_m.py", entrypoint="main")
    record = dict(
        attempt_id="fang-q1-stage-m-20260925-044-k2-r0", revision=1,
        run_id="fang-q1-stage-m-20260925", algorithm_id="q1-adjacent-union-stage-m",
        algorithm_name="Guarded adjacent Task union", variant="adjacent-union-resident-capacity-guard",
        solver_commit=SOURCE_COMMIT,
        parameters=dict(cores=CORES, baseline_commit=BASELINE_COMMIT,
                       prior_v4_reference=dict(commit=V4_COMMIT, result=V4_K2_RESULT, makespan_cycles=64624),
                       batch_budget=manifest["budget"], batch_actual_calls=calls),
        problem="P1", case_id=CASE, cores=CORES, status=status,
        metrics=dict(makespan_cycles=result.get("makespan") if success else None,
            solver_wall_seconds=solver.get("wall_seconds"), evaluation_wall_seconds=e0.get("wall_seconds"),
            ddr_bytes=movement.get("scheduled_copy_bytes") if success else None,
            extra_ddr_bytes=movement.get("added_copy_bytes") if success else None,
            spill_bytes=movement.get("spill_added_copy_bytes") if success else None, cache_hit_rate=None),
        evaluator=dict(route="E0", commit=SOURCE_COMMIT,
                       entrypoint="data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"),
        identity=dict(graph_sha256=manifest["source_closure"]["graph_sha256"],
                      config_sha256=manifest["source_closure"]["config_sha256"],
                      official_sha256=manifest["source_closure"]["official_code_hash"],
                      plan_sha256=artifacts.get("plan", {}).get("sha256")),
        artifacts=artifacts, runtime_id="fang-windows-q1-stage-m-20260925",
        observed_at=row.get("finished_at"),
        timing=dict(solver_includes_evaluation=False,
                    evaluation_precision="Cold constructor plus I/O measured through owned process cleanup; independent unchanged E0 wall"),
        provenance=dict(producer_session=manifest["producer_session"],
            task_url="https://github.com/huaweibei123/huaweicup2026/issues/98",
            solver=dict(source=source_ref, authors=["yuanzhifang30-sudo"],
                method="One cold shared-input plan followed by guarded adjacent-task union; only a structurally active merge is evaluated.",
                upstream=[dict(repo=REPO, commit=manifest["base_commit"],
                               path="src/q1/shared_input_budget.py", entrypoint="construct")],
                selected_algorithm_id=None, selected_solver_commit=None),
            runner=dict(source=runner_ref, argv=solver.get("command", []), working_directory="cell directory"),
            environment=dict(os=manifest.get("platform"), cpu=manifest.get("cpu") or "unavailable",
                gpu=None, ram_bytes=None, python=manifest.get("python"), workers=1, threads=None,
                peak_rss_bytes=None, dependencies="frozen source closure; no dependency install"),
            measurement=dict(started_at=row.get("started_at"), finished_at=row.get("finished_at"),
                seed=None, repeat_index=0, cold_start=True,
                solver_scope="Process launch through owned Job cleanup; graph read/hash and plan construction included",
                evaluation_scope="One independent unchanged official E0 CLI through owned Job cleanup, if merge mechanism triggers",
                budget=dict(wall_seconds=180, candidate_limit=1, stop_reason=row.get("status") + "; 0 retries"),
                calls=calls, offline_costs="none; historical result is comparison context only",
                failure=failure), missing_reasons=missing),
        notes=["One real-graph 044/k2 mechanism trial only; not a full-matrix mean.",
               f"Fixed single-core baseline is {base_result['makespan']} cycles.",
               "Historical v4 044/k2 value is context, not a matched rerun or a newly measured speed.",
               "No solver/E0 is run by this exporter."],
        source_url=f"https://github.com/{REPO}/blob/{SOURCE_COMMIT}/src/q1_yuanzhifang_stage_m/adjacent_union.py",
        baseline=baseline_ref, cache_pair=None)
    if feed.exists():
        raise FileExistsError(feed)
    feed.parent.mkdir(parents=True, exist_ok=True)
    feed.write_text(json.dumps({"schema_version": 1, "submission_version": 1, "records": [record]},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"records": 1, "status": status, "feed": feed.as_posix()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=OUT)
    parser.add_argument("--feed", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.run_dir.resolve(), args.feed.resolve()), ensure_ascii=False))


if __name__ == "__main__":
    main()
