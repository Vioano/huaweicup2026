"""One-cell Stage M benchmark with an explicit parent START token."""
from __future__ import annotations

import argparse
import ast
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

from src.q1_yuanzhifang_stage_m.job_m import JOB_MEMORY_BYTES, managed_process

ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = "a0537aeb72dc702af86d67d3194587d581ac207c"
SOURCE_COMMIT = "6003ef7684c5649b5ccafb653c4b11aa67945439"
JOB_SOURCE = "aa66a805551a2f2225795f2ec5b2db444ba35b28"
JOB_SOURCE_PATH = "src/q1_yuanzhifang/job_l.py"
SOLVER_PATH = "src/q1_yuanzhifang_stage_m/adjacent_union.py"
SOLVER_MODULE = "src.q1_yuanzhifang_stage_m.adjacent_union"
E0_PATH = "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"
CONFIG_PATH = "data/raw/a/official/data/config.txt"
OUT = ROOT / "results/a/q1-yuanzhifang-stage-m/stage-m-20260925/run"
TOKEN = "STAGE-M-20260925-START"
CASE, CORES = "044", 2
MIN_RAM_BYTES = 1 << 30
SOLVER_TIMEOUT, E0_TIMEOUT, BATCH_TIMEOUT = 60, 60, 180

# The static local import closure of adjacent_union -> shared_input_budget.
BASE_DEPENDENCIES = (
    "src/q1/shared_input_budget.py",
    "src/q1/bounded_tasks.py",
    "src/q1/tree_frontier.py",
    "src/q1/component_pack.py",
    "data/raw/a/official/code/stub_multicore_cut_and_schedule.py",
    "data/raw/a/official/code/evaluation_validation.py",
    CONFIG_PATH,
)
METHOD_FILES = (
    SOLVER_PATH,
    "src/q1_yuanzhifang_stage_m/__init__.py",
    "src/q1_yuanzhifang_stage_m/sources.json",
)
BASELINE_COMMIT = "6fcec11ccc472a1a652b21feb6fccf85a4555598"
BASELINE_DIR = "results/benchmark-board/official-singlecore-20260924/044"
V4_COMMIT = "9c5f87548cc7588465a638e032993969b5cac891"
V4_K2_RESULT = (
    "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/"
    "cells/044/k2/result.json.gz"
)


def sha(path_or_bytes) -> str:
    raw = path_or_bytes if isinstance(path_or_bytes, bytes) else Path(path_or_bytes).read_bytes()
    return hashlib.sha256(raw).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def available_ram_bytes() -> int:
    """Windows available physical memory from GlobalMemoryStatusEx."""
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


def source_manifest() -> dict:
    return json.loads(git("show", f"{SOURCE_COMMIT}:docs/a/source-manifest.json"))


def check_source_file(commit: str, path: str, expected: str | None = None) -> str:
    pinned = git("rev-parse", f"{commit}:{path}").decode().strip()
    local = git("hash-object", path).decode().strip()
    if local != pinned:
        raise RuntimeError(f"working source differs from pinned {commit}:{path}")
    raw = (ROOT / path).read_bytes()
    actual = sha(raw)
    if expected is not None and actual != expected:
        raise RuntimeError(f"SHA-256 mismatch for {path}")
    return actual


