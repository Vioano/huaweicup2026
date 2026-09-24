"""Read-only audit and aggregation of the fixed, complete P1 fixed64 matrix.

Reads immutable Git objects, or a GitHub ZIP snapshot of the same commit.
Does not run a solver/evaluator, fetch data, or alter original evidence.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "6664a63adc3464d28d1f835d907cdeaea23e6b35"
SOLVER = "4dff90ef699fd51845cf482951e8477066f5f566"
BASELINE_COMMIT = "b0937de5b97cb2e85fda68d702c8076457993588"
DATA = "results/a/local-p1-fixed64-20260924/20260924T1337Z-s59ee"
FEED = DATA + "/board-feed-full500.json"
BASELINES = "results/benchmark-board/official-singlecore-20260924"
REPO_URL = "https://github.com/huaweibei123/huaweicup2026"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(raw):
    def bad_constant(value):
        raise ValueError("Non-finite JSON number: " + value)
    return json.loads(raw, parse_constant=bad_constant)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def same_number(a, b, label):
    require(number(a) and number(b) and type(a) is type(b) and a == b, label)


class Source:
    def __init__(self, archive=None):
        self.archive = ZipFile(archive) if archive else None
        self.items = {}
        if self.archive:
            names = self.archive.namelist()
            roots = {n.split("/")[0] for n in names}
            require(len(roots) == 1, "ambiguous archive root")
            self.prefix = roots.pop() + "/"
            require(COMMIT[:7] in self.prefix, "archive root is not the pinned GitHub snapshot")
            require(len(names) == len(set(names)), "duplicate archive names")
        else:
            self.process = subprocess.Popen(["git", "-C", str(ROOT), "cat-file", "--batch"],
                                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def get(self, path):
        require(not Path(path).is_absolute() and ".." not in Path(path).parts, "unsafe evidence path")
        if self.archive:
            raw = self.archive.read(self.prefix + path)
        else:
            self.process.stdin.write((COMMIT + ":" + path + "\n").encode())
            self.process.stdin.flush()
            header = self.process.stdout.readline().split()
            require(len(header) == 3 and header[1] == b"blob", "missing blob: " + path)
            raw = self.process.stdout.read(int(header[2]))
            require(self.process.stdout.read(1) == b"\n", "Git batch framing")
        identity = {"path": path, "sha256": sha(raw), "bytes": len(raw)}
        require(path not in self.items or self.items[path] == identity, "source changed")
        self.items[path] = identity
        return raw

    def artifact(self, reference, decompress=True):
        raw = self.get(reference["path"])
        require(sha(raw) == reference["sha256"], "artifact hash: " + reference["path"])
        if reference["path"].endswith(".gz") and decompress:
            raw = gzip.decompress(raw)
            if "raw_sha256" in reference:
                require(sha(raw) == reference["raw_sha256"], "raw hash: " + reference["path"])
            if "raw_bytes" in reference:
                require(len(raw) == reference["raw_bytes"], "raw size: " + reference["path"])
        return raw

    def close(self):
        if self.archive:
            self.archive.close()
        else:
            self.process.stdin.close()
            self.process.wait(timeout=10)


def distribution(values):
    values = sorted(values)
    require(bool(values) and all(number(v) for v in values), "empty/nonfinite distribution")
    return {"n": len(values), "mean": statistics.fmean(values), "median": statistics.median(values),
            "p95_nearest_rank": values[math.ceil(0.95 * len(values)) - 1],
            "min": values[0], "max": values[-1], "sum": math.fsum(values)}


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def verify_materials(source):
    manifest = read_json(source.get("docs/a/source-manifest.json"))
    archive = source.get(manifest["case_archive"]["path"])
    require(sha(archive) == manifest["case_archive"]["sha256"], "official case archive hash")
    cases = ZipFile(io.BytesIO(archive))
    expected = {r["path"]: r for r in manifest["files"]}
    require(len(cases.namelist()) == 100 and set(cases.namelist()) ==
            {n for n in expected if n.startswith("data/case_")}, "official 100 cases")
    for path, item in expected.items():
        raw = cases.read(path) if path.startswith("data/case_") else source.get("data/raw/a/official/" + path)
        require(sha(raw) == item["sha256"] and len(raw) == item["bytes"], "official source identity: " + path)
        # Imported static validators are checked against the same frozen bytes.
        if path.startswith("code/"):
            require((ROOT / "data/raw/a/official" / path).read_bytes() == raw, "local static validator identity")
    combined = "".join(path + "\t" + item["sha256"] + "\n" for path, item in sorted(expected.items()) if path.startswith("code/"))
    require(sha(combined.encode()) == manifest["official_code_hash"], "official code set hash")
    return manifest, expected, cases


def audit(source):
    start = time.perf_counter()
    manifest, expected, case_archive = verify_materials(source)
    sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order

    feed = read_json(source.get(FEED))
    batch = read_json(source.get(DATA + "/batch.json"))
    require(feed["schema_version"] == 1 and feed["submission_version"] == 1, "feed version")
    records = feed["records"]
    require(len(records) == 500, "not a full 500-cell feed")
    required_keys = {(f"{case:03d}", k) for case in range(1, 101) for k in range(1, 6)}
    require({(r["case_id"], r["cores"]) for r in records} == required_keys, "missing/duplicate cell")
    require(len({r["attempt_id"] for r in records}) == 500, "duplicate attempt")
    require(len({r["run_id"] for r in records}) == 1, "mixed run identity")
    require(len({r["variant"] for r in records}) == 1, "mixed variant")
    require(all(r["algorithm_id"] == "q1-fixed64-local-finish" and r["solver_commit"] == SOLVER
                and r["problem"] == "P1" and r["status"] == "ok" and r["evaluator"]["route"] == "E0"
                for r in records), "mixed/failed/approximate cells")
    require(batch["solver_commit"] == SOLVER and sum(v["counts"]["ok"] for v in batch["invocations"]) == 500,
            "batch/source mismatch")
    rows, baselines, anomaly_rows = [], [], []
    graph = previous_case = None
    baseline_by_case = {}
    over64 = []
    for index, record in enumerate(sorted(records, key=lambda r: (r["case_id"], r["cores"])), 1):
        case, cores = record["case_id"], record["cores"]
        label = f"{case}/k{cores}"
        identity = record["identity"]
        require(identity["graph_sha256"] == expected[f"data/case_{case}.json"]["sha256"], label + " graph")
        require(identity["config_sha256"] == expected["data/config.txt"]["sha256"], label + " config")
        require(identity["official_sha256"] == manifest["official_code_hash"], label + " official")
        if case != previous_case:
            graph = read_json(case_archive.read(f"data/case_{case}.json"))
            previous_case = case
            base_run = read_json(source.get(f"{BASELINES}/{case}/run.json"))
            require(base_run["status"] == "ok" and base_run["returncode"] == 0 and
                    base_run["entrypoint"] == "singlecore_evaluate.evaluate_singlecore", case + " baseline status/entrypoint")
            for target, origin in [("graph_sha256", "graph_sha256"), ("config_sha256", "config_sha256"), ("official_code_hash", "official_sha256")]:
                require(base_run[target] == identity[origin], case + " baseline identity")
            base_ref = base_run["artifacts"]["result.json"]
            base_raw = source.artifact(base_ref)
            require(sha(base_raw) == base_ref["raw_sha256"] and len(base_raw) == base_ref["bytes"], case + " baseline raw bytes")
            base = read_json(base_raw)
            require(base["scene"] == "A" and base["num_cores"] == 1, case + " official singlecore result")
            same_number(base["makespan"], base_run["makespan_cycles"], case + " baseline numeric")
            baseline_by_case[case] = base["makespan"]
            baselines.append({"case_id": case, "baseline_cycles": base["makespan"], "baseline_source_commit": BASELINE_COMMIT,
                              "result_path": base_ref["path"], "result_sha256": base_ref["sha256"],
                              "graph_sha256": identity["graph_sha256"], "config_sha256": identity["config_sha256"],
                              "official_sha256": identity["official_sha256"]})
            del base, base_raw, base_run
        baseline = baseline_by_case[case]
        artifacts = record["artifacts"]
        plan_raw = source.artifact(artifacts["plan"])
        require(sha(plan_raw) == identity["plan_sha256"], label + " plan identity")
        plan = read_json(plan_raw)
        require(len(plan["core_schedules"]) == cores, label + " plan cores")
        view = derive_multicore_plan(graph, plan)
        validate_task_order(view)
        run = read_json(source.artifact(artifacts["run"]))
        require(run["status"] == "ok" and run["case_id"] == case and run["cores"] == cores and
                run["solver_commit"] == SOLVER and run["algorithm_id"] == record["algorithm_id"], label + " run identity/status")
        require(run["calls"] == {"solver": 1, "E0": 1, "E1": 0, "E2": 0}, label + " calls")
        for target, origin in [("graph_sha256", "graph_sha256"), ("config_sha256", "config_sha256"), ("official_code_hash", "official_sha256")]:
            require(run[target] == identity[origin], label + " run identity")
        require(run["artifacts"]["plan"]["sha256"] == artifacts["plan"]["sha256"] and
                run["artifacts"]["result"]["sha256"] == artifacts["result"]["sha256"], label + " run artifact references")
        result_raw = source.artifact(run["artifacts"]["result"])
        if len(result_raw) > 64 * 1024**2:
            over64.append({"case_id": case, "cores": cores, "raw_bytes": len(result_raw)})
        result = read_json(result_raw)
        require(result["scene"] == "A" and result["num_cores"] == cores, label + " result identity")
        makespan = result["makespan"]
        same_number(makespan, run["makespan_cycles"], label + " run cycles")
        same_number(makespan, record["metrics"]["makespan_cycles"], label + " feed cycles")
        require(makespan > 0, label + " cycles positive")
        require(result["data_movement_bytes"] == run["data_movement_bytes"], label + " DDR fields")
        for key, item in run["artifacts"].items():
            if key not in {"plan", "result"}:
                source.artifact(item)  # Preserve and check original trace/log bytes; never re-evaluate.
        for stage in ("solver", "evaluation"):
            require(run[stage]["status"] == "ok" and run[stage]["returncode"] == 0, label + " stage success")
            require(number(run[stage]["wall_seconds"]) and run[stage]["wall_seconds"] >= 0, label + " stage wall")
        argv = run["solver"]["argv"]
        require("propose" in argv and argv[argv.index("--kind") + 1] == "fixed64" and
                argv[argv.index("--seed") + 1] == "0" and int(argv[argv.index("--cores") + 1]) == cores, label + " actual solver command")
        same_number(run["solver"]["wall_seconds"], record["metrics"]["solver_wall_seconds"], label + " solver timing")
        same_number(run["evaluation"]["wall_seconds"], record["metrics"]["evaluation_wall_seconds"], label + " evaluation timing")
        require(record["timing"]["solver_includes_evaluation"] is False, label + " timing inclusion")
        if record.get("baseline"):
            require(record["baseline"]["result"]["sha256"] == baselines[-1]["result_sha256"], label + " referenced denominator")
        movement = result["data_movement_bytes"]
        rows.append({"case_id": case, "problem": "P1", "cores": cores, "status": "ok", "algorithm_id": record["algorithm_id"],
                     "variant": record["variant"], "source_commit": COMMIT, "solver_commit": SOLVER,
                     "makespan_cycles": makespan, "baseline_cycles": baseline, "baseline_speedup": baseline / makespan,
                     "speedup_per_core": baseline / makespan / cores,
                     "solver_wall_seconds": run["solver"]["wall_seconds"], "evaluation_wall_seconds": run["evaluation"]["wall_seconds"],
                     "scheduled_copy_bytes": movement["scheduled_copy_bytes"], "extra_ddr_bytes": movement["added_copy_bytes"],
                     "spill_bytes": movement["spill_added_copy_bytes"], "subgraphs": len(view["subgraph_ids"]),
                     "active_cores": sum(bool(v) for v in plan["core_schedules"]),
                     "solver_peak_rss_bytes_sampled": run["solver"].get("peak_rss_bytes_sampled"),
                     "evaluation_peak_rss_bytes_sampled": run["evaluation"].get("peak_rss_bytes_sampled"),
                     "plan_sha256": identity["plan_sha256"], "result_sha256": artifacts["result"]["sha256"],
                     "plan_path": artifacts["plan"]["path"], "result_path": artifacts["result"]["path"], "run_path": artifacts["run"]["path"]})
        del result, result_raw, plan, plan_raw, run, view
        if index % 25 == 0:
            print(json.dumps({"verified_cells": index, "expected": 500}), flush=True)
    case_archive.close()
    by_core = {}
    for cores in range(1, 6):
        subset = [r for r in rows if r["cores"] == cores]
        by_core[str(cores)] = {field: distribution([r[field] for r in subset]) for field in
                             ("baseline_speedup", "makespan_cycles", "solver_wall_seconds", "evaluation_wall_seconds", "extra_ddr_bytes")}
        by_core[str(cores)].update(slower_than_official_singlecore=sum(r["baseline_speedup"] < 1 for r in subset),
                                  faster_than_official_singlecore=sum(r["baseline_speedup"] > 1 for r in subset))
    by_key = {(r["case_id"], r["cores"]): r for r in rows}
    for row in rows:
        case, cores = row["case_id"], row["cores"]
        if row["makespan_cycles"] > row["baseline_cycles"]:
            anomaly_rows.append({"case_id": case, "cores": cores, "kind": "slower_than_official_singlecore",
                                 "makespan_cycles": row["makespan_cycles"], "reference_cycles": row["baseline_cycles"],
                                 "relative_increase": row["makespan_cycles"] / row["baseline_cycles"] - 1})
        if cores > 1:
            previous = by_key[case, cores - 1]["makespan_cycles"]
            if row["makespan_cycles"] > previous:
                anomaly_rows.append({"case_id": case, "cores": cores, "kind": "slower_than_previous_core_count",
                                     "makespan_cycles": row["makespan_cycles"], "reference_cycles": previous,
                                     "relative_increase": row["makespan_cycles"] / previous - 1})
    summary = {"source_commit": COMMIT, "solver_commit": SOLVER, "algorithm_id": records[0]["algorithm_id"],
               "variant": records[0]["variant"], "run_id": records[0]["run_id"], "expected_cells": 500,
               "verified_cells": len(rows), "verified_baselines": len(baselines), "by_cores": by_core,
               "official_curve_anchor_k1": 1.0, "k1_note": "Actual optimized solver k1 is separately measured; it is not the official singlecore denominator.",
               "all_solver_wall_seconds": distribution([r["solver_wall_seconds"] for r in rows]),
               "all_evaluation_wall_seconds": distribution([r["evaluation_wall_seconds"] for r in rows]),
               "source_calls": {"solver": 500, "E0": 500, "E1": 0, "E2": 0},
               "new_calls_from_this_audit": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
               "static_plan_validation": "500 derive_multicore_plan + validate_task_order using hash-verified frozen helpers; no simulation replay or independent capacity/runtime validation",
               "source_environment": records[0]["provenance"]["environment"],
               "source_workers_history": batch["workers_history"], "source_started_at": batch["started_at"],
               "source_finished_at": max(v["finished_at"] for v in batch["invocations"]),
               "results_over_64_mib": over64, "audit_wall_seconds": time.perf_counter() - start,
               "anomaly_counts": {kind: sum(a["kind"] == kind for a in anomaly_rows) for kind in
                                  ("slower_than_official_singlecore", "slower_than_previous_core_count")}}
    return rows, baselines, anomaly_rows, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-zip", type=Path, help="Optional fixed GitHub ZIP; default reads local Git objects")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Use a new output directory; do not overwrite an earlier audit")
    source = Source(args.source_zip)
    try:
        rows, baselines, anomalies, summary = audit(source)
        args.output.mkdir(parents=True)
        write_csv(args.output / "cells.csv", rows)
        write_csv(args.output / "baselines.csv", baselines)
        if anomalies:
            write_csv(args.output / "regressions.csv", anomalies)
        matrix = []
        by_key = {(r["case_id"], r["cores"]): r for r in rows}
        for case in sorted({r["case_id"] for r in rows}):
            entry = {"case_id": case, "official_singlecore_cycles": by_key[case, 1]["baseline_cycles"]}
            for cores in range(1, 6):
                entry[f"k{cores}_cycles"] = by_key[case, cores]["makespan_cycles"]
                entry[f"k{cores}_speedup"] = by_key[case, cores]["baseline_speedup"]
            matrix.append(entry)
        write_csv(args.output / "matrix_100x5.csv", matrix)
        save(args.output / "summary.json", summary)
        save(args.output / "source-audit.json", {"source_commit": COMMIT, "source_url": REPO_URL + "/tree/" + COMMIT,
             "reader": "fixed GitHub ZIP" if args.source_zip else "git cat-file --batch",
             "auditor_sha256": sha(Path(__file__).read_bytes()), "python": sys.version,
             "checked_files": len(source.items), "files": sorted(source.items.values(), key=lambda v: v["path"]),
             "scope": "All plan/result/run and referenced trace/log hashes, 100 denominators, frozen inputs, numeric fields, static plan order and aggregation. This is not an independent E0 rerun."})
        print(json.dumps({"verified_cells": len(rows), "verified_baselines": len(baselines),
                          "files": len(source.items), "by_cores": {k: v["baseline_speedup"]["mean"] for k, v in summary["by_cores"].items()},
                          "anomalies": summary["anomaly_counts"]}), flush=True)
    finally:
        source.close()


if __name__ == "__main__":
    main()
