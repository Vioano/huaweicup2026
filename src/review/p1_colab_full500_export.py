"""Export verified successful Colab P1 cells; never construct or evaluate."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
SOLVER = "3a1b82b71ca1ff6689eb8e72f17d26c48b52073c"
WRAPPER = "bd6dc85a0b69f30d08714cbb46200f90632bb2d7"
WRAPPER_SHA = "589cf9a544b3edfe31b3b515d5bdf9ec876badda52f3a26310af8640d5baa4e9"
FROZEN_RUNNER = "8335b5c55b0c12bd34b206e315582d1198439069"
BASE = "6fcec11ccc472a1a652b21feb6fccf85a4555598"
BASE_DIR = "results/benchmark-board/official-singlecore-20260924"
RUN_ID = "20260925T0110Z-s6607"
REPO = "huaweibei123/huaweicup2026"


def digest(raw): return hashlib.sha256(raw).hexdigest()
def raw(path): return Path(path).read_bytes()
def read(path): return json.loads(raw(path))
def artifact(path): return {"path": Path(path).resolve().relative_to(ROOT).as_posix(), "sha256": digest(raw(path))}
def source(commit, path, entry): return dict(repo=REPO, commit=commit, path=path, entrypoint=entry)

def validate_record_shape(record):
    required = {"attempt_id","revision","run_id","algorithm_id","algorithm_name",
                "solver_commit","problem","case_id","cores","status","metrics",
                "evaluator","identity","artifacts","provenance"}
    if required - record.keys() or set(record["artifacts"]) & {"plan","result","run"} != {"plan","result","run"}:
        raise ValueError("board submission success record lacks required structure")


def validate_success(row, folder, batch):
    if row.get("status") != "ok" or row.get("calls", {}).get("E0") != 1 or row.get("reused_e0"):
        raise ValueError("only new-E0 successful cells are exportable")
    if row.get("calls", {}).get("solver") != 1 or type(row.get("calls", {}).get("E1")) is not int:
        raise ValueError("solver/E1 call ledger unknown")
    if (row.get("case_id") != folder.parent.name or row.get("cores") != int(folder.name[1:]) or
            row.get("model_source", {}).get("solver_commit") != SOLVER or
            row["calls"].get("E2") != 0 or not 0 <= row["calls"]["E1"] <= 9):
        raise ValueError("cell path/model/call identity mismatch")
    if (row.get("solver", {}).get("cleanup_confirmed") is not True or
            row.get("evaluation", {}).get("cleanup_confirmed") is not True or
            not any(str(part).endswith("multicore_cut_evaluate_problem_1.py")
                    for part in row.get("evaluation", {}).get("argv", []))):
        raise ValueError("official E0 command or process cleanup unverified")
    plan, result, receipt = folder / "plan.json", folder / "result.json", folder / "run.json"
    if any(not path.is_file() for path in (plan, result, receipt)):
        raise ValueError("plan/result/run original missing")
    for key, path in (("plan", plan), ("result", result)):
        if row.get("artifacts", {}).get(key, {}).get("sha256") != digest(raw(path)):
            raise ValueError(f"{key} receipt hash differs from bytes")
    hashes = batch.get("download_file_hashes", {})
    for path in (plan, result, receipt):
        relative = path.relative_to(batch["download_root"]).as_posix()
        if hashes.get(relative) != digest(raw(path)):
            raise ValueError(f"downloaded original hash missing or mismatched: {relative}")
    if set(read(plan)) != {"node_to_subgraph", "core_schedules"}:
        raise ValueError("plan is not exactly two keys")
    value = read(result)
    if (value.get("scene") != "A" or value.get("num_cores") != row["cores"] or
            value.get("makespan") != row.get("makespan_cycles") or
            value.get("data_movement_bytes", {}).get("scheduled_copy_bytes") != row.get("scheduled_copy_bytes")):
        raise ValueError("E0 result/receipt identity mismatch")
    if (row.get("graph_sha256") != batch["input_hashes"][row["case_id"]] or
            batch.get("solver_commit") != SOLVER or batch.get("run_id") != RUN_ID or
            batch.get("config_sha256") != batch.get("official_config_sha256") or
            batch.get("official_code_hash") != batch.get("official_expected_hash")):
        raise ValueError("input/solver/run identity mismatch")
    if row.get("solver", {}).get("status") != "ok" or row.get("evaluation", {}).get("status") != "ok":
        raise ValueError("process receipt lacks successful solver/E0")
    return value


def git_base(case):
    path = f"{BASE_DIR}/{case}/result.json.gz"
    packed = subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)
    baseline = json.loads(gzip.decompress(packed))
    if baseline.get("makespan") is None:
        raise ValueError("single-core original missing Makespan")
    return packed


def verified_download(batch_dir, manifest_path):
    listing = read(manifest_path)
    if not isinstance(listing.get("files"), list): raise ValueError("download manifest needs files")
    hashes = {}
    for item in listing["files"]:
        name = item["path"]
        candidate = Path(name)
        if (candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts or
                "\\" in name or ":" in name or
                not name or name in hashes):
            raise ValueError("unsafe or duplicate download manifest path")
        path = batch_dir / candidate
        if not path.is_file() or not path.resolve().is_relative_to(batch_dir.resolve()):
            raise ValueError(f"download original missing or escapes batch: {name}")
        data = raw(path)
        if len(data) != item["bytes"] or digest(data) != item["sha256"]:
            raise ValueError(f"download original bytes/hash differ: {name}")
        hashes[name] = item["sha256"]
    if "batch.json" not in hashes: raise ValueError("download manifest lacks batch.json")
    return hashes


def export(batch_dir, manifest_path, environment_path, output_dir, task_url):
    batch_dir, output_dir = Path(batch_dir), Path(output_dir).resolve()
    if not output_dir.is_relative_to(ROOT): raise ValueError("export directory must be inside repository")
    hashes = verified_download(batch_dir, manifest_path)
    batch = read(batch_dir / "batch.json")
    if (batch.get("run_id") != RUN_ID or batch.get("solver_commit") != SOLVER or
            batch.get("wrapper_head") != WRAPPER or batch.get("wrapper_sha256") != WRAPPER_SHA or
            batch.get("frozen_runner_commit") != FROZEN_RUNNER):
        raise ValueError("wrong frozen Colab batch")
    expected = {(f"{c:03d}", k) for c in range(1,101) for k in range(1,6)}
    if len(batch.get("cells", [])) != 500 or {tuple(cell) for cell in batch["cells"]} != expected:
        raise ValueError("batch does not declare the fixed 500 unique cells")
    if not task_url.startswith(f"https://github.com/{REPO}/issues/"):
        raise ValueError("explicit P1 task URL required")
    evidence = read(environment_path)
    if evidence.get("run_id", RUN_ID) != RUN_ID:
        raise ValueError("environment evidence run_id mismatch")
    env_keys = ("os","cpu","gpu","ram_bytes","python","dependencies","threads","workers","peak_rss_bytes")
    if any(key not in evidence for key in env_keys) or evidence.get("workers") != 1:
        raise ValueError("Colab environment evidence lacks required fields or worker1")
    for key in env_keys:
        if evidence[key] is None and not evidence.get("missing_reasons", {}).get(f"provenance.environment.{key}"):
            raise ValueError(f"missing reason for environment {key}")
    official = read(ROOT / "docs/a/source-manifest.json")
    files = {item["path"]: item for item in official["files"]}
    batch["input_hashes"] = {f"{i:03d}":files[f"data/case_{i:03d}.json"]["sha256"] for i in range(1,101)}
    batch["official_config_sha256"] = files["data/config.txt"]["sha256"]
    batch["official_expected_hash"] = official["official_code_hash"]
    batch["download_root"] = batch_dir
    batch["download_file_hashes"] = hashes
    rows = []
    for case, cores in batch["cells"]:
        path = batch_dir / "cells" / case / f"k{cores}"
        rows.append((case, cores, path, read(path / "run.json") if (path / "run.json").exists() else {"status":"missing"}))
    output_dir.mkdir(parents=True, exist_ok=False)
    records, skipped = [], []
    for case, cores, folder, row in rows:
        if row.get("status") != "ok":
            skipped.append(dict(case_id=case, cores=cores, status=row.get("status"), reason=row.get("failure",row.get("not_run_reason"))))
            continue
        value = validate_success(row, folder, batch)
        dest = output_dir / "cells" / case / f"k{cores}"
        dest.mkdir(parents=True)
        plan = dest / "plan.json"; plan.write_bytes(raw(folder / "plan.json"))
        run = dest / "run.json"; run.write_bytes(raw(folder / "run.json"))
        result = dest / "result.json.gz"
        result.write_bytes(gzip.compress(raw(folder / "result.json"), compresslevel=6, mtime=0))
        baseline = output_dir / "baseline" / case / "result.json.gz"
        baseline.parent.mkdir(parents=True, exist_ok=True)
        if not baseline.exists(): baseline.write_bytes(git_base(case))
        machine = {key:evidence[key] for key in env_keys}
        missing = dict(evidence.get("missing_reasons", {}))
        movement = value.get("data_movement_bytes", {})
        failure = None
        record = dict(attempt_id=f"nikolastarx-{RUN_ID}-P1-{case}-k{cores}-r0", revision=1,
            run_id=RUN_ID, algorithm_id="q1-structural-refine-experimental",
            algorithm_name="P1 variable response with intact structural refinement",
            variant="variable-parent-then-intact-two-v1", solver_commit=SOLVER,
            parameters=dict(cores=cores, max_candidates=9, online_backend="E1", workers=1,
                            solver_timeout_seconds=300, external_e0_timeout_seconds=900),
            problem="P1",case_id=case,cores=cores,status="ok",
            metrics=dict(makespan_cycles=value["makespan"],
                         solver_wall_seconds=row["solver"]["wall_seconds"],
                         evaluation_wall_seconds=row["evaluation"]["wall_seconds"],
                         ddr_bytes=movement.get("scheduled_copy_bytes"),
                         extra_ddr_bytes=movement.get("added_copy_bytes"),
                         spill_bytes=movement.get("spill_added_copy_bytes")),
            evaluator=dict(route="E0",commit=SOLVER,entrypoint="multicore_cut_evaluate_problem_1.py"),
            identity=dict(graph_sha256=row["graph_sha256"],config_sha256=batch["config_sha256"],
                          official_sha256=batch["official_code_hash"],plan_sha256=digest(raw(plan))),
            artifacts=dict(plan=artifact(plan),result=artifact(result),run=artifact(run)),
            baseline=dict(graph_sha256=row["graph_sha256"],config_sha256=batch["config_sha256"],
                          official_sha256=batch["official_code_hash"],route="E0",
                          entrypoint="singlecore_evaluate.evaluate_singlecore",result=artifact(baseline)),
            runtime_id="nikolastarx-colab-linux-cpu-py31213-20260925",
            observed_at=row.get("finished_at"),
            timing=dict(solver_includes_evaluation=False,evaluation_precision="outer subprocess perf_counter wall",utc="ISO UTC Z"),
            provenance=dict(producer_session="nikolastarx/s-6607cb2735304751b36662035723372b",
              task_url=task_url,
              solver=dict(source=source(SOLVER,"src/q1/structural_refine.py","main"),authors=["NikolaStarx"],
                          method="Variable response parent, then guarded intact paced/fused candidates with online E1 strict selection",references=[],upstream=[],
                          selected_algorithm_id=row.get("selected"),selected_solver_commit=SOLVER if row.get("selected") else None),
              runner=dict(source=source(WRAPPER,"src/q1_benchmarks/s6607_colab_fresh.py","run"),
                          argv=[".venv/bin/python","-B","src/q1_benchmarks/s6607_colab_fresh.py","--full500"],working_directory="."),
              environment=machine,measurement=dict(started_at=row.get("started_at"),finished_at=row.get("finished_at"),
                seed=None,repeat_index=0,cold_start=True,
                solver_scope="Fresh child through plan and diagnostics output and exit; online E1 included",
                evaluation_scope="Independent new official E0 child through result/trace/log and exit",
                budget=dict(wall_seconds=300,candidate_limit=9,stop_reason="successful complete"),
                calls=row["calls"],offline_costs="none",failure=failure),missing_reasons=missing),
            notes=["Fresh official E0 for this cell; no historical E0 reuse", "Partial batch if feed contains fewer than 500 successful cells"],
            source_url=task_url)
        validate_record_shape(record)
        records.append(record)
    feed=dict(schema_version=1,submission_version=1,records=records)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    feed_path=output_dir/f"board-feed-{stamp}-colab.json"
    feed_path.write_text(json.dumps(feed,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    manifest=dict(run_id=RUN_ID,batch_status=batch.get("status"),partial=(batch.get("status")!="complete" or len(records)!=500),
                  exported_successes=len(records),skipped=skipped,feed=artifact(feed_path),
                  environment_evidence_sha256=digest(raw(environment_path)),download_manifest_sha256=digest(raw(manifest_path)),
                  source_batch_sha256=digest(raw(batch_dir/"batch.json")))
    (output_dir/"export-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--environment",type=Path,required=True)
    p.add_argument("--output-root",type=Path,required=True)
    p.add_argument("--task-url",required=True)
    a=p.parse_args()
    print(json.dumps(export(a.batch,a.manifest,a.environment,a.output_root,a.task_url)))


if __name__=="__main__": main()
