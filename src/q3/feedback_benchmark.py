"""Run a pinned, explicitly manifested Q3 batch; never propose or retry jobs.

The solver is a fresh child process with an integrated E0 validation. A later
manifest may append jobs with --continue, retaining the original deadline and
call ledger. That flag is an explicit dispatch, not an automatic research gate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
REPO = "huaweibei123/huaweicup2026"


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith(".gz") else raw)


def write(path, value):
    """Atomically replace only this runner's own mutable receipt."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def relative(path, root=ROOT):
    return Path(path).resolve().relative_to(root.resolve()).as_posix()


def artifact(path, root=ROOT):
    return {"path": relative(path, root), "sha256": digest(path)}


def validate_manifest(m):
    required = {"schema", "run_id", "stage_id", "producer_session", "task_url", "solver_commit",
                "solver_module", "algorithm", "runtime_id", "budget", "jobs", "offline_costs"}
    if set(m) != required or m["schema"] != "q3-feedback-benchmark-v1":
        raise ValueError("unexpected manifest fields or schema")
    for field in ("run_id", "stage_id", "runtime_id"):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", m[field]):
            raise ValueError(f"unsafe {field}")
    if not re.fullmatch(r"[0-9a-f]{40}", m["solver_commit"]):
        raise ValueError("solver_commit must be a full SHA")
    if not re.fullmatch(r"src\.q3\.[a-z_]+", m["solver_module"]):
        raise ValueError("solver_module must be a Q3 module")
    budget = m["budget"]
    if set(budget) != {"max_e0_calls", "total_wall_seconds", "per_job_seconds"}:
        raise ValueError("budget must declare call, whole-batch and per-job limits")
    if type(budget["max_e0_calls"]) is not int or budget["max_e0_calls"] < 1:
        raise ValueError("invalid E0 limit")
    for key in ("total_wall_seconds", "per_job_seconds"):
        if type(budget[key]) not in (int, float) or not 0 < budget[key] < float("inf"):
            raise ValueError("invalid time budget")
    alg = m["algorithm"]
    if set(alg) != {"id", "name", "authors", "method", "references", "upstream"}:
        raise ValueError("algorithm requires stable identity and complete source attribution")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", alg["id"]):
        raise ValueError("invalid algorithm ID")
    if not m["jobs"]:
        raise ValueError("empty job list")
    seen = set()
    for j in m["jobs"]:
        if set(j) != {"case_id", "cores", "variant", "solver_args", "parameters", "e0_call_limit"}:
            raise ValueError("unexpected job fields")
        if not re.fullmatch(r"00[1-9]|0[1-9][0-9]|100", j["case_id"]):
            raise ValueError("invalid case")
        if type(j["cores"]) is not int or j["cores"] not in range(1, 6):
            raise ValueError("invalid cores")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,69}", j["variant"]):
            raise ValueError("unsafe variant")
        if type(j["e0_call_limit"]) is not int or j["e0_call_limit"] < 1:
            raise ValueError("invalid job call limit")
        if not isinstance(j["parameters"], dict) or not isinstance(j["solver_args"], list):
            raise ValueError("invalid parameters or argv")
        for arg in j["solver_args"]:
            if not isinstance(arg, str) or not arg or arg.startswith(("/", "~")):
                raise ValueError("unsafe solver argument")
            if arg.split("=", 1)[0] in {"--cores", "-o", "--output", "--evidence"}:
                raise ValueError("manifest may not override controlled output arguments")
        key = job_key(j)
        if key in seen:
            raise ValueError("duplicate job; repeated experiments need a distinct run")
        seen.add(key)


def job_key(job):
    return f"{job['case_id']}-k{job['cores']}-{job['variant']}"


def verify_source(commit, cases, root=ROOT):
    """Verify as-run code and frozen inputs; no evaluator imports."""
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                    cwd=root, text=True)
    if actual != commit or dirty:
        raise RuntimeError("pinned source HEAD differs or tracked files are dirty")
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "src"],
                                        cwd=root, text=True).splitlines()
    if any(p.endswith(".py") for p in untracked):
        raise RuntimeError("untracked source files would invalidate fixed source identity")
    manifest = read(root / "docs/a/source-manifest.json")
    hashes = {}
    for item in manifest["files"]:
        name = item["path"]
        if (name.startswith("code/") or name == "data/config.txt"
                or name in {f"data/case_{case}.json" for case in cases}):
            path = root / "data/raw/a/official" / name
            if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
                raise RuntimeError(f"frozen identity differs: {name}")
            hashes[relative(path, root)] = item["sha256"]
    for path in sorted((root / "src/q3").glob("*.py")):
        hashes[relative(path, root)] = digest(path)
    hashes["uv.lock"] = digest(root / "uv.lock")
    return manifest["official_code_hash"], hashes


