#!/usr/bin/env python3
"""Export retained P3/P2 evidence to board-submission-v1; runs no evaluators."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[5]
RUN = ROOT / "results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z"
OUT = Path(__file__).resolve().parent
ARCHIVE = RUN / "evidence.tar.gz"
SOURCE = "817e9e399f5efaf66cea6ddc495fe444950e43f2"
CONTROLLER = "f4bc0b983f247e3395394e9b4ac25b25fd210d0b"
PACKAGE_SHA = "5b293299544502de4c5aa2569d55ebd768262d5462ea54f4f68092749445c6f7"
ARCHIVE_SHA = "02fa71024fcc6fe35071c7dd9e8a5516caa55609bcbb8fa930bcc661aa114898"
OFFICIAL_SHA = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"
GRAPH_SHA = "9abd4468a4be365e384de47431ac914ee44fd6e7b6221dffc584561f388cd57e"
CONFIG_SHA = "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9"
CANDIDATE_PLAN_SHA = "0a75e3613ad5f69e293e45e6c1cfc1545b3b1036245ebc7bf0af75b3321df0fd"
CONTROL_PLAN_SHA = "13914b24c18b59366be17de86a26d227ff85427cb00b184799587777547a6508"
BASELINE_SHA = "73f1d15fdea4f706b22099d2339a0e74a76c4114a68672077a98a8e15faa913c"
REUSED_P3_SHA = "d4cdf8dbabe22923b9a74329741fb39e74a588e619d9f101db1fd28ecd629da1"
RESULTS = {
    "candidate-p3": "cd420766d4e25ee64c4228ab4796a360b76c579709a3e5ab97ae21505303bdb2",
    "candidate-p2": "876c2d041a2d9eb58329335d973a64af28d5c9a1ab067c3b699eb402bba3688f",
    "control-p2": "fca6843530f98c01aa22a36a2b5e96a0b06285e5635067cbdd2c76cd6c80ae14",
}
ATTEMPTS = {k: f"nikolastarx-partial-preload-{k}-044-k5-20260925-s3172" for k in RESULTS}
FEED_NAME = "board-feed-20260925T0603Z-s3172.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(data: bytes):
    return json.loads(data.decode("utf-8"))


def dump(path: Path, value) -> bytes:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def copy_exact(src: Path, dst: Path, expected_sha: str) -> bytes:
    data = src.read_bytes()
    if sha(data) != expected_sha:
        raise SystemExit(f"SHA mismatch: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    return data


def archive_members() -> dict[str, bytes]:
    if sha(ARCHIVE.read_bytes()) != ARCHIVE_SHA:
        raise SystemExit("retained evidence archive SHA mismatch")
    wanted = {
        f"probe/{name}.json.gz": f"{name}.json.gz"
        for name in RESULTS
    }
    wanted.update({
        "probe/run.json": "probe-run.json",
        "probe/prepare/run.json": "prepare-run.json",
        **{f"probe/{name}.worker.json": f"{name}.worker.json" for name in RESULTS},
        **{f"probe/{name}.stdout.txt": f"{name}.stdout.txt" for name in RESULTS},
    })
    found = {}
    with tarfile.open(ARCHIVE, "r:gz") as tf:
        for m in tf.getmembers():
            p = PurePosixPath(m.name)
            if p.is_absolute() or ".." in p.parts or not (m.isfile() or m.isdir()):
                raise SystemExit(f"unsafe archive member: {m.name}")
        for member, target in wanted.items():
            m = tf.getmember(member)
            if not m.isfile():
                raise SystemExit(f"archive member is not a regular file: {member}")
            f = tf.extractfile(m)
            if f is None:
                raise SystemExit(f"cannot read archive member: {member}")
            data = f.read()
            (OUT / "raw-evidence" / target).parent.mkdir(parents=True, exist_ok=True)
            (OUT / "raw-evidence" / target).write_bytes(data)
            found[member] = data
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "src/benchmark_board/protocol.py")
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args()

    evidence = archive_members()
    plans = {
        "candidate": ROOT / "results/a/q3-nikolastarx/partial-preload-one-20260925/case_044_multicore_res.json",
        "control": ROOT / "results/a/q3-nikolastarx/pipeline-prefix-static-20260925/case_044_multicore_res.json",
    }
    plan_bytes = {k: p.read_bytes() for k, p in plans.items()}
    if {k: sha(v) for k, v in plan_bytes.items()} != {"candidate": CANDIDATE_PLAN_SHA, "control": CONTROL_PLAN_SHA}:
        raise SystemExit("frozen candidate/control plan hash mismatch")
    baseline_src = ROOT / "results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/receipt-public/artifacts/044-baseline-result.json.gz"
    baseline = baseline_src.read_bytes()
    if sha(baseline) != BASELINE_SHA:
        raise SystemExit("retained official single-core baseline hash mismatch")
    reused_p3_src = ROOT / "results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/receipt-public/artifacts/044-result.json.gz"
    reused_p3 = reused_p3_src.read_bytes()
    if sha(reused_p3) != REUSED_P3_SHA or load_json(gzip.decompress(reused_p3)).get("makespan") != 38024:
        raise SystemExit("retained full-prefix P3 identity mismatch")
    old_feed_path = ROOT / "results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/receipt-public/board-feed-20260925T035741Z-s3172.json"
    old_records = load_json(old_feed_path.read_bytes())["records"]
    old_p3_rows = [r for r in old_records if r.get("problem") == "P3" and r.get("artifacts", {}).get("result", {}).get("sha256") == REUSED_P3_SHA]
    if not old_p3_rows or old_p3_rows[0].get("identity", {}).get("plan_sha256") != CONTROL_PLAN_SHA:
        raise SystemExit("reused full-prefix P3 does not identify the frozen control plan")
    control_algorithm = old_p3_rows[0]
    baseline_result = load_json(gzip.decompress(baseline))
    if baseline_result.get("scene") != "A" or baseline_result.get("num_cores") != 1:
        raise SystemExit("retained baseline is not official single-core A")

    probe = load_json(evidence["probe/run.json"])
    prep = load_json(evidence["probe/prepare/run.json"])
    if probe.get("status") != "complete" or probe.get("source_commit") != SOURCE:
        raise SystemExit("probe receipt status/source mismatch")
    if probe.get("official_code_sha256") != OFFICIAL_SHA or probe.get("manifest_sha256") != "b36ef3ae7b974b139d9f7d5969a27df7868ebfba9d69818d26055bc83bd310a4":
        raise SystemExit("official or manifest identity mismatch")
    if prep.get("status") != "complete" or prep.get("manifest_sha256") != probe.get("manifest_sha256"):
        raise SystemExit("prepare receipt identity/status mismatch")
    if prep.get("counts_started") != {"Step1": 5, "Step2": 5, "Step3": 5, "Task": 1}:
        raise SystemExit("unexpected prepare call ledger")

    workers, outputs, plans_for = {}, {}, {}
    for key, expected in RESULTS.items():
        worker = load_json(evidence[f"probe/{key}.worker.json"])
        raw = evidence[f"probe/{key}.json.gz"]
        result = load_json(gzip.decompress(raw))
        plan_key = "candidate" if key.startswith("candidate-") else "control"
        psha = sha(plan_bytes[plan_key])
        if worker.get("status") != "complete" or worker.get("source_commit") != SOURCE:
            raise SystemExit(f"incomplete/wrong-source worker: {key}")
        if worker.get("result_sha256") != expected or sha(raw) != expected:
            raise SystemExit(f"original compressed result/worker SHA mismatch: {key}")
        if worker.get("plan_sha256") != psha or result.get("num_cores") != 5 or result.get("scene") != "B":
            raise SystemExit(f"plan/result identity mismatch: {key}")
        expected_counts = ({"P3": 1, "P2": 0, "Step1": 5, "Step2": 5, "prepare_Step3": 5, "step3_simulation": 5}
                           if key == "candidate-p3" else
                           {"P3": 0, "P2": 1, "Step1": 5, "Step2": 5, "prepare_Step3": 5, "step3_simulation": 5})
        if worker.get("counts_started") != expected_counts:
            raise SystemExit(f"unexpected scoring call ledger: {key}")
        workers[key], outputs[key], plans_for[key] = worker, result, plan_key

    # Preserve exact plan, baseline, and evaluator output bytes; no metric is rewritten.
    artifact_paths = {}
    for k, data in plan_bytes.items():
        name = f"artifacts/{k}-case_044_multicore_res.json"
        (OUT / name).parent.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_bytes(data)
        artifact_paths[k] = (name, sha(data))
    base_path = "artifacts/044-baseline-result.json.gz"
    (OUT / base_path).parent.mkdir(parents=True, exist_ok=True)
    (OUT / base_path).write_bytes(baseline)
    reused_p3_path = "artifacts/reused-full-prefix-044-p3.json.gz"
    (OUT / reused_p3_path).write_bytes(reused_p3)
    result_paths = {}
    for k in RESULTS:
        name = f"artifacts/{k}.json.gz"
        (OUT / name).write_bytes(evidence[f"probe/{k}.json.gz"])
        result_paths[k] = (name, RESULTS[k])

    # A public projection keeps timing and calls but drops the local admission path.
    phases = probe.get("phases", [])
    control = load_json((RUN / "control.json").read_bytes())
    watchdog = load_json((RUN / "watchdog.json").read_bytes())
    t0 = load_json(Path(str(RUN) + ".T0-preflight.json").read_bytes())
    attempts = {a.get("label"): a for a in control.get("attempts", [])}
    sessions_log = (RUN / "sessions-after.stdout.txt").read_text(encoding="utf-8")
    sessions_err = (RUN / "sessions-after.stderr.txt").read_text(encoding="utf-8")
    if (attempts.get("sessions-after", {}).get("exit_code") != 0
            or attempts.get("stop", {}).get("exit_code") != 0
            or control.get("stop_confirmation") != "confirmed_empty"
            or watchdog.get("status") != "disarmed_by_confirmed_parent"
            or sessions_log != "[colab] No active sessions found on server.\n"
            or sessions_err != ""):
        raise SystemExit("session cleanup is not proven by exact local receipts")
    public_run = {
        "schema": "q3-partial-preload-public-run-v1", "status": probe["status"],
        "source_commit": SOURCE, "controller_commit": CONTROLLER,
        "controller_host_head": "ff6e16ea8fbc2af90417aa045c457f37f6e167d7",
        "package_sha256": PACKAGE_SHA, "source_evidence_sha256": ARCHIVE_SHA,
        "t0_preflight_utc": t0["preflight_utc"],
        "controller_t0_ready_observed_at": "2026-09-25T06:08:27Z",
        "controller_wall_seconds": control.get("wall_seconds"),
        "terminal_state": {"stop_confirmation": control.get("stop_confirmation"),
                           "stop_exit_code": attempts["stop"]["exit_code"],
                           "controller_status": control.get("status"), "watchdog_status": watchdog.get("status"),
                           "sessions_after": {"exit_code": attempts["sessions-after"]["exit_code"],
                                              "stdout": sessions_log.rstrip("\n"), "stderr": sessions_err}},
        "controller_script_sha256": t0["evidence"]["scripts/q3_partial_colab_control.py"]["sha256"],
        "job_script_sha256": t0["evidence"]["scripts/q3_partial_colab_job.py"]["sha256"],
        "watchdog_script_sha256": t0["evidence"]["scripts/q3_partial_colab_watchdog.py"]["sha256"],
        "manifest_sha256": probe["manifest_sha256"], "official_code_sha256": OFFICIAL_SHA,
        "started_at": probe["started_at"], "finished_at": probe["finished_at"],
        "budget": probe["budget"], "phase_ledger": [
            {k: p.get(k) for k in ("phase", "wall_seconds", "exit_code", "stop_reason")}
            for p in phases
        ],
        "prepare_counts": prep["counts_started"],
        "score_counts": {k: workers[k]["counts_started"] for k in RESULTS},
        "candidate_M": probe["candidate_M"], "control_M": probe["control_M"],
        "candidate_G": probe["candidate_G"], "control_G": probe["control_G"],
        "solver_wall_seconds": None,
        "timing_scope": probe.get("timing_scope"),
        "environment": probe.get("environment"),
        "privacy_note": "Local admission reference omitted; original run receipts remain in the retained evidence archive.",
    }
    run_bytes = dump(OUT / "artifacts/run-public.json", public_run)
    run_sha = sha(run_bytes)

    graph_sha = probe["source_input_sha256"]["data/raw/a/official/data/case_044.json"]
    config_sha = probe["source_input_sha256"]["data/raw/a/official/data/config.txt"]
    if graph_sha != GRAPH_SHA or config_sha != CONFIG_SHA:
        raise SystemExit("probe graph/config SHA differs from frozen input identities")
    expected_ids = {
        "candidate-p3": ("P3", "multicore_cut_evaluate_problem_3.evaluate_problem_3"),
        "candidate-p2": ("P2", "multicore_cut_evaluate_problem_2.evaluate_scene_b"),
        "control-p2": ("P2", "multicore_cut_evaluate_problem_2.evaluate_scene_b"),
    }
    missing = {
        "provenance.environment.cpu": "Colab receipt records a 2-vCPU count but not CPU model.",
        "provenance.environment.ram_bytes": "Total VM RAM was not retained in the execution receipts.",
        "provenance.environment.threads": "Thread count was not retained.",
        "provenance.measurement.seed": "This deterministic fixed plan records no random seed.",
        "provenance.measurement.cold_start": "Cold/warm process and filesystem cache state was not recorded.",
        "provenance.measurement.solver_scope": "Solver start-to-finish wall time was not measured; preparation diagnostics are not solver wall time.",
        "timing.solver_includes_evaluation": "Solver wall time was not measured, so evaluator inclusion is unknown.",
        "provenance.solver.selected_algorithm_id": "One frozen plan was evaluated; no per-input portfolio selection occurred.",
        "provenance.solver.selected_solver_commit": "One frozen plan was evaluated; no per-input portfolio selection occurred.",
    }
    records = []
    for key in RESULTS:
        worker, result = workers[key], outputs[key]
        plan_key = plans_for[key]
        plan_path, plan_hash = artifact_paths[plan_key]
        result_path, result_hash = result_paths[key]
        problem, entrypoint = expected_ids[key]
        score_stdout = load_json(evidence[f"probe/{key}.stdout.txt"])
        eval_seconds = score_stdout["read_evaluate_write_seconds"]
        cache = result.get("cache_stats")
        is_control = key == "control-p2"
        algorithm = control_algorithm if is_control else None
        record = {
            "attempt_id": ATTEMPTS[key], "revision": 1,
            "run_id": "q3-partial-preload-linux-20260925-s3172",
            "algorithm_id": algorithm["algorithm_id"] if is_control else "q3-partial-preload",
            "algorithm_name": algorithm["algorithm_name"] if is_control else "Q3 partial-preload mechanism candidate",
            "variant": algorithm["variant"] if is_control else "one-frozen-partial-preload-plan-044-k5",
            "solver_commit": algorithm["solver_commit"] if is_control else SOURCE,
            "parameters": algorithm["parameters"] if is_control else {"changed_core": 2, "head_count": 15, "candidate_count": 1,
                           "max_workers": 1, "retries": 0, "same_frozen_plan": True},
            "problem": problem, "case_id": "044", "cores": 5, "status": "ok",
            "runtime_id": "colab-cpu-standard-managed-image", "observed_at": worker["finished_at"],
            "metrics": {
                "makespan_cycles": result["makespan"], "solver_wall_seconds": None,
                "evaluation_wall_seconds": eval_seconds,
                "ddr_bytes": result["data_movement_bytes"]["scheduled_copy_bytes"],
                "extra_ddr_bytes": result["data_movement_bytes"]["added_copy_bytes"],
                "spill_bytes": result["data_movement_bytes"]["spill_added_copy_bytes"],
                "cache_hit_rate": cache["hit_rate"] if cache is not None else None,
            },
            "evaluator": {"route": "E0", "commit": SOURCE, "entrypoint": entrypoint},
            "identity": {"graph_sha256": graph_sha, "config_sha256": config_sha,
                         "official_sha256": OFFICIAL_SHA, "plan_sha256": plan_hash},
            "artifacts": {
                "plan": {"path": f"results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/receipt-public/{plan_path}", "sha256": plan_hash},
                "result": {"path": f"results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/receipt-public/{result_path}", "sha256": result_hash},
                "run": {"path": "results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/receipt-public/artifacts/run-public.json", "sha256": run_sha},
            },
            "baseline": {
                "graph_sha256": graph_sha, "config_sha256": config_sha,
                "official_sha256": OFFICIAL_SHA, "route": "E0",
                "entrypoint": "singlecore_evaluate.evaluate_singlecore",
                "result": {"path": "results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/receipt-public/artifacts/044-baseline-result.json.gz", "sha256": BASELINE_SHA},
            },
            "timing": {"solver_includes_evaluation": None,
                       "evaluation_precision": "official evaluator read/evaluate/write wall time from worker output",
                       "utc": "UTC timestamps retained in original worker receipts"},
            "provenance": {
                "producer_session": "nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc", "task_url": "https://github.com/huaweibei123/huaweicup2026/issues/51",
                "solver": {**algorithm["provenance"]["solver"], "method": "One fixed offline-constructed full-prefix control plan; this receipt is its new P2 E0 evaluation, paired with the retained earlier P3 result."} if is_control else {
                    "source": {"repo": "huaweibei123/huaweicup2026", "commit": SOURCE,
                               "path": "results/a/q3-nikolastarx/partial-preload-one-20260925/build.py", "entrypoint": "python results/a/q3-nikolastarx/partial-preload-one-20260925/build.py"},
                    "authors": ["nikolastarx"],
                    "method": "One statically frozen partial-preload plan; one P3 and its conditional same-plan P2 E0 evaluation; mechanism experiment only.",
                    "references": [], "upstream": [], "selected_algorithm_id": None, "selected_solver_commit": None,
                },
                "runner": {
                    "source": {"repo": "huaweibei123/huaweicup2026", "commit": CONTROLLER,
                               "path": "scripts/q3_partial_colab_control.py", "entrypoint": "q3_partial_colab_control.py"},
                    "argv": ["python3 scripts/q3_partial_colab_control.py <frozen transport.zip> <new output> --package-sha256 <sha256> --admission-ref <redacted> --cli <colab>"],
                    "working_directory": ".",
                },
                "environment": {"os": "Linux 6.6.122+ x86_64; managed Colab CPU Standard image",
                                 "cpu": None, "gpu": "none", "ram_bytes": None, "python": "CPython 3.12.13",
                                 "dependencies": "uv.lock sha256:7b03fee57044ac272d8895533cbdca6d70a29d2da955f98a5552e72ef944fdc4",
                                 "threads": None, "workers": 1,
                                 "peak_rss_bytes": score_stdout.get("max_rss_bytes")},
                "measurement": {
                    "started_at": worker["started_at"], "finished_at": worker["finished_at"],
                    "seed": None, "repeat_index": 0, "cold_start": None,
                    "solver_scope": None,
                    "evaluation_scope": f"One official {problem} E0 evaluation; {eval_seconds:.9f}s evaluator read/evaluate/write. This is not solver wall time.",
                    "budget": {"wall_seconds": 90, "candidate_limit": 1,
                               "stop_reason": f"One admitted {key} E0 phase completed; automatic retries=0."},
                    "calls": {"solver": 0, "E0": 1, "E1": 0, "E2": 0},
                    "offline_costs": "No training. One separately budgeted phase prepared official Task graphs for the already frozen candidate; its 7.9257s diagnostic wall is not solver wall time.",
                    "failure": None,
                },
                "missing_reasons": missing,
            },
            "notes": [
                "One mechanism cell only; not a full-algorithm or full-500 score. solver_wall_seconds is null/unknown.",
                f"Original compressed E0 bytes are preserved unchanged; worker result_sha256 verified as {result_hash}.",
                f"Phase calls: prepare Step1/Step2/Step3=5/5/5; {key} score counts are copied from its original worker receipt. Batch totals: prepare and each score phase were within the frozen 1+3 E0 budget; retries=0.",
                "Host/phase diagnostic wall times are not reported as solver wall time.",
                "Independent audit is retained at results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/INDEPENDENT_AUDIT.json; it checked identities and FIFO/operation sets, but does not establish full causal decomposition.",
                f"The old full-prefix P3 result M=38024 (SHA {REUSED_P3_SHA}) is exact reused evidence for the control plan; no new P3 attempt is claimed. Same-plan control G=1.0.",
                "Both new P2 records have the same graph/config/official evaluator identities as their plan and the retained official single-core A baseline.",
            ],
            "source_url": algorithm.get("source_url") if is_control else f"https://github.com/huaweibei123/huaweicup2026/blob/{SOURCE}/{plans[plan_key].relative_to(ROOT).as_posix()}",
        }
        if key == "candidate-p3":
            pair_path, pair_hash = result_paths["candidate-p2"]
            record["cache_pair"] = {
                "graph_sha256": graph_sha, "config_sha256": config_sha, "official_sha256": OFFICIAL_SHA,
                "plan_sha256": plan_hash, "cores": 5, "route": "E0",
                "result": {"path": f"results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/receipt-public/{pair_path}", "sha256": pair_hash},
            }
        records.append(record)

    feed = {"schema_version": 1, "submission_version": 1, "records": records}
    feed_path = OUT / FEED_NAME
    dump(feed_path, feed)
    protocol = args.protocol.resolve()
    if not protocol.is_file():
        raise SystemExit(f"protocol script not found: {protocol}")
    cmd = [sys.executable, str(protocol), str(feed_path.relative_to(args.repo.resolve())), "--submission", "--repo", str(args.repo.resolve())]
    proc = subprocess.run(cmd, cwd=args.repo.resolve(), capture_output=True, text=True)
    preflight = {"command": cmd, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    dump(OUT / "protocol-preflight.json", preflight)
    eligible = None
    try:
        eligible = json.loads(proc.stdout).get("eligible")
    except Exception:
        pass
    delta = 38024 - 37060
    report = f"""# Q3 partial-preload Linux mechanism receipt\n\nThis receipt contains exactly three new official E0 attempts for case 044, five cores: candidate P3, same-plan candidate P2, and control-plan P2. It is a mechanism experiment, not a full-500 result.\n\n- Candidate P3 Makespan: **37060** cycles; reused full-prefix P3: **38024** cycles, a reduction of **{delta} ({delta / 38024 * 100:.4f}%)**. Candidate G = 37060/37060 = **1.0**; control G = 38024/38024 = **1.0**. The prior P3 is exact reused evidence (SHA `{REUSED_P3_SHA}`) and is not represented as a new attempt.\n- All three new results report 140800 added bytes and 0 spill bytes. Candidate P3 has 11 hits / 182 accesses, 11264 hit bytes, 1012064 miss bytes, byte hit rate {outputs['candidate-p3']['cache_stats']['hit_rate']:.10f}; same-plan P2 provides the paired non-cache result.\n- `solver_wall_seconds` is `null`/unknown. The 7.9257 s prepare diagnostic and score/host diagnostics are not solver wall time. `full500=false`.\n- One prepare plus three E0 calls were made; no E1/E2, retry, or new full-prefix P3 call. Phase and per-core evidence remain in raw receipts.\n- Candidate plan SHA: `{CANDIDATE_PLAN_SHA}`. Control plan SHA: `{CONTROL_PLAN_SHA}`. The retained old P3 result uses the same control plan. Official single-core baseline SHA: `{BASELINE_SHA}`. Source commit: `{SOURCE}`; controller commit: `{CONTROLLER}`; host checkout HEAD was `ff6e16ea8fbc2af90417aa045c457f37f6e167d7`.\n- T0/guard READY was observed at `2026-09-25T06:08:27Z`; exact UTC start is not recorded by the controller (its deadline is monotonic). Preflight receipt was captured at `{t0['preflight_utc']}`. Controller wall {control.get('wall_seconds')} s; stop `{control.get('stop_confirmation')}`, watchdog `{watchdog.get('status')}`, and fresh sessions-after exact empty rc 0.\n- Evidence archive SHA: `{ARCHIVE_SHA}`; transport package SHA: `{PACKAGE_SHA}`. Original result gzip bytes were copied without recompression and verified against each worker `result_sha256`.\n- Independent identity/FIFO audit: `results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/INDEPENDENT_AUDIT.json`. It reports timing deltas consistent with earlier downstream starts; it does not prove complete causal decomposition.\n- Protocol preflight: exit `{proc.returncode}`, eligible `{eligible}`. See `protocol-preflight.json` for the actual command and output.\n\nThe exporter copies exact source bytes, verifies archive/member safety and hashes, generates public run projections without the local admission path, runs the read-only submission preflight, and records its real result. It does not execute a solver or evaluator.\n"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    sums = {str(p.relative_to(OUT)): sha(p.read_bytes()) for p in sorted(OUT.rglob("*"))
            if p.is_file() and p.name != "SHA256SUMS.json"}
    dump(OUT / "SHA256SUMS.json", sums)
    print(json.dumps({"feed": str(feed_path), "records": len(records), "protocol_exit_code": proc.returncode,
                      "eligible": eligible, "files_hashed": len(sums)}, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
