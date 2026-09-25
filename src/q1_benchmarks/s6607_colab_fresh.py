"""One-worker fresh-E0 Colab wrapper for the frozen structural P1 runner.

Prepared only. Every cell invokes the frozen solver and a new official E0;
historical results and single-core baselines are never read by this wrapper.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import bounded_probe_e0 as h
from src.q1_benchmarks import s6607_structural_full500 as frozen

FROZEN_RUNNER_COMMIT = "8335b5c55b0c12bd34b206e315582d1198439069"
MAX_CALLS = dict(solver=500, E1=4500, E0=500, E2=0)


def parse_cells(cases, cores, full500):
    if full500:
        if cases or cores:
            raise ValueError("--full500 excludes partial selectors")
        return [(f"{c:03d}", k) for c in range(1, 101) for k in range(1, 6)]
    if not cases or not cores:
        raise ValueError("partial run requires --cases and --cores")
    names = cases.split(",")
    counts = [int(x) for x in cores.split(",")]
    valid = {f"{c:03d}" for c in range(1, 101)}
    if (len(set(names)) != len(names) or len(set(counts)) != len(counts) or
            any(c not in valid for c in names) or any(k not in range(1, 6) for k in counts)):
        raise ValueError("invalid or duplicate cell selector")
    return [(case, core) for case in names for core in counts]


def summarize(rows):
    known = {key: sum(row["calls"][key] for row in rows if type(row["calls"][key]) is int)
             for key in MAX_CALLS}
    actual = {key: known[key] if all(type(row["calls"][key]) is int for row in rows) else None
              for key in MAX_CALLS}
    return actual, known


def run(output_root, cells, *, process_cell=None, verify=True):
    """Sequential dispatcher; process_cell injection is for pure fixture tests."""
    began = time.perf_counter()
    if verify:
        if sys.version_info[:3] != (3, 12, 13):
            raise RuntimeError("frozen Colab runtime requires Python 3.12.13")
        if platform.system() != "Linux":
            raise RuntimeError("this runner is reserved for the dedicated Linux Colab VM")
        head, official, files = frozen.preflight()
        wrapper_path = "src/q1_benchmarks/s6607_colab_fresh.py"
        if Path(__file__).read_bytes() != frozen.frozen(head, wrapper_path):
            raise RuntimeError("Colab wrapper differs from committed HEAD")
        runner_path = "src/q1_benchmarks/s6607_structural_full500.py"
        if (ROOT / runner_path).read_bytes() != frozen.frozen(FROZEN_RUNNER_COMMIT, runner_path):
            raise RuntimeError("underlying full500 runner differs from frozen 8335 source")
    else:
        head, official, files = "fixture-only", {}, {}
    target = Path(output_root).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError("output root must be within repository")
    target.mkdir(parents=True, exist_ok=False)
    worker = frozen.process_cell if process_cell is None else process_cell
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[key] = "1"
    meta = dict(run_id=target.name, status="running", started_at=h.utc(), finished_at=None,
                solver_commit=frozen.SOLVER, frozen_runner_commit=FROZEN_RUNNER_COMMIT,
                wrapper_head=head, wrapper_sha256=h.sha(__file__),
                official_code_hash=official.get("official_code_hash"),
                config_sha256=files.get("data/config.txt", {}).get("sha256"),
                archive_sha256=official.get("case_archive", {}).get("sha256"),
                environment=dict(platform=platform.platform(), python=sys.version,
                                 cpu_count=os.cpu_count(), workers=1, threads_per_process=1,
                                 cold_start="new interpreter per cell; OS caches not flushed"),
                cells=cells, maximum_calls=MAX_CALLS, retries=0,
                solver_timeout_seconds=frozen.MAX_SOLVER,
                new_e0_timeout_seconds=frozen.MAX_E0,
                total_admission_seconds=frozen.ADMISSION,
                e0_policy="always new official E0; no prior_index, old result, or baseline fetch",
                cleanup_boundary="Per-cell supervisor owns process groups; on unconfirmed cleanup, stop and shut down dedicated Colab VM externally")
    h.write(target / "batch.json", meta)
    rows = []
    stopped = None
    deadline = began + frozen.ADMISSION
    # This mapping has no historical rows. The frozen cell processor sees only
    # status=unavailable and therefore must take its new-E0 branch.
    empty_prior = defaultdict(lambda: {"status": "unavailable"})
    with tempfile.TemporaryDirectory(prefix="q1-colab-fresh-input-") as tmp:
        inputs = Path(tmp)
        if verify:
            with zipfile.ZipFile(ROOT / official["case_archive"]["path"]) as archive:
                for case in sorted({c for c, _ in cells}):
                    raw = archive.read(f"data/case_{case}.json")
                    if h.digest(raw) != files[f"data/case_{case}.json"]["sha256"]:
                        raise RuntimeError(f"official input hash mismatch: {case}")
                    (inputs / f"case_{case}.json").write_bytes(raw)
        for case, cores in cells:
            folder = target / "cells" / case / f"k{cores}"
            if stopped:
                row = dict(case_id=case, cores=cores, status="not_run", not_run_reason=stopped,
                           calls=dict(solver=0, E1=0, E0=0, E2=0))
                folder.mkdir(parents=True, exist_ok=True)
                h.write(folder / "run.json", row)
            else:
                attempted = False
                try:
                    if time.perf_counter() >= deadline:
                        raise TimeoutError("4500-second admission threshold reached")
                    attempted = True
                    row = worker((case, cores), target, inputs, files, official,
                                 empty_prior, deadline)
                    if row["status"] == "ok" and (row.get("reused_e0") or row["calls"]["E0"] != 1):
                        raise RuntimeError("fresh E0 not confirmed by cell receipt")
                except Exception as exc:
                    prior_receipt = folder / "run.json"
                    row = (h.read(prior_receipt) if prior_receipt.exists() else
                           dict(case_id=case, cores=cores,
                                calls=dict(solver=None, E1=None, E0=None, E2=0)))
                    if "solver" not in row:
                        row["calls"]["solver"] = None
                        row["calls"]["E1"] = None
                    if "evaluation" not in row:
                        row["calls"]["E0"] = None
                    if not attempted:
                        row["calls"] = dict(solver=0, E1=0, E0=0, E2=0)
                    row.update(status="failed", failure=dict(stage="wrapper",
                               type=type(exc).__name__, message=str(exc)))
                    folder.mkdir(parents=True, exist_ok=True)
                    h.write(folder / "run.json", row)
                if row["status"] != "ok":
                    stopped = f"first failure {case}/k{cores}: {row.get('failure', row['status'])}"
            rows.append(row)
            meta["completed_or_skipped_cells"] = len(rows)
            h.write(target / "batch.json", meta)
    actual, known = summarize(rows)
    if any(known[key] > MAX_CALLS[key] for key in MAX_CALLS):
        stopped = "call budget exceeded"
    meta.update(status="stopped" if stopped else "complete", stop_reason=stopped,
                finished_at=h.utc(), batch_wall_seconds=time.perf_counter() - began,
                actual_calls=actual, known_calls_lower_bound=known,
                new_e0_calls=actual["E0"], reused_e0_cells=0)
    h.write(target / "batch.json", meta)
    return 1 if stopped else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cases")
    parser.add_argument("--cores")
    parser.add_argument("--full500", action="store_true")
    args = parser.parse_args()
    try:
        cells = parse_cells(args.cases, args.cores, args.full500)
    except ValueError as exc:
        parser.error(str(exc))
    raise SystemExit(run(args.output_root, cells))


if __name__ == "__main__":
    main()