def environment(root=ROOT):
    cpu = platform.processor() or platform.machine()
    if sys.platform == "darwin":
        cpu = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
    try:
        ram = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        ram = None
    return {"os": platform.platform(), "cpu": cpu, "gpu": "none used (CPU-only solver)",
            "ram_bytes": ram, "python": sys.version, "dependencies": "uv.lock sha256=" + digest(root / "uv.lock"),
            "threads": None, "workers": 1, "peak_rss_bytes": None}


def run_child(argv, timeout, folder, root=ROOT):
    """Measure spawn through reaped exit, killing the process group on timeout."""
    start = time.perf_counter()
    proc = subprocess.Popen(argv, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    status = "ok"
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
        status = "timeout"
    except BaseException:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise
    elapsed = time.perf_counter() - start
    if proc.returncode and status != "timeout":
        status = "failed"
    # Logs remain complete apart from explicitly disclosed local path redaction.
    for name, raw in (("stdout.txt", stdout), ("stderr.txt", stderr)):
        (folder / name).write_bytes(raw.replace(str(root).encode(), b"<repo>")
                                   .replace(sys.executable.encode(), b"<python>"))
    return {"status": status, "exit_code": proc.returncode, "wall_seconds": elapsed,
            "argv": ["python", *map(str, argv[1:])],
            "log_derivation": "stdout/stderr preserve bytes except repository and interpreter absolute paths replaced by markers"}


def validate_result(folder, job, root=ROOT):
    plan_path = folder / f"case_{job['case_id']}_multicore_res.json"
    result_path = folder / "evidence/result.json.gz"
    receipt_path = folder / "evidence/receipt.json"
    plan, result, receipt = read(plan_path), read(result_path), read(receipt_path)
    if set(plan) != {"node_to_subgraph", "core_schedules"}:
        raise ValueError("plan is not official two-field format")
    if (result.get("scene") != "B" or type(result.get("problem")) is not int
            or result["problem"] != 3 or result.get("cache_mode") != "read_only"
            or result.get("num_cores") != job["cores"]):
        raise ValueError("P3 result scene/problem/cache/core identity differs")
    count = receipt["official_e0_calls"]
    if type(count) is not int or not 1 <= count <= job["e0_call_limit"]:
        raise ValueError("actual E0 call count exceeds fixed job reservation")
    makespan = result["makespan"]
    if (type(makespan) not in (int, float) or not 0 < makespan < float("inf")
            or type(receipt["makespan"]) is not type(makespan) or receipt["makespan"] != makespan):
        raise ValueError("receipt/result Makespan value or numeric type differs")
    expected = {"plan_sha256": digest(plan_path), "result_sha256": digest(result_path),
                "graph_sha256": digest(root / f"data/raw/a/official/data/case_{job['case_id']}.json"),
                "config_sha256": digest(root / "data/raw/a/official/data/config.txt")}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("receipt does not bind graph/config/final plan/full result bytes")
    if "candidates" in receipt:
        successful = []
        for candidate in receipt["candidates"]:
            if candidate["status"] != "ok":
                if candidate["status"] not in {"unsupported", "duplicate", "rejected", "bound_pruned"} or candidate["makespan"] is not None:
                    raise ValueError("unrecognized candidate status or fabricated failed score")
                if candidate["status"] == "bound_pruned":
                    lower = candidate.get("certified_lower_bound_cycles")
                    if type(lower) is not int or lower < receipt["makespan"]:
                        raise ValueError("pruned candidate lacks an adequate lower bound")
                    unscored = candidate.get("unscored_plan")
                    if not isinstance(unscored, dict):
                        raise ValueError("pruned candidate lacks its unscored plan")
                    payload = (json.dumps(unscored, separators=(",", ":")) + "\n").encode()
                    if hashlib.sha256(payload).hexdigest() != candidate.get("unscored_plan_sha256"):
                        raise ValueError("pruned candidate plan hash differs")
                continue
            refs = candidate["artifacts"]
            for ref in refs.values():
                path = (folder / "evidence" / ref["path"]).resolve()
                if not path.is_relative_to((folder / "evidence").resolve()) or digest(path) != ref["sha256"]:
                    raise ValueError("candidate artifact hash/path differs")
            candidate_result = read(folder / "evidence" / refs["result"]["path"])
            if (candidate_result.get("scene") != "B" or candidate_result.get("problem") != 3
                    or candidate_result.get("cache_mode") != "read_only" or candidate_result.get("num_cores") != job["cores"]
                    or type(candidate_result["makespan"]) is not type(candidate["makespan"])
                    or candidate_result["makespan"] != candidate["makespan"]):
                raise ValueError("candidate score/identity disagrees with full E0 bytes")
            successful.append(candidate)
        # Stable min preserves the first (seed) candidate on exact score ties.
        if not successful or successful[0].get("name") != "seed":
            raise ValueError("confirmed seed missing")
        chosen = min(successful, key=lambda c: c["makespan"])
        if (chosen["artifacts"]["plan"]["sha256"] != expected["plan_sha256"]
                or chosen["artifacts"]["result"]["sha256"] != expected["result_sha256"]
                or chosen["strategy"] != receipt["selected_strategy"]):
            raise ValueError("published plan does not follow strict-improvement/seed-on-tie rule")
        evaluations = read(folder / "evidence/evaluations.json")
        if len(evaluations) != count or any(e["status"] not in {"ok", "failed"} for e in evaluations):
            raise ValueError("actual evaluation ledger disagrees with completed solver receipt")
    return result, receipt, {"plan": artifact(plan_path, root), "result": artifact(result_path, root),
                             "trace": artifact(receipt_path, root)}


def same_batch(old, manifest):
    for key in ("run_id", "producer_session", "task_url", "solver_commit", "solver_module", "algorithm",
                "runtime_id", "budget", "offline_costs"):
        if old[key] != manifest[key]:
            raise ValueError(f"continuation cannot change {key}")
    if old["status"] not in ("stage_complete",):
        raise ValueError("only a completed successful stage may be explicitly continued")
    if manifest["stage_id"] in [stage["stage_id"] for stage in old["stages"]]:
        raise ValueError("stage already attempted; no implicit retry")
    if {job_key(j) for j in manifest["jobs"]} & {r["job_key"] for r in old["records"]}:
        raise ValueError("job already attempted; no implicit retry")


def execute(manifest, output, continuing=False, root=ROOT, runner_argv=None):
    validate_manifest(manifest)
    root = Path(root).resolve()
    output = Path(output).resolve()
    if not output.is_relative_to(root / "results/a/q3-nikolastarx"):
        raise ValueError("batch must be in the Q3 result write area")
    meta_path = output / "batch.json"
    if continuing:
        batch = read(meta_path)
        same_batch(batch, manifest)
    else:
        if output.exists():
            raise FileExistsError("batch exists; no overwrite or automatic resume")
        batch = {key: value for key, value in manifest.items() if key not in ("jobs", "stage_id")}
        batch.update(started_at=utc(), status="prepared", stages=[], records=[], e0_budget_used=0)
    code_hash, hashes = verify_source(manifest["solver_commit"], [j["case_id"] for j in manifest["jobs"]], root)
    env = environment(root)
    if continuing and env != batch["environment"]:
        raise ValueError("continuation environment changed")
    batch.update(environment=env, official_sha256=code_hash)
    output.mkdir(parents=True, exist_ok=continuing)
    snapshot = output / f"manifest-{manifest['stage_id']}.json"
    if snapshot.exists():
        raise FileExistsError("manifest snapshot exists")
    write(snapshot, manifest)
    stage = {"stage_id": manifest["stage_id"], "started_at": utc(), "manifest": artifact(snapshot, root),
             "source_input_sha256": hashes, "status": "running", "runner_argv": runner_argv or []}
    batch["stages"].append(stage)
    batch["status"] = "running"
    write(meta_path, batch)
    deadline_utc = datetime.fromisoformat(batch["started_at"].replace("Z", "+00:00")).timestamp() + batch["budget"]["total_wall_seconds"]
    deadline = time.monotonic() + deadline_utc - time.time()
    for job in manifest["jobs"]:
        key = job_key(job)
        remaining = deadline - time.monotonic()
        if remaining <= 0 or batch["e0_budget_used"] + job["e0_call_limit"] > batch["budget"]["max_e0_calls"]:
            batch["status"] = stage["status"] = "stopped_before_dispatch"
            batch["stop_reason"] = "original deadline or global E0 reservation cap reached"
            break
        # Detect concurrent code changes before every dispatch. No calls made by this check.
        _, fresh_hashes = verify_source(manifest["solver_commit"], [job["case_id"]], root)
        if any(fresh_hashes[k] != v for k, v in hashes.items() if k in fresh_hashes):
            raise RuntimeError("source bytes changed between jobs")
        folder = output / "cells" / key
        folder.mkdir(parents=True, exist_ok=False)
        record = {**job, "job_key": key, "stage_id": manifest["stage_id"], "started_at": utc(),
                  "status": "running", "calls": {"solver": 0, "E0": None, "E1": 0, "E2": 0},
                  "e0_reserved": job["e0_call_limit"], "artifacts": {}, "run_path": relative(folder / "run.json", root),
                  "failure": None, "solver_process": None, "identity": {
                      "graph_sha256": digest(root / f"data/raw/a/official/data/case_{job['case_id']}.json"),
                      "config_sha256": digest(root / "data/raw/a/official/data/config.txt"),
                      "official_sha256": code_hash, "plan_sha256": None}}
        batch["records"].append(record)
        batch["e0_budget_used"] += job["e0_call_limit"]
        write(folder / "run.json", record)
        write(meta_path, batch)  # reserve BEFORE a child can enter E0
        argv = [sys.executable, "-B", "-m", manifest["solver_module"],
                f"data/raw/a/official/data/case_{job['case_id']}.json", "--cores", str(job["cores"]),
                "-o", relative(folder / f"case_{job['case_id']}_multicore_res.json", root),
                "--evidence", relative(folder / "evidence", root), *job["solver_args"]]
        try:
            record["calls"]["solver"] = 1
            record["solver_process"] = run_child(argv, min(remaining, batch["budget"]["per_job_seconds"]), folder, root)
            process = record["solver_process"]
            if process["status"] != "ok":
                record["status"] = process["status"]
                raise RuntimeError("solver child did not complete; no retry")
            verify_source(manifest["solver_commit"], [job["case_id"]], root)
            result, receipt, refs = validate_result(folder, job, root)
            record.update(status="ok", artifacts=refs, makespan_cycles=result["makespan"],
                          data_movement_bytes=result.get("data_movement_bytes"), cache_stats=result.get("cache_stats"),
                          solver_receipt=receipt)
            record["identity"]["plan_sha256"] = refs["plan"]["sha256"]
            record["calls"]["E0"] = receipt["official_e0_calls"]
            # Successful receipts prove unused reservations; failures/unknowns never refund.
            batch["e0_budget_used"] -= job["e0_call_limit"] - receipt["official_e0_calls"]
            if any(c["status"] == "rejected" for c in receipt.get("candidates", [])):
                record["research_stop"] = "tree candidate rejected by E0; confirmed seed preserved, no further dispatch"
                batch["status"] = stage["status"] = "stopped_on_candidate_rejection"
        except BaseException as error:
            if record["status"] == "running":
                record["status"] = "failed"
            process = record["solver_process"] or {}
            record["failure"] = {"stage": "solver_or_evidence", "reason": f"{type(error).__name__}: {error}".replace(str(root), "<repo>"),
                                 "exit_code": process.get("exit_code"), "elapsed_seconds": process.get("wall_seconds")}
            batch["status"] = stage["status"] = "stopped_on_failure"
        finally:
            ledger = folder / "evidence/evaluations.json"
            if ledger.exists():
                record["evaluation_ledger"] = artifact(ledger, root)
            record["finished_at"] = utc()
            write(folder / "run.json", record)
            write(meta_path, batch)
        if record["status"] != "ok" or batch["status"] == "stopped_on_candidate_rejection":
            break
    else:
        batch["status"] = stage["status"] = "stage_complete"
    stage["finished_at"] = batch["finished_at"] = utc()
    batch["elapsed_wall_seconds"] = time.time() - datetime.fromisoformat(batch["started_at"].replace("Z", "+00:00")).timestamp()
    write(meta_path, batch)
    return batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--continue", action="store_true", dest="continuing")
    args = parser.parse_args()
    invocation = ["python", "-m", "src.q3.feedback_benchmark", *sys.argv[1:]]
    invocation = [value.replace(str(ROOT), "<repo>") for value in invocation]
    batch = execute(read(args.manifest), args.output, args.continuing, runner_argv=invocation)
    print(json.dumps({"status": batch["status"], "attempts": len(batch["records"]),
                      "e0_budget_used": batch["e0_budget_used"], "elapsed_wall_seconds": batch["elapsed_wall_seconds"]}))
    return 0 if batch["status"] == "stage_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
