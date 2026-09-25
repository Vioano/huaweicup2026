#!/usr/bin/env python3
"""Create a revision-2 feed by attaching already-existing official baselines."""
import copy
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(subprocess.check_output(["git", "-C", str(HERE), "rev-parse", "--show-toplevel"], text=True).strip())
BASE = HERE / "baseline"
OUT = HERE / "board-feed-20260925T-revision2-s3172.json"
CASES = {
    "044": {
        "attempt_id": "nikolastarx-pipeline-capacity-044-k5-20260925-s3172",
        "input": ROOT / "results/a/q3-nikolastarx/pipeline-capacity-two-shot-20260925/board-feed-20260925T004004Z-s3172.json",
        "target_commit": "da1c9e86f9353ad4ca1bb3b8c720cef9b5043b49",
        "target_blob": "2b5909f5efc50655a1d4d0b2a1a0ae61d00275d3",
        "graph": "9abd4468a4be365e384de47431ac914ee44fd6e7b6221dffc584561f388cd57e",
        "makespan": 154407,
        "sha256": "73f1d15fdea4f706b22099d2339a0e74a76c4114a68672077a98a8e15faa913c",
        "source_commit": "19bebf35205d23fdd832781540f8879da52eeb62",
        "source_feed": "results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/board-feed-s05-revision2.json",
        "source_artifact": "results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/baseline/044/result.json.gz",
    },
    "046": {
        "attempt_id": "nikolastarx-pipeline-capacity-046-k5-20260925-s3172",
        "input": ROOT / "results/a/q3-nikolastarx/pipeline-capacity-two-shot-20260925/board-feed-20260925T004004Z-s3172.json",
        "target_commit": "da1c9e86f9353ad4ca1bb3b8c720cef9b5043b49",
        "target_blob": "2b5909f5efc50655a1d4d0b2a1a0ae61d00275d3",
        "graph": "1917fbb2bfe1141fd8dc4bdac6119dd44014df9a13eb18faa3e55f25bcc91659",
        "makespan": 276455,
        "sha256": "d34869c92f2f414dfe9c6f1bf715e0c26f4f2438c8f8cb4840868b9199b6997f",
        "source_commit": "830542ecba075af269cedce22009695cf6503faa",
        "source_feed": "results/a/q3-nikolastarx/expanded-full500-20260925-s59/20260924T1837Z-s59ee/board-feed-500-with-baselines.json",
        "source_artifact": "results/a/q3-nikolastarx/expanded-full500-20260925-s59/20260924T1837Z-s59ee/baseline/046/result.json.gz",
    },
    "097": {
        "attempt_id": "nikolastarx-leaf-tile-097-k1-20260925-s3172",
        "input": ROOT / "results/a/q3-nikolastarx/leaf-tile-097-one-shot-20260925/board-feed-20260925T001030Z-s3172.json",
        "target_commit": "8a7052d35090516b8dd1dcea59cbcf8cac11ca47",
        "target_blob": "32344a56bc01f46d5d80fc1ad5e1d66f36da0a5c",
        "graph": "7dc5c8ebf92052dbdd1bf59794a8fcef74e3ab3c59d5f0b4e753bf38a741ffaf",
        "makespan": 11491509,
        "sha256": "bfd1fddfe03ac16242562d8849fc9e21f82a179ee1b25c13d7b21126888af534",
        "source_commit": "19bebf35205d23fdd832781540f8879da52eeb62",
        "source_feed": "results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/board-feed-s10-revision2.json",
        "source_artifact": "results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/baseline/097/result.json.gz",
    },
}
CONFIG = "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9"
OFFICIAL = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(path):
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


