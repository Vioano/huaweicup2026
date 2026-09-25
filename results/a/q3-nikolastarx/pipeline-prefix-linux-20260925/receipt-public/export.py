#!/usr/bin/env python3
"""Rebuild the P3-044 export from retained bytes; this script runs no evaluators."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / "results/a/q3-nikolastarx/pipeline-prefix-linux-20260925"
OUT = Path(__file__).resolve().parent
ARCHIVE = BASE / "run-local/evidence.tar.gz"
PACKAGE_SHA = "9c16cf654a8c5521c5bab414724a962f07c8d95806d1dbc64b0c7c0206ed86ec"
PLAN_SHA = "13914b24c18b59366be17de86a26d227ff85427cb00b184799587777547a6508"
BASELINE_SHA = "73f1d15fdea4f706b22099d2339a0e74a76c4114a68672077a98a8e15faa913c"
ARCHIVE_SHA = "a923a07fc1ad549eecaae227e534d7a7de83ef1647a67a60a70d130c4aef8b05"
SOURCE_COMMIT = "62c69b20ab887c76567dbab5fcce6eef30107b5c"
SUPERVISOR_COMMIT = "c642da2b016a5796882a24432bc5f01eb9dd6a7c"
ATTEMPT = "nikolastarx-prefix-linux-044-k5-20260925-s3172"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(data: bytes):
    return json.loads(data.decode("utf-8"))


def safe_member(tf: tarfile.TarFile, name: str) -> bytes:
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"unsafe archive path: {name}")
    member = tf.getmember(name)
    if not member.isfile():
        raise ValueError(f"not a regular file: {name}")
    return tf.extractfile(member).read()


def write_bytes(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha(data)


def dump(path: Path, value) -> str:
    return write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--observed-at", default="2026-09-25T03:57:41.846342Z")
    args = parser.parse_args()

    if sha(ARCHIVE.read_bytes()) != ARCHIVE_SHA:
        raise SystemExit("evidence archive SHA mismatch")
    plan_src = ROOT / "results/a/q3-nikolastarx/pipeline-prefix-static-20260925/case_044_multicore_res.json"
    baseline_src = ROOT / "results/a/q3-nikolastarx/baseline-revision-20260925/baseline/044-result.json.gz"
    plan = plan_src.read_bytes()
    baseline = baseline_src.read_bytes()
    if sha(plan) != PLAN_SHA or sha(baseline) != BASELINE_SHA:
        raise SystemExit("frozen plan or baseline SHA mismatch")

    # Read only named regular files. Retain exact source bytes under this staging folder.
    names = {
        "probe/official-p3.json.gz": "raw-evidence/official-p3.json.gz",
        "probe/run.json": "raw-evidence/probe-run.json",
        "probe/prepare/run.json": "raw-evidence/prepare-run.json",
        "probe/score-reservation.json": "raw-evidence/score-reservation.json",
        "probe/score-worker-claim.json": "raw-evidence/score-worker-claim.json",
        "probe/score-worker.json": "raw-evidence/score-worker.json",
        "probe/score.stdout.txt": "raw-evidence/score.stdout.txt",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with tarfile.open(ARCHIVE, "r:gz") as tf:
        for member in tf.getmembers():
            p = PurePosixPath(member.name)
            if p.is_absolute() or ".." in p.parts or not (member.isfile() or member.isdir()):
                raise SystemExit(f"unsafe archive member: {member.name}")
        source = {name: safe_member(tf, name) for name in names}
    evidence_hashes = {name: write_bytes(OUT / target, data) for name, target in names.items() for data in [source[name]]}
    probe = read_json(source["probe/run.json"])
    prep = read_json(source["probe/prepare/run.json"])
    worker = read_json(source["probe/score-worker.json"])
    score = read_json(source["probe/score.stdout.txt"])
    result_bytes = gzip.decompress(source["probe/official-p3.json.gz"])
    result = read_json(result_bytes)
    baseline_result = read_json(gzip.decompress(baseline))
    if probe['status'] != 'complete' or prep['status'] != 'complete' or worker['status'] != 'complete':
        raise SystemExit('incomplete original execution receipt')
    if prep['calls_started'] != {'Step1': 5, 'Step2': 5, 'Step3': 5}:
        raise SystemExit('unexpected preparation calls')
    if worker['counts_started'] != {'P3': 1, 'P2': 0, 'Step1': 5, 'Step2': 5, 'prepare_Step3': 5, 'step3_simulation': 5}:
        raise SystemExit('unexpected scoring calls')
    if sha(source['probe/official-p3.json.gz']) != worker['official_result_sha256'] or worker['official_result_sha256'] != probe['official_result_sha256']:
        raise SystemExit('official result receipt hash mismatch')

    expected = {
        "source_commit": SOURCE_COMMIT,
        "plan_sha256": PLAN_SHA,
        "official_code_sha256": "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0",
        "manifest_sha256": "b2ec66eb5e4e0777519c09a3f8937e5df514e1fc6372e1a88e3aa369af9c9a14",
    }
    for key, value in expected.items():
        if probe.get(key) != value:
            raise SystemExit(f"probe receipt mismatch: {key}")
    input_hashes = probe["source_input_sha256"]
    graph_sha = input_hashes["data/raw/a/official/data/case_044.json"]
    config_sha = input_hashes["data/raw/a/official/data/config.txt"]
    if result.get("scene") != "B" or result.get("problem") != 3 or result.get("num_cores") != 5:
        raise SystemExit("official result identity mismatch")
    if result.get("makespan") is None or result.get("cache_mode") != "read_only":
        raise SystemExit("official result incomplete")
    if baseline_result.get("scene") != "A" or baseline_result.get("num_cores") != 1:
        raise SystemExit("baseline identity mismatch")

    artifact_dir = OUT / "artifacts"
    plan_hash = write_bytes(artifact_dir / "case_044_multicore_res.json", plan)
    result_hash = write_bytes(artifact_dir / "044-result.json.gz", source["probe/official-p3.json.gz"])
    baseline_hash = write_bytes(artifact_dir / "044-baseline-result.json.gz", baseline)
    score_started = worker["started_at"]
    score_finished = worker["finished_at"]
    score_seconds = score.get("read_evaluate_write_seconds")
    sampled_peak = score.get("max_rss_bytes")

    # Publishable derived run projection omits local admission path and all CLI/session credentials.
    public_run = {
        "schema": "q3-prefix-linux-public-run-v1",
        "status": probe["status"],
        "source_commit": probe["source_commit"],
        "supervisor_commit": SUPERVISOR_COMMIT,
        "package_sha256": PACKAGE_SHA,
        "source_archive_sha256": ARCHIVE_SHA,
        "manifest_sha256": probe["manifest_sha256"],
        "plan_sha256": probe["plan_sha256"],
        "official_code_sha256": probe["official_code_sha256"],
        "official_result_sha256": probe["official_result_sha256"],
        "started_at": probe["started_at"],
        "finished_at": probe["finished_at"],
        "evaluation_started_at": score_started,
        "evaluation_finished_at": score_finished,
        "budget": probe["budget"],
        "prepare_calls": prep["calls_started"],
        "score_counts_started": worker["counts_started"],
        "score_limits": worker["limits"],
        "score_diagnostic_wall_seconds": worker["diagnostic_wall_seconds"],
        "evaluation_read_evaluate_write_seconds": score_seconds,
        "sampled_process_max_rss_bytes": sampled_peak,
        "environment": {
            "os": "Linux 6.6.122+ x86_64; Colab managed CPU Standard image",
            "python": "CPython 3.12.13",
            "cpu_count": None,
            "cpu_model": None,
            "gpu": "none",
            "ram_bytes": None,
            "dependencies": "uv.lock sha256:7b03fee57044ac272d8895533cbdca6d70a29d2da955f98a5552e72ef944fdc4",
            "workers": 1,
            "threads": None,
        },
        "privacy_note": "Admission reference path removed from this derived copy; exact original receipts remain in raw-evidence and run-local/evidence.tar.gz.",
    }
    public_run_hash = dump(OUT / "artifacts/run-public.json", public_run)

    missing = {
        "provenance.solver.selected_algorithm_id": "This is a frozen single-plan mechanism probe, not a portfolio-selected subalgorithm.",
        "provenance.solver.selected_solver_commit": "This is a frozen single-plan mechanism probe, not a portfolio-selected subalgorithm.",
        "provenance.environment.cpu": "Colab receipt records CPU count but not the CPU model.",
        "provenance.environment.ram_bytes": "Host total RAM was not retained in the selected evidence.",
        "provenance.environment.threads": "Thread count was not retained.",
        "provenance.measurement.solver_scope": "The plan was constructed offline; complete construction start-to-finish wall time is unavailable.",
        "provenance.measurement.seed": "The frozen construction is deterministic and no random seed was recorded.",
        "provenance.measurement.cold_start": "Cold/warm process and filesystem cache state was not recorded.",
    }
    record = {
        "attempt_id": ATTEMPT,
        "revision": 1,
        "run_id": "q3-pipeline-prefix-linux-20260925-s3172",
        "algorithm_id": "q3-pipeline-prefix",
        "algorithm_name": "Q3 static-constructed pipeline-prefix mechanism",
        "variant": "static-constructed-prefix-one-shot",
        "solver_commit": SOURCE_COMMIT,
        "parameters": {"requested_cores": 5, "candidate_count": 1, "selection": "one frozen offline-constructed plan; no online selection"},
        "problem": "P3",
        "case_id": "044",
        "cores": 5,
        "status": "ok",
        "metrics": {
            "makespan_cycles": result["makespan"],
            "solver_wall_seconds": None,
            "evaluation_wall_seconds": score_seconds,
            "ddr_bytes": result["data_movement_bytes"]["scheduled_copy_bytes"],
            "extra_ddr_bytes": result["data_movement_bytes"]["added_copy_bytes"],
            "spill_bytes": result["data_movement_bytes"]["spill_added_copy_bytes"],
            "cache_hit_rate": result["cache_stats"]["hit_rate"],
        },
        "evaluator": {"route": "E0", "commit": SOURCE_COMMIT, "entrypoint": "multicore_cut_evaluate_problem_3.evaluate_problem_3"},
        "identity": {"graph_sha256": graph_sha, "config_sha256": config_sha, "official_sha256": probe["official_code_sha256"], "plan_sha256": plan_hash},
        "artifacts": {
            "plan": {"path": "results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/receipt-public/artifacts/case_044_multicore_res.json", "sha256": plan_hash},
            "result": {"path": "results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/receipt-public/artifacts/044-result.json.gz", "sha256": result_hash},
            "run": {"path": "results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/receipt-public/artifacts/run-public.json", "sha256": public_run_hash},
        },
        "baseline": {
            "graph_sha256": graph_sha,
            "config_sha256": config_sha,
            "official_sha256": probe["official_code_sha256"],
            "route": "E0",
            "entrypoint": "singlecore_evaluate.evaluate_singlecore",
            "result": {"path": "results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/receipt-public/artifacts/044-baseline-result.json.gz", "sha256": baseline_hash},
        },
        "runtime_id": "colab-cpu-standard-managed-image",
        "observed_at": args.observed_at,
        "timing": {"solver_includes_evaluation": False, "evaluation_precision": "traced external evaluator read/evaluate/write wall time", "utc": "UTC timestamps retained by remote supervisor and score worker"},
        "provenance": {
            "producer_session": "nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc",
            "task_url": "https://github.com/huaweibei123/huaweicup2026/issues/51",
            "solver": {
                "source": {"repo": "huaweibei123/huaweicup2026", "commit": SOURCE_COMMIT, "path": "results/a/q3-nikolastarx/pipeline-prefix-static-20260925/case_044_multicore_res.json", "entrypoint": "frozen plan; no solver process in this run"},
                "authors": ["nikolastarx"],
                "method": "One fixed offline-constructed pipeline-prefix plan, independently evaluated once by official P3 E0; mechanism-cell result only.",
                "references": [], "upstream": [], "selected_algorithm_id": None, "selected_solver_commit": None,
            },
            "runner": {
                "source": {"repo": "huaweibei123/huaweicup2026", "commit": SUPERVISOR_COMMIT, "path": "scripts/q3_prefix_linux_supervisor.py", "entrypoint": "q3_prefix_linux_supervisor.py"},
                "argv": ["python -B q3_prefix_linux_supervisor.py <frozen manifest> <run output> --manifest-sha256 <sha256> --admission-ref <redacted>"],
                "working_directory": ".",
            },
            "environment": {"os": "Linux 6.6.122+ x86_64; managed Colab image", "cpu": None, "gpu": "none", "ram_bytes": None, "python": "CPython 3.12.13", "dependencies": "uv.lock sha256:7b03fee57044ac272d8895533cbdca6d70a29d2da955f98a5552e72ef944fdc4", "threads": None, "workers": 1, "peak_rss_bytes": sampled_peak},
            "measurement": {
                "started_at": score_started, "finished_at": score_finished, "seed": None, "repeat_index": 0, "cold_start": None,
                "solver_scope": None,
                "evaluation_scope": "One official P3 E0 evaluation; 1.952790842 s read/evaluate/write with tracing enabled. This is not solver wall time.",
                "budget": {"wall_seconds": 60, "candidate_limit": 1, "stop_reason": "One admitted P3 completed; P2=0 and retries=0."},
                "calls": {"solver": 0, "E0": 1, "E1": 0, "E2": 0},
                "offline_costs": "The static plan was constructed before this evaluation; full construction wall time is unavailable. No online solver call occurred.",
                "failure": None,
            },
            "missing_reasons": missing,
        },
        "notes": [
            "Single mechanism cell P3 044-k5; not a full-algorithm or full-suite score.",
            "The complete end-to-end solver wall time is unknown; solver_wall_seconds is null because the static plan construction time was not captured.",
            "Evaluation time is the traced E0 read/evaluate/write measurement and must not be presented as solver wall time.",
            "Call ledger: prepare executed Step1=5, Step2=5, Step3=5; P3 score executed Step1=5, Step2=5, prepare Step3=5, step3_simulation=5; aggregate prepare_step3_execution=10, P3=1, P2=0, retries=0, unknown=0.",
            "Compared with the retained prior 044 P3 result (makespan 38390), this result is 38024 (0.9533732743% lower); added bytes remain 140800 and spill remains 0.",
            "Old and new P3 cache_stats are identical (11264 hit bytes, 1012064 miss bytes, hit_rate 0.011007223490415585). No same-plan P2 result exists, so CacheGain is unknown; no cache improvement is claimed.",
            "P3 result scene is B, problem=3, cache_mode=read_only. Baseline is the frozen official single-core A result.",
            "No P2 cache_pair is included.",
        ],
        "source_url": f"https://github.com/huaweibei123/huaweicup2026/blob/{SOURCE_COMMIT}/results/a/q3-nikolastarx/pipeline-prefix-static-20260925/case_044_multicore_res.json",
    }
    dump(OUT / "board-feed-20260925T035741Z-s3172.json", {"schema_version": 1, "submission_version": 1, "records": [record]})

    report = f"""# P3 044 Linux mechanism-cell export\n\nThis is one P3 044 / five-core official E0 result for frozen static plan `{PLAN_SHA}` from solver/source commit `{SOURCE_COMMIT}`. It is a mechanism cell, not a complete algorithm or full-suite score.\n\n- Makespan: **{result['makespan']} cycles**, versus the retained prior P3 result **38390** (0.9533732743% lower).\n- Added data movement: **{result['data_movement_bytes']['added_copy_bytes']} B**; spill: **{result['data_movement_bytes']['spill_added_copy_bytes']} B**.\n- P3 cache stats match the prior P3 result: hit bytes 11264, miss bytes 1012064, byte hit rate {result['cache_stats']['hit_rate']:.16f}. This does not establish CacheGain; the required same-plan P2 result is absent, so CacheGain remains unknown.\n- Evaluation read/evaluate/write time: **{score_seconds:.9f} s**, measured with tracing. It is external evaluation time, not solver time. Full plan-construction end-to-end wall time is unavailable, so solver wall is null.\n- Calls: prepare phase Step1/Step2/Step3 = 5/5/5; P3 score phase Step1/Step2/prepare-Step3/step3-simulation = 5/5/5/5. Aggregate prepare-Step3 executions = 10; P3=1, P2=0, retries=0, unknown=0.\n- Plan SHA: `{plan_hash}`; result SHA: `{result_hash}`; baseline SHA: `{baseline_hash}`; source archive SHA: `{ARCHIVE_SHA}`.\n\n## Evidence handling\n\n`export.py` copies the frozen plan and baseline and safely reads only named regular members from the retained tar. The exact selected result and receipt bytes are kept under `raw-evidence/`; original `run-local` remains unchanged. Exact original receipts retain the local admission-document path as provenance; the derived `artifacts/run-public.json` omits it. Root reviewed the original archive and CLI outputs before publication; no credential material was found. No CLI credential or session connection fields are included in the feed.\n\nThe official result identity is scene B, problem 3, cache_mode read_only, five cores. Baseline is the unchanged official single-core scene A result. No P2 cache pair is claimed.\n"""
    write_bytes(OUT / "REPORT.md", report.encode())

    hashes = {str(p.relative_to(OUT)): sha(p.read_bytes()) for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.json"}
    dump(OUT / "SHA256SUMS.json", hashes)
    print(json.dumps({"feed": str(OUT / "board-feed-20260925T035741Z-s3172.json"), "files": len(hashes), "official_makespan": result["makespan"], "evaluation_wall_seconds": score_seconds, "evidence_hashes": evidence_hashes}, indent=2))


if __name__ == "__main__":
    main()
