#!/usr/bin/env python3
"""Generate a minimal board-submission-v1 feed from retained R8 evidence; no scoring."""
from __future__ import annotations
import gzip, hashlib, json, platform, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[5]
HERE = pathlib.Path(__file__).resolve().parent
BASE = ROOT / "results/a/q3-nikolastarx/query-flow-one-shot-20260925"
RUN = BASE / "run"
PLAN = ROOT / "results/a/q3-nikolastarx/query-flow-static-repair-20260925/run/case_071_multicore_res.json"
SUMMARY = PLAN.parent / "summary.json"
BASELINE = ROOT / "results/benchmark-board/official-singlecore-20260924/071/result.json.gz"
CONTROL = BASE / "resource-control/receipt.json"
SOURCE = "65d7355ee0856783ede81328915e8bd43227c842"
PLAN_SOURCE = "b1eb32aca82436b20cc82da8c86d4301ef00cfb1"
PLAN_SHA = "b0ccb1c9d9e2f90ae6566ecaa725a0440c47d942401a3cdcb261d90eb0968136"
GRAPH_SHA = "437cc74cae9e0fc0cb89b05403c62062ceff8d5bc2224c8834c519e69524e897"
CONFIG_SHA = "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9"
OFFICIAL_SHA = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"
SUPERVISOR_SHA = "651a8a9ee62253961abc656bfa50e01cdca4e17b5f799ad7d233826dcd438fa7"
BASELINE_SHA = "d2e46fd00db3766c4ca574084cde6d94b1aa062cab5b5199474c86013e51daa5"
RUN_ID = "q3-query-flow-071-r8-20260925T122351Z"
TASK_URL = "https://github.com/huaweibei123/huaweicup2026/issues/51"
REPO = "huaweibei123/huaweicup2026"

def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))

def read_gzip(path: pathlib.Path):
    return json.loads(gzip.decompress(path.read_bytes()))

def artifact(path: pathlib.Path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}

def code(path: str, entrypoint: str, commit: str = SOURCE):
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}

