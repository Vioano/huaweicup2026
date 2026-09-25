"""Prepared one-worker P1 unified checkpoint integration: 085, 075, 016 at K5.

No child starts without a separately supplied scheduler admission and an exact
source/input manifest. This is three mechanism cells, not a full-matrix result.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from src.review import p1_r6_pilot_once as supervisor
from src.review.p1_r6_transfer_batch import ResourceGuard, file_sha


ROOT = Path(__file__).resolve().parents[2]
ORDER = ("085", "075", "016")
TOTAL = 1320.0
SOLVER_SECONDS = 300.0
E0_SECONDS = 120.0
CELL_RESERVE = SOLVER_SECONDS + E0_SECONDS
REQUIRED_SOURCES = {
    "src/review/p1_unified_integration_three.py",
    "src/review/p1_r6_pilot_once.py",
    "src/review/p1_r6_transfer_batch.py",
    "src/q1/branch_refine.py",
    "src/q1/structural_refine.py",
    "src/q1/response_refine.py",
    "src/q1/unified.py",
    "src/q1/branch_aid.py",
    "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
    "data/raw/a/official/code/evaluation_validation.py",
    "data/raw/a/official/code/stub_multicore_cut_and_schedule.py",
    "data/raw/a/official/data/config.txt",
}
BUDGET = {
    "workers": 1, "solver_max": 3, "E1_max": 30, "E0_max": 3,
    "E2": 0, "retry": 0, "per_solver_seconds": 300,
    "per_E0_seconds": 120, "total_seconds": 1320,
    "sampled_group_RSS_limit_MiB": 1536,
    "variable_optional_representative_compiles_per_cell_max": 512,
    "variable_optional_final_compiles_per_cell_max": 2048,
    "new_external_Task_experiments": 0,
}
OWNER = "nikolastarx/s-6607cb2735304751b36662035723372b"
SCOPE = "p1-unified-integration-three"


def _budget_matches(value):
    return (isinstance(value, dict) and set(value) == set(BUDGET)
            and all(type(value[k]) is int and value[k] == expected
                    for k, expected in BUDGET.items()))


def _output_target(output):
    if (not output.is_absolute() or output.exists() or output.is_symlink()
            or output.resolve() != output):
        raise ValueError("output directory must be absent, absolute, and non-symlink")
    return str(output)


def checked_manifest(path, expected_head, admission, output):
    manifest = json.loads(path.read_text())
    target = _output_target(output)
    if tuple(manifest.get("order", ())) != ORDER or manifest.get("cores") != 5:
        raise ValueError("frozen three-cell order/K5 mismatch")
    if manifest.get("source_head") != expected_head:
        raise ValueError("manifest HEAD differs from requested HEAD")
    if not _budget_matches(manifest.get("budget")):
        raise ValueError("manifest budget differs from fixed integration budget")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != expected_head:
        raise ValueError("current HEAD differs from requested HEAD")
    hashes = manifest.get("source_sha256")
    required = REQUIRED_SOURCES | {
        p.relative_to(ROOT).as_posix()
        for folder in (ROOT / "src/q1", ROOT / "src/eval_exact")
        for p in folder.rglob("*.py")
    }
    if not isinstance(hashes, dict) or not required.issubset(hashes):
        raise ValueError("source manifest lacks required files")
    for name, digest in hashes.items():
        source = (ROOT / name).resolve()
        if (not source.is_relative_to(ROOT) or not source.is_file()
                or file_sha(source) != digest):
            raise ValueError(f"source SHA mismatch: {name}")
    rows = manifest.get("graphs")
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("three graph rows required")
    checked = []
    for case, row in zip(ORDER, rows):
        if row.get("case") != case:
            raise ValueError("graph order mismatch")
        graph = Path(row["path"]).resolve()
        if (not graph.is_file() or graph.stat().st_size != row.get("bytes")
                or file_sha(graph) != row.get("sha256")):
            raise ValueError(f"graph SHA/size mismatch: {case}")
        checked.append({"case": case, "graph": graph,
                        "sha256": row["sha256"], "bytes": row["bytes"]})
    gate = json.loads(admission.read_text())
    if not isinstance(gate, dict) or any((gate.get(k) != value for k, value in {
            "status": "admitted", "scope": SCOPE, "owner_session": OWNER,
            "source_head": expected_head, "manifest_sha256": file_sha(path),
            "runner_sha256": file_sha(Path(__file__)),
            "output_dir": target}.items())):
        raise ValueError("scheduler admission identity/hash/output mismatch")
    if not _budget_matches(gate.get("budget")):
        raise ValueError("scheduler admission budget mismatch")
    try:
        expiry = datetime.fromisoformat(gate["expires_at_utc"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("scheduler admission expiry missing/invalid") from exc
    if (expiry.tzinfo is None or expiry.utcoffset() is None
            or expiry.utcoffset().total_seconds() != 0
            or expiry <= datetime.now(timezone.utc)):
        raise ValueError("scheduler admission expired or lacks timezone")
    return {"head": head, "manifest_sha256": file_sha(path),
            "admission_path": str(admission.resolve()),
            "admission_sha256": file_sha(admission), "graphs": checked}


def exact_e1(diag):
    """Reconcile all three online ledgers; uncertainty must remain unknown."""
    if not isinstance(diag, dict):
        raise ValueError("solver diagnostics unavailable")
    structural = diag.get("parent")
    response = structural.get("parent") if isinstance(structural, dict) else None
    if not isinstance(response, dict):
        raise ValueError("response/structural parent ledger absent")
    baseline = response.get("baseline", {})
    unified = baseline.get("diagnostics", {})
    scores = unified.get("online_scores")
    if (not isinstance(scores, list)
            or type(unified.get("online_score_attempts")) is not int
            or len(scores) != unified["online_score_attempts"]
            or any(not isinstance(item, dict)
                   or type(item.get("worker_pid")) is not int
                   or item["worker_pid"] <= 0
                   for item in scores)):
        raise ValueError("unified online score worker identity missing/uncertain")
    values = [response.get("baseline", {}).get("actual_e1_calls"),
              response.get("refinement", {}).get("actual_e1_calls"),
              structural.get("extra_actual_e1_calls"),
              diag.get("attempt", {}).get("actual_e1_worker_calls")]
    if not all(type(v) is int and v >= 0 for v in values):
        raise ValueError("E1 dispatch count uncertain")
    if (len(scores) != values[0]
            or sum(values[:3]) != structural.get("actual_e1_calls_total")
            or sum(values) != diag.get("actual_e1_calls_total")
            or values[0] != response.get("baseline", {}).get("diagnostics", {}).get("actual_e1_calls")):
        raise ValueError("nested E1 ledgers disagree")
    if sum(values) > 10:
        raise ValueError("per-cell online E1 cap exceeded")
    return {"unified": values[0], "response": values[1],
            "structural": values[2], "branch": values[3], "total": sum(values)}


def _stage(name, argv, cap, output, check):
    # The established supervisor has a fixed 180s *pilot* total guard. Move
    # its monotonic anchor forward for this stage's cap; its own timeout,
    # identity, RSS, resource, and cleanup logic remain unchanged.
    anchor = time.monotonic() + cap - (supervisor.TOTAL_SECONDS - 4.0)
    return supervisor.run_stage(name, argv, cap, output, anchor,
                                resource_check=check)


def _clean(stage):
    return (stage.get("reason") == "complete" and stage.get("returncode") == 0
            and stage.get("same_pgid_residual") == []
            and stage.get("same_pgid_residual_error") is None)


def run(manifest_path, output, expected_head, admission, *,
        manifest_check=checked_manifest, stage_fn=_stage,
        guard=None, clock=time.monotonic):
    begun = clock()
    guard = guard or ResourceGuard()
    result = {"status": "started", "order": list(ORDER), "cells": [],
              "limits": {"worker": 1, "total_seconds": TOTAL,
                         "solver_seconds": SOLVER_SECONDS, "E0_seconds": E0_SECONDS,
                         "solver_calls": 3, "online_E1_calls": 30,
                         "E0_calls": 3, "E2_calls": 0, "retry_calls": 0},
              "calls": {"solver_process": 0, "online_E1_exact": 0,
                        "E0_process": 0, "E2": 0, "retry": 0}}
    frozen = manifest_check(manifest_path, expected_head, admission, output)
    output.mkdir(parents=True, exist_ok=False)
    try:
        result["frozen"] = {k: v for k, v in frozen.items() if k != "graphs"}
        for row in frozen["graphs"]:
            if TOTAL - (clock() - begun) < CELL_RESERVE:
                raise RuntimeError("less than 420 seconds remain before next cell")
            if not guard.check()["ok"]:
                raise RuntimeError("resource guard rejected next cell")
            case, graph = row["case"], row["graph"]
            cell = output / case
            cell.mkdir(exist_ok=False)
            plan = cell / "plan.json"
            diag_path = cell / "diagnostics.json"
            argv = [sys.executable, "-B", "-m", "src.q1.branch_refine",
                    str(graph), "--cores", "5", "--output", str(plan),
                    "--diagnostics", str(diag_path)]
            entry = {"case": case, "status": "started", "graph_sha256": row["sha256"],
                     "solver_argv": argv, "online_E1_exact": None, "stages": []}
            result["cells"].append(entry)

            def check():
                sample = guard.check()
                if clock() - begun >= TOTAL - 4.0:
                    return {**sample, "ok": False, "reason": "batch cleanup reserve"}
                return sample

            solver = stage_fn("solver", argv, SOLVER_SECONDS, cell, check)
            entry["stages"].append(solver)
            if "pid" in solver:
                result["calls"]["solver_process"] += 1
            if not _clean(solver):
                raise RuntimeError(f"{case} solver supervision failed: {solver.get('reason')}")
            if not plan.is_file() or not diag_path.is_file():
                raise RuntimeError(f"{case} solver outputs missing")
            entry["plan_sha256"] = file_sha(plan)
            entry["diagnostics_sha256"] = file_sha(diag_path)
            diag = json.loads(diag_path.read_text())
            ledger = exact_e1(diag)
            entry["online_E1_ledger"] = ledger
            entry["online_E1_exact"] = ledger["total"]
            result["calls"]["online_E1_exact"] += ledger["total"]
            if result["calls"]["online_E1_exact"] > 30:
                raise RuntimeError("cumulative E1 cap exceeded")
            if diag.get("selected_plan_sha256") != entry["plan_sha256"]:
                raise RuntimeError(f"{case} selected plan bytes disagree with diagnostics")
            selected = json.loads(plan.read_bytes())
            if (not isinstance(selected, dict)
                    or set(selected) != {"node_to_subgraph", "core_schedules"}
                    or not isinstance(selected["core_schedules"], list)
                    or len(selected["core_schedules"]) != 5):
                raise RuntimeError(f"{case} selected plan has wrong keys/core count")
            if "selected_objective" in diag:
                entry["selected_objective"] = diag["selected_objective"]
            e0dir = cell / "e0"
            e0dir.mkdir(exist_ok=False)
            official = supervisor.OFFICIAL
            e0_argv = [sys.executable, "-B",
                       str(official / "code/multicore_cut_evaluate_problem_1.py"),
                       str(graph), str(plan), "--config",
                       str(official / "data/config.txt"), "--output",
                       str(e0dir / "result.json"), "--trace-output",
                       str(e0dir / "trace.json"), "--log-output",
                       str(e0dir / "official.log")]
            e0 = stage_fn("E0", e0_argv, E0_SECONDS, cell, check)
            entry["stages"].append(e0)
            if "pid" in e0:
                result["calls"]["E0_process"] += 1
            if not _clean(e0):
                raise RuntimeError(f"{case} E0 supervision failed: {e0.get('reason')}")
            if not all((e0dir / name).is_file()
                       for name in ("result.json", "trace.json", "official.log")):
                raise RuntimeError(f"{case} E0 original artifacts missing")
            official_result = json.loads((e0dir / "result.json").read_text())
            movement = official_result.get("data_movement_bytes")
            makespan = official_result.get("makespan")
            copies = movement.get("scheduled_copy_bytes") if isinstance(movement, dict) else None
            selected_objective = entry.get("selected_objective")
            if (official_result.get("scene") != "A"
                    or type(official_result.get("num_cores")) is not int
                    or official_result["num_cores"] != 5
                    or type(makespan) is not int or makespan <= 0
                    or type(copies) is not int or copies < 0
                    or not isinstance(selected_objective, list)
                    or len(selected_objective) != 2
                    or type(selected_objective[0]) is not int
                    or type(selected_objective[1]) is not int
                    or selected_objective != [makespan, copies]):
                raise RuntimeError(f"{case} official E0 identity/objective mismatch")
            entry["official_objective"] = [makespan, copies]
            entry["official_artifact_hashes"] = supervisor.artifact_hashes(e0dir)
            entry["status"] = "complete"
        result["status"] = "complete"
    except Exception as exc:
        result["status"] = "stopped"
        result["reason"] = f"{type(exc).__name__}: {exc}"
        if result["cells"] and result["cells"][-1]["status"] == "started":
            result["cells"][-1]["status"] = "failed"
        if result["cells"] and result["cells"][-1].get("online_E1_exact") is None:
            result["calls"]["online_E1_exact"] = None
    finally:
        seen = {cell["case"] for cell in result["cells"]}
        result["cells"].extend({"case": case, "status": "not-run"}
                               for case in ORDER if case not in seen)
        result["resource_samples"] = guard.samples
        result["wall_seconds"] = clock() - begun
        try:
            result["artifact_hashes"] = supervisor.artifact_hashes(output)
        except (OSError, ValueError) as exc:
            result["status"] = "stopped"
            result["artifact_hash_error"] = f"{type(exc).__name__}: {exc}"
        with (output / "receipt.json").open("x") as stream:
            json.dump(result, stream, indent=2, sort_keys=True, default=str)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        record = checked_manifest(args.manifest, args.expected_head, args.admission,
                                  args.output_dir)
        print(json.dumps(record, default=str, sort_keys=True))
        return 0
    record = run(args.manifest, args.output_dir, args.expected_head, args.admission)
    print(json.dumps({"status": record["status"], "reason": record.get("reason"),
                      "receipt": str(args.output_dir / "receipt.json")}))
    return 0 if record["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
