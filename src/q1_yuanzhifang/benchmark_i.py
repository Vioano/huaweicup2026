"""Prospective five-cell P1 pilot runner. Requires an explicit START token.

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
import time

ROOT = Path(__file__).resolve().parents[2]
SOLVER_SHA = "397e7ca0b680f50336e4dd4eefb14831015107d8"
CELLS = (("051", 5), ("084", 2), ("084", 4), ("084", 5), ("008", 5))
START_TOKEN = "STAGE-I-20260925-START"
CONFIG = ROOT / "data/raw/a/official/data/config.txt"
SOLVER = ROOT / "src/q1_yuanzhifang/unified.py"
E0 = ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"
DEFAULT_OUTPUT = ROOT / "results/a/q1-yuanzhifang-stage-i/stage-i-20260925/run"
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


def managed_process(entry, args, cell_dir, label, timeout):
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
    limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
    if not api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        error = ctypes.WinError(ctypes.get_last_error())
        api.CloseHandle(job)
        raise error
    proc = None
    timed_out = False
    assigned = False
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
                stdout=str(stdout.relative_to(cell_dir)), stderr=str(stderr.relative_to(cell_dir)))


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


def preflight(graph_dir, output):
    from src.q1_yuanzhifang.unified import verify_sources
    verify_sources()
    for relative in ("src/q1_yuanzhifang/unified.py", "src/q1_yuanzhifang/unified_sources.json"):
        frozen = subprocess.check_output(["git", "rev-parse", f"{SOLVER_SHA}:{relative}"], cwd=ROOT).strip()
        local = subprocess.check_output(["git", "hash-object", relative], cwd=ROOT).strip()
        if local != frozen:
            raise RuntimeError(f"solver bytes differ from {SOLVER_SHA}: {relative}")
    source_paths = list(json.loads((ROOT / "src/q1_yuanzhifang/unified_sources.json").read_text(
        encoding="utf-8"))["files_sha256"])
    if os.name != "nt":
        raise RuntimeError("Windows Job Object runner requires Windows")
    if output.exists():
        raise FileExistsError(f"pilot output already exists: {output}")
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
        raise RuntimeError("less than 1 GB free near pilot output")
    return dict(solver_commit=SOLVER_SHA,
                runner_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                python=sys.version, platform=platform.platform(), cpu=platform.processor(),
                logical_cpus=os.cpu_count(), started_at=utc(),
                graph_dir=str(graph_dir), graph_sha256={case: sha(path) for case, path in graphs.items()},
                config_sha256=sha(CONFIG), official_e0_sha256=sha(E0),
                cells=[f"{case}/k{cores}" for case, cores in CELLS],
                workers=2, solver_timeout_seconds=180, e0_timeout_seconds=180,
                batch_deadline_seconds=1200, max_solver_attempts=5,
                max_online_e1_interface_attempts=25, max_external_e0_attempts=5,
                retries=0, e2_attempts=0)


def run_cell(case, cores, graph, output, deadline):
    cell = output / f"case_{case}_k{cores}"
    cell.mkdir(exist_ok=False)
    plan, diag = cell / f"case_{case}_multicore_res.json", cell / "diagnostics.json"
    record = dict(case=case, cores=cores, graph_sha256=sha(graph), status="started",
                  started_at=utc())
    try:
        left = deadline - time.monotonic()
        if left <= 0:
            record["status"] = "global-deadline-before-solver"
            return record
        record["solver"] = managed_process(SOLVER,
            [graph, "--cores", cores, "--output", plan, "--diagnostics", diag],
            cell, "solver", min(180, left))
        online = events(cell / "solver.stdout.jsonl")
        (cell / "online_events.json").write_text(json.dumps(online, indent=2) + "\n", encoding="utf-8")
        record["e1_interface_attempts_observed"] = sum(
            row["event"] == "e1_interface_attempt_started" for row in online)
        record["e1_worker_confirmed_calls"] = sum(
            row["event"] == "e1_interface_attempt_returned" and row.get("worker_pid") is not None for row in online)
        record["e1_worker_execution_unknown_attempts"] = max(
            0, record["e1_interface_attempts_observed"] - record["e1_worker_confirmed_calls"])
        record["e1_budget_charge"] = 5 if not diag.is_file() else record["e1_interface_attempts_observed"]
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
        submitted = json.loads(plan.read_text(encoding="utf-8"))
        if set(submitted) != {"node_to_subgraph", "core_schedules"}:
            record["status"] = "bad-plan-keys"
            return record
        record["plan_sha256"] = sha(plan)
        left = deadline - time.monotonic()
        if left <= 0:
            record["status"] = "global-deadline-before-e0"
            return record
        record["e0"] = managed_process(E0,
            [graph, plan, "--config", CONFIG, "--output", cell / "e0_result.json",
             "--trace-output", cell / "e0_trace.json", "--log-output", cell / "e0_log.txt"],
            cell, "e0", min(180, left))
        record["status"] = "success" if record["e0"]["returncode"] == 0 and not record["e0"]["timeout"] else "e0-failed"
        if record["status"] == "success":
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
    args = parser.parse_args()
    facts = preflight(args.graph_dir.resolve(), args.output.resolve())
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
    deadline = time.monotonic() + 1200
    started = time.perf_counter()
    rows = []
    pending = iter(CELLS)
    hard_failure = False
    with ThreadPoolExecutor(max_workers=2) as pool:
        active = {}
        def launch_next():
            case, cores = next(pending)
            active[pool.submit(run_cell, case, cores, args.graph_dir / f"case_{case}.json", output, deadline)] = (case, cores)
        for _ in range(2):
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
                for _ in range(2 - len(active)):
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
                   solver_attempts=sum("solver" in row for row in rows),
                   online_e1_interface_budget_charge=sum(row.get("e1_budget_charge", 5 if "solver" in row else 0) for row in rows),
                   external_e0_attempts=sum("e0" in row for row in rows),
                   statuses={f"{row['case']}/k{row['cores']}": row["status"] for row in rows},
                   no_retries=True, stopped_after_supervision_failure=hard_failure)
    if receipt["solver_attempts"] > 5 or receipt["online_e1_interface_budget_charge"] > 25 or receipt["external_e0_attempts"] > 5:
        raise AssertionError("pilot call budget exceeded")
    (output / "batch_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
