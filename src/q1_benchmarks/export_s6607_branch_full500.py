"""Prepare one immutable submission shard from explicitly selected terminal cells.

This script is not an admission or publisher. Run only after the batch receipts
exist and root has authorized writes to the requested results/a destination.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import platform
import shlex
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
SOLVER = "834d8c957538ee069c66aadac9509552a4cc69d7"
RUNNER_HEAD = "20d534ce93252c462132bd643b5e8039b8a139a1"
OLD = "0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297"
OLD_FEED = "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json"
OLD_FEED_SHA = "4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764"
THREE_TEMPLATE = ROOT / "results/a/p1-unified-integration-three-20260925/board-feed-20260925T1507Z-branch-refine-three.json"
TERMINAL = {"ok", "failed", "timeout", "not_run"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_stable(path):
    first = path.read_bytes()
    if path.read_bytes() != first:
        raise RuntimeError(f"input still changing: {path}")
    return first


def git_blob(commit, name):
    return subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)


def put(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)


def dump(path, value):
    put(path, (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode())


def ref(path):
    if path.is_symlink() or not path.is_relative_to(ROOT):
        raise ValueError("artifact must be a repository file, not a symlink")
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path.read_bytes())}


def normalized_utc(value):
    if value is None:
        return None
    return value.replace("+00:00", "Z")


def old_baselines():
    raw = git_blob(OLD, OLD_FEED)
    if digest(raw) != OLD_FEED_SHA:
        raise RuntimeError("old feed SHA differs from fixed source")
    records = json.loads(raw)["records"]
    rows = {(r["case_id"], r["cores"]): r for r in records}
    if len(rows) != 500:
        raise RuntimeError("old feed must contain 500 unique cells")
    return rows


def capture_metadata(batch):
    observation = ROOT / "output/p1-unified-full500-preparation/launcher-observation.json"
    launch_raw = read_stable(observation)
    launch = json.loads(launch_raw)
    if (launch.get("status") not in {"started", "complete"}
            or str(batch) not in launch.get("command", "")):
        raise RuntimeError("launcher observation does not identify this batch")
    argv = shlex.split(launch["command"])
    safe = []
    for arg in argv:
        if arg == argv[0]:
            safe.append("python")
        elif arg.startswith(str(ROOT) + "/"):
            safe.append(Path(arg).relative_to(ROOT).as_posix())
        elif arg.startswith("/Users/"):
            safe.append("<external-admission-path>")
        else:
            safe.append(arg)
    return {"captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "os": platform.platform(), "python": platform.python_version(),
            "runtime_id": f"{platform.system().lower()}-{platform.machine().lower()}-python{platform.python_version()}",
            "launcher_argv": safe, "launcher_original_sha256": digest(launch_raw),
            "launcher_original": launch_raw}


def terminal_cell(batch, case, cores, batch_meta):
    folder = batch / "cells" / case / f"k{cores}"
    raw = read_stable(folder / "run.json")
    row = json.loads(raw)
    if (row.get("case_id") != case or row.get("cores") != cores
            or row.get("status") not in TERMINAL
            or (not row.get("finished_at") and batch_meta.get("status") == "running")
            or (row["status"] == "not_run" and
                (batch_meta.get("status") == "running" or not batch_meta.get("finished_at")))):
        raise RuntimeError(f"cell is not finished: {case}/k{cores}")
    return folder, row, raw


def package_cell(folder, dest, row, run_raw):
    out = dest / "originals"
    names = ("plan.json", "diagnostics.json", "result.json", "trace.json",
             "official.log", "prior-result.json.gz", "solver.stdout.raw",
             "solver.stderr.raw", "E0.stdout.raw", "E0.stderr.raw")
    claims = {}
    for value in row.get("artifacts", {}).values():
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            claims[Path(value["path"]).name] = value.get("sha256")
    for stage in (row.get("solver"), row.get("evaluation")):
        if isinstance(stage, dict):
            for key in ("stdout", "stderr"):
                value = stage.get(key)
                if isinstance(value, dict) and isinstance(value.get("path"), str):
                    claims[Path(value["path"]).name] = value.get("sha256")
    mapping = []
    def archive(name, raw):
        if name in claims and digest(raw) != claims[name]:
            raise RuntimeError(f"declared source SHA mismatch: {name}")
        stored_name = name + ".gz" if name in {
            "run.json", "diagnostics.json", "result.json", "trace.json"} else name
        stored = gzip.compress(raw, compresslevel=6, mtime=0) if stored_name.endswith(".json.gz") and name != "prior-result.json.gz" else raw
        path = out / stored_name
        put(path, stored)
        if stored is not raw and gzip.decompress(stored) != raw:
            raise RuntimeError("gzip roundtrip mismatch")
        mapping.append({"source": (folder / name).relative_to(ROOT).as_posix(),
                        "raw_sha256": digest(raw), "storage": ref(path),
                        "raw_bytes": len(raw), "stored_bytes": len(stored)})
    archive("run.json", run_raw)
    for name in names:
        source = folder / name
        if source.exists():
            raw = read_stable(source)
            archive(name, raw)
            if source.read_bytes() != raw:
                raise RuntimeError(f"source changed during export: {source}")
    for name in claims:
        if not (folder / name).is_file():
            raise RuntimeError(f"declared artifact missing: {name}")
    if (folder / "run.json").read_bytes() != run_raw:
        raise RuntimeError("cell receipt changed during export")
    return out, mapping


def record_for(row, original, dest, old_row, baseline, batch_meta, template, capture):
    case, cores = row["case_id"], row["cores"]
    status = row["status"]
    rec = copy.deepcopy(template)
    rec.update(attempt_id=f"{batch_meta['run_id']}-p1-{case}-k{cores}", revision=1,
               run_id=batch_meta["run_id"], algorithm_id="q1-branch-refine-research-v1",
               algorithm_name="P1 unified branch-refine research entry",
               variant="fixed-structural-parent-optional-branch-aid",
               solver_commit=SOLVER, problem="P1", case_id=case, cores=cores,
               status=status, runtime_id=capture["runtime_id"],
               observed_at=normalized_utc(row.get("started_at")),
               source_url="https://github.com/huaweibei123/huaweicup2026/issues/98",
               notes=["Incremental shard of the fixed full500 run; full-matrix conclusion requires all 500 terminal cells.",
                      f"OS/Python metadata was captured on the same host at {capture['captured_at_utc']}; not a run-time package inventory."])
    calls = row.get("calls", {})
    solver = row.get("solver", {})
    evaluation = row.get("evaluation", {})
    reused = row.get("reused_e0")
    official = None
    if status == "ok":
        if not (original / "plan.json").is_file() or not (original / "diagnostics.json.gz").is_file():
            raise RuntimeError("successful cell lacks plan/diagnostics originals")
        if reused:
            raw = (original / "prior-result.json.gz").read_bytes()
            if digest(raw) != reused["prior_result"]["sha256"]:
                raise RuntimeError("reused E0 original differs from cell receipt")
            official = json.loads(gzip.decompress(raw))
            result_path = original / "prior-result.json.gz"
        else:
            raw = (original / "result.json.gz").read_bytes()
            official = json.loads(gzip.decompress(raw))
            result_path = original / "result.json.gz"
        if (official.get("scene") != "A" or official.get("num_cores") != cores
                or official.get("makespan") != row.get("makespan_cycles")
                or official["data_movement_bytes"]["scheduled_copy_bytes"] != row.get("scheduled_copy_bytes")):
            raise RuntimeError("official result and cell receipt disagree")
        if (type(official.get("makespan")) is not int or official["makespan"] <= 0
                or type(official["data_movement_bytes"]["scheduled_copy_bytes"]) is not int
                or official["data_movement_bytes"]["scheduled_copy_bytes"] < 0):
            raise RuntimeError("official objective is not a valid integer pair")
        selected = row.get("selected_objective")
        if selected is not None and selected != [official["makespan"],
                                                 official["data_movement_bytes"]["scheduled_copy_bytes"]]:
            raise RuntimeError("selected and official objectives differ")
    baseline_meta = old_row["baseline"]
    if (baseline_meta["graph_sha256"] != row.get("graph_sha256")
            or baseline_meta["config_sha256"] != batch_meta["config_sha256"]
            or baseline_meta["official_sha256"] != batch_meta["official_code_hash"]):
        raise RuntimeError("singlecore baseline identity mismatch")
    rec["parameters"] = {"cores": cores, "max_online_E1": 10,
                         "solver_timeout_seconds": batch_meta["solver_timeout_seconds"],
                         "new_E0_timeout_seconds": batch_meta["new_e0_timeout_seconds"],
                         "workers": batch_meta["workers"], "E1_actual": calls.get("E1"),
                         "E2": 0, "retry": 0}
    rec["metrics"] = {"makespan_cycles": official["makespan"] if official else None,
                      "solver_wall_seconds": solver.get("wall_seconds"),
                      "evaluation_wall_seconds": (None if reused else evaluation.get("wall_seconds")),
                      "ddr_bytes": (official["data_movement_bytes"]["scheduled_copy_bytes"]
                                    if official else None),
                      "extra_ddr_bytes": (official["data_movement_bytes"].get("added_copy_bytes")
                                          if official else None),
                      "spill_bytes": (official["data_movement_bytes"].get("spill_added_copy_bytes")
                                      if official else None), "cache_hit_rate": None}
    rec["evaluator"] = {**old_row["evaluator"],
                        "commit": OLD if reused else SOLVER}
    rec["identity"] = {"graph_sha256": row.get("graph_sha256"),
                       "config_sha256": batch_meta["config_sha256"],
                       "official_sha256": batch_meta["official_code_hash"],
                       "plan_sha256": (ref(original / "plan.json")["sha256"]
                                       if (original / "plan.json").is_file() else None)}
    artifacts = {"run": ref(original / "run.json.gz")}
    if (original / "plan.json").is_file():
        artifacts["plan"] = ref(original / "plan.json")
    if official:
        artifacts["result"] = ref(result_path)
    for key, name in (("trace", "trace.json.gz"), ("log", "official.log")):
        if (original / name).is_file():
            artifacts[key] = ref(original / name)
    rec["artifacts"] = artifacts
    rec["baseline"] = {"graph_sha256": baseline_meta["graph_sha256"],
                       "config_sha256": baseline_meta["config_sha256"],
                       "official_sha256": baseline_meta["official_sha256"],
                       "route": baseline_meta["route"],
                       "entrypoint": baseline_meta["entrypoint"],
                       "result": ref(baseline)}
    rec["cache_pair"] = None
    rec["timing"] = {"solver_includes_evaluation": False,
                     "evaluation_precision": ("Reused exact old E0 bytes; no new E0 wall"
                                              if reused else "Supervisor process-group wall"),
                     "utc": "UTC"}
    rec["provenance"]["solver"]["source"].update(commit=SOLVER, path="src/q1/branch_refine.py")
    rec["provenance"]["solver"]["method"] = (
        "Structural parent with at most one branch-aid refinement; select strict "
        "(Makespan, scheduled COPY) improvement under the fixed branch_refine rule.")
    rec["provenance"]["solver"]["selected_algorithm_id"] = row.get("selected")
    rec["provenance"]["solver"]["selected_solver_commit"] = (SOLVER if row.get("selected") else None)
    rec["provenance"]["runner"]["source"].update(commit=batch_meta["runner_head"],
                                                    path="src/q1_benchmarks/s6607_branch_full500.py")
    rec["provenance"]["runner"]["argv"] = capture["launcher_argv"]
    samples = solver.get("supervision", {}).get("resource_samples", [])
    mem = next((s.get("mem_bytes") for s in samples
                if isinstance(s, dict) and type(s.get("mem_bytes")) is int), None)
    peaks = [stage.get("supervision", {}).get("peak_group_rss_kib")
             for stage in (solver, evaluation) if isinstance(stage, dict)]
    peak = max((p for p in peaks if type(p) is int), default=None)
    interpreter = Path(solver.get("argv", [""])[0]).name if solver.get("argv") else None
    rec["provenance"]["environment"].update(os=capture["os"], cpu=None, gpu=None,
                                                ram_bytes=mem, python=capture["python"],
                                                dependencies=None, threads=1,
                                                workers=batch_meta["workers"],
                                                peak_rss_bytes=peak * 1024 if peak is not None else None)
    measurement = rec["provenance"]["measurement"]
    measurement.update(started_at=normalized_utc(row.get("started_at")),
                       finished_at=normalized_utc(row.get("finished_at")),
                       seed=None, repeat_index=0, cold_start=None,
                       solver_scope="Fresh solver child; online E1 included; OS cache not flushed",
                       evaluation_scope=("Exact old E0 result reused by byte identity"
                                         if reused else "Independent official E0"),
                       budget={"wall_seconds": batch_meta["solver_timeout_seconds"],
                               "candidate_limit": 10,
                               "stop_reason": (
                                   json.loads(gzip.decompress((original / "diagnostics.json.gz").read_bytes()))["stop_reason"]
                                   if status == "ok" else
                                   row.get("failure", {}).get("message")
                                   or row.get("not_run_reason") or status)},
                       calls={"solver": calls.get("solver"), "E0": calls.get("E0"),
                              "E1": calls.get("E1"), "E2": calls.get("E2")},
                       offline_costs="No offline training in this run; frozen source preparation excluded",
                       failure=(None if status == "ok" else {
                           "stage": row.get("failure", {}).get("stage", "runner"),
                           "reason": row.get("failure", {}).get("message", row.get("not_run_reason", "not run")),
                           "exit_code": None, "elapsed_seconds": solver.get("wall_seconds")}))
    rec["provenance"]["missing_reasons"] = {
        "provenance.environment.cpu": "Not recorded in the cell receipt",
        "provenance.environment.gpu": "Not recorded in the cell receipt",
        "provenance.environment.dependencies": "Installed package inventory not recorded",
        "provenance.measurement.cold_start": "Fresh interpreter confirmed; OS cache state not measured",
        "provenance.measurement.seed": "Deterministic solver; seed not recorded"}
    if mem is None:
        rec["provenance"]["missing_reasons"]["provenance.environment.ram_bytes"] = "Resource sample absent"
    if peak is None:
        rec["provenance"]["missing_reasons"]["provenance.environment.peak_rss_bytes"] = "Sampled group RSS absent"
    if interpreter:
        rec["notes"].append(f"Solver argv interpreter basename: {interpreter}.")
    rec["notes"].append("Each solver uses a fresh child interpreter; OS cache was not flushed or measured. Peak RSS is sampled process-group RSS.")
    if reused:
        rec["notes"].append(
            f"E0 reused from {reused['source_commit']}:{reused['old_feed_path']} "
            "after exact plan/input/official/receipt identity; evaluation wall is null.")
    if status != "ok":
        rec["notes"].append("Terminal failure/timeout/not_run retained; no success score inferred.")
    return rec


def export(batch, cells, output):
    if (not batch.is_absolute() or not batch.is_relative_to(ROOT)
            or not output.is_absolute() or not output.is_relative_to(ROOT / "results/a")
            or output.exists() or output.is_symlink() or output.resolve() != output):
        raise ValueError("batch/output paths must be canonical repository paths; output must not exist")
    meta_raw = read_stable(batch / "batch.json")
    meta = json.loads(meta_raw)
    runner_bytes = git_blob(RUNNER_HEAD, "src/q1_benchmarks/s6607_branch_full500.py")
    if (meta.get("solver_commit") != SOLVER or meta.get("runner_head") != RUNNER_HEAD
            or meta.get("runner_sha256") != digest(runner_bytes)
            or len(meta.get("cells", [])) != 500):
        raise RuntimeError("not the fixed branch full500 batch")
    old_rows = old_baselines()
    template = json.loads(THREE_TEMPLATE.read_bytes())["records"][0]
    capture = capture_metadata(batch)
    selected = []
    for case, cores in cells:
        if (case, cores) not in {tuple(x) for x in meta["cells"]}:
            raise ValueError("selected cell not in batch")
        selected.append((case, cores, *terminal_cell(batch, case, cores, meta)))
    output.mkdir(parents=True, exist_ok=False)
    put(output / "batch.original.json", meta_raw)
    put(output / "launcher-observation.original.json", capture["launcher_original"])
    if (batch / "admission.original.json").is_file():
        put(output / "admission.original.json", read_stable(batch / "admission.original.json"))
    records = []
    raw_storage = []
    for case, cores, folder, row, run_raw in selected:
        dest = output / "cells" / f"{case}-k{cores}"
        original, mapping = package_cell(folder, dest, row, run_raw)
        raw_storage.extend(mapping)
        old_row = old_rows[case, cores]
        bmeta = old_row["baseline"]
        baseline_raw = git_blob(OLD, bmeta["result"]["path"])
        if digest(baseline_raw) != bmeta["result"]["sha256"]:
            raise RuntimeError("singlecore baseline blob differs from fixed feed")
        baseline = output / "baselines" / f"{case}-singlecore.json.gz"
        if not baseline.exists():
            put(baseline, baseline_raw)
        elif baseline.read_bytes() != baseline_raw:
            raise RuntimeError("singlecore baseline differs across K for same case")
        records.append(record_for(row, original, dest, old_row, baseline, meta, template, capture))
    feed = output / "board-feed.json"
    dump(feed, {"schema_version": 1, "submission_version": 1, "records": records})
    dump(output / "MANIFEST.json", {"kind": "incremental-full500-terminal-shard",
                                    "run_id": meta["run_id"], "solver_commit": SOLVER,
                                    "source_batch": batch.relative_to(ROOT).as_posix(),
                                    "old_feed_commit": OLD, "old_feed_sha256": OLD_FEED_SHA,
                                    "capture_utc": capture["captured_at_utc"],
                                    "launcher_observation_sha256": capture["launcher_original_sha256"],
                                    "cells": [f"{c}-k{k}" for c, k in cells],
                                    "feed": ref(feed),
                                    "raw_to_storage": raw_storage,
                                    "files": [ref(p) for p in sorted(output.rglob("*"))
                                              if p.is_file() and p.name != "MANIFEST.json"]})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch", type=Path, required=True)
    p.add_argument("--cells", required=True, help="comma-separated 001:1,002:5 etc")
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    cells = []
    for token in args.cells.split(","):
        case, sep, core = token.partition(":")
        if not sep or case not in {f"{i:03d}" for i in range(1, 101)} or core not in "12345":
            p.error("invalid cell selector")
        cells.append((case, int(core)))
    if len(set(cells)) != len(cells):
        p.error("duplicate cell selector")
    export(args.batch, cells, args.output_dir)


if __name__ == "__main__":
    main()