def main():
    if __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != SOURCE:
        raise SystemExit("frozen worktree HEAD mismatch")
    if sha(PLAN) != PLAN_SHA:
        raise SystemExit("candidate plan SHA mismatch")
    for path in ("src/q3/query_flow.py", "src/q3/query_flow_static.py"):
        a = __import__("subprocess").check_output(["git", "show", f"{PLAN_SOURCE}:{path}"], cwd=ROOT)
        b = __import__("subprocess").check_output(["git", "show", f"{SOURCE}:{path}"], cwd=ROOT)
        if hashlib.sha256(a).hexdigest() != hashlib.sha256(b).hexdigest():
            raise SystemExit(f"plan-generation source blob differs between recorded and frozen runner: {path}")
    summary = read(SUMMARY)
    if summary.get("source_commit") != PLAN_SOURCE:
        raise SystemExit("static-repair summary source commit mismatch")
    run = read(RUN / "run.json")
    monitor = read(CONTROL)
    if run.get("status") != "complete" or run.get("source_commit") != SOURCE or run.get("plan_sha256") != PLAN_SHA:
        raise SystemExit("probe run receipt identity/status mismatch")
    if run.get("official_code_sha256") != OFFICIAL_SHA:
        raise SystemExit("official evaluator hash mismatch")
    if monitor.get("status") != "failed" or monitor.get("supervisor_sha256") != SUPERVISOR_SHA:
        raise SystemExit("external supervision state/hash mismatch; preserve it as-is")
    base = read_gzip(BASELINE)
    if sha(BASELINE) != BASELINE_SHA or base.get("scene") != "A" or base.get("num_cores") != 1 or base.get("makespan") != 18919:
        raise SystemExit("official single-core baseline identity mismatch")
    common = {
        "graph_sha256": GRAPH_SHA, "config_sha256": CONFIG_SHA,
        "official_sha256": OFFICIAL_SHA, "plan_sha256": PLAN_SHA,
    }
    base_ref = {"graph_sha256": GRAPH_SHA, "config_sha256": CONFIG_SHA,
        "official_sha256": OFFICIAL_SHA, "route": "E0",
        "entrypoint": "singlecore_evaluate.evaluate_singlecore",
        "result": artifact(BASELINE)}
    p2_path, p3_path = RUN / "p2.json.gz", RUN / "p3.json.gz"
    p2, p3 = read_gzip(p2_path), read_gzip(p3_path)
    p2w, p3w = read(RUN / "p2.worker.json"), read(RUN / "p3.worker.json")
    if any(w.get("status") != "complete" for w in (p2w, p3w)):
        raise SystemExit("one or more official phase worker receipts incomplete")
    if any(w.get("result_sha256") != sha(p) for w, p in ((p2w,p2_path),(p3w,p3_path))):
        raise SystemExit("worker/result byte hashes differ")
    if p2.get("scene") != "B" or p3.get("scene") != "B" or p2.get("num_cores") != 5 or p3.get("num_cores") != 5:
        raise SystemExit("official result scene/core mismatch")
    guard = p3w.get("guard")
    if not guard or p3.get("makespan") != run.get("candidate_M") or p2.get("makespan") != run.get("candidate_P2_M"):
        raise SystemExit("guard/result/run values mismatch")
    start, finish = run["started_at"], run["finished_at"]
    no_evaluation_wall = "Worker receipts retain wrapper/diagnostic wall time, not isolated official-E0 time."
    no_solver_wall = "The offline fixed-plan construction time was not measured as end-to-end solver wall time."
    shared_notes = [
        "Localized 071/K5 mechanism evidence only: one frozen query-flow-affinity plan, official evaluator output retained byte-for-byte; not a full algorithm/full-500 result or a generalization claim.",
        f"Board ddr_bytes maps the evaluator's scheduled_copy_bytes={p3['data_movement_bytes']['scheduled_copy_bytes']}; it is a scheduled COPY total, not a measured physical DDR counter. added={p3['data_movement_bytes']['added_copy_bytes']}B, spill={p3['data_movement_bytes']['spill_added_copy_bytes']}B.",
        f"P3 cache_stats are copied from its original result: hit_bytes={p3['cache_stats']['hit_bytes']}, miss_bytes={p3['cache_stats']['miss_bytes']}, byte hit_rate={p3['cache_stats']['hit_rate']}; do not infer cold-solver speed from these values.",
        "The resource supervisor's retained raw receipt is status=failed with parent identity/process-group verification error and the same cleanup_error. This is not rewritten as supervisor success; probe run and both worker receipts independently report complete. No retry was run.",
        no_solver_wall, no_evaluation_wall,
        f"Static-repair summary records plan-generation source commit {PLAN_SOURCE}; query_flow.py and query_flow_static.py blobs match the R8 probe commit {SOURCE} byte-for-byte. The one-shot probe/E0 runner itself is pinned to {SOURCE}; the historical generator commit is preserved, not overwritten. The local admission path is redacted from argv.",
    ]
    solver_source = code("src/q3/query_flow_static.py", "src.q3.query_flow_static.main", PLAN_SOURCE)
    runner_source = code("src/q3/query_flow_probe.py", "src.q3.query_flow_probe.main")
    missing = {
        "provenance.environment.cpu": "The retained run records 18 logical CPUs but no CPU model.",
        "provenance.environment.threads": "Thread count was not recorded.",
        "provenance.environment.peak_rss_bytes": "Supervisor sampling failed before a trustworthy process-peak receipt; sampled RSS is not treated as process peak.",
        "provenance.measurement.cold_start": "Cold/warm process and filesystem cache state was not recorded.",
        "provenance.measurement.seed": "The fixed plan is deterministic and has no random seed.",
        "provenance.measurement.solver_scope": no_solver_wall,
    }
    def record(problem, phase, result_path, worker_path, result, worker):
        cache_rate = result.get("cache_stats", {}).get("hit_rate") if phase == "p3" else None
        metrics = {"makespan_cycles": result["makespan"], "solver_wall_seconds": None,
            "evaluation_wall_seconds": None,
            "ddr_bytes": result["data_movement_bytes"]["scheduled_copy_bytes"],
            "extra_ddr_bytes": result["data_movement_bytes"]["added_copy_bytes"],
            "spill_bytes": result["data_movement_bytes"]["spill_added_copy_bytes"],
            "cache_hit_rate": cache_rate}
        prov_missing = dict(missing)
        if phase == "p2":
            prov_missing["provenance.solver.method"] = "The P2 record is the same fixed plan evaluated without Cache; no separate P2 solver construction occurred."
        return {
            "attempt_id": f"nikolastarx-query-flow-071-r8-{phase}", "revision": 1,
            "run_id": RUN_ID, "algorithm_id": "q3-query-flow-affinity",
            "algorithm_name": "Q3 guarded query-flow affinity construction",
            "variant": "query-flow-affinity-r8-fixed071-k5",
            "solver_commit": PLAN_SOURCE,
            "parameters": {"candidate_count": 1, "requested_cores": 5,
                "plan_sha256": PLAN_SHA, "selection": "one offline fixed plan; no online selection"},
            "problem": problem, "case_id": "071", "cores": 5, "status": "ok",
            "metrics": metrics,
            "evaluator": {"route": "E0", "commit": SOURCE,
                "entrypoint": "multicore_cut_evaluate_problem_3.evaluate_problem_3" if phase == "p3" else "multicore_cut_evaluate_problem_2.evaluate_scene_b"},
            "identity": common,
            "artifacts": {"plan": artifact(PLAN), "result": artifact(result_path),
                "run": artifact(RUN / "run.json"), "trace": artifact(worker_path),
                "manifest": artifact(SUMMARY)},
            "runtime_id": "macos-arm64-local-shared-48GiB",
            "observed_at": worker.get("started_at", start),
            "timing": {"solver_includes_evaluation": None,
                "evaluation_precision": no_evaluation_wall,
                "utc": "Original run and worker receipt UTC timestamps; wrapper diagnostic seconds are not solver/evaluator-only wall time."},
            "provenance": {"producer_session": "nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc",
                "task_url": TASK_URL,
                "solver": {"source": solver_source, "authors": ["nikolastarx"],
                    "method": "Query-flow affinity construction groups shared query-flow components under a frozen owner assignment; this feed covers only one fixed 071/K5 mechanism plan.",
                    "references": [], "upstream": [], "selected_algorithm_id": None,
                    "selected_solver_commit": None},
                "runner": {"source": runner_source, "argv": ["python3", "-B", "-m", "src.q3.query_flow_probe", "results/a/q3-nikolastarx/query-flow-static-repair-20260925/run", "results/a/q3-nikolastarx/query-flow-one-shot-20260925/run", "--source", SOURCE, "--plan-sha256", PLAN_SHA, "--admission-ref", "<R2-approved-admission-path>"], "working_directory": "."},
                "environment": {"os": run["environment"]["platform"], "cpu": None, "gpu": "none",
                    "ram_bytes": 48 * 1024**3, "python": run["environment"]["python"],
                    "dependencies": "uv.lock sha256:7b03fee57044ac272d8895533cbdca6d70a29d2da955f98a5552e72ef944fdc4",
                    "threads": None, "workers": 1, "peak_rss_bytes": None},
                "measurement": {"started_at": worker.get("started_at", start),
                    "finished_at": worker.get("finished_at", finish), "seed": None,
                    "repeat_index": 0, "cold_start": None,
                    "solver_scope": None,
                    "evaluation_scope": "One frozen-plan official E0 phase; worker diagnostic wall includes process startup, observer, and evaluator and is not reported as E0-only wall.",
                    "budget": {"wall_seconds": 600, "candidate_limit": 1,
                        "stop_reason": "P3 and conditional same-plan P2 E0 worker phases completed; zero retries. External resource supervisor failed its process identity/cleanup check after the probe outputs were written."},
                    "calls": {"solver": 0, "E0": 1, "E1": 0, "E2": 0},
                    "offline_costs": "Plan was constructed in the earlier static-repair phase. That phase summary aggregates 2 construct and 2 pipe-bound calls across cases 071 and 069; it does not isolate this 071 cell's end-to-end solver wall and is not charged as an invented per-cell time.",
                    "failure": None},
                "missing_reasons": prov_missing},
            "notes": shared_notes + [
                f"Original supervisor receipt SHA256={sha(CONTROL)} is retained at {CONTROL.relative_to(ROOT).as_posix()} with status failed; do not equate the worker's completed E0 with successful external process-group supervision.",
                "`status=ok` identifies only the completed official evaluator output for this cell; it does not claim successful supervision, solver timing, independent replay, or full-algorithm acceptance."
            ],
            "source_url": f"https://github.com/{REPO}/blob/{PLAN_SOURCE}/src/q3/query_flow.py",
            "baseline": base_ref,
            "cache_pair": ({"graph_sha256": GRAPH_SHA, "config_sha256": CONFIG_SHA,
                "official_sha256": OFFICIAL_SHA, "plan_sha256": PLAN_SHA,
                "cores": 5, "route": "E0", "result": artifact(p2_path)} if phase == "p3" else None),
        }
    feed = {"schema_version": 1, "submission_version": 1, "records": [
        record("P3", "p3", p3_path, RUN / "p3.worker.json", p3, p3w),
        record("P2", "p2", p2_path, RUN / "p2.worker.json", p2, p2w),
    ]}
    (HERE / "feed.json").write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
