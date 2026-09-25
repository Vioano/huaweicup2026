"""Offline, fail-closed export of a fixed fifth-core 500-cell study.

No solver or evaluator is invoked. Historical originals are copied byte for
byte from their pinned Git commits into a new, self-contained submission area.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import uuid

from . import board_export, feedback_benchmark as base, fifth_core_full500_runner as runner

RUNNER_COMMIT = "65c07e062ed9be78dda32ef4bb58a9891f373de9"
SOLVER_COMMIT = "f6fd8153375a7fb64f9af2c8f36c35356fb7d878"
BASELINE_COMMIT = "6fcec11ccc472a1a652b21feb6fccf85a4555598"
CONTROL = Path("results/a/q3-nikolastarx/forest-cachepair-delta-20260925/manifest.json")
CONTROL_RUN = Path("results/a/q3-nikolastarx/forest-cachepair-delta-20260925/20260924T2205Z-s3172")
MAX_FEED = 8 * 1024 * 1024


def original(root: Path, commit: str, name: str, expected: str | None = None) -> bytes:
    raw = base.git_bytes(root, commit, name)
    if expected and hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"pinned original hash differs: {name}")
    return raw


def local_original(root: Path, name: str, expected: str | None = None) -> bytes:
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"missing or escaped original: {name}")
    raw = path.read_bytes()
    if expected and hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"original hash differs: {name}")
    return raw


def save_original(stage: Path, destination: Path, raw: bytes, root: Path, output: Path) -> dict:
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    final = output / destination.relative_to(stage)
    return {"path": final.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()}


def json_gz(raw: bytes) -> dict:
    return json.loads(gzip.decompress(raw))


def strict_batch(root: Path, batch_name: str) -> tuple[dict, Path, dict]:
    root = root.resolve()
    if Path(batch_name).is_absolute() or ".." in Path(batch_name).parts:
        raise ValueError("--batch must be a repository-relative batch.json[.gz]")
    batch_path = (root / batch_name).resolve()
    if not batch_path.is_relative_to(root) or batch_path.name not in {"batch.json", "batch.json.gz"}:
        raise ValueError("--batch must be a repository-relative batch.json[.gz]")
    batch = base.read(batch_path)
    if (batch.get("status") not in {"stage_complete", "stopped_before_dispatch"} or
            not 1 <= len(batch.get("records", [])) <= 500 or
            batch.get("solver_commit") != SOLVER_COMMIT or
            batch.get("solver_module") != "src.q3.fifth_core_final_solve"):
        raise ValueError("batch is not a stopped fixed-solver segment")
    expected = {(f"{n:03d}", k) for n in range(1, 101) for k in range(1, 6)}
    records = batch["records"]
    coords = {(r["case_id"], r["cores"]) for r in records}
    if (not coords <= expected or len(coords) != len(records) or
            any(r.get("status") != "ok" for r in records)):
        raise ValueError("batch has failed, duplicated or absent cells")
    if len(records) == 500 and batch.get("full500_verified", {}).get("cells") != 500:
        raise ValueError("single full500 batch lacks runner verification")
    actual_e0 = 0
    for record in records:
        calls = record.get("calls", {})
        process = record.get("solver_process") or {}
        wall = process.get("wall_seconds")
        if (calls.get("solver") != 1 or calls.get("E1") != 0 or calls.get("E2") != 0 or
                type(calls.get("E0")) is not int or calls["E0"] < 1 or
                record.get("failure") is not None or process.get("status") != "ok" or
                process.get("exit_code") != 0 or type(wall) not in (int, float) or
                not math.isfinite(wall) or wall <= 0):
            raise ValueError("successful cell has invalid call, process or timing evidence")
        actual_e0 += calls["E0"]
    segment_cap = batch.get("budget", {}).get("max_e0_calls")
    if (type(segment_cap) is not int or not 1 <= segment_cap <= 1800 or
            actual_e0 != batch.get("e0_budget_used") or actual_e0 > segment_cap):
        raise ValueError("full500 E0 call total or frozen cap differs")
    for stage in batch["stages"]:
        if (stage["status"] not in {"stage_complete", "stopped_before_dispatch"} or
                stage["runner_argv"] != ["python", "-m", "src.q3.fifth_core_full500_runner",
                                         "--runner-commit", RUNNER_COMMIT]):
            raise ValueError("unexpected stage/runner identity")
        board_export.checked_ref(stage["manifest"], root)
    control_raw = original(root, RUNNER_COMMIT, CONTROL.as_posix())
    control = json.loads(control_raw)
    if (control.get("counts", {}).get("coordinates") != 500 or len(control.get("records", [])) != 500 or
            {(r["case_id"], r["cores"]) for r in control["records"]} != expected):
        raise ValueError("incomplete frozen Forest control map")
    return batch, batch_path.parent, control


def study_segments(root: Path, names: list[str]) -> tuple[list[tuple[str, dict, str]], dict]:
    if not 1 <= len(names) <= 2 or len(set(names)) != len(names):
        raise ValueError("study needs one or two distinct original batches")
    segments, reference, control = [], None, None
    seen, run_ids, case_inputs = set(), set(), {}
    for name in names:
        batch, _, current_control = strict_batch(root, name)
        identity = tuple(batch.get(k) for k in ("solver_commit", "solver_module", "runtime_id", "official_sha256"))
        common = (identity, batch.get("algorithm"), batch.get("environment"))
        if reference is not None and common != reference:
            raise ValueError("segments differ in fixed algorithm, runtime, inputs or environment")
        reference = common
        if batch["run_id"] in run_ids:
            raise ValueError("distinct segments must retain distinct run IDs")
        run_ids.add(batch["run_id"])
        for record in batch["records"]:
            coord = (record["case_id"], record["cores"])
            if coord in seen:
                raise ValueError(f"overlapping study coordinate: {coord}")
            seen.add(coord)
            inputs = tuple(record["identity"][k] for k in ("graph_sha256", "config_sha256", "official_sha256"))
            previous = case_inputs.setdefault(record["case_id"], inputs)
            if inputs != previous or inputs[2] != batch["official_sha256"]:
                raise ValueError("segments differ in fixed graph/config/official inputs")
        segments.append((name, batch, base.digest(root / name)))
        control = current_control
    expected = {(f"{n:03d}", k) for n in range(1, 101) for k in range(1, 6)}
    if seen != expected:
        raise ValueError(f"study has {len(seen)} unique coordinates, expected 500")
    if sum(b["e0_budget_used"] for _, b, _ in segments) > 1800:
        raise ValueError("combined study E0 calls exceed fixed 1800 cap")
    return segments, control


def percent95(values: list[float]) -> float:
    ordered = sorted(values)
    position = .95 * (len(ordered) - 1)
    low = int(position)
    return ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (position - low)


def export(root: Path, batch_names: str | list[str], output_name: str) -> dict:
    root = root.resolve()
    if Path(output_name).is_absolute() or ".." in Path(output_name).parts:
        raise ValueError("--output must be a new repository-relative Q3 result directory")
    output = (root / output_name).resolve()
    area = root / "results/a/q3-nikolastarx"
    if (not output.is_relative_to(area) or output == area or output.exists() or
            (root / output_name).absolute() != output):
        raise ValueError("--output must be a new repository-relative Q3 result directory")
    if isinstance(batch_names, str):
        batch_names = [batch_names]
    segments, control = study_segments(root, batch_names)
    jobs = [(batch, job) for _, batch, _ in segments for job in batch["records"]]
    control_by_coord = {(r["case_id"], r["cores"]): r for r in control["records"]}
    stage = output.with_name(output.name + ".tmp-" + uuid.uuid4().hex)
    stage.mkdir(parents=True, exist_ok=False)
    try:
        rows, report_rows, baselines = [], [], {}
        for batch, job in sorted(jobs, key=lambda pair: (pair[1]["case_id"], pair[1]["cores"])):
            case, cores = job["case_id"], job["cores"]
            coord = control_by_coord[(case, cores)]
            folder = (root / job["run_path"]).parent
            if base.read(root / job["run_path"]) != job:
                raise ValueError(f"batch and child receipt differ: {case}/{cores}")
            result, receipt, refs = runner.validate_result(folder, job, root)
            for name, ref in refs.items():
                board_export.checked_ref(ref, root)
                if job["artifacts"][name] != ref:
                    raise ValueError(f"batch artifact differs: {case}/{cores}/{name}")
            if receipt["official_e0_calls"] != job["calls"]["E0"] or receipt["plan_sha256"] != job["identity"]["plan_sha256"]:
                raise ValueError(f"call or identity differs: {case}/{cores}")
            board_export.checked_ref(job["evaluation_ledger"], root)
            paired = runner.audited_control(control, job, receipt, root, root / CONTROL_RUN)
            if job["solver_receipt"]["runner_paired_audit"] != paired:
                raise ValueError(f"stored paired audit differs: {case}/{cores}")
            if paired["status"] == "available_internal":
                extra = receipt["candidates"][-1]
                key = "fifth_core_p2" if receipt["selection"]["fifth_core_policy"]["status"] == "accepted" else "incumbent_p2"
                control_ref = extra[key]["artifacts"]["result"]
                raw_p2 = local_original(root, (folder / "evidence" / control_ref["path"]).relative_to(root).as_posix(), control_ref["sha256"])
                origin = "online paired E0 in this solver child"
            else:
                source = paired["source"]
                if source["kind"] == "archived_reuse":
                    raw_p2 = original(root, source["commit"], source["path"], paired["p2_result_sha256"])
                else:
                    raw_p2 = local_original(root, source["path"], paired["p2_result_sha256"])
                origin = source["kind"]
            p2 = json_gz(raw_p2)
            if (p2["makespan"] != paired["p2_makespan"] or p2["num_cores"] != cores or
                    p2.get("scene") != "B" or p2.get("problem") not in (None, 2) or
                    "cache_stats" in p2 or "cache_mode" in p2):
                raise ValueError(f"P2 control differs: {case}/{cores}")
            pair_ref = save_original(stage, stage / "p2-control" / f"{case}-k{cores}.json.gz", raw_p2, root, output)
            if case not in baselines:
                source_dir = f"results/benchmark-board/official-singlecore-20260924/{case}"
                raw_run = original(root, BASELINE_COMMIT, source_dir + "/run.json")
                raw_base = original(root, BASELINE_COMMIT, source_dir + "/result.json.gz")
                br, b = json.loads(raw_run), json_gz(raw_base)
                if (br["status"] != "ok" or br["entrypoint"] != "singlecore_evaluate.evaluate_singlecore" or
                        b["scene"] != "A" or b["num_cores"] != 1 or b["makespan"] != br["makespan_cycles"] or
                        hashlib.sha256(raw_base).hexdigest() != br["artifacts"]["result.json"]["sha256"]):
                    raise ValueError(f"official baseline differs: {case}")
                base_ref = save_original(stage, stage / "baseline" / case / "result.json.gz", raw_base, root, output)
                save_original(stage, stage / "baseline" / case / "run.json", raw_run, root, output)
                baselines[case] = (br, b, base_ref)
            br, b, base_ref = baselines[case]
            identity = job["identity"]
            if (br["graph_sha256"], br["config_sha256"], br["official_code_hash"]) != tuple(identity[k] for k in ("graph_sha256", "config_sha256", "official_sha256")):
                raise ValueError(f"baseline input differs: {case}")
            old_receipt = json.loads(original(root, control["sources"]["forest_artifact_commit"], coord["forest_receipt"]))
            old_result_raw = original(root, control["sources"]["forest_artifact_commit"], coord["forest_p3_result"])
            old_result = json_gz(old_result_raw)
            if (old_receipt["plan_sha256"] != coord["forest_plan"]["sha256"] or
                    old_receipt["result_sha256"] != hashlib.sha256(old_result_raw).hexdigest() or
                    old_result["makespan"] != old_receipt["makespan"] or
                    old_result.get("scene") != "B" or old_result.get("problem") != 3 or
                    old_result.get("cache_mode") != "read_only" or old_result.get("num_cores") != cores or
                    tuple(coord[k] for k in ("graph_sha256", "config_sha256", "official_sha256")) != tuple(identity[k] for k in ("graph_sha256", "config_sha256", "official_sha256"))):
                raise ValueError(f"Forest comparison differs: {case}/{cores}")
            old_pair = runner.audited_control(control, {**job, "case_id": case, "cores": cores},
                {"runner_paired_audit": {"status": "missing_same_plan_p2"},
                 "plan_sha256": coord["forest_plan"]["sha256"], "graph_sha256": identity["graph_sha256"],
                 "config_sha256": identity["config_sha256"], "makespan": old_result["makespan"]}, root, root / CONTROL_RUN)
            if old_pair["status"] != "available_verified_reuse":
                raise ValueError(f"Forest P2 comparison absent: {case}/{cores}")
            provenance = {
                "producer_session": batch["producer_session"], "task_url": batch["task_url"],
                "solver": {"source": board_export.source(SOLVER_COMMIT, "src/q3/fifth_core_final_solve.py", "src.q3.fifth_core_final_solve.main"),
                    "authors": batch["algorithm"]["authors"], "method": batch["algorithm"]["method"],
                    "references": batch["algorithm"]["references"], "upstream": batch["algorithm"]["upstream"],
                    "selected_algorithm_id": None, "selected_solver_commit": None},
                "runner": {"source": board_export.source(RUNNER_COMMIT, "src/q3/fifth_core_full500_runner.py", "src.q3.fifth_core_full500_runner.main"),
                    "argv": next(s["runner_argv"] for s in batch["stages"] if s["stage_id"] == job["stage_id"]),
                    "working_directory": "."},
                "environment": batch["environment"],
                "measurement": {"started_at": job["started_at"], "finished_at": job["finished_at"],
                    "seed": None, "repeat_index": 0, "cold_start": None,
                    "solver_scope": "Fresh child process through reaped exit, including import, input, construction, all online E0 calls, plan/evidence write and cleanup; OS page cache not controlled.",
                    "evaluation_scope": "Integrated E0 calls included in solver wall; no standalone final E0 timer. Archived controls and baselines excluded.",
                    "budget": {"wall_seconds": batch["budget"]["per_job_seconds"], "candidate_limit": 4 if cores == 5 else 3, "stop_reason": "completed"},
                    "calls": job["calls"], "offline_costs": batch["offline_costs"], "failure": None},
                "missing_reasons": {}}
            provenance["missing_reasons"] = board_export.explain_nulls(provenance)
            movement, cache = result["data_movement_bytes"], result["cache_stats"]
            row = {"attempt_id": f"{batch['run_id']}-P3-{job['job_key']}", "revision": 1,
                "run_id": batch["run_id"], "algorithm_id": batch["algorithm"]["id"],
                "algorithm_name": batch["algorithm"]["name"], "variant": job["variant"],
                "solver_commit": SOLVER_COMMIT,
                "parameters": {**job["parameters"], "solver_args": job["solver_args"], "e0_call_limit": job["e0_call_limit"],
                    "global_budget": batch["budget"], "workers": 1, "retry": False},
                "problem": "P3", "case_id": case, "cores": cores, "status": "ok",
                "metrics": {"makespan_cycles": result["makespan"], "solver_wall_seconds": job["solver_process"]["wall_seconds"],
                    "evaluation_wall_seconds": None, "ddr_bytes": movement["scheduled_copy_bytes"],
                    "extra_ddr_bytes": movement["added_copy_bytes"], "spill_bytes": movement["spill_added_copy_bytes"],
                    "cache_hit_rate": cache["hit_rate"]},
                "evaluator": {"route": "E0", "commit": SOLVER_COMMIT,
                    "entrypoint": "multicore_cut_evaluate_problem_3.evaluate_problem_3"},
                "identity": identity, "artifacts": {**refs, "run": base.artifact(root / job["run_path"], root),
                    "manifest": board_export.checked_ref(next(s["manifest"] for s in batch["stages"] if s["stage_id"] == job["stage_id"]), root)},
                "runtime_id": batch["runtime_id"], "observed_at": job["finished_at"],
                "timing": {"solver_includes_evaluation": True,
                    "evaluation_precision": "Parent perf_counter whole fresh child, no standalone final evaluation timer", "utc": "UTC"},
                "provenance": provenance,
                "notes": ["Fresh process; OS page cache and host contention are not controlled.",
                    f"Same-plan P2 source: {origin}; copied original bytes without new evaluation.",
                    f"Official single-core A result copied from fixed commit {BASELINE_COMMIT}; no new evaluation.",
                    "ddr_bytes is scheduled_copy_bytes, not physical DDR traffic."],
                "source_url": batch["task_url"],
                "baseline": {"graph_sha256": identity["graph_sha256"], "config_sha256": identity["config_sha256"],
                    "official_sha256": identity["official_sha256"], "route": "E0",
                    "entrypoint": "singlecore_evaluate.evaluate_singlecore", "result": base_ref},
                "cache_pair": {"graph_sha256": identity["graph_sha256"], "config_sha256": identity["config_sha256"],
                    "official_sha256": identity["official_sha256"], "plan_sha256": identity["plan_sha256"],
                    "cores": cores, "route": "E0", "result": pair_ref}}
            rows.append(row)
            report_rows.append({"case_id": case, "cores": cores, "baseline_cycles": b["makespan"],
                "forest_m3": old_result["makespan"], "forest_m2": old_pair["p2_makespan"],
                "final_m3": result["makespan"], "final_m2": p2["makespan"],
                "forest_b_over_m": b["makespan"] / old_result["makespan"],
                "final_b_over_m": b["makespan"] / result["makespan"],
                "forest_g": old_pair["p2_makespan"] / old_result["makespan"],
                "final_g": p2["makespan"] / result["makespan"],
                "solver_wall_seconds": job["solver_process"]["wall_seconds"],
                "fifth_core_status": receipt["selection"]["fifth_core_policy"]["status"],
                "selected_strategy": receipt["strategy"], "plan_changed_vs_forest": identity["plan_sha256"] != coord["forest_plan"]["sha256"],
                "makespan_delta_vs_forest": result["makespan"] - old_result["makespan"],
                "scheduled_copy_bytes": movement["scheduled_copy_bytes"], "extra_ddr_bytes": movement["added_copy_bytes"],
                "cache_hit_rate_bytes": cache["hit_rate"]})
        segment_info = [{"batch": name, "sha256": sha, "run_id": b["run_id"],
            "status": b["status"], "started_at": b["started_at"], "finished_at": b["finished_at"],
            "original_budget": b["budget"], "attempted_cells": len(b["records"]),
            "actual_calls": {"solver": len(b["records"]), "E0": b["e0_budget_used"], "E1": 0, "E2": 0}}
            for name, b, sha in segments]
        summary = {"schema": "q3-fifth-core-final-audit-v2",
            "study_id": "q3-fifth-core-final-fixed-full500", "run_ids": [b["run_id"] for _, b, _ in segments],
            "segments": segment_info,
            "actual_calls": {"solver": 500, "E0": sum(b["e0_budget_used"] for _, b, _ in segments), "E1": 0, "E2": 0},
            "source_runner_commit": RUNNER_COMMIT, "source_solver_commit": SOLVER_COMMIT,
            "cells": 500, "new_evaluations": 0, "baseline_source_commit": BASELINE_COMMIT,
            "forest_control_manifest": CONTROL.as_posix(), "forest_control_commit": control["sources"]["forest_artifact_commit"],
            "timing_scope": "fresh child process wall, not strict cold OS cache; control timings not compared",
            "solver_wall_seconds_500": {}, "selected_strategy_counts": {},
            "fifth_core_policy_status_counts": {"all": {}, "k5": {}},
            "by_core": {}}
        all_times = [r["solver_wall_seconds"] for r in report_rows]
        summary["solver_wall_seconds_500"] = {"min": min(all_times), "median": statistics.median(all_times),
            "p95": percent95(all_times), "max": max(all_times), "sum": sum(all_times)}
        for row in report_rows:
            strategy = row["selected_strategy"]
            summary["selected_strategy_counts"][strategy] = summary["selected_strategy_counts"].get(strategy, 0) + 1
            status = row["fifth_core_status"]
            for group in ("all", "k5") if row["cores"] == 5 else ("all",):
                counts = summary["fifth_core_policy_status_counts"][group]
                counts[status] = counts.get(status, 0) + 1
        for k in range(1, 6):
            subset = [r for r in report_rows if r["cores"] == k]
            times = [r["solver_wall_seconds"] for r in subset]
            summary["by_core"][str(k)] = {"n": len(subset),
                "forest_mean_b_over_m": statistics.mean(r["forest_b_over_m"] for r in subset),
                "final_mean_b_over_m": statistics.mean(r["final_b_over_m"] for r in subset),
                "forest_mean_g": statistics.mean(r["forest_g"] for r in subset),
                "final_mean_g": statistics.mean(r["final_g"] for r in subset),
                "forest_median_g": statistics.median(r["forest_g"] for r in subset),
                "final_median_g": statistics.median(r["final_g"] for r in subset),
                "solver_wall_seconds": {"min": min(times), "median": statistics.median(times),
                    "p95": percent95(times), "max": max(times), "sum": sum(times)},
                "accepted": sum(r["fifth_core_status"] == "accepted" for r in subset),
                "plan_changed_vs_forest": sum(r["plan_changed_vs_forest"] for r in subset),
                "mean_scheduled_copy_bytes": statistics.mean(r["scheduled_copy_bytes"] for r in subset),
                "mean_extra_ddr_bytes": statistics.mean(r["extra_ddr_bytes"] for r in subset),
                "mean_cache_hit_rate_bytes": statistics.mean(r["cache_hit_rate_bytes"] for r in subset)}
        (stage / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        with (stage / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(report_rows[0]))
            writer.writeheader()
            writer.writerows(report_rows)
        feeds = []
        for index in range(0, len(rows), 100):
            name = f"board-feed-{index // 100 + 1:02}-of-05.json"
            raw = (json.dumps({"schema_version": 1, "submission_version": 1,
                "records": rows[index:index + 100]}, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
            if len(raw) > MAX_FEED:
                raise ValueError(f"feed exceeds 8 MiB: {name}")
            (stage / name).write_bytes(raw)
            feeds.append({"path": (output / name).relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        (stage / "export-manifest.json").write_text(json.dumps({"summary": summary,
            "feeds": feeds, "comparison_csv": (output / "comparison.csv").relative_to(root).as_posix()},
            ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        for name, _, sha in segments:
            if base.digest(root / name) != sha:
                raise ValueError("batch changed during export")
        if output.exists():
            raise FileExistsError(output)
        os.rename(stage, output)
        return {"output": output.relative_to(root).as_posix(), "feeds": feeds, "cells": 500, "evaluations": 0}
    except BaseException:
        shutil.rmtree(stage)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="execution checkout")
    parser.add_argument("--batch", required=True, action="append", help="one or two repository-relative batch.json[.gz] originals")
    parser.add_argument("--output", required=True, help="new repository-relative output directory")
    args = parser.parse_args()
    print(json.dumps(export(args.root, args.batch, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
