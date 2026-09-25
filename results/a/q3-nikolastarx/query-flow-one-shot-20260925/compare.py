"""Compare archived official pairs without dispatching any evaluator."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OLD = "19bebf35205d23fdd832781540f8879da52eeb62"
FEED = "results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/board-feed-s08-revision2.json"


def blob(path):
    return subprocess.check_output(["git", "show", f"{OLD}:{path}"], cwd=ROOT)


def old_artifact(ref):
    raw = blob(ref["path"])
    assert hashlib.sha256(raw).hexdigest() == ref["sha256"]
    return json.loads(gzip.decompress(raw) if ref["path"].endswith(".gz") else raw)


def new_result(phase):
    worker = json.loads((HERE / "run" / f"{phase}.worker.json").read_text())
    raw = (HERE / "run" / f"{phase}.json.gz").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == worker["result_sha256"]
    assert worker["status"] == "complete"
    return json.loads(gzip.decompress(raw)), worker


def main():
    feed_raw = blob(FEED)
    record = next(r for r in json.loads(feed_raw)["records"]
                  if r["case_id"] == "071" and r["cores"] == 5)
    old3 = old_artifact(record["artifacts"]["result"])
    old2 = old_artifact(record["cache_pair"]["result"])
    old_plan = old_artifact(record["artifacts"]["plan"])
    baseline = old_artifact(record["baseline"]["result"])
    assert set(old_plan) == {"node_to_subgraph", "core_schedules"}
    for field in ("graph_sha256", "config_sha256", "official_sha256", "plan_sha256"):
        assert record["identity"][field] == record["cache_pair"][field]
    new3, w3 = new_result("p3")
    new2, w2 = new_result("p2")
    run = json.loads((HERE / "run" / "run.json").read_text())
    assert run["status"] == "complete"
    assert w3["plan_sha256"] == w2["plan_sha256"] == run["plan_sha256"]
    assert run["official_code_sha256"] == record["identity"]["official_sha256"]
    for field, path in (("graph_sha256", "data/raw/a/official/data/case_071.json"),
                        ("config_sha256", "data/raw/a/official/data/config.txt")):
        assert run["source_input_sha256"][path] == record["identity"][field]
    m20, m30, m21, m31 = [x["makespan"] for x in (old2, old3, new2, new3)]
    # Official P2 has scene=B but no problem field; its entrypoint is
    # established by the paired feed/worker, not an invented JSON key.
    assert old2["scene"] == new2["scene"] == "B"
    assert "cache_stats" not in old2 and "cache_stats" not in new2
    assert old2["num_cores"] == new2["num_cores"] == 5
    assert old3["problem"] == new3["problem"] == 3
    out = {
        "case": "071", "cores": 5, "old_evidence_commit": OLD,
        "old_feed": FEED, "old_feed_sha256": hashlib.sha256(feed_raw).hexdigest(),
        "old_identity": record["identity"], "new_plan_sha256": run["plan_sha256"],
        "old_P2_M": m20, "old_P3_M": m30, "old_G": m20 / m30,
        "new_P2_M": m21, "new_P3_M": m31, "new_G": m21 / m31,
        "P2_cycle_reduction_fraction": 1 - m21 / m20,
        "P3_cycle_reduction_fraction": 1 - m31 / m30,
        "not_inflated_by_worse_nocache": m21 <= m20,
        "strict_cache_improvement": m31 < m30,
        "G_nondegradation_exact_cross_product": m21 * m30 >= m20 * m31,
        "baseline_M": baseline["makespan"],
        "old_baseline_speedup": baseline["makespan"] / m30,
        "new_baseline_speedup": baseline["makespan"] / m31,
        "old_data_movement_bytes": old3["data_movement_bytes"],
        "new_data_movement_bytes": new3["data_movement_bytes"],
        "old_cache_stats": old3["cache_stats"], "new_cache_stats": new3["cache_stats"],
        "new_evaluation_calls": 0,
        "scope": "One case only. Existing official result bytes rehashed; pair plan identity is attested by the frozen feeds/workers, not re-evaluated here. Outer resource supervisor failed on terminal parent identity; independent postchecks found no surviving recorded processes. This is not full500 or a solver timing result.",
    }
    (HERE / "comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if "stats" not in k and "movement" not in k}))


if __name__ == "__main__":
    main()
