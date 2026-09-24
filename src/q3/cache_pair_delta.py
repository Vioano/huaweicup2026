"""Verify a frozen forest P3/P2 pairing, then score only its 24 missing P2 cells."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / "results/a/q3-nikolastarx/forest-cachepair-delta-20260925"
MANIFEST = AREA / "manifest.json"
FOREST_ALGORITHM = "311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1"
FOREST_ARTIFACT = "bff88a66cd76ceb2d75242bf99d34bfe8b1879d4"
C2_ARTIFACT = "f0ead1a3722f70a59a084acc70700a963945b567"
P2_ARTIFACT = "11d5d3ba1820864626bb49acccbeec7a75553e80"
OFFICIAL = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"
NEW = {(case, core) for case, cores in {
    "021": (2, 4, 5), "027": (2,), "037": (1, 2, 3, 4, 5),
    "039": (1, 2, 3, 4, 5), "058": (3, 4, 5), "079": (5,),
    "080": (1, 2, 3), "097": (3, 4, 5),
}.items() for core in cores}
BUDGET = {"new_p2_e0_calls": 24, "solver_calls": 0, "p3_e0_calls": 0,
          "workers": 1, "retries": 0, "per_job_seconds": 90, "batch_seconds": 1800}


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd)


def blob(commit, path):
    return git("show", f"{commit}:{path}")


def read_json(raw):
    return json.loads(raw)


def checked_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"unsafe artifact path: {relative}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"artifact escapes checkout: {relative}")
    return resolved


def write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def checked_plan(raw, expected_hash):
    if sha(raw) != expected_hash:
        raise ValueError("plan byte hash differs")
    plan = read_json(raw)
    if set(plan) != {"node_to_subgraph", "core_schedules"}:
        raise ValueError("plan has fields outside official two-field contract")
    return plan


def clean_execution_source(manifest):
    head = git("rev-parse", "HEAD").decode().strip()
    # The execution commit is unknown until review/commit. Require its relevant
    # tracked content to be exactly what the executing checkout declares.
    paths = ["src/q3/cache_pair_delta.py", "src/q3/oracle.py",
             "results/a/q3-nikolastarx/forest-cachepair-delta-20260925/manifest.json",
             "docs/a/source-manifest.json", "data/raw/a/official"]
    subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *paths], cwd=ROOT, check=True)
    for path in paths[:-1]:
        if not git("ls-files", "--error-unmatch", path).strip():
            raise ValueError(f"execution file not tracked: {path}")
    for path, expected in manifest["sources"]["source_code_file_sha256"].items():
        if sha(checked_path(ROOT, path).read_bytes()) != expected:
            raise ValueError(f"source code file differs: {path}")
    source_manifest = read_json((ROOT / "docs/a/source-manifest.json").read_bytes())
    if source_manifest["official_code_hash"] != OFFICIAL:
        raise ValueError("official aggregate hash differs")
    return head


def preflight(manifest, forest_root):
    if manifest.get("schema") != "forest-cachepair-delta-v1" or manifest.get("budget") != BUDGET:
        raise ValueError("manifest schema or fixed budget differs")
    sources = manifest["sources"]
    if (sources["forest_algorithm_commit"] != FOREST_ALGORITHM
            or sources["forest_artifact_commit"] != FOREST_ARTIFACT
            or sources["c2_p3_artifact_commit"] != C2_ARTIFACT
            or sources["p2_result_artifact_commit"] != P2_ARTIFACT
            or sources["official_code_sha256"] != OFFICIAL):
        raise ValueError("frozen source or artifact commit differs")
    if manifest["counts"] != {"coordinates": 500, "reuse_existing_p2": 476, "new_p2_e0": 24}:
        raise ValueError("manifest count differs")
    declared = [(x["case_id"], x["cores"]) for x in manifest["new_p2_coordinates"]]
    if len(declared) != 24 or set(declared) != NEW:
        raise ValueError("frozen new P2 coordinates differ")
    head = clean_execution_source(manifest)
    if Path(git("rev-parse", "--show-toplevel", cwd=forest_root).decode().strip()).resolve() != forest_root.resolve():
        raise ValueError("--forest-root must be producer checkout root")
    records = manifest["records"]
    coords = [(r["case_id"], r["cores"]) for r in records]
    expected = {(f"{i:03}", k) for i in range(1, 101) for k in range(1, 6)}
    if len(coords) != 500 or set(coords) != expected or len(set(coords)) != 500:
        raise ValueError("full 500 mapping differs")
    if [(r["case_id"], r["cores"]) for r in records if r["action"] == "requires_new_p2_e0"] != declared:
        raise ValueError("new job order differs")
    config = (ROOT / "data/raw/a/official/data/config.txt").read_bytes()
    checked = {}
    reused = 0
    for r in records:
        case, core = r["case_id"], r["cores"]
        key = f"{case}-k{core}"
        if sha(config) != r["config_sha256"] or r["official_sha256"] != OFFICIAL:
            raise ValueError(f"config/official identity differs: {key}")
        graph_path = forest_root / f"data/raw/a/official/data/case_{case}.json"
        if sha(graph_path.read_bytes()) != r["graph_sha256"]:
            raise ValueError(f"graph identity differs: {key}")
        fp = r["forest_plan"]
        raw = checked_path(forest_root, fp["path"]).read_bytes()
        checked_plan(raw, fp["sha256"])
        if raw != blob(FOREST_ARTIFACT, fp["path"]):
            raise ValueError(f"forest artifact commit differs: {key}")
        receipt_raw = checked_path(forest_root, r["forest_receipt"]).read_bytes()
        receipt = read_json(receipt_raw)
        result_raw = checked_path(forest_root, r["forest_p3_result"]).read_bytes()
        if (receipt_raw != blob(FOREST_ARTIFACT, r["forest_receipt"])
                or result_raw != blob(FOREST_ARTIFACT, r["forest_p3_result"])):
            raise ValueError(f"forest P3 artifact commit differs: {key}")
        result = read_json(gzip.decompress(result_raw))
        if (receipt["plan_sha256"] != fp["sha256"]
                or receipt["graph_sha256"] != r["graph_sha256"]
                or receipt["config_sha256"] != r["config_sha256"]
                or receipt["result_sha256"] != sha(result_raw)
                or result.get("scene") != "B" or result.get("problem") != 3
                or result.get("cache_mode") != "read_only"
                or result.get("num_cores") != core
                or result.get("makespan") != receipt.get("makespan")):
            raise ValueError(f"forest P3 identity differs: {key}")
        c2 = r["c2_plan"]
        if r["action"] == "reuse_existing_p2":
            c2_raw = blob(C2_ARTIFACT, c2["path"])
            checked_plan(c2_raw, c2["sha256"])
            if (not r["same_plan_bytes"] or c2_raw != raw or c2["sha256"] != fp["sha256"]):
                raise ValueError(f"reuse plan differs: {key}")
            p2 = r["reused_p2"]
            if p2["source_plan_sha256"] != fp["sha256"]:
                raise ValueError(f"P2 source plan differs: {key}")
            p2raw = blob(P2_ARTIFACT, p2["path"])
            p2result = read_json(gzip.decompress(p2raw))
            if (sha(p2raw) != p2["sha256"] or p2result.get("scene") != "B"
                    or p2result.get("num_cores") != core
                    or "cache_mode" in p2result or "cache_stats" in p2result
                    or p2result.get("makespan") != p2["historical_no_l2_makespan"]):
                raise ValueError(f"historical P2 result differs: {key}")
            reused += 1
        else:
            if (case, core) not in NEW or r["same_plan_bytes"] or r.get("reused_p2") is not None:
                raise ValueError(f"new P2 action differs: {key}")
            checked[key] = (graph_path, raw, r)
    if reused != 476 or len(checked) != 24:
        raise ValueError("reuse/new counts differ")
    return head, checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forest-root", type=Path, required=True, help="producer checkout root")
    parser.add_argument("--batch", type=Path, help="new output directory inside delta result area")
    parser.add_argument("--preflight", action="store_true", help="verify all sources; run zero E0")
    args = parser.parse_args()
    if not args.preflight and args.batch is None:
        parser.error("--batch is required for execution")
    forest_root = args.forest_root.resolve()
    start = time.monotonic()
    manifest_bytes = MANIFEST.read_bytes()
    manifest = read_json(manifest_bytes)
    head, jobs = preflight(manifest, forest_root)
    if args.preflight:
        print(json.dumps({"valid": True, "mapped": 500, "historical_reuse": 476,
                          "new_jobs": 24, "new_e0_calls": 0, "execution_head": head,
                          "manifest_sha256": sha(manifest_bytes),
                          "preflight_seconds": round(time.monotonic() - start, 3)}))
        return 0
    batch = args.batch.resolve()
    if batch == AREA or not batch.is_relative_to(AREA.resolve()):
        parser.error("--batch must be a new directory inside the delta result area")
    batch.mkdir(parents=True, exist_ok=False)
    (batch / "manifest.json").write_bytes(manifest_bytes)
    state = {"schema": "forest-cachepair-delta-run-v1", "started_utc": utc(),
             "status": "running", "execution_head": head,
             "controller_sha256": sha(Path(__file__).read_bytes()),
             "manifest_sha256": sha(manifest_bytes), "forest_artifact_commit": FOREST_ARTIFACT,
             "p2_artifact_commit": P2_ARTIFACT, "budget": BUDGET,
             "preflight_seconds": time.monotonic() - start,
             "new_p2_e0_started": 0, "new_p2_e0_succeeded": 0, "jobs": []}
    write_json(batch / "run.json", state)
    deadline = start + BUDGET["batch_seconds"]
    for key, (graph, plan_raw, r) in jobs.items():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            state.update(status="stopped", stop_reason="batch_deadline")
            break
        cell = batch / "cells" / key
        cell.mkdir(parents=True, exist_ok=False)
        plan = cell / "plan.json"
        plan.write_bytes(plan_raw)
        output = cell / "result.json.gz"
        command = [sys.executable, "-B", "-m", "src.q3.oracle", str(graph),
                   str(plan), "2", str(output)]
        job = {"coordinate": key, "status": "started", "started_utc": utc(),
               "graph_sha256": r["graph_sha256"], "plan_sha256": sha(plan_raw),
               "command": ["python", "-B", "-m", "src.q3.oracle",
                           f"data/raw/a/official/data/case_{r['case_id']}.json",
                           "plan.json", "2", "result.json.gz"]}
        state["jobs"].append(job)
        state["new_p2_e0_started"] += 1
        write_json(batch / "run.json", state)
        t = time.monotonic()
        with (cell / "stdout.txt").open("xb") as stdout, (cell / "stderr.txt").open("xb") as stderr:
            proc = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                    start_new_session=True)
            try:
                returncode = proc.wait(timeout=min(BUDGET["per_job_seconds"], remaining))
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                returncode = None
        job.update(finished_utc=utc(), wall_seconds=time.monotonic() - t,
                   returncode=returncode, stdout_sha256=sha((cell / "stdout.txt").read_bytes()),
                   stderr_sha256=sha((cell / "stderr.txt").read_bytes()))
        if returncode == 0 and output.exists():
            result_raw = output.read_bytes()
            result = read_json(gzip.decompress(result_raw))
            if (result.get("scene") == "B" and result.get("num_cores") == r["cores"]
                    and "cache_mode" not in result and "cache_stats" not in result):
                job.update(status="ok", result_sha256=sha(result_raw),
                           makespan=result["makespan"])
                state["new_p2_e0_succeeded"] += 1
            else:
                job.update(status="failed", reason="P2 result identity differs")
        else:
            job.update(status="failed", reason="timeout" if returncode is None else "oracle exit")
        write_json(cell / "run.json", job)
        write_json(batch / "run.json", state)
        if job["status"] != "ok":
            state.update(status="stopped", stop_reason=f"{key}: {job['reason']}")
            break
    else:
        state["status"] = "complete"
    # Cheap terminal readback: all new inputs and execution source are still
    # exactly those preflight approved. This never dispatches another E0 call.
    try:
        if MANIFEST.read_bytes() != manifest_bytes or (batch / "manifest.json").read_bytes() != manifest_bytes:
            raise ValueError("manifest changed during run")
        for path, expected in manifest["sources"]["source_code_file_sha256"].items():
            if sha(checked_path(ROOT, path).read_bytes()) != expected:
                raise ValueError(f"source changed during run: {path}")
        for key, (graph, plan_raw, r) in jobs.items():
            if sha(graph.read_bytes()) != r["graph_sha256"]:
                raise ValueError(f"graph changed during run: {key}")
            plan = batch / "cells" / key / "plan.json"
            if state["status"] == "complete" and not plan.exists():
                raise ValueError(f"completed batch has no plan: {key}")
            if plan.exists() and plan.read_bytes() != plan_raw:
                raise ValueError(f"plan changed during run: {key}")
    except (OSError, ValueError) as error:
        state.update(status="stopped", stop_reason=f"terminal_identity: {error}")
    state.update(finished_utc=utc(), total_wall_seconds=time.monotonic() - start)
    write_json(batch / "run.json", state)
    return 0 if state["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
