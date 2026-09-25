"""Strict final-selector adapter for the pinned, serial feedback batch runner.

This wrapper does not change the solver or call E0 itself.  A completed P3
batch is not a complete paired P2/P3 cache-benefit benchmark when the selected
plan has no same-plan P2 result; such cells are explicitly marked unpaired.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

from . import feedback_benchmark as base

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = ROOT / "results/a/q3-nikolastarx/r9f-final-full500-20260926/identity-proposed.json"
PAIR_MANIFEST = ROOT / "results/a/q3-nikolastarx/forest-cachepair-delta-20260925/manifest.json"
PAIR_RUN = ROOT / "results/a/q3-nikolastarx/forest-cachepair-delta-20260925/20260924T2205Z-s3172"
NON_SCORED = {"unsupported", "duplicate", "rejected", "bound_pruned"}
FIFTH_STATUSES = {"skip", "unsupported", "duplicate", "bound_pruned", "p3_rejected",
                  "m3_not_better", "p2_rejected", "paired_gate_rejected", "accepted"}


def checked_ref(folder: Path, ref: dict) -> Path:
    if set(ref) != {"path", "sha256"} or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]):
        raise ValueError("invalid artifact reference")
    target = (folder / "evidence" / ref["path"]).resolve()
    if not target.is_relative_to((folder / "evidence").resolve()) or base.digest(target) != ref["sha256"]:
        raise ValueError("candidate artifact path/hash differs")
    return target


def artifact_pair(folder: Path, refs: dict, *, problem: int, cores: int, plan_sha: str | None = None):
    if set(refs) != {"plan", "result"}:
        raise ValueError("expected plan and result artifacts")
    plan_path = checked_ref(folder, refs["plan"])
    result_path = checked_ref(folder, refs["result"])
    plan, result = base.read(plan_path), base.read(result_path)
    if (set(plan) != {"node_to_subgraph", "core_schedules"} or
            result.get("scene") != "B" or
            (problem == 3 and (type(result.get("problem")) is not int or result["problem"] != 3)) or
            (problem == 2 and result.get("problem") not in (None, 2)) or
            result.get("num_cores") != cores or
            (result.get("cache_mode") == "read_only") != (problem == 3) or
            (problem == 2 and "cache_stats" in result)):
        raise ValueError("candidate plan/result official identity differs")
    if plan_sha is not None and refs["plan"]["sha256"] != plan_sha:
        raise ValueError("P2 does not score the exact P3 plan bytes")
    makespan = result.get("makespan")
    if type(makespan) is not int or makespan <= 0:
        raise ValueError("official Makespan must be positive integer cycles")
    return makespan, refs["plan"]["sha256"], refs["result"]["sha256"]


def validate_result(folder: Path, job: dict, root: Path = ROOT):
    """Audit the Forest and fifth-core decisions from immutable E0 artifacts."""
    plan_path = folder / f"case_{job['case_id']}_multicore_res.json"
    result_path = folder / "evidence/result.json.gz"
    receipt_path = folder / "evidence/receipt.json"
    result, receipt = base.read(result_path), base.read(receipt_path)
    plan = base.read(plan_path)
    if set(plan) != {"node_to_subgraph", "core_schedules"}:
        raise ValueError("submission has extra/missing fields")
    if (result.get("scene") != "B" or result.get("problem") != 3 or
            result.get("cache_mode") != "read_only" or result.get("num_cores") != job["cores"]):
        raise ValueError("final P3 identity differs")
    expected = {"plan_sha256": base.digest(plan_path), "result_sha256": base.digest(result_path),
                "graph_sha256": base.digest(root / f"data/raw/a/official/data/case_{job['case_id']}.json"),
                "config_sha256": base.digest(root / "data/raw/a/official/data/config.txt")}
    if any(receipt.get(k) != v for k, v in expected.items()) or receipt.get("makespan") != result.get("makespan"):
        raise ValueError("final receipt hash/Makespan identity differs")
    if type(result.get("makespan")) is not int or result["makespan"] <= 0:
        raise ValueError("invalid final Makespan")
    ledger = base.read(folder / "evidence/evaluations.json")
    n3 = sum(e.get("phase") == "p3" for e in ledger)
    n2 = sum(e.get("phase") == "p2" for e in ledger)
    if (not isinstance(ledger, list) or len(ledger) != receipt.get("official_e0_calls") or
            n3 != receipt.get("official_p3_calls") or n2 != receipt.get("official_p2_calls") or
            n3 > (4 if job["cores"] == 5 else 3) or n2 > (2 if job["cores"] == 5 else 0) or
            len(ledger) > job["e0_call_limit"] or not 1 <= n3 <= 4 or
            [e.get("ordinal") for e in ledger] != list(range(len(ledger))) or
            any(e.get("phase") not in {"p2", "p3"} or e.get("status") != "ok"
                or not re.fullmatch(r"[0-9a-f]{64}", e.get("plan_sha256", "")) for e in ledger)):
        raise ValueError("per-phase E0 ledger/cap differs or first E0 anomaly occurred")
    for e in ledger:
        raw = folder / "evidence" / f"evaluated-plan-{e['ordinal']}-{e['phase']}.json"
        if base.digest(raw) != e["plan_sha256"]:
            raise ValueError("pre-call evaluated plan differs from ledger")
    forest = receipt.get("candidates")
    if not isinstance(forest, list) or not forest or forest[0].get("name") != "seed":
        raise ValueError("fresh Forest seed missing")
    scored = []
    for candidate in forest[:-1] if forest[-1].get("name") == "component_contiguous_extra_core" else forest:
        status = candidate.get("status")
        if status == "ok":
            m, sha, result_sha = artifact_pair(folder, candidate["artifacts"], problem=3, cores=job["cores"])
            if m != candidate.get("makespan"):
                raise ValueError("Forest candidate score differs")
            scored.append((m, sha, result_sha, candidate.get("strategy")))
        elif status not in NON_SCORED or candidate.get("makespan") is not None:
            raise ValueError("unexpected Forest candidate status")
        elif status == "bound_pruned":
            lower = candidate.get("certified_lower_bound_cycles")
            if not scored or type(lower) is not int or lower < min(x[0] for x in scored):
                raise ValueError("Forest bound cannot certify a prune")
            unscored = candidate.get("unscored_plan")
            raw = json.dumps(unscored, separators=(",", ":")).encode() + b"\n"
            if hashlib.sha256(raw).hexdigest() != candidate.get("unscored_plan_sha256"):
                raise ValueError("Forest unscored plan hash differs")
    if not scored or not 1 <= len(scored) <= 3:
        raise ValueError("Forest scored set invalid")
    p3_plan_shas = [e["plan_sha256"] for e in ledger if e["phase"] == "p3"]
    if any(value[1] not in p3_plan_shas for value in scored):
        raise ValueError("Forest candidate artifact has no matching P3 call")
    incumbent = min(scored, key=lambda value: value[0])
    extra = forest[-1] if forest[-1].get("name") == "component_contiguous_extra_core" else None
    policy = receipt.get("selection", {}).get("fifth_core_policy", {})
    status = policy.get("status")
    if status not in FIFTH_STATUSES or (extra is None) != (status == "skip"):
        # Unsupported K5 records are present; only K1-K4 skip without record.
        if not (status == "unsupported" and extra is not None):
            raise ValueError("fifth-core policy/record missing or inconsistent")
    if extra is not None and extra.get("status") != status:
        raise ValueError("fifth-core record status differs")
    if job["cores"] != 5 and (status != "skip" or extra is not None):
        raise ValueError("fifth-core policy ran below K5")
    if status == "bound_pruned":
        lower = extra.get("certified_lower_bound_cycles")
        ref = extra.get("proposal_plan")
        if (type(lower) is not int or lower < incumbent[0] or not isinstance(ref, dict) or
                set(ref) != {"path", "sha256"} or checked_ref(folder, ref).name != "fifth-core-proposal.json" or
                ref["sha256"] != extra.get("unscored_plan_sha256")):
            raise ValueError("fifth-core bound cannot certify a prune")
    if n3 != len(scored) + int(status in {"p3_rejected", "m3_not_better", "p2_rejected",
                                      "paired_gate_rejected", "accepted"}):
        raise ValueError("P3 ledger count differs from scored candidates")
    selected = incumbent
    paired = {"status": "missing_same_plan_p2", "reason": "selected plan lacks fresh paired P2"}
    if status in {"m3_not_better", "p2_rejected", "paired_gate_rejected", "accepted"}:
        if extra is None or not isinstance(extra.get("p3"), dict):
            raise ValueError("scored fifth-core artifact missing")
        new_m3, new_sha, new_result_sha = artifact_pair(folder, extra["p3"]["artifacts"],
                                                         problem=3, cores=job["cores"])
        if new_m3 != extra["p3"].get("makespan"):
            raise ValueError("fifth-core P3 score differs")
        if new_sha not in p3_plan_shas:
            raise ValueError("fifth-core P3 artifact has no matching E0 call")
        if status == "m3_not_better":
            if new_m3 < incumbent[0] or n2:
                raise ValueError("non-improvement incorrectly skipped paired gate")
        elif new_m3 >= incumbent[0]:
            raise ValueError("paired gate ran without strict P3 improvement")
        if status in {"paired_gate_rejected", "accepted"}:
            if n2 != 2 or [e["phase"] for e in ledger[-2:]] != ["p2", "p2"]:
                raise ValueError("paired P2 sequence missing")
            old_m2, old_sha, _ = artifact_pair(folder, extra["incumbent_p2"]["artifacts"],
                                               problem=2, cores=job["cores"], plan_sha=incumbent[1])
            new_m2, _, _ = artifact_pair(folder, extra["fifth_core_p2"]["artifacts"],
                                         problem=2, cores=job["cores"], plan_sha=new_sha)
            if [e["plan_sha256"] for e in ledger[-2:]] != [old_sha, new_sha]:
                raise ValueError("paired P2 call order/plan differs")
            if old_m2 != extra["incumbent_p2"]["makespan"] or new_m2 != extra["fifth_core_p2"]["makespan"]:
                raise ValueError("paired P2 score differs")
            eligible = new_m2 <= old_m2 and new_m2 * incumbent[0] >= old_m2 * new_m3
            if eligible != (status == "accepted") or extra.get("m2_nonworse") != (new_m2 <= old_m2) or extra.get("g_nonworse") != (new_m2 * incumbent[0] >= old_m2 * new_m3):
                raise ValueError("paired acceptance decision differs")
            if status == "accepted":
                selected = (new_m3, new_sha, new_result_sha, extra["metadata"]["rule"])
                paired = {"status": "available_internal", "p2_makespan": new_m2,
                          "p3_makespan": new_m3, "plan_sha256": new_sha}
            else:
                paired = {"status": "available_internal", "p2_makespan": old_m2,
                          "p3_makespan": incumbent[0], "plan_sha256": incumbent[1]}
    if status not in {"paired_gate_rejected", "accepted", "p2_rejected"} and n2:
        raise ValueError("P2 occurred without a strict P3 improvement")
    if selected[:3] != (result["makespan"], expected["plan_sha256"], expected["result_sha256"]) or selected[3] != receipt.get("strategy"):
        raise ValueError("published plan/result not selected by frozen policy")
    return result, {**receipt, "runner_paired_audit": paired}, {
        "plan": base.artifact(plan_path, root), "result": base.artifact(result_path, root),
        "trace": base.artifact(receipt_path, root)}


def audited_control(manifest, job, receipt, root=ROOT, run=PAIR_RUN):
    """Reuse archived P2 only for exactly identical selected plan bytes/inputs.

    Existing paired controls were produced by a separate frozen Forest run.
    Their original byte artifacts and the 24 new P2 run receipts are checked;
    historical scores never influence solver selection.
    """
    paired = receipt["runner_paired_audit"]
    if paired["status"] == "available_internal":
        if paired["plan_sha256"] != receipt["plan_sha256"] or paired["p3_makespan"] != receipt["makespan"]:
            raise ValueError("internal selected P2/P3 pair differs")
        return paired
    key = f"{job['case_id']}-k{job['cores']}"
    matching = [r for r in manifest["records"] if (r["case_id"], r["cores"]) ==
                (job["case_id"], job["cores"])]
    if len(matching) != 1:
        raise ValueError("frozen control map lacks unique coordinate")
    record = matching[0]
    if (record["forest_plan"]["sha256"] != receipt["plan_sha256"] or
            record["graph_sha256"] != receipt["graph_sha256"] or
            record["config_sha256"] != receipt["config_sha256"] or
            record["official_sha256"] != manifest["sources"]["official_code_sha256"]):
        raise ValueError("archived same-plan P2 control cannot pair with current output")
    if record["action"] == "reuse_existing_p2":
        ref = record["reused_p2"]
        if not record["same_plan_bytes"] or ref["source_plan_sha256"] != receipt["plan_sha256"]:
            raise ValueError("historical P2 input plan differs")
        raw = base.git_bytes(root, manifest["sources"]["p2_result_artifact_commit"], ref["path"])
        expected_sha = ref["sha256"]
        origin = {"kind": "archived_reuse", "commit": manifest["sources"]["p2_result_artifact_commit"],
                  "path": ref["path"]}
    elif record["action"] == "requires_new_p2_e0":
        cell = run / "cells" / key
        run_receipt = base.read(cell / "run.json")
        if (run_receipt["status"] != "ok" or run_receipt["returncode"] != 0 or
                run_receipt["plan_sha256"] != receipt["plan_sha256"] or
                run_receipt["graph_sha256"] != receipt["graph_sha256"] or
                base.digest(cell / "plan.json") != receipt["plan_sha256"]):
            raise ValueError("archived newly scored P2 input identity differs")
        raw = (cell / "result.json.gz").read_bytes()
        expected_sha = run_receipt["result_sha256"]
        origin = {"kind": "archived_new_p2", "path": (cell / "result.json.gz").relative_to(root).as_posix()}
    else:
        raise ValueError("unknown paired control source")
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("archived P2 byte hash differs")
    p2 = json.loads(gzip.decompress(raw))
    if (p2.get("scene") != "B" or p2.get("problem") not in (None, 2) or
            p2.get("num_cores") != job["cores"] or "cache_mode" in p2 or
            "cache_stats" in p2 or type(p2.get("makespan")) is not int or
            p2["makespan"] <= 0):
        raise ValueError("archived P2 official result identity differs")
    if record["action"] == "reuse_existing_p2" and p2["makespan"] != ref["historical_no_l2_makespan"]:
        raise ValueError("historical P2 score differs")
    return {"status": "available_verified_reuse", "p2_makespan": p2["makespan"],
            "p3_makespan": receipt["makespan"], "plan_sha256": receipt["plan_sha256"],
            "p2_result_sha256": expected_sha, "source": origin}


def validate_variable_caps(manifest):
    base.validate_manifest(manifest)
    if manifest["solver_module"] != "src.q3.fifth_core_final_solve":
        raise ValueError("wrong fixed solver entrypoint")
    for job in manifest["jobs"]:
        expected = 6 if job["cores"] == 5 else 3
        if job["e0_call_limit"] != expected:
            raise ValueError("per-cell E0 reservation must be 3 for K1-K4, 6 for K5")
    if manifest["budget"]["max_e0_calls"] != 1800:
        raise ValueError("full500 worst-case E0 cap must be 1800")


def verify_pinned_source(manifest, cases, root, *, runner_commit, identity_path=IDENTITY):
    identity = base.read(identity_path)
    if manifest["solver_commit"] != identity["solver_commit"] or manifest["solver_module"] != identity["solver_module"]:
        raise ValueError("solver source does not match frozen identity")
    official, hashes = base.verify_source(runner_commit, cases, root)
    if official != identity["official_code_hash"]:
        raise ValueError("official code identity changed")
    for name, expected in identity["source_files_sha256"].items():
        path = root / name
        if base.digest(path) != expected or hashlib.sha256(base.git_bytes(root, manifest["solver_commit"], name)).hexdigest() != expected:
            raise ValueError("frozen solver dependency changed: " + name)
    if base.digest(root / "data/raw/a/official/data/config.txt") != identity["config_sha256"]:
        raise ValueError("fixed config changed")
    for case in cases:
        if base.digest(root / f"data/raw/a/official/data/case_{case}.json") != identity["case_json_sha256"][case]:
            raise ValueError("fixed graph changed: " + case)
    return official, hashes


def execute(manifest, output, *, continuing=False, root=ROOT, runner_commit, identity_path=IDENTITY):
    """Reuse established child supervision and budget ledger with strict audit."""
    validate_variable_caps(manifest)
    control_bytes = PAIR_MANIFEST.read_bytes()
    if base.git_bytes(root, runner_commit, PAIR_MANIFEST.relative_to(root).as_posix()) != control_bytes:
        raise ValueError("archived pair-control manifest differs from pinned runner commit")
    control = json.loads(control_bytes)
    if control.get("counts", {}).get("coordinates") != 500 or len(control.get("records", [])) != 500:
        raise ValueError("incomplete original Forest paired control map")
    if continuing:
        prior = base.read(Path(output) / "batch.json")
        previous_argv = prior["stages"][0].get("runner_argv", [])
        if previous_argv != ["python", "-m", "src.q3.fifth_core_full500_runner",
                             "--runner-commit", runner_commit]:
            raise ValueError("continuation cannot change pinned runner commit")
    original_source, original_result = base.verify_manifest_source, base.validate_result
    try:
        base.verify_manifest_source = lambda m, cases, checkout: verify_pinned_source(
            m, cases, checkout, runner_commit=runner_commit, identity_path=identity_path)
        def validate_and_pair(folder, job, checkout):
            result, receipt, refs = validate_result(folder, job, checkout)
            receipt["runner_paired_audit"] = audited_control(control, job, receipt, checkout)
            return result, receipt, refs
        base.validate_result = validate_and_pair
        batch = base.execute(manifest, output, continuing, root, runner_argv=[
            "python", "-m", "src.q3.fifth_core_full500_runner", "--runner-commit", runner_commit])
        if batch["status"] == "stage_complete" and len(batch["records"]) == 500:
            coords = {(r["case_id"], r["cores"]) for r in batch["records"]}
            expected = {(f"{i:03}", k) for i in range(1, 101) for k in range(1, 6)}
            if coords == expected and all(r["status"] == "ok" for r in batch["records"]):
                by_core = {str(k): sum(r["solver_receipt"]["runner_paired_audit"]["p2_makespan"] /
                                       r["solver_receipt"]["runner_paired_audit"]["p3_makespan"]
                                       for r in batch["records"] if r["cores"] == k) / 100 for k in range(1, 6)}
                batch["full500_verified"] = {"cells": 500, "paired_g_mean_by_core": by_core,
                                             "scope": "same selected plan, official P2/P3 bytes; archived P2 reuse only after exact plan/input identity"}
                base.write(Path(output) / "batch.json", batch)
        return batch
    finally:
        base.verify_manifest_source, base.validate_result = original_source, original_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--runner-commit", required=True)
    parser.add_argument("--continue", action="store_true", dest="continuing")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.runner_commit):
        parser.error("runner commit must be a full SHA")
    batch = execute(base.read(args.manifest), args.output, continuing=args.continuing,
                    runner_commit=args.runner_commit)
    print(json.dumps({"status": batch["status"], "attempts": len(batch["records"]),
                      "e0_budget_used": batch["e0_budget_used"]}))
    return 0 if batch["status"] == "stage_complete" else 1


if __name__ == "__main__":
    sys.exit(main())
