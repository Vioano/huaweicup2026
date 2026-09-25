"""Prepared bounded P1 structural-refine matrix runner; explicit run only.

Every cell starts the frozen solver anew. Prior E0 reuse requires byte-identical
plan and complete old official identity; absent evidence triggers a new E0.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
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

SOLVER = "3a1b82b71ca1ff6689eb8e72f17d26c48b52073c"
OLD = "0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297"
OLD_RUNNER = "85b99a74101e3a7981b60566ad7937bcc8dc5426"
SINGLECORE = "6fcec11ccc472a1a652b21feb6fccf85a4555598"
SINGLECORE_DIR = "results/benchmark-board/official-singlecore-20260924"
OLD_FEED = "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json"
SOLVER_PATH = "src/q1/structural_refine.py"
RUNNER_PATH = "src/q1_benchmarks/s6607_structural_full500.py"
MAX_SOLVER, MAX_E0, ADMISSION = 300, 900, 4500
MAX_CALLS = dict(solver=500, E1=4500, E0=500, E2=0)


def frozen(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def preflight():
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("locked Python 3.12 required")
    head = h.git("rev-parse", "HEAD").decode().strip()
    if Path(__file__).read_bytes() != frozen(head, RUNNER_PATH):
        raise RuntimeError("runner is not the committed HEAD version")
    paths = set(h.git("ls-tree", "-r", "--name-only", SOLVER, "--", "src/q1", "src/eval_exact").decode().splitlines())
    current = set(h.git("ls-files", "--", "src/q1", "src/eval_exact").decode().splitlines())
    if paths != current or SOLVER_PATH not in paths:
        raise RuntimeError("frozen solver source set differs")
    for path in sorted(paths):
        if (ROOT / path).read_bytes() != frozen(SOLVER, path):
            raise RuntimeError(f"frozen solver source mismatch: {path}")
    for path in ("src/q1_benchmarks/bounded_probe_e0.py",
                 "AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py"):
        if (ROOT / path).read_bytes() != frozen(SOLVER, path):
            raise RuntimeError(f"frozen helper mismatch: {path}")
    manifest = h.read(ROOT / "docs/a/source-manifest.json")
    if (ROOT / "docs/a/source-manifest.json").read_bytes() != frozen(SOLVER, "docs/a/source-manifest.json"):
        raise RuntimeError("official manifest differs from frozen solver")
    prior_runner_path = "src/q1_benchmarks/s59ee_v4_full500_e0900.py"
    prior_runner = frozen(OLD_RUNNER, prior_runner_path)
    if b"multicore_cut_evaluate_problem_1.py" not in prior_runner:
        raise RuntimeError("prior evaluator runner source does not identify official E0")
    files = {r["path"]: r for r in manifest["files"]}
    for path, row in files.items():
        if path.startswith("code/") or path == "data/config.txt":
            if h.sha(h.OFFICIAL / path) != row["sha256"]:
                raise RuntimeError(f"official byte mismatch: {path}")
    code_hash = h.digest("".join(f"{p}\t{files[p]['sha256']}\n" for p in sorted(files)
                                 if p.startswith("code/")).encode())
    if code_hash != manifest["official_code_hash"]:
        raise RuntimeError("official code hash mismatch")
    if h.sha(ROOT / manifest["case_archive"]["path"]) != manifest["case_archive"]["sha256"]:
        raise RuntimeError("archive hash mismatch")
    return head, manifest, files


def prior_index():
    feed = json.loads(frozen(OLD, OLD_FEED))
    rows = {(r["case_id"], r["cores"]): r for r in feed["records"]}
    if len(rows) != 500:
        raise RuntimeError("prior feed is not 500 unique cells")
    # The denominator is a separate official source, not any new k=1 solver run.
    for number in range(1, 101):
        case = f"{number:03d}"
        sample = [rows[case, k]["baseline"] for k in range(1, 6)]
        if any(item != sample[0] for item in sample[1:]):
            raise RuntimeError(f"single-core baseline differs across cores: {case}")
        reference = frozen(SINGLECORE, f"{SINGLECORE_DIR}/{case}/result.json.gz")
        if (h.digest(reference) != sample[0]["result"]["sha256"] or
                sample[0]["entrypoint"] != "singlecore_evaluate.evaluate_singlecore"):
            raise RuntimeError(f"fixed single-core denominator mismatch: {case}")
        gzip.decompress(reference)
    return rows


def maybe_reuse(row, plan, graph_hash, config_hash, official_hash, folder):
    """Return verified prior E0 metadata or None; never substitute E1 output."""
    try:
        if row.get("status") != "ok":
            return None
        identity, artifacts = row["identity"], row["artifacts"]
        if (identity["graph_sha256"], identity["config_sha256"],
            identity["official_sha256"], identity["plan_sha256"]) != (
                graph_hash, config_hash, official_hash, h.sha(plan)):
            return None
        provenance = row["provenance"]
        if provenance["runner"]["source"]["commit"] != OLD_RUNNER:
            return None
        previous_plan = frozen(OLD, artifacts["plan"]["path"])
        prior_result = frozen(OLD, artifacts["result"]["path"])
        old_run = frozen(OLD, artifacts["run"]["path"])
        for raw, key in ((previous_plan, "plan"), (prior_result, "result"), (old_run, "run")):
            if h.digest(raw) != artifacts[key]["sha256"]:
                return None
        if previous_plan != plan.read_bytes():
            return None
        receipt = json.loads(old_run)
        evaluation = receipt["evaluation"]
        argv = evaluation["argv"]
        if (receipt["status"] != "ok" or receipt["calls"]["external_E0"] != 1 or
                evaluation["status"] != "ok" or not evaluation["cleanup_confirmed"] or
                not any(str(x).endswith("multicore_cut_evaluate_problem_1.py") for x in argv)):
            return None
        result_bytes = gzip.decompress(prior_result)
        result = json.loads(result_bytes)
        if (result.get("scene") != "A" or result.get("num_cores") != row["cores"] or
                result.get("makespan") != row["metrics"]["makespan_cycles"] or
                result["data_movement_bytes"]["scheduled_copy_bytes"] != row["metrics"]["ddr_bytes"]):
            return None
        reference = folder / "prior-result.json.gz"
        reference.write_bytes(prior_result)
        return dict(source_commit=OLD, old_runner_commit=OLD_RUNNER,
                    old_feed_path=OLD_FEED, prior_result=h.artifact(reference),
                    old_plan_sha256=artifacts["plan"]["sha256"],
                    evaluation_wall_seconds=None,
                    makespan_cycles=result["makespan"],
                    scheduled_copy_bytes=result["data_movement_bytes"]["scheduled_copy_bytes"])
    except (KeyError, ValueError, TypeError, OSError, subprocess.CalledProcessError, gzip.BadGzipFile):
        return None


def checked_e1(diag):
    parent = diag["parent"]
    base = parent["baseline"]
    scores = base["diagnostics"].get("online_scores", [])
    base_calls = base["actual_e1_calls"]
    refinement = parent["refinement"]
    extra = diag["extra"]
    counts = (base_calls, refinement["actual_e1_calls"], diag["extra_actual_e1_calls"])
    ref_attempts = refinement.get("score_attempts", 0)
    extra_attempts = sum(bool(r.get("score_attempted")) for r in extra)
    extra_pid_rows = sum(bool(r.get("score_attempted") and
                              r.get("score", {}).get("worker_pid") is not None) for r in extra)
    if (any(type(x) is not int or x < 0 for x in counts) or
            len(scores) != base_calls or any(s.get("worker_pid") is None for s in scores) or
            ref_attempts not in (0, 1) or counts[1] != ref_attempts or
            (ref_attempts and refinement.get("score", {}).get("worker_pid") is None) or
            len(extra) > 2 or extra_attempts > 2 or
            diag["extra_score_attempts"] != extra_attempts or
            counts[2] != extra_attempts or extra_pid_rows != extra_attempts):
        raise RuntimeError("unknown or inconsistent online E1 dispatch ledger")
    total = sum(counts)
    if (diag.get("actual_e1_calls_total") != total or
            diag.get("known_e1_calls_lower_bound") != total):
        raise RuntimeError("diagnostic E1 total differs from verified score rows")
    if total > 9:
        raise RuntimeError("E1 cell budget exceeded")
    return total


def checked_diagnostics(diag, plan_sha256):
    if diag.get("selected_plan_sha256") != plan_sha256:
        raise RuntimeError("selected plan hash differs from output bytes")
    return checked_e1(diag)


def process_cell(cell, batch, inputs, files, manifest, prior, deadline):
    case, cores = cell
    folder = batch / "cells" / case / f"k{cores}"
    folder.mkdir(parents=True)
    graph = inputs / f"case_{case}.json"
    plan, diag, result = folder / "plan.json", folder / "diagnostics.json", folder / "result.json"
    row = dict(run_id=batch.name, attempt_id=f"{batch.name}-p1-{case}-k{cores}",
               case_id=case, cores=cores, started_at=h.utc(), finished_at=None,
               graph_sha256=files[f"data/case_{case}.json"]["sha256"], status="running",
               calls=dict(solver=0, E1=0, E0=0, E2=0), artifacts={})
    h.write(folder / "run.json", row)
    stage = "solver"
    try:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError("batch admission threshold reached")
        row["calls"]["solver"] = None  # dispatch unknown until supervisor returns
        row["calls"]["E1"] = None
        row["solver"] = h.process([sys.executable, "-B", ROOT / SOLVER_PATH, graph,
            "--cores", cores, "--output", plan, "--diagnostics", diag], folder,
            "solver", min(MAX_SOLVER, remaining), inputs)
        row["calls"]["solver"] = 1
        if row["solver"]["status"] != "ok" or not row["solver"]["cleanup_confirmed"]:
            raise RuntimeError("solver failed or cleanup unconfirmed")
        diagnosis = h.read(diag)
        row["calls"]["E1"] = checked_diagnostics(diagnosis, h.sha(plan))
        if set(h.read(plan)) != {"node_to_subgraph", "core_schedules"}:
            raise RuntimeError("not an exact two-key plan")
        row["artifacts"].update(plan=h.artifact(plan), diagnostics=h.artifact(diag))
        row["selected"] = diagnosis["selected"]
        row["model_source"] = dict(solver_commit=SOLVER, selected=diagnosis["selected"],
                                   algorithm_id=diagnosis["algorithm_id"])
        stage = "E0"
        reused = maybe_reuse(prior[cell], plan, row["graph_sha256"],
                             files["data/config.txt"]["sha256"],
                             manifest["official_code_hash"], folder)
        if reused:
            row["reused_e0"] = reused
            row["evaluation_wall_seconds"] = None
            row["makespan_cycles"] = reused["makespan_cycles"]
            row["scheduled_copy_bytes"] = reused["scheduled_copy_bytes"]
        else:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise TimeoutError("batch admission expired before new E0")
            row["calls"]["E0"] = None  # dispatch unknown until supervisor returns
            row["evaluation"] = h.process([sys.executable, "-B",
                h.OFFICIAL / "code/multicore_cut_evaluate_problem_1.py", graph, plan,
                "--config", h.OFFICIAL / "data/config.txt", "--output", result,
                "--trace-output", folder / "trace.json", "--log-output", folder / "official.log"],
                folder, "E0", min(MAX_E0, remaining), inputs)
            row["calls"]["E0"] = 1
            if row["evaluation"]["status"] != "ok" or not row["evaluation"]["cleanup_confirmed"]:
                raise RuntimeError("new E0 failed or cleanup unconfirmed")
            value = h.read(result)
            if value.get("scene") != "A" or value.get("num_cores") != cores:
                raise RuntimeError("new E0 identity mismatch")
            row["artifacts"].update(result=h.artifact(result), trace=h.artifact(folder / "trace.json"),
                                    official_log=h.artifact(folder / "official.log"))
            row["evaluation_wall_seconds"] = row["evaluation"]["wall_seconds"]
            row["makespan_cycles"] = value["makespan"]
            row["scheduled_copy_bytes"] = value["data_movement_bytes"]["scheduled_copy_bytes"]
        row["status"] = "ok"
    except Exception as exc:
        process = row.get("evaluation" if stage == "E0" else "solver", {})
        row["status"] = "timeout" if isinstance(exc, TimeoutError) or process.get("status") == "timeout" else "failed"
        row["failure"] = dict(stage=stage, type=type(exc).__name__, message=str(exc))
    finally:
        row["finished_at"] = h.utc()
        h.write(folder / "run.json", row)
    return row


def run(output_root, cells, workers):
    started = time.perf_counter()
    head, manifest, files = preflight()
    prior = prior_index()
    batch = Path(output_root).resolve()
    if not batch.is_relative_to(ROOT):
        raise ValueError("output root must be inside repository")
    batch.mkdir(parents=True, exist_ok=False)
    meta = dict(run_id=batch.name, status="running", started_at=h.utc(), finished_at=None,
                solver_commit=SOLVER, runner_head=head, runner_sha256=h.sha(__file__),
                official_code_hash=manifest["official_code_hash"],
                config_sha256=files["data/config.txt"]["sha256"],
                archive_sha256=manifest["case_archive"]["sha256"],
                singlecore_source_commit=SINGLECORE, singlecore_gzip_count=100,
                cells=cells, workers=workers, threads_per_process=1,
                solver_timeout_seconds=MAX_SOLVER, new_e0_timeout_seconds=MAX_E0,
                total_admission_seconds=ADMISSION, retries=0, maximum_calls=MAX_CALLS,
                cold_start="fresh child interpreter per cell; OS caches not flushed",
                scope="E1 online selection; independent E0 or strictly matched prior E0")
    h.write(batch / "batch.json", meta)
    stop = None
    rows = {}
    deadline = started + ADMISSION
    with tempfile.TemporaryDirectory(prefix="q1-structural-full500-input-") as temp:
        inputs = Path(temp)
        with zipfile.ZipFile(ROOT / manifest["case_archive"]["path"]) as archive:
            for case in sorted({c for c, _ in cells}):
                raw = archive.read(f"data/case_{case}.json")
                if h.digest(raw) != files[f"data/case_{case}.json"]["sha256"]:
                    raise RuntimeError(f"input hash mismatch: {case}")
                (inputs / f"case_{case}.json").write_bytes(raw)
        cursor = iter(cells)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            live = {}
            def dispatch():
                if time.perf_counter() >= deadline:
                    raise TimeoutError("4500-second batch admission expired")
                cell = next(cursor)
                live[pool.submit(process_cell, cell, batch, inputs, files, manifest, prior, deadline)] = cell
            try:
                for _ in range(min(workers, len(cells))):
                    dispatch()
            except StopIteration:
                pass
            except Exception as exc:
                stop = f"admission: {type(exc).__name__}: {exc}"
            while live:
                done, _ = wait(live, return_when=FIRST_COMPLETED)
                for future in done:
                    cell = live.pop(future)
                    try:
                        row = future.result()
                    except Exception as exc:
                        row = dict(case_id=cell[0], cores=cell[1], status="failed",
                                   calls=dict(solver=None, E1=None, E0=None, E2=0),
                                   failure=dict(stage="runner", type=type(exc).__name__, message=str(exc)))
                        folder = batch / "cells" / cell[0] / f"k{cell[1]}"
                        folder.mkdir(parents=True, exist_ok=True)
                        h.write(folder / "run.json", row)
                    rows[cell] = row
                    if row["status"] != "ok" and stop is None:
                        stop = f"first failure {cell}: {row.get('failure')}"
                while not stop and len(live) < workers:
                    try:
                        dispatch()
                    except StopIteration:
                        break
                    except Exception as exc:
                        stop = f"admission: {type(exc).__name__}: {exc}"
                        break
    for case, cores in cells:
        if (case, cores) not in rows:
            rows[case, cores] = dict(case_id=case, cores=cores, status="not_run",
                                     not_run_reason=stop, calls=dict(solver=0, E1=0, E0=0, E2=0))
            folder = batch / "cells" / case / f"k{cores}"
            folder.mkdir(parents=True, exist_ok=True)
            h.write(folder / "run.json", rows[case, cores])
    ledger = [rows[cell] for cell in cells]
    known = {k: sum(r["calls"][k] for r in ledger if type(r["calls"][k]) is int)
             for k in ("solver", "E1", "E0", "E2")}
    actual = {k: known[k] if all(type(r["calls"][k]) is int for r in ledger) else None
              for k in known}
    if any(known[k] > MAX_CALLS[k] for k in known):
        stop = "call budget exceeded"
    meta.update(status="stopped" if stop else "complete", stop_reason=stop,
                finished_at=h.utc(), batch_wall_seconds=time.perf_counter() - started,
                actual_calls=actual, known_calls_lower_bound=known,
                new_e0_calls=actual["E0"],
                reused_e0_cells=sum(bool(r.get("reused_e0")) for r in ledger))
    h.write(batch / "batch.json", meta)
    return 1 if stop else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cases", help="comma-separated 001..100; required without --full500")
    parser.add_argument("--cores", help="comma-separated 1..5; required without --full500")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--full500", action="store_true", help="explicitly admit all 500 cells")
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("workers must be 1..4")
    if args.full500:
        if args.cases or args.cores:
            parser.error("--full500 cannot be combined with partial selectors")
        cells = [(f"{case:03d}", core) for case in range(1, 101) for core in range(1, 6)]
    else:
        if not args.cases or not args.cores:
            parser.error("partial run requires --cases and --cores")
        cases = args.cases.split(",")
        cores = [int(x) for x in args.cores.split(",")]
        if (len(set(cases)) != len(cases) or len(set(cores)) != len(cores) or
                any(c not in {f"{i:03d}" for i in range(1, 101)} for c in cases) or
                any(k not in range(1, 6) for k in cores)):
            parser.error("invalid or duplicate cell selector")
        cells = [(c, k) for c in cases for k in cores]
    raise SystemExit(run(args.output_root, cells, args.workers))


if __name__ == "__main__":
    main()