records = []
checks = []
for case, spec in CASES.items():
    if git_blob(spec["input"]) != spec["target_blob"]:
        raise SystemExit(f"fixed source feed bytes differ for {case}")
    original = json.loads(spec["input"].read_text())
    matches = [r for r in original["records"] if r["attempt_id"] == spec["attempt_id"]]
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one source attempt for {case}")
    old = matches[0]
    if old["revision"] != 1 or old.get("baseline") is not None:
        raise SystemExit(f"unexpected source revision/baseline for {case}")
    if old["identity"]["graph_sha256"] != spec["graph"] or old["identity"]["config_sha256"] != CONFIG or old["identity"]["official_sha256"] != OFFICIAL:
        raise SystemExit(f"source identity mismatch for {case}")

    raw = (BASE / f"{case}-result.json.gz").read_bytes()
    actual_sha = sha(raw)
    if actual_sha != spec["sha256"]:
        raise SystemExit(f"baseline byte hash mismatch for {case}")
    result = json.loads(gzip.decompress(raw))
    if result.get("scene") != "A" or result.get("num_cores") != 1 or result.get("makespan") != spec["makespan"]:
        raise SystemExit(f"baseline payload mismatch for {case}")

    revised = copy.deepcopy(old)
    revised["revision"] = 2
    revised["baseline"] = {
        "graph_sha256": spec["graph"], "config_sha256": CONFIG,
        "official_sha256": OFFICIAL, "route": "E0",
        "entrypoint": "singlecore_evaluate.evaluate_singlecore",
        "result": {"path": f"results/a/q3-nikolastarx/baseline-revision-20260925/baseline/{case}-result.json.gz", "sha256": actual_sha},
    }
    revised["notes"] = [n for n in revised.get("notes", []) if not n.startswith("No baseline included")]
    revised["notes"].append(
        f"Revision 2 adds the existing verified official E0 single-core baseline from "
        f"huaweibei123/huaweicup2026@f26704ed8748f0a575b55f1a02b83d7335a1083f "
        f"({spec['source_artifact']}); source record {spec['source_commit']}:{spec['source_feed']}. "
        "The gzip bytes are copied unchanged; no evaluation was run. Revision 1 metrics, "
        "plan/result/run artifacts, and null end-to-end solver timing are preserved."
    )
    changed = {key for key in set(old) | set(revised) if old.get(key) != revised.get(key)}
    if changed != {"revision", "baseline", "notes"}:
        raise SystemExit(f"unexpected field changes for {case}: {sorted(changed)}")
    records.append(revised)
    checks.append({
        "case_id": case, "attempt_id": spec["attempt_id"], "old_revision": 1, "new_revision": 2,
        "target_source_commit": spec["target_commit"], "target_source_feed": str(spec["input"].relative_to(ROOT)),
        "target_source_git_blob_sha": spec["target_blob"], "baseline_donor_commit": "f26704ed8748f0a575b55f1a02b83d7335a1083f",
        "baseline_reuse_source_commit": spec["source_commit"], "baseline_reuse_source_feed": spec["source_feed"],
        "baseline_reuse_source_artifact": spec["source_artifact"], "baseline_sha256": actual_sha,
        "baseline_scene": result["scene"], "baseline_num_cores": result["num_cores"],
        "baseline_makespan_cycles": result["makespan"], "graph_sha256": spec["graph"],
        "config_sha256": CONFIG, "official_sha256": OFFICIAL,
        "speedup_preview_only": result["makespan"] / revised["metrics"]["makespan_cycles"],
        "solver_wall_seconds_preserved": revised["metrics"]["solver_wall_seconds"],
        "changed_top_level_fields": sorted(changed),
        "makespan_preserved": revised["metrics"]["makespan_cycles"] == old["metrics"]["makespan_cycles"],
        "plan_result_run_artifacts_preserved": revised["artifacts"] == old["artifacts"],
    })

feed = {"schema_version": 1, "submission_version": 1, "records": records}
OUT.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n")
(HERE / "verification.json").write_text(json.dumps({"checks": checks}, ensure_ascii=False, indent=2) + "\n")
print(f"wrote {OUT.relative_to(ROOT)} ({len(records)} revision-2 records)")
