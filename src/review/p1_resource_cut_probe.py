"""Opt-in static rational-model probe for two frozen public P1 plans; NOT E0."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.review.p1_memory_key_contract import source_scope

PUBLIC = ROOT / "results/a/p1-resource-cut-candidate-20260925/public"
CASES = ("008", "095")
RECEIPT_SHA256 = "f307723a5d623d64620c3f9bf6cdfc696c937f733d8269448c864cf2fcdc63af"
RECEIPT_SOURCE_COMMIT = "cd185d3d96b1068a18d68900938e5dfcbf722bc4"
MAX_TASK_COMPILES = 20
MAX_RESPONSES = 2


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def execute(output):
    from src.q1.response_compile import _official_modules
    from src.q1.compiled_memory_response import compile_plan
    from src.q1.response_oracle import simulate

    began = time.perf_counter()
    report = {"kind": "full-graph-compiled-Fraction-model-NOT-E0",
              "status": "started", "rows": [],
              "calls": {"candidate_constructor": 0, "Task_compile_attempts_reserved": 0,
                        "Task_compile_confirmed_completed": 0, "response_attempts": 0,
                        "response_completed": 0, "E0": 0, "E1": 0, "E2": 0,
                        "retry": 0}}
    try:
        receipt_path = PUBLIC / "receipt.json"
        receipt_raw = receipt_path.read_bytes()
        if digest(receipt_raw) != RECEIPT_SHA256:
            raise ValueError("public receipt bytes differ from frozen SHA-256")
        receipt = json.loads(receipt_raw)
        if receipt.get("source_commit") != RECEIPT_SOURCE_COMMIT:
            raise ValueError("public receipt source commit differs")
        rows = receipt.get("rows")
        if not isinstance(rows, list) or [row.get("case_id") for row in rows] != list(CASES):
            raise ValueError("public receipt case order differs")
        task_counts = [row.get("tasks") for row in rows]
        if any(type(count) is not int or not 1 <= count <= 10 for count in task_counts):
            raise ValueError("each frozen plan must contain 1..10 Tasks")
        if sum(task_counts) > MAX_TASK_COMPILES or len(rows) > MAX_RESPONSES:
            raise ValueError("whole-batch compile/response budget exceeded")
        shutil.copyfile(receipt_path, output / "input-receipt.json")
        manifest = json.loads((ROOT / "docs/a/source-manifest.json").read_text())
        manifest_files = {row["path"]: row for row in manifest["files"]}
        archive = ROOT / manifest["case_archive"]["path"]
        if digest(archive.read_bytes()) != manifest["case_archive"]["sha256"]:
            raise ValueError("official case archive hash differs")
        config = ROOT / "data/raw/a/official/data/config.txt"
        if digest(config.read_bytes()) != manifest_files["data/config.txt"]["sha256"]:
            raise ValueError("frozen config hash differs")
        scene, _, _, validation = _official_modules()
        settings = validation.read_evaluation_config(config)
        capacity, bandwidth = settings["capacity"], settings["bandwidth"]
        gate = scene.read_scene_a_config(config)["task_same_core_wait_cycles"]
        scope = source_scope(capacity, bandwidth)
        report.update(receipt_sha256=digest(receipt_raw), receipt_source_commit=receipt["source_commit"],
                      official_archive_sha256=manifest["case_archive"]["sha256"],
                      config_sha256=manifest_files["data/config.txt"]["sha256"],
                      source_scope=repr(scope), capacity=capacity, bandwidth=bandwidth,
                      same_core_gate=gate)
        with zipfile.ZipFile(archive) as z:
            for entry in rows:
                case = entry["case_id"]
                row = {"case_id": case, "status": "started", "plan_sha256": entry["plan_sha256"],
                       "graph_sha256": entry["graph_sha256"], "task_compiles_confirmed_completed": None}
                report["rows"].append(row)
                plan_path = PUBLIC / case / "plan.json"
                plan_raw = plan_path.read_bytes()
                graph_raw = z.read(f"data/case_{case}.json")
                if digest(plan_raw) != entry["plan_sha256"] or digest(graph_raw) != entry["graph_sha256"]:
                    raise ValueError(f"receipt plan/graph SHA mismatch for {case}")
                (output / f"{case}-plan.json").write_bytes(plan_raw)
                (output / f"{case}-graph.json").write_bytes(graph_raw)
                plan, graph = json.loads(plan_raw), json.loads(graph_raw)
                expected = entry["tasks"]
                if sum(map(len, plan["core_schedules"])) != expected:
                    raise ValueError(f"{case}: Task budget or plan count mismatch")
                if source_scope(capacity, bandwidth) != scope:
                    raise ValueError("source/config/runtime drift before Task compile")
                if report["calls"]["Task_compile_attempts_reserved"] + expected > MAX_TASK_COMPILES:
                    raise ValueError("whole-batch Task compile budget exceeded")
                report["calls"]["Task_compile_attempts_reserved"] += expected
                # A thrown compile may have completed an unknown prefix of Tasks.
                try:
                    lines, certificate = compile_plan(graph, plan, capacity, bandwidth)
                except Exception:
                    row["task_compile_unknown_prefix"] = True
                    report["calls"]["Task_compile_confirmed_completed"] = None
                    raise
                completed = sum(map(len, lines))
                row["task_compiles_confirmed_completed"] = completed
                report["calls"]["Task_compile_confirmed_completed"] += completed
                if completed != expected or source_scope(capacity, bandwidth) != scope:
                    raise ValueError(f"{case}: compiled Task count or source drift")
                row["certificate"] = certificate
                if report["calls"]["response_attempts"] >= MAX_RESPONSES:
                    raise ValueError("whole-batch Fraction response budget exceeded")
                report["calls"]["response_attempts"] += 1
                response = simulate(lines, gate)
                report["calls"]["response_completed"] += 1
                row.update(status="success", fraction_model_makespan=str(response["makespan"]),
                           fraction_model_response=response)
        report["status"] = "success"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}",
                      traceback=traceback.format_exc())
        raise
    finally:
        report["elapsed_seconds"] = time.perf_counter() - began
        (output / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("explicit --execute required; no graph compilation started")
    args.output.mkdir(parents=False, exist_ok=False)
    execute(args.output)


if __name__ == "__main__":
    main()
