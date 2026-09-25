"""Prepared fixed branch_refine full500 run; requires a separate formal gate.

Reuses the frozen structural runner's supervisor, prior E0 proof, denominator,
archive checks, and stop/not_run ledger. No execution is authorized by this file.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time

from src.q1_benchmarks import s6607_structural_full500 as old
from src.review import p1_r6_pilot_once as supervisor
from src.review.p1_r6_transfer_batch import ResourceGuard
from src.review.p1_unified_integration_three import exact_e1, _stage, _clean

ROOT = Path(__file__).resolve().parents[2]
SOLVER = "834d8c957538ee069c66aadac9509552a4cc69d7"
RUNNER_PATH = "src/q1_benchmarks/s6607_branch_full500.py"
CELLS = [(f"{case:03d}", core) for case in range(1, 101) for core in range(1, 6)]
BUDGET = {"workers": 4, "solver_seconds": old.MAX_SOLVER,
          "new_E0_seconds": old.MAX_E0, "batch_seconds": old.ADMISSION,
          "solver_max": 500, "E1_max": 5000, "E0_max": 500,
          "E2": 0, "retry": 0,
          "process_group_rss_limit_kib": supervisor.RSS_LIMIT_KIB}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_dependencies():
    """Freeze non-q1 imports omitted by the legacy runner's source-set check."""
    for name in ("src/q1_benchmarks/s6607_structural_full500.py",
                 "src/review/p1_unified_integration_three.py",
                 "src/review/p1_r6_pilot_once.py",
                 "src/review/p1_r6_transfer_batch.py"):
        if (ROOT / name).read_bytes() != old.frozen(SOLVER, name):
            raise RuntimeError(f"frozen helper differs: {name}")