def source_closure() -> dict:
    manifest = source_manifest()
    local_hashes = {}
    for path in METHOD_FILES:
        local_hashes[path] = check_source_file(SOURCE_COMMIT, path)
    m_sources = json.loads((ROOT / METHOD_FILES[-1]).read_text(encoding="utf-8"))
    if m_sources.get("base_commit") != BASE_COMMIT:
        raise RuntimeError("Stage M base source commit mismatch")
    listed = m_sources.get("source_files_sha256", {})
    for path in BASE_DEPENDENCIES:
        pinned = git("rev-parse", f"{BASE_COMMIT}:{path}").decode().strip()
        local = git("hash-object", path).decode().strip()
        if local != pinned:
            raise RuntimeError(f"base dependency differs from {BASE_COMMIT}:{path}")
        digest = sha(ROOT / path)
        if path in listed and digest != listed[path]:
            raise RuntimeError(f"M sources manifest SHA mismatch for {path}")
        local_hashes[path] = digest
    if "src/q1/component_pack.py" not in listed:
        raise RuntimeError("Stage M source manifest must include transitive component_pack dependency")
    code_dir = ROOT / "data/raw/a/official/code"
    code_files = sorted(p for p in code_dir.iterdir() if p.is_file())
    signature = "".join(f"code/{p.name}\t{sha(p)}\n" for p in code_files)
    official_hash = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    if official_hash != manifest["official_code_hash"]:
        raise RuntimeError("complete official code identity differs from source manifest")
    if sha(ROOT / CONFIG_PATH) != next(x["sha256"] for x in manifest["files"] if x["path"] == "data/config.txt"):
        raise RuntimeError("official config differs from source manifest")
    case_rows = [x for x in manifest["files"] if x["path"] == f"data/case_{CASE}.json"]
    if len(case_rows) != 1:
        raise RuntimeError("frozen manifest must contain exactly one case 044 graph hash")
    graph_expected_sha = case_rows[0]["sha256"]
    # AST-only check: no evaluator or Task compiler is imported by this source closure.
    py_paths = [p for p in METHOD_FILES if p.endswith(".py")] + [p for p in BASE_DEPENDENCIES if p.endswith(".py")]
    imports = {}
    for path in py_paths:
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
        imports[path] = sorted({(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} |
                               {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names})
    if any(any(token in name.lower() for token in ("e1", "task_compil", "multicore_cut_evaluate"))
           for names in imports.values() for name in names):
        raise RuntimeError("unexpected online evaluator or Task compiler import in source closure")
    return dict(method_source_commit=SOURCE_COMMIT, method_files=local_hashes,
                base_commit=BASE_COMMIT, official_code_hash=official_hash,
                official_code_files={p.name: sha(p) for p in code_files},
                config_sha256=sha(ROOT / CONFIG_PATH), expected_graph_sha256=graph_expected_sha,
                graph_id="official/case_044.json", static_imports=imports,
                no_online_evaluator_or_task_compiler_import=True)


def preflight(graph_dir: Path, output: Path) -> dict:
    if os.name != "nt":
        raise RuntimeError("Stage M requires Windows Job Objects")
    if output.exists():
        raise FileExistsError(f"refuse to overwrite {output}")
    if available_ram_bytes() < MIN_RAM_BYTES:
        raise RuntimeError("less than 1 GiB available RAM at preflight")
    if shutil.disk_usage(output.parent if output.parent.exists() else ROOT).free < 500_000_000:
        raise RuntimeError("less than 500 MB free near batch output")
    closure = source_closure()
    if not (graph_dir / f"case_{CASE}.json").is_file():
        raise FileNotFoundError(graph_dir / f"case_{CASE}.json")
    graph_sha = sha(graph_dir / f"case_{CASE}.json")
    if graph_sha != closure["expected_graph_sha256"]:
        raise RuntimeError("input graph hash mismatch")
    for path in ("src/q1_yuanzhifang_stage_m/benchmark_m.py",
                 "src/q1_yuanzhifang_stage_m/job_m.py", "src/q1_yuanzhifang_stage_m/export_m.py"):
        pinned = git("rev-parse", f"HEAD:{path}").decode().strip()
        if git("hash-object", path).decode().strip() != pinned:
            raise RuntimeError(f"runner/exporter differs from HEAD: {path}")
    upstream_job = git("show", f"{JOB_SOURCE}:{JOB_SOURCE_PATH}")
    if (ROOT / "src/q1_yuanzhifang_stage_m/job_m.py").read_bytes() != upstream_job:
        raise RuntimeError("copied job supervisor differs from fixed Stage L bytes")
    baseline = git("show", f"{BASELINE_COMMIT}:{BASELINE_DIR}/result.json.gz")
    baseline_run = json.loads(git("show", f"{BASELINE_COMMIT}:{BASELINE_DIR}/run.json"))
    baseline_result = json.loads(__import__("gzip").decompress(baseline))
    if (baseline_run.get("status") != "ok" or baseline_result.get("num_cores") != 1
            or baseline_result.get("makespan") != baseline_run.get("makespan_cycles")):
        raise RuntimeError("fixed single-core baseline identity mismatch")
    closure["graph_sha256"] = graph_sha
    return dict(source_closure=closure, runner_head=git("rev-parse", "HEAD").decode().strip(),
                input_graph_dir="<external frozen official graph directory>",
                baseline=dict(commit=BASELINE_COMMIT, result_sha256=sha(baseline), makespan_cycles=baseline_result["makespan"]),
                prior_v4_reference=dict(commit=V4_COMMIT, result_path=V4_K2_RESULT,
                                        makespan_cycles=64624),
                job_supervisor=dict(source_commit=JOB_SOURCE, source_path=JOB_SOURCE_PATH,
                                    copied_sha256=sha(upstream_job), memory_cap_bytes=JOB_MEMORY_BYTES),
                available_ram_min_bytes=MIN_RAM_BYTES, workers=1,
                solver_timeout_seconds=SOLVER_TIMEOUT, e0_timeout_seconds=E0_TIMEOUT,
                batch_wall_seconds=BATCH_TIMEOUT, budget=dict(solver=1, E0=1, E1=0, E2=0, retries=0))


def rel(path: Path, base: Path) -> str:
    return os.path.relpath(path, base)


def run_cell(graph: Path, output: Path, deadline: float, graph_sha: str) -> dict:
    cell = output / f"case_{CASE}_k{CORES}"
    cell.mkdir(exist_ok=False)
    plan, diag = cell / f"case_{CASE}_multicore_res.json", cell / "diagnostics.json"
    row = dict(case=CASE, cores=CORES, graph_sha256=graph_sha, status="started",
               started_at=utc(), calls=dict(solver=0, E0=0, E1=0, E2=0))
    try:
        row["available_ram_bytes_before_cell"] = available_ram_bytes()
        if row["available_ram_bytes_before_cell"] < MIN_RAM_BYTES:
            row["status"] = "ram-insufficient-before-cell"
            return row
        left = deadline - time.monotonic()
        if left <= 0:
            row["status"] = "deadline-before-solver"
            return row
        row["calls"]["solver"] = 1
        solver = managed_process(ROOT / SOLVER_PATH,
            [rel(graph, ROOT), "--cores", str(CORES), "--output", rel(plan, ROOT), "--diagnostics", rel(diag, ROOT)],
            cell, "solver", min(SOLVER_TIMEOUT, left), module=SOLVER_MODULE,
            job_memory_bytes=JOB_MEMORY_BYTES)
        # Do not publish the local Python installation path in tracked receipts.
        solver["command"][0] = "python"
        solver["command_path_normalization"] = "sys.executable normalized to python; child argv paths are repo-relative"
        row["solver"] = solver
        stdout_path = cell / solver["stdout"]
        online_events = []
        for line in stdout_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                online_events.append(item)
        unexpected_e1 = [e for e in online_events if "e1" in str(e.get("event", "")).lower()]
        row["online_e1_events"] = len(unexpected_e1)
        (cell / "online_events.json").write_text(json.dumps(online_events, indent=2) + "\n", encoding="utf-8")
        if unexpected_e1:
            row["status"] = "unexpected-online-e1"
            return row
        if solver["timeout"] or solver["returncode"] != 0 or not plan.is_file() or not diag.is_file():
            row["status"] = "solver-failed"
            return row
        candidate = json.loads(plan.read_bytes())
        diagnostics = json.loads(diag.read_bytes())
        if (set(candidate) != {"node_to_subgraph", "core_schedules"}
                or diagnostics.get("algorithm_id") != "q1-adjacent-union-stage-m"
                or diagnostics.get("graph_sha256") != graph_sha or len(candidate["core_schedules"]) != CORES):
            row["status"] = "identity-failed"
            return row
        row["selected"] = diagnostics.get("selected")
        row["merged_pairs"] = diagnostics.get("merged_pairs", [])
        if row["selected"] != "adjacent-union" or not row["merged_pairs"]:
            row["status"] = "mechanism-not-triggered"
            return row
        row["plan_sha256"] = sha(plan)
        left = deadline - time.monotonic()
        if left <= 0:
            row["status"] = "deadline-before-e0"
            return row
        row["calls"]["E0"] = 1
        e0 = managed_process(ROOT / E0_PATH,
            [rel(graph, ROOT), rel(plan, ROOT), "--config", rel(ROOT / CONFIG_PATH, ROOT),
             "--output", rel(cell / "e0_result.json", ROOT),
             "--trace-output", rel(cell / "e0_trace.json", ROOT),
             "--log-output", rel(cell / "e0_log.txt", ROOT)],
            cell, "e0", min(E0_TIMEOUT, left), job_memory_bytes=JOB_MEMORY_BYTES)
        e0["command"][0] = "python"
        e0["command_path_normalization"] = "sys.executable normalized to python; child argv paths are repo-relative"
        row["e0"] = e0
        if e0["timeout"] or e0["returncode"] != 0:
            row["status"] = "e0-failed"
            return row
        result_path, trace_path, log_path = (cell / "e0_result.json", cell / "e0_trace.json", cell / "e0_log.txt")
        result = json.loads(result_path.read_bytes())
        if (result.get("scene") != "A" or result.get("num_cores") != CORES
                or type(result.get("makespan")) is not int or not trace_path.is_file() or not log_path.is_file()):
            row["status"] = "identity-failed"
            return row
        row.update(status="success", makespan_cycles=result["makespan"],
                   e0_result_sha256=sha(result_path), e0_trace_sha256=sha(trace_path),
                   e0_log_sha256=sha(log_path))
    except Exception as error:
        row.update(status="supervision-error", error_type=type(error).__name__, message=str(error))
    finally:
        row["finished_at"] = utc()
        (cell / "run.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--start-token")
    parser.add_argument("--producer-session")
    args = parser.parse_args()
    graph = args.graphs.resolve() / f"case_{CASE}.json"
    output = args.output.resolve()
    facts = preflight(args.graphs.resolve(), output)
    if args.preflight:
        print(json.dumps(facts, indent=2))
        return
    if args.start_token != TOKEN or not args.producer_session or "/s-" not in args.producer_session:
        raise ValueError("parent START token and actual producer session required")
    # The unchanged Job supervisor launches children without -B; prevent pycache
    # writes to the read-only official source tree through inherited environment.
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    output.mkdir(parents=True, exist_ok=False)
    facts.update(producer_session=args.producer_session, started_at=utc(),
                 pycache_disabled=True, platform=platform.platform(),
                 python=platform.python_version(), cpu=platform.processor() or None)
    (output / "batch_manifest.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    start = time.monotonic()
    deadline = start + BATCH_TIMEOUT
    calls = dict(solver=0, E0=0, E1=0, E2=0)
    status = "runner-error"
    row = None
    try:
        row = run_cell(graph, output, deadline, facts["source_closure"]["graph_sha256"])
        calls = dict(row.get("calls", calls))
        status = row.get("status", "runner-error")
    except Exception as error:
        # An exception escaping run_cell may occur after a child launched (for
        # example while writing its final receipt). Keep the exact count unknown
        # and publish the frozen one-attempt-per-stage upper bound.
        calls = dict(solver=None, E0=None, E1=0, E2=0)
        receipt_calls_exact = False
        row = dict(case=CASE, cores=CORES, status="runner-error", error_type=type(error).__name__, message=str(error))
    else:
        receipt_calls_exact = True
    finished = utc()
    receipt = dict(finished_at=finished, wall_seconds=time.monotonic() - start,
                   calls=calls, calls_exact=receipt_calls_exact,
                   calls_upper_bound=dict(solver=1, E0=1, E1=0, E2=0), retries=0,
                   stopped_after_supervision_failure=status == "supervision-error",
                   status=status, cells=[row] if row else [])
    (output / "batch_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(T0=facts["started_at"], T1=finished, status=status, calls=calls), ensure_ascii=False))


if __name__ == "__main__":
    main()
