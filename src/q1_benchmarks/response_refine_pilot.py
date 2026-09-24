"""Two-cell experimental response-refinement pilot; no new E0 or board export.

Run only after the declared frozen solver commit exists locally. The 660-second
batch deadline is an admission threshold; supervisor cleanup is measured, so
it is not a hard whole-process wall cap. Zero retries and one active worker.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import bounded_probe_e0 as h

SOLVER = "9bb066a294c5fa0d3ba16a3aa0c27941c9c61848"
OLD_080 = "0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297"
OLD_FEED = ("results/a/q1-unified-v4-full500-20260925-s59/"
            "20260924T1952Z-s59ee/board-feed-500.json")
OLD_084_PLAN = "8685b5a867a4f66c7cacaf166d50896bd7c09a41"
OLD_084_PATH = "results/a/p1-response-dp-static-20260925/three/plan.json"
OLD_084_SHA = "5203ed797935cbf3777586247fa82191518485da839a6d680b150efb6ed5e3f6"
OLD_084_E0 = ROOT / "results/a/p1-response-dp-e0-20260925/084-k5"
CELLS = (("084", 5), ("080", 5))
MAX_SOLVER_SECONDS = 300
BATCH_ADMISSION_SECONDS = 660


def git_show(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def preflight():
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("locked Python 3.12 required")
    runner_head = h.git("rev-parse", "HEAD").decode().strip()
    runner_path = "src/q1_benchmarks/response_refine_pilot.py"
    if (ROOT / runner_path).read_bytes() != git_show(runner_head, runner_path):
        raise RuntimeError("runner differs from its committed HEAD")
    helper_path = "src/q1_benchmarks/bounded_probe_e0.py"
    if (ROOT / helper_path).read_bytes() != git_show(SOLVER, helper_path):
        raise RuntimeError("supervisor helper differs from frozen solver")
    frozen = set(h.git("ls-tree", "-r", "--name-only", SOLVER, "--",
                       "src/q1", "src/eval_exact").decode().splitlines())
    current = set(h.git("ls-files", "--", "src/q1", "src/eval_exact").decode().splitlines())
    if frozen != current:
        raise RuntimeError("tracked solver source set differs from frozen commit")
    for path in sorted(frozen):
        if (ROOT / path).read_bytes() != git_show(SOLVER, path):
            raise RuntimeError(f"frozen solver source mismatch: {path}")
    if (ROOT / "src/q1/response_refine.py").read_bytes() != git_show(SOLVER, "src/q1/response_refine.py"):
        raise RuntimeError("response wrapper differs from frozen solver")
    author_path = "AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py"
    if (ROOT / author_path).read_bytes() != git_show(SOLVER, author_path):
        raise RuntimeError("packet author dependency differs from frozen solver")
    official = h.read(ROOT / "docs/a/source-manifest.json")
    files = {row["path"]: row for row in official["files"]}
    for path, row in files.items():
        if path.startswith("code/") or path == "data/config.txt":
            if h.sha(h.OFFICIAL / path) != row["sha256"]:
                raise RuntimeError(f"official source mismatch: {path}")
    code_hash = h.digest("".join(f"{p}\t{files[p]['sha256']}\n" for p in sorted(files)
                                 if p.startswith("code/")).encode())
    if code_hash != official["official_code_hash"]:
        raise RuntimeError("official code hash mismatch")
    if h.sha(ROOT / official["case_archive"]["path"]) != official["case_archive"]["sha256"]:
        raise RuntimeError("official archive hash mismatch")
    return runner_head, official, files


def references(official, files):
    raw084 = git_show(OLD_084_PLAN, OLD_084_PATH)
    receipt = h.read(OLD_084_E0 / "receipt.json")
    if (h.digest(raw084) != OLD_084_SHA or receipt["status"] != "ok" or
            receipt["plan"]["sha256"] != OLD_084_SHA or
            receipt["official"]["official_code_hash"] != official["official_code_hash"] or
            receipt["config_sha256"] != files["data/config.txt"]["sha256"] or
            receipt["input"]["sha256"] != files["data/case_084.json"]["sha256"]):
        raise RuntimeError("084 prior E0 identity mismatch")
    old_result_path = OLD_084_E0 / "case_084_multicore_res.json"
    raw084_result = old_result_path.read_bytes()
    if h.digest(raw084_result) != receipt["artifacts"]["result"]["sha256"]:
        raise RuntimeError("084 E0 result bytes mismatch")
    feed = json.loads(git_show(OLD_080, OLD_FEED))
    rows = [r for r in feed["records"] if r.get("case_id") == "080" and r.get("cores") == 5]
    if len(rows) != 1 or rows[0].get("status") != "ok":
        raise RuntimeError("080 full500 feed row unavailable")
    row = rows[0]
    artifacts = row["artifacts"]
    raw080 = git_show(OLD_080, artifacts["plan"]["path"])
    compressed = git_show(OLD_080, artifacts["result"]["path"])
    if (h.digest(raw080) != artifacts["plan"]["sha256"] or
            h.digest(raw080) != row["identity"]["plan_sha256"] or
            h.digest(compressed) != artifacts["result"]["sha256"] or
            row["identity"]["graph_sha256"] != files["data/case_080.json"]["sha256"] or
            row["identity"]["config_sha256"] != files["data/config.txt"]["sha256"] or
            row["identity"]["official_sha256"] != official["official_code_hash"]):
        raise RuntimeError("080 full500 evidence identity mismatch")
    raw080_result = gzip.decompress(compressed)
    result080 = json.loads(raw080_result)
    result084 = json.loads(raw084_result)
    for case, result in (("084", result084), ("080", result080)):
        if result.get("scene") != "A" or result.get("num_cores") != 5:
            raise RuntimeError(f"{case} reused E0 result identity mismatch")
    if (result080["makespan"] != row["metrics"]["makespan_cycles"] or
            result080["data_movement_bytes"]["scheduled_copy_bytes"] != row["metrics"]["ddr_bytes"] or
            result084["makespan"] != receipt["metrics"]["makespan_cycles"]):
        raise RuntimeError("reused E0 metrics mismatch")
    return {"084": (raw084, raw084_result, {"plan_commit": OLD_084_PLAN,
            "plan_path": OLD_084_PATH, "result_source": "local prior E0 receipt",
            "result_receipt_path": str((OLD_084_E0 / "receipt.json").relative_to(ROOT)),
            "result_path": str(old_result_path.relative_to(ROOT))}),
            "080": (raw080, raw080_result, {"commit": OLD_080,
            "feed_path": OLD_FEED, "plan_path": artifacts["plan"]["path"],
            "result_path": artifacts["result"]["path"],
            "compressed_result_sha256": artifacts["result"]["sha256"]})}


def run(output_root):
    began = time.perf_counter()
    deadline = began + BATCH_ADMISSION_SECONDS
    runner_head, official, files = preflight()
    old = references(official, files)
    batch = Path(output_root).resolve()
    if not batch.is_relative_to(ROOT):
        raise ValueError("output root must be inside repository for supervisor receipts")
    batch.mkdir(parents=True, exist_ok=False)
    metadata = {"status": "running", "started_at": h.utc(), "finished_at": None,
                "solver_commit": SOLVER, "runner_head": runner_head,
                "runner_sha256": h.sha(__file__), "cells": CELLS,
                "maximum_calls": {"solver": 2, "E1": 13, "E0": 0, "E2": 0},
                "workers": 1, "retries": 0, "solver_timeout_seconds": MAX_SOLVER_SECONDS,
                "batch_admission_seconds": BATCH_ADMISSION_SECONDS,
                "batch_limit_scope": "Admission threshold; cleanup may extend wall time",
                "official_manifest_sha256": h.sha(ROOT / "docs/a/source-manifest.json"),
                "official_code_hash": official["official_code_hash"],
                "archive_sha256": official["case_archive"]["sha256"],
                "scope": "Two fixed cells; read-only reuse of matching prior E0; no new E0, E2 or board feed"}
    h.write(batch / "batch.json", metadata)
    stopped, total_e1 = None, 0
    with tempfile.TemporaryDirectory(prefix="q1-response-pilot-input-") as tmp:
        inputs = Path(tmp)
        with zipfile.ZipFile(ROOT / official["case_archive"]["path"]) as archive:
            for case, _ in CELLS:
                raw = archive.read(f"data/case_{case}.json")
                if h.digest(raw) != files[f"data/case_{case}.json"]["sha256"]:
                    raise RuntimeError(f"official input mismatch: {case}")
                (inputs / f"case_{case}.json").write_bytes(raw)
        for case, cores in CELLS:
            folder = batch / "cells" / case / f"k{cores}"
            folder.mkdir(parents=True)
            row = {"case_id": case, "cores": cores, "status": "not_run",
                   "graph_sha256": files[f"data/case_{case}.json"]["sha256"],
                   "calls": {"solver": 0, "E1": 0, "E0": 0, "E2": 0}}
            if stopped:
                row["not_run_reason"] = stopped
                h.write(folder / "run.json", row)
                continue
            try:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    raise TimeoutError("660-second batch admission expired")
                plan = folder / "plan.json"
                diag = folder / "diagnostics.json"
                row["calls"]["solver"] = 1
                row["calls"]["E1"] = None  # dispatch state unknown until diagnostic PID audit
                row["solver"] = h.process([sys.executable, "-B", ROOT / "src/q1/response_refine.py",
                    inputs / f"case_{case}.json", "--cores", cores, "--output", plan,
                    "--diagnostics", diag], folder, "solver", min(MAX_SOLVER_SECONDS, remaining), inputs)
                if row["solver"]["status"] != "ok" or not row["solver"]["cleanup_confirmed"]:
                    raise RuntimeError("solver failed, timed out, or cleanup unconfirmed")
                diagnosis = h.read(diag)
                baseline = diagnosis["baseline"]
                refinement = diagnosis["refinement"]
                base_scores = baseline["diagnostics"].get("online_scores", [])
                if (any(r.get("worker_pid") is None for r in base_scores) or
                        len(base_scores) != baseline["actual_e1_calls"]):
                    raise RuntimeError("baseline score dispatch count is unknown or inconsistent")
                if refinement.get("score_attempts", 0) > 1:
                    raise RuntimeError("refinement attempted more than one score")
                counts = (baseline["actual_e1_calls"], refinement["actual_e1_calls"])
                if any(type(x) is not int or x < 0 for x in counts):
                    raise RuntimeError("unknown E1 call count; stop without treating it as zero")
                if counts[0] > 6 or counts[1] > 1 or sum(counts) > 7:
                    raise RuntimeError("per-cell E1 budget exceeded")
                row["calls"]["E1"] = sum(counts)
                total_e1 += row["calls"]["E1"]
                if total_e1 > 13:
                    raise RuntimeError("batch E1 budget exceeded")
                row["baseline_score_worker_pids"] = [r["worker_pid"] for r in base_scores]
                row["refinement_score_worker_pid"] = refinement.get("score", {}).get("worker_pid")
                row["selected"] = diagnosis["selected"]
                row["plan_sha256"] = h.sha(plan)
                prior_plan, prior_result, source = old[case]
                if plan.read_bytes() != prior_plan:
                    raise RuntimeError("plan bytes differ from prior E0 plan; no reuse")
                references_dir = folder / "references"
                references_dir.mkdir()
                (references_dir / "prior-plan.json").write_bytes(prior_plan)
                (references_dir / "prior-result.json").write_bytes(prior_result)
                row["reused_e0"] = {"new_e0_calls": 0, "source": source,
                    "plan": h.artifact(references_dir / "prior-plan.json"),
                    "result": h.artifact(references_dir / "prior-result.json")}
                row["artifacts"] = {"plan": h.artifact(plan), "diagnostics": h.artifact(diag)}
                row["status"] = "ok"
            except Exception as exc:
                row["status"] = "timeout" if isinstance(exc, TimeoutError) or row.get("solver", {}).get("status") == "timeout" else "failed"
                row["failure"] = {"type": type(exc).__name__, "message": str(exc)}
                stopped = f"first failure {case}/k{cores}: {type(exc).__name__}: {exc}"
            finally:
                h.write(folder / "run.json", row)
    rows = [h.read(batch / "cells" / c / f"k{k}" / "run.json") for c, k in CELLS]
    unknown_e1 = any(r["calls"]["solver"] and r["calls"]["E1"] is None for r in rows)
    metadata.update(status="stopped" if stopped else "complete", stop_reason=stopped,
                    finished_at=h.utc(),
                    batch_wall_seconds=time.perf_counter() - began,
                    actual_e1_known_lower_bound=total_e1,
                    actual_calls={"solver": sum(r["calls"]["solver"] for r in rows),
                                  "E1": None if unknown_e1 else total_e1, "E0": 0, "E2": 0})
    h.write(batch / "batch.json", metadata)
    return 1 if stopped else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.output_root))


if __name__ == "__main__":
    main()