def check_gate(path, output, expected_head):
    if (not output.is_absolute() or output.exists() or output.is_symlink()
            or output.resolve() != output or not output.is_relative_to(ROOT)):
        raise ValueError("output must be absent canonical repository path")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()
    if head != expected_head:
        raise ValueError("HEAD differs from requested frozen runner HEAD")
    gate = json.loads(path.read_text())
    expected = {"status": "admitted", "scope": "p1-branch-refine-full500",
                "owner_session": "nikolastarx/s-6607cb2735304751b36662035723372b",
                "source_head": expected_head, "solver_commit": SOLVER,
                "runner_sha256": sha(Path(__file__)), "output_dir": str(output)}
    if not isinstance(gate, dict) or any(gate.get(k) != value for k, value in expected.items()):
        raise ValueError("full500 gate identity/hash/output mismatch")
    budget = gate.get("budget")
    if (not isinstance(budget, dict) or set(budget) != set(BUDGET)
            or any(type(budget[k]) is not int or budget[k] != value
                   for k, value in BUDGET.items())):
        raise ValueError("full500 gate budget mismatch")
    try:
        expiry = datetime.fromisoformat(gate["expires_at_utc"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError) as exc:
        raise ValueError("full500 gate expiry missing/invalid") from exc
    if (expiry.tzinfo is None or expiry.utcoffset() is None
            or expiry.utcoffset().total_seconds() != 0
            or expiry <= datetime.now(timezone.utc)):
        raise ValueError("full500 gate expired/non-UTC")
    return {"gate_sha256": sha(path), "source_head": head, "budget": budget}


def objective(diag):
    value = diag.get("selected_objective")
    if (not isinstance(value, list) or len(value) != 2
            or type(value[0]) is not int or value[0] <= 0
            or type(value[1]) is not int or value[1] < 0):
        raise ValueError("selected objective unavailable/invalid")
    return tuple(value)


def selected_objective(diag):
    """A sole unchanged candidate requires E0 acceptance, not online ranking."""
    if diag.get("selected_objective") is not None:
        return objective(diag)
    structural = diag["parent"]
    response = structural["parent"]
    base = response["baseline"]["diagnostics"]
    candidates = base.get("candidates")
    digest = diag.get("selected_plan_sha256")
    if (diag.get("selected") != "parent"
            or diag.get("stop_reason") not in (
                "single-core-or-invalid", "parent-objective-unavailable-or-invalid")
            or diag.get("parent_plan_sha256") != digest
            or structural.get("selected_plan_sha256") != digest
            or structural.get("selected_objective") is not None
            or diag.get("actual_e1_calls_total") != 0
            or diag.get("attempt", {}).get("constructor_attempts") != 0
            or structural.get("extra") != []
            or response.get("refinement", {}).get("child_attempts") != 0
            or base.get("stop_reason") != "single-distinct-plan"
            or not isinstance(candidates, list) or len(candidates) != 1
            or candidates[0].get("plan_sha256") != digest
            or candidates[0].get("name") != base.get("selected")
            or response.get("selected") != base.get("selected")
            or structural.get("selected") != base.get("selected")):
        raise RuntimeError("unscored output is not a verified sole unchanged candidate")
    return None


def checked_diagnostics(diag, plan_sha256):
    if diag.get("selected_plan_sha256") != plan_sha256:
        raise RuntimeError("selected plan bytes differ")
    parent = diag.get("parent")
    if not isinstance(parent, dict):
        raise RuntimeError("structural parent missing")
    parent_total = old.checked_e1(parent)
    ledger = exact_e1(diag)
    if ledger["total"] != parent_total + ledger["branch"]:
        raise RuntimeError("branch E1 ledger differs from verified parent")
    attempt = diag.get("attempt", {})
    count = attempt.get("score_attempts")
    if (type(count) is not int or count not in (0, 1)
            or count != ledger["branch"]
            or (count and (not isinstance(attempt.get("score"), dict)
                           or type(attempt["score"].get("worker_pid")) is not int
                           or attempt["score"]["worker_pid"] <= 0))
            or diag.get("known_e1_calls_lower_bound") != ledger["total"]):
        raise RuntimeError("branch E1 worker identity/count uncertain")
    selected_objective(diag)
    return ledger["total"]


def checked_plan(plan, diag, cores):
    value = json.loads(plan.read_bytes())
    if (not isinstance(value, dict)
            or set(value) != {"node_to_subgraph", "core_schedules"}
            or not isinstance(value["core_schedules"], list)
            or len(value["core_schedules"]) != cores):
        raise RuntimeError("plan two-key/core count mismatch")
    if sha(plan) != diag.get("selected_plan_sha256"):
        raise RuntimeError("selected plan hash mismatch")
    if (diag.get("stop_reason") == "single-core-or-invalid") != (cores == 1):
        raise RuntimeError("single-core diagnostic differs from requested core count")


def reconcile_process_calls(row):
    """A resource rejection before Popen is not a launched process."""
    for key, stage_name in (("solver", "solver"), ("E0", "evaluation")):
        process = row.get(stage_name, {})
        if "supervision" not in process:
            continue
        stage = process["supervision"]
        pid = stage.get("pid")
        if type(pid) is int and pid > 0:
            row["calls"][key] = 1
        elif str(stage.get("reason", "")).startswith("resource guard before Popen"):
            row["calls"][key] = 0
            if key == "solver":
                row["calls"]["E1"] = 0
        else:
            row["calls"][key] = None


def install_checks():
    old.SOLVER = SOLVER
    old.SOLVER_PATH = "src/q1/branch_refine.py"
    old.RUNNER_PATH = RUNNER_PATH
    old.__file__ = str(Path(__file__).resolve())  # old.preflight and old.run use module __file__.
    old.MAX_CALLS = dict(solver=500, E1=5000, E0=500, E2=0)
    old.checked_diagnostics = checked_diagnostics
    prior_reuse = old.maybe_reuse
    prior_cell = old.process_cell

    def maybe_reuse(row, plan, graph_hash, config_hash, official_hash, folder):
        diag = json.loads((folder / "diagnostics.json").read_text())
        checked_plan(plan, diag, row["cores"])
        reused = prior_reuse(row, plan, graph_hash, config_hash, official_hash, folder)
        selected = selected_objective(diag)
        if (reused and selected is not None
                and (reused["makespan_cycles"], reused["scheduled_copy_bytes"]) != selected):
            raise RuntimeError("reused E0 differs from selected objective")
        return reused

    def process_cell(cell, batch, inputs, files, manifest, prior, deadline):
        row = prior_cell(cell, batch, inputs, files, manifest, prior, deadline)
        folder = batch / "cells" / cell[0] / f"k{cell[1]}"
        reconcile_process_calls(row)
        if row.get("calls", {}).get("E1") is None:
            try:
                claim = json.loads((folder / "diagnostics.json").read_text()).get(
                    "known_e1_calls_lower_bound")
                if type(claim) is int and 0 <= claim <= 10:
                    row["diagnostic_e1_lower_bound_claim"] = claim
                    old.h.write(folder / "run.json", row)
            except (OSError, ValueError, TypeError):
                pass
        if row.get("status") == "ok":
            try:
                diag = json.loads((folder / "diagnostics.json").read_text())
                official = (row["makespan_cycles"], row["scheduled_copy_bytes"])
                if (type(official[0]) is not int or official[0] <= 0
                        or type(official[1]) is not int or official[1] < 0):
                    raise RuntimeError("official E0 objective invalid")
                selected = selected_objective(diag)
                if selected is not None and official != selected:
                    raise RuntimeError("official E0 differs from selected objective")
                row["selected_objective"] = list(selected) if selected else None
                row["official_objective"] = list(official)
            except Exception as exc:
                row["status"] = "failed"
                row["failure"] = {"stage": "official-objective", "type": type(exc).__name__,
                                  "message": str(exc)}
        old.h.write(folder / "run.json", row)
        return row

    old.maybe_reuse = maybe_reuse
    old.process_cell = process_cell

    guard = ResourceGuard()
    guard_lock = threading.Lock()

    def resource_check():
        with guard_lock:
            return guard.check()

    def supervised_process(argv, folder, name, timeout, input_root):
        stage = _stage(name, [str(x) for x in argv], timeout, folder, resource_check)
        clean = (_clean(stage) or
                 (stage.get("same_pgid_residual") == []
                  and stage.get("same_pgid_residual_error") is None
                  and stage.get("cleanup", {}).get("confirmed") is True))
        return {"argv": [str(x) for x in argv], "cwd": str(ROOT),
                "started_at": stage["started_utc"], "finished_at": stage["finished_utc"],
                "wall_seconds": stage["wall_seconds"], "timeout_seconds": timeout,
                "exit_code": stage.get("returncode"), "cleanup_confirmed": clean,
                "status": ("ok" if _clean(stage) else
                           "timeout" if "timeout" in str(stage.get("reason")) else "failed"),
                "stdout": old.h.artifact(folder / f"{name}.stdout.raw"),
                "stderr": old.h.artifact(folder / f"{name}.stderr.raw"),
                "supervision": stage, "resource_sample_count": len(guard.samples),
                "log_derivation": "original child bytes, no rewrite"}

    old.h.process = supervised_process
    return guard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--full500", action="store_true", required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.workers != BUDGET["workers"]:
        parser.error("worker count must match frozen full500 budget")
    gate = check_gate(args.admission, args.output_root, args.expected_head)
    freeze_dependencies()
    install_checks()
    old.preflight()  # git-tree identity; new runner must be committed at HEAD.
    if args.prepare_only:
        print(json.dumps({"status": "prepared", **gate}, sort_keys=True))
        return 0
    admission_raw = args.admission.read_bytes()
    if hashlib.sha256(admission_raw).hexdigest() != gate["gate_sha256"]:
        raise RuntimeError("admission changed during read-only preflight")
    original_write = old.h.write
    def write_with_gate(path, obj):
        path = Path(path)
        if path.name == "batch.json":
            original = path.parent / "admission.original.json"
            if not original.exists():
                original.write_bytes(admission_raw)
            obj["admission"] = {**gate, "original_path": str(original.relative_to(ROOT)),
                                "original_sha256": sha(original)}
        return original_write(path, obj)
    old.h.write = write_with_gate
    try:
        code = old.run(args.output_root, CELLS, args.workers)
        batch = Path(args.output_root)
        meta = old.h.read(batch / "batch.json")
        lower, claimed = 0, 0
        for case, cores in CELLS:
            row = old.h.read(batch / "cells" / case / f"k{cores}" / "run.json")
            actual = row.get("calls", {}).get("E1")
            estimate = row.get("diagnostic_e1_lower_bound_claim")
            if type(actual) is int:
                lower += actual
            elif type(estimate) is int:
                lower += estimate
                claimed += 1
        meta["known_calls_lower_bound"]["E1"] = lower
        meta["diagnostic_e1_lower_bound_claim_cells"] = claimed
        old.h.write(batch / "batch.json", meta)
        return code
    finally:
        old.h.write = original_write


if __name__ == "__main__":
    raise SystemExit(main())
