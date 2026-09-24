"""Prospective 100-case P1 k4 runner. Requires an explicit parent START token.

Windows Job Objects own each solver/E0 process tree. A gate holds the child
before imports until its process is assigned to the Job, so a timeout closes
only that cell's Job and its descendants.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
SOLVER_SHA = "08e5cbf96c57bbfb603ec9661ee591e2adb8c26f"
CELLS = tuple((f"{number:03d}", 4) for number in range(1, 101))
START_TOKEN = "STAGE-K-100K4-ONEWORKER-START"
CONFIG = ROOT / "data/raw/a/official/data/config.txt"
SOLVER = ROOT / "src/q1_yuanzhifang_stage_k/unified.py"
E0 = ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"
DEFAULT_OUTPUT = ROOT / "results/a/q1-yuanzhifang-stage-k/stage-k-100k4-oneworker-20260925/run"
MAX_SOLVER = 100
MAX_E1_ATTEMPTS = 700
MAX_NEW_E0 = 8
SOLVER_TIMEOUT = 120
E0_TIMEOUT = 180
BATCH_TIMEOUT = 2400
JOB_MEMORY_BYTES = 1 << 30
MIN_AVAILABLE_RAM_BYTES = 3 * (1 << 29)
APPROVED_REUSE_COMMIT = "9c5f87548cc7588465a638e032993969b5cac891"
APPROVED_REUSE_FEED = "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json"
APPROVED_REUSE_SHA256 = "4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764"
GATE_CODE = (
    "import os,runpy,sys,time;"
    "gate=os.environ['Q1_JOB_GATE'];entry=os.environ['Q1_JOB_ENTRY'];"
    "\nwhile not os.path.exists(gate): time.sleep(.01)"
    "\nsys.path.insert(0,os.path.dirname(entry));"
    "runpy.run_path(entry,run_name='__main__')"
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def job_api():
    """Return Win32 Job functions with verified pointer-sized structure layout."""
    from ctypes import c_size_t, c_longlong, c_uint32, c_uint64, c_void_p

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", c_longlong),
                    ("PerJobUserTimeLimit", c_longlong), ("LimitFlags", c_uint32),
                    ("MinimumWorkingSetSize", c_size_t), ("MaximumWorkingSetSize", c_size_t),
                    ("ActiveProcessLimit", c_uint32), ("Affinity", c_size_t),
                    ("PriorityClass", c_uint32), ("SchedulingClass", c_uint32)]

    class Io(ctypes.Structure):
        _fields_ = [(name, c_uint64) for name in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Io),
                    ("ProcessMemoryLimit", c_size_t), ("JobMemoryLimit", c_size_t),
                    ("PeakProcessMemoryUsed", c_size_t), ("PeakJobMemoryUsed", c_size_t)]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateJobObjectW.argtypes = (c_void_p, wintypes.LPCWSTR)
    api.CreateJobObjectW.restype = c_void_p
    api.SetInformationJobObject.argtypes = (c_void_p, ctypes.c_int, c_void_p, c_uint32)
    api.SetInformationJobObject.restype = wintypes.BOOL
    api.AssignProcessToJobObject.argtypes = (c_void_p, c_void_p)
    api.AssignProcessToJobObject.restype = wintypes.BOOL
    api.CloseHandle.argtypes = (c_void_p,)
    api.CloseHandle.restype = wintypes.BOOL
    class Accounting(ctypes.Structure):
        _fields_ = [(name, c_longlong) for name in
                    ("TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")]
        _fields_ += [(name, c_uint32) for name in
                     ("TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]

    api.QueryInformationJobObject.argtypes = (c_void_p, ctypes.c_int, c_void_p, c_uint32, c_void_p)
    api.QueryInformationJobObject.restype = wintypes.BOOL
    api.TerminateJobObject.argtypes = (c_void_p, c_uint32)
    api.TerminateJobObject.restype = wintypes.BOOL
    return api, Extended, Accounting


def managed_process(entry, args, cell_dir, label, timeout, job_memory_bytes=JOB_MEMORY_BYTES):
    """Run one owned tree; verify Job active count is zero before returning."""
    api, Extended, Accounting = job_api()
    gate = cell_dir / f"{label}.gate"
    stdout = cell_dir / f"{label}.stdout.jsonl"
    stderr = cell_dir / f"{label}.stderr.txt"
    env = os.environ.copy()
    env.update(Q1_JOB_GATE=str(gate), Q1_JOB_ENTRY=str(entry))
    command = [sys.executable, "-u", "-c", GATE_CODE, *map(str, args)]
    job = api.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = Extended()
    if type(job_memory_bytes) is not int or job_memory_bytes <= 0:
        raise ValueError("positive Job memory limit required")
    limits.BasicLimitInformation.LimitFlags = 0x00002000 | 0x00000200  # KILL_ON_JOB_CLOSE | JOB_MEMORY
    limits.JobMemoryLimit = job_memory_bytes  # aggregate committed bytes across owned descendants
    if not api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        error = ctypes.WinError(ctypes.get_last_error())
        api.CloseHandle(job)
        raise error
    proc = None
    timed_out = False
    assigned = False
    active_at_close = None
    try:
        with stdout.open("xb") as out, stderr.open("xb") as err:
            start = time.perf_counter()
            proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=out, stderr=err,
                                    stdin=subprocess.DEVNULL, close_fds=True)
            if not api.AssignProcessToJobObject(job, int(proc._handle)):
                # The child is still held at the gate and cannot spawn workers.
                raise ctypes.WinError(ctypes.get_last_error())
            assigned = True
            gate.write_text("assigned\n", encoding="utf-8")
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
    finally:
        supervision_error = None
        try:
            if assigned:
                if timed_out and not api.TerminateJobObject(job, 1):
                    supervision_error = "TerminateJobObject failed"
                end = time.monotonic() + 10
                while True:
                    accounting = Accounting()
                    if not api.QueryInformationJobObject(job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
                        supervision_error = "Job active-process query failed"
                        break
                    active_at_close = accounting.ActiveProcesses
                    if accounting.ActiveProcesses == 0:
                        break
                    if time.monotonic() >= end:
                        api.TerminateJobObject(job, 1)
                        supervision_error = f"Job still has {accounting.ActiveProcesses} active processes"
                        break
                    time.sleep(.05)
            elif proc is not None:
                # Assignment failed: this gated process is not owned by the Job.
                proc.kill()
            if proc is not None:
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    supervision_error = "parent did not exit after cleanup"
        finally:
            api.CloseHandle(job)
        if supervision_error:
            raise RuntimeError(f"{label} supervision failure: {supervision_error}")
    return dict(command=command, pid=proc.pid, returncode=proc.returncode,
                timeout=timed_out, wall_seconds=time.perf_counter() - start,
                stdout=str(stdout.relative_to(cell_dir)), stderr=str(stderr.relative_to(cell_dir)),
                job_memory_limit_bytes=job_memory_bytes, job_active_processes_at_close=active_at_close)


def events(path):
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and "event" in row:
            rows.append(row)
    return rows


def pack_exact(path):
    """Store a lossless deterministic gzip of a completed official artifact."""
    packed = path.with_name(path.name + ".gz")
    with path.open("rb") as source, packed.open("xb") as target:
        with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as out:
            shutil.copyfileobj(source, out)
    path.unlink()
    return packed


def available_ram_bytes():
    """Current Windows available physical memory, not installed capacity."""
    class Memory(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in
            ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
             "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]
    state = Memory()
    state.dwLength = ctypes.sizeof(state)
    if not ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx(ctypes.byref(state)):
        raise ctypes.WinError(ctypes.get_last_error())
    return state.ullAvailPhys


def git_original(commit, relative):
    if (not relative.startswith("results/") or ".." in Path(relative).parts
            or "\\" in relative or ":" in relative):
        raise ValueError(f"unsafe original artifact path: {relative}")
    return subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=ROOT)


def load_reuse_feed(feed, commit):
    """Pin an approved board feed to Git bytes; keep only eligible k4 rows."""
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("reuse commit must be a full Git SHA")
    relative = feed.resolve().relative_to(ROOT).as_posix()
    if commit != APPROVED_REUSE_COMMIT or relative != APPROVED_REUSE_FEED:
        raise ValueError("reuse feed/commit differs from parent-approved fixed originals")
    original = git_original(commit, relative)
    if hashlib.sha256(original).hexdigest() != APPROVED_REUSE_SHA256:
        raise ValueError("approved fixed feed SHA-256 mismatch")
    if feed.is_file() and feed.read_bytes() != original:
        raise ValueError("reuse feed differs from fixed Git bytes")
    board = json.loads(original)
    if board.get("schema_version") != 1 or board.get("submission_version") != 1:
        raise ValueError("reuse feed is not submission-v1")
    rows = {}
    for row in board.get("records", []):
        if row.get("problem") != "P1" or row.get("cores") != 4 or row.get("status") != "ok":
            continue
        case = row.get("case_id")
        if case not in {c for c, _ in CELLS}:
            continue
        if (row.get("evaluator", {}).get("route") != "E0"
                or row.get("solver_commit") != "a0537aeb72dc702af86d67d3194587d581ac207c"
                or row.get("provenance", {}).get("solver", {}).get("source", {}).get("commit")
                    != "a0537aeb72dc702af86d67d3194587d581ac207c"
                or not row.get("attempt_id") or not row.get("baseline")):
            continue
        identity = row.get("identity", {})
        if not identity.get("plan_sha256"):
            continue
        key = (case, identity["plan_sha256"])
        if key in rows:
            raise ValueError(f"ambiguous fixed E0 reuse for {case}/{key[1]}")
        rows[key] = row
    return rows, dict(commit=commit, feed_path=relative, feed_sha256=hashlib.sha256(original).hexdigest(),
                      eligible_rows=len(rows))


def reuse_e0(case, graph_sha, config_sha, official_sha, plan_path, cell, rows, commit):
    """Copy only a fully identity-matched E0 original; no score table shortcut."""
    plan_sha = sha(plan_path)
    row = rows.get((case, plan_sha))
    if row is None:
        return None
    identity = row["identity"]
    if (identity.get("graph_sha256") != graph_sha or identity.get("config_sha256") != config_sha
            or identity.get("official_sha256") != official_sha or row.get("cores") != 4):
        raise ValueError(f"fixed reuse identity mismatch for {case}")
    if row.get("metrics", {}).get("makespan_cycles") is None:
        raise ValueError("reuse record lacks official result")
    artifacts = dict(row.get("artifacts", {}))
    required = {"run", "plan", "result"}
    if not required <= set(artifacts):
        raise ValueError(f"reuse missing raw artifacts: {case}")
    # The captain's fixed 500 feed points to run-derived.json; the immutable
    # trace original is its sibling, although the feed does not list it.
    source_run_path = artifacts["run"]["path"]
    trace_path = str(Path(source_run_path).with_name("trace.json.gz")).replace("\\", "/")
    originals = {}
    for name in required:
        item = artifacts[name]
        raw = git_original(commit, item["path"])
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError(f"fixed reuse artifact hash mismatch: {case}/{name}")
        originals[name] = raw
    originals["trace"] = git_original(commit, trace_path)
    if hashlib.sha256(originals["plan"]).hexdigest() != plan_sha:
        raise ValueError("fixed reuse plan bytes differ from new plan")
    run = json.loads(originals["run"])
    if (run.get("case", run.get("case_id")) != case
            or run.get("cores", run.get("num_cores")) != 4
            or run.get("status") not in ("success", "ok")
            or run.get("graph_sha256") != graph_sha):
        raise ValueError("fixed reuse run identity mismatch")
    if (run.get("config_sha256", config_sha) != config_sha
            or run.get("official_code_hash", official_sha) != official_sha
            or run.get("evaluation", {}).get("status") not in (None, "ok")
            or run.get("evaluation", {}).get("exit_code") not in (None, 0)):
        raise ValueError("fixed reuse run configuration mismatch")
    result = json.loads(gzip.decompress(originals["result"]))
    if (result.get("scene") != "A" or result.get("num_cores") != 4
            or result.get("makespan") != row["metrics"]["makespan_cycles"]):
        raise ValueError("fixed reuse raw E0 result mismatch")
    trace_raw = gzip.decompress(originals["trace"])
    json.loads(trace_raw)
    source_artifacts = run.get("artifacts", {})
    if (source_artifacts.get("plan.json", {}).get("sha256") != plan_sha
            or source_artifacts.get("result.json", {}).get("sha256") != hashlib.sha256(gzip.decompress(originals["result"])).hexdigest()
            or source_artifacts.get("trace.json", {}).get("sha256") != hashlib.sha256(trace_raw).hexdigest()):
        raise ValueError("fixed reuse original run artifact hashes mismatch")
    # Do not write until all original bytes and identity checks pass.
    names = {"run": "reused_source_run.json", "plan": "reused_source_plan.json",
             "result": "e0_result.json.gz", "trace": "e0_trace.json.gz"}
    for name, target in names.items():
        (cell / target).write_bytes(originals[name])
    return dict(source_commit=commit, source_attempt_id=row.get("attempt_id"),
                source_artifacts={name: artifacts[name] for name in required},
                trace_git_path=trace_path, trace_sha256=hashlib.sha256(originals["trace"]).hexdigest(),
                missing_source_log="Original fixed Git archive did not include the external E0 log",
                source_e0_wall_seconds=row.get("metrics", {}).get("evaluation_wall_seconds"),
                current_external_e0_attempts=0, result_sha256=sha(cell / "e0_result.json.gz"))


def preflight(graph_dir, output, reuse_feed, reuse_commit):
    from src.q1_yuanzhifang_stage_k.unified import verify_sources
    verify_sources()
    for relative in ("src/q1_yuanzhifang_stage_k/unified.py", "src/q1_yuanzhifang_stage_k/sources.json"):
        frozen = subprocess.check_output(["git", "rev-parse", f"{SOLVER_SHA}:{relative}"], cwd=ROOT).strip()
        local = subprocess.check_output(["git", "hash-object", relative], cwd=ROOT).strip()
        if local != frozen:
            raise RuntimeError(f"solver bytes differ from {SOLVER_SHA}: {relative}")
    runner_relative = "src/q1_yuanzhifang_stage_k/benchmark_k.py"
    runner_head_blob = subprocess.check_output(["git", "rev-parse", f"HEAD:{runner_relative}"], cwd=ROOT).strip()
    runner_local_blob = subprocess.check_output(["git", "hash-object", runner_relative], cwd=ROOT).strip()
    if runner_head_blob != runner_local_blob:
        raise RuntimeError("runner bytes differ from checked out HEAD")
    source_paths = list(json.loads((ROOT / "src/q1_yuanzhifang_stage_k/sources.json").read_text(
        encoding="utf-8"))["files_sha256"]) + ["src/q1_yuanzhifang_stage_k/unified.py",
                                                        "src/q1_yuanzhifang_stage_k/sources.json"]
    if os.name != "nt":
        raise RuntimeError("Windows Job Object runner requires Windows")
    if output.exists():
        raise FileExistsError(f"batch output already exists: {output}")
    if subprocess.run(["git", "diff", "--quiet", SOLVER_SHA, "HEAD", "--", *source_paths],
                      cwd=ROOT).returncode:
        raise RuntimeError("HEAD differs from frozen solver/dependencies")
    if subprocess.run(["git", "diff", "--quiet", "--", *source_paths],
                      cwd=ROOT).returncode:
        raise RuntimeError("unstaged solver/dependency changes")
    if subprocess.run(["git", "diff", "--cached", "--quiet", "--", *source_paths],
                      cwd=ROOT).returncode:
        raise RuntimeError("staged solver/dependency changes")
    frozen_manifest = json.loads(subprocess.check_output(
        ["git", "show", f"{SOLVER_SHA}:docs/a/source-manifest.json"], cwd=ROOT))
    expected_graphs = {item["path"].split("/")[-1]: item["sha256"] for item in frozen_manifest["files"]
                       if item["path"] in {f"data/case_{case}.json" for case, _ in CELLS}}
    if len(expected_graphs) != 100:
        raise RuntimeError("frozen source manifest lacks all 100 graph hashes")
    graphs = {case: graph_dir / f"case_{case}.json" for case, _ in CELLS}
    for path in graphs.values():
        if not path.is_file():
            raise FileNotFoundError(path)
        if sha(path) != expected_graphs.get(path.name):
            raise RuntimeError(f"graph differs from frozen source manifest: {path.name}")
    from src.eval_exact._official import compute_official_code_hash
    if compute_official_code_hash() != frozen_manifest["official_code_hash"]:
        raise RuntimeError("official code hash differs from frozen source manifest")
    if shutil.disk_usage(output.parent if output.parent.exists() else ROOT).free < 1_000_000_000:
        raise RuntimeError("less than 1 GB free near batch output")
    available = available_ram_bytes()
    if available < MIN_AVAILABLE_RAM_BYTES:
        raise RuntimeError("less than 1.5 GiB available physical RAM at batch start")
    if reuse_feed is None or reuse_commit is None:
        raise ValueError("fixed --reuse-feed and --reuse-commit required; fail closed")
    reuse_rows, reuse_identity = load_reuse_feed(reuse_feed, reuse_commit)
    if len(reuse_rows) != 100:
        raise ValueError("approved feed lacks exactly 100 eligible k4 E0 originals")
    for case, _ in CELLS:
        matches = [row for (row_case, _), row in reuse_rows.items() if row_case == case]
        if len(matches) != 1:
            raise ValueError(f"approved feed has missing/ambiguous k4 original: {case}")
        identity = matches[0]["identity"]
        if (identity.get("graph_sha256") != expected_graphs[f"case_{case}.json"]
                or identity.get("config_sha256") != sha(CONFIG)
                or identity.get("official_sha256") != frozen_manifest["official_code_hash"]):
            raise ValueError(f"approved feed graph/config/official mismatch: {case}")
    return dict(solver_commit=SOLVER_SHA,
                runner_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                python=sys.version, platform=platform.platform(), cpu=platform.processor(),
                logical_cpus=os.cpu_count(), started_at=utc(),
                graph_dir=str(graph_dir), graph_sha256={case: sha(path) for case, path in graphs.items()},
                config_sha256=sha(CONFIG), official_e0_sha256=sha(E0),
                cells=[f"{case}/k{cores}" for case, cores in CELLS],
                official_code_hash=frozen_manifest["official_code_hash"],
                available_ram_bytes_at_preflight=available, reuse_source=reuse_identity,
                workers=1, available_ram_min_bytes=MIN_AVAILABLE_RAM_BYTES,
                owned_job_memory_limit_bytes=JOB_MEMORY_BYTES,
                solver_timeout_seconds=SOLVER_TIMEOUT, e0_timeout_seconds=E0_TIMEOUT,
                batch_deadline_seconds=BATCH_TIMEOUT, max_solver_attempts=MAX_SOLVER,
                max_online_e1_interface_attempts=MAX_E1_ATTEMPTS, max_external_e0_attempts=MAX_NEW_E0,
                retries=0, e2_attempts=0)


def run_cell(case, cores, graph, output, deadline, rows, reuse_commit, e0_budget,
             graph_sha, config_sha, official_sha):
    cell = output / f"case_{case}_k{cores}"
    cell.mkdir(exist_ok=False)
    plan, diag = cell / f"case_{case}_multicore_res.json", cell / "diagnostics.json"
    record = dict(case=case, cores=cores, graph_sha256=graph_sha, status="started",
                  started_at=utc())
    try:
        left = deadline - time.monotonic()
        if left <= 0:
            record["status"] = "global-deadline-before-solver"
            return record
        record["solver_attempt_charge"] = 1
        record["e1_budget_charge"] = 7
        record["solver"] = managed_process(SOLVER,
            [graph, "--cores", cores, "--output", plan, "--diagnostics", diag],
            cell, "solver", min(SOLVER_TIMEOUT, left))
        online = events(cell / "solver.stdout.jsonl")
        (cell / "online_events.json").write_text(json.dumps(online, indent=2) + "\n", encoding="utf-8")
        record["e1_interface_attempts_observed"] = sum(
            row["event"] == "e1_interface_attempt_started" for row in online)
        record["e1_worker_confirmed_calls"] = sum(
            row["event"] == "e1_interface_attempt_returned" and row.get("worker_pid") is not None for row in online)
        record["e1_worker_execution_unknown_attempts"] = max(
            0, record["e1_interface_attempts_observed"] - record["e1_worker_confirmed_calls"])
        if record["solver"]["returncode"] or not plan.is_file() or not diag.is_file():
            record["status"] = "solver-failed"
            return record
        diagnosis = json.loads(diag.read_text(encoding="utf-8"))
        record["e1_interface_attempts_diagnostics"] = diagnosis["e1_interface_attempts"]
        record["e1_worker_confirmed_calls"] = diagnosis["actual_e1_calls"]
        record["e1_worker_execution_unknown_attempts"] = diagnosis["e1_worker_execution_unknown_attempts"]
        if diagnosis["e1_interface_attempts"] != record["e1_interface_attempts_observed"]:
            record["status"] = "online-accounting-mismatch"
            return record
        if (not 0 <= diagnosis["e1_interface_attempts"] <= 7
                or diagnosis["actual_e1_calls"] > diagnosis["e1_interface_attempts"]
                or diagnosis["e1_worker_execution_unknown_attempts"]
                    != diagnosis["e1_interface_attempts"] - diagnosis["actual_e1_calls"]):
            record["status"] = "online-accounting-mismatch"
            return record
        record["e1_budget_charge"] = diagnosis["e1_interface_attempts"]
        submitted = json.loads(plan.read_text(encoding="utf-8"))
        if set(submitted) != {"node_to_subgraph", "core_schedules"}:
            record["status"] = "bad-plan-keys"
            return record
        record["plan_sha256"] = sha(plan)
        reused = reuse_e0(case, graph_sha, config_sha, official_sha, plan, cell, rows, reuse_commit)
        if reused is not None:
            record["e0_reuse"] = reused
            record["e0_result_sha256"] = reused["result_sha256"]
            record["status"] = "success-reused-e0"
            return record
        left = deadline - time.monotonic()
        if left <= 0:
            record["status"] = "global-deadline-before-e0"
            return record
        with e0_budget["lock"]:
            if e0_budget["used"] >= MAX_NEW_E0:
                record["status"] = "unevaluated-e0-budget"
                return record
            e0_budget["used"] += 1
            record["external_e0_attempt_charge"] = 1
        record["e0"] = managed_process(E0,
            [graph, plan, "--config", CONFIG, "--output", cell / "e0_result.json",
             "--trace-output", cell / "e0_trace.json", "--log-output", cell / "e0_log.txt"],
            cell, "e0", min(E0_TIMEOUT, left))
        record["status"] = "success" if record["e0"]["returncode"] == 0 and not record["e0"]["timeout"] else "e0-failed"
        if record["status"] == "success":
            result = json.loads((cell / "e0_result.json").read_bytes())
            if (result.get("scene") != "A" or result.get("num_cores") != cores
                    or type(result.get("makespan")) is not int
                    or not (cell / "e0_trace.json").is_file()
                    or not (cell / "e0_log.txt").is_file()):
                raise ValueError("official E0 success lacks valid raw result, trace or log")
            packed_result = pack_exact(cell / "e0_result.json")
            pack_exact(cell / "e0_trace.json")
            record["e0_result_sha256"] = sha(packed_result)
        return record
    except Exception as error:
        record.update(status="runner-error", error_type=type(error).__name__, message=str(error))
        return record
    finally:
        record["finished_at"] = utc()
        with (cell / "run.json").open("x", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2)
            stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--start-token")
    parser.add_argument("--producer-session", help="Actual supervising session for the run and board provenance")
    parser.add_argument("--reuse-feed", type=Path, help="Approved submission-v1 feed in fixed Git commit")
    parser.add_argument("--reuse-commit", help="Full Git SHA containing feed and raw E0 artifacts")
    args = parser.parse_args()
    facts = preflight(args.graph_dir.resolve(), args.output.resolve(), args.reuse_feed, args.reuse_commit)
    if args.preflight:
        print(json.dumps(facts, indent=2))
        return
    if args.start_token != START_TOKEN:
        raise ValueError("explicit parent START token required; preflight is read-only")
    if not args.producer_session or "/s-" not in args.producer_session:
        raise ValueError("actual supervising producer session is required")
    facts["producer_session"] = args.producer_session
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "batch_manifest.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    deadline = time.monotonic() + BATCH_TIMEOUT
    started = time.perf_counter()
    rows = []
    pending = iter(CELLS)
    hard_failure = False
    reuse_rows, _ = load_reuse_feed(args.reuse_feed, args.reuse_commit)
    e0_budget = {"used": 0, "lock": threading.Lock()}
    with ThreadPoolExecutor(max_workers=1) as pool:
        active = {}
        def launch_next():
            case, cores = next(pending)
            active[pool.submit(run_cell, case, cores, args.graph_dir / f"case_{case}.json",
                               output, deadline, reuse_rows, args.reuse_commit, e0_budget,
                               facts["graph_sha256"][case], facts["config_sha256"],
                               facts["official_code_hash"])] = (case, cores)
        for _ in range(1):
            launch_next()
        while active:
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                case, cores = active.pop(future)
                row = future.result()
                rows.append(row)
                print(json.dumps({"cell": f"{case}/k{cores}", "status": row["status"]}), flush=True)
                if row["status"] in {"runner-error", "online-accounting-mismatch", "bad-plan-keys"}:
                    hard_failure = True
            if not hard_failure:
                for _ in range(1 - len(active)):
                    try:
                        launch_next()
                    except StopIteration:
                        break
    for case, cores in pending:
        cell = output / f"case_{case}_k{cores}"
        cell.mkdir(exist_ok=False)
        row = dict(case=case, cores=cores, graph_sha256=facts["graph_sha256"][case],
                   status="not-started-after-supervision-failure", started_at=utc(), finished_at=utc())
        (cell / "run.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        rows.append(row)
    receipt = dict(finished_at=utc(), wall_seconds=time.perf_counter()-started,
                   solver_attempts_charged=sum(row.get("solver_attempt_charge", 0) for row in rows),
                   online_e1_interface_attempts_observed=sum(row.get("e1_interface_attempts_observed", 0) for row in rows),
                   online_e1_worker_confirmed_calls=sum(row.get("e1_worker_confirmed_calls", 0) for row in rows),
                   online_e1_worker_execution_unknown_attempts=sum(row.get("e1_worker_execution_unknown_attempts", 0) for row in rows),
                   online_e1_interface_budget_charge=sum(row.get("e1_budget_charge", 0) for row in rows),
                   external_e0_attempts_charged=sum(row.get("external_e0_attempt_charge", 0) for row in rows),
                   reused_e0_count=sum("e0_reuse" in row for row in rows),
                   statuses={f"{row['case']}/k{row['cores']}": row["status"] for row in rows},
                   no_retries=True, stopped_after_supervision_failure=hard_failure)
    if (receipt["solver_attempts_charged"] > MAX_SOLVER
            or receipt["online_e1_interface_budget_charge"] > MAX_E1_ATTEMPTS
            or receipt["external_e0_attempts_charged"] > MAX_NEW_E0):
        raise AssertionError("batch call budget exceeded")
    (output / "batch_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
