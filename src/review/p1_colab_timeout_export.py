"""Export the one frozen 014/k4 E0 timeout as a separate board record."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from src.review.p1_colab_full500_export import ROOT, RUN_ID, SOLVER, artifact, digest

PUBLIC = ROOT / "results/a/p1-colab-full500-20260925/public-v3"
CASE = "014"
CORES = 4


def build_record(template: dict, run: dict, plan_artifact: dict, run_artifact: dict) -> dict:
    ev = run.get("evaluation", {})
    if (run.get("run_id") != RUN_ID or run.get("case_id") != CASE or
            run.get("cores") != CORES or run.get("status") != "timeout" or
            run.get("model_source", {}).get("solver_commit") != SOLVER or
            run.get("calls") != {"solver": 1, "E1": 3, "E0": 1, "E2": 0} or
            run.get("solver", {}).get("status") != "ok" or
            run["solver"].get("cleanup_confirmed") is not True or
            ev.get("status") != "timeout" or ev.get("cleanup_confirmed") is not True or
            ev.get("exit_code") != -9 or ev.get("wall_seconds") != 900.065508997):
        raise ValueError("014/k4 frozen timeout identity or child receipt differs")
    r = deepcopy(template)
    r.update(attempt_id=f"nikolastarx-{RUN_ID}-P1-{CASE}-k{CORES}-r0",
             revision=1, case_id=CASE, cores=CORES, status="timeout",
             observed_at=run["finished_at"])
    r["parameters"]["cores"] = CORES
    r["metrics"] = {"makespan_cycles": None,
                    "solver_wall_seconds": run["solver"]["wall_seconds"],
                    "evaluation_wall_seconds": ev["wall_seconds"],
                    "ddr_bytes": None, "extra_ddr_bytes": None, "spill_bytes": None}
    r["identity"]["graph_sha256"] = run["graph_sha256"]
    r["identity"]["plan_sha256"] = plan_artifact["sha256"]
    r["artifacts"] = {"plan": plan_artifact, "run": run_artifact}
    r.pop("baseline", None)
    r["provenance"]["solver"]["selected_algorithm_id"] = run["selected"]
    r["provenance"]["solver"]["selected_solver_commit"] = SOLVER
    m = r["provenance"]["measurement"]
    m.update(started_at=run["started_at"], finished_at=run["finished_at"],
             calls=run["calls"], failure={"stage": "E0",
             "reason": "Official E0 child reached its 900-second timeout; cause of runtime unknown; no result was produced",
             "exit_code": ev["exit_code"], "elapsed_seconds": ev["wall_seconds"]})
    m["budget"]["stop_reason"] = "official E0 timeout; no retry"
    r["provenance"]["missing_reasons"]["provenance.measurement.seed"] = "No random seed was specified or recorded for this run"
    r["notes"] = ["014/k4 official E0 timed out and produced no result; prior v4 score is not used",
                  "E0 direct child cleanup confirmed; supervisor whole-tree cleanup is a separate boundary"]
    return r


def export(output: Path) -> Path:
    if output.exists():
        raise FileExistsError(output)
    batch = json.loads((PUBLIC / "batch.json").read_text())
    if batch.get("run_id") != RUN_ID or batch.get("status") != "stopped":
        raise ValueError("wrong source batch")
    run_path = PUBLIC / "failures/014/k4/run.json"
    plan_path = PUBLIC / "failures/014/k4/plan.json"
    run = json.loads(run_path.read_text())
    if run.get("artifacts", {}).get("plan", {}).get("sha256") != digest(plan_path.read_bytes()):
        raise ValueError("plan does not match frozen run receipt")
    if set(json.loads(plan_path.read_text())) != {"node_to_subgraph", "core_schedules"}:
        raise ValueError("plan shape differs")
    source_feed = next(PUBLIC.glob("board-feed-*.json"))
    template = json.loads(source_feed.read_text())["records"][0]
    r = build_record(template, run, artifact(plan_path), artifact(run_path))
    output.mkdir(parents=True)
    feed = output / "board-feed-014-k4-timeout.json"
    feed.write_text(json.dumps({"schema_version": 1, "submission_version": 1, "records": [r]},
                               ensure_ascii=False, indent=2) + "\n")
    return feed


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-root", type=Path, required=True)
    print(export(p.parse_args().output_root.resolve()))
