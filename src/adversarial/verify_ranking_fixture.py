"""复验排序对抗夹具：读 tests/adversarial/ranking-inversion-pair.json，用官方入口重算两个方案。

夹具里的 makespan 不允许靠手写；本脚本必须复现出同样的数值。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "data/raw/a/official/code"
FIXTURE = ROOT / "tests/adversarial/ranking-inversion-pair.json"
OUT_DIR = ROOT / "results/a/form/r1-20260923-farmeruncle123"

sys.dont_write_bytecode = True
sys.path.insert(0, str(CODE))

import multicore_cut_evaluate_problem_1 as p1  # noqa: E402


def main():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    C = fx["constants"]
    graph = fx["graph"]
    pair = fx["pair"]

    results = {}
    for key in ("a", "b"):
        entry = pair[key]
        result = p1.evaluate_scene_a(
            graph, entry["plan"],
            C["bandwidth"], C["capacity"],
            C["task_cross_core_wait_cycles"], C["task_same_core_wait_cycles"])
        traffic = result["data_movement_bytes"]
        results[key] = {
            "label": entry["label"],
            "plan": entry["plan"],
            "claimed_makespan": entry["official_makespan"],
            "observed_makespan": result["makespan"],
            "observed_cross_task_traffic": result["cross_task_traffic"],
            "observed_added_copy_bytes": traffic["added_copy_bytes"],
            "observed_partition_added_copy_bytes": traffic["partition_added_copy_bytes"],
            "matches_claim": result["makespan"] == entry["official_makespan"],
        }

    a, b = results["a"], results["b"]
    metrics_identical = (
        a["observed_cross_task_traffic"] == b["observed_cross_task_traffic"]
        and a["observed_added_copy_bytes"] == b["observed_added_copy_bytes"]
        and a["observed_partition_added_copy_bytes"] == b["observed_partition_added_copy_bytes"]
    )
    delta = a["observed_makespan"] - b["observed_makespan"]
    claimed_metrics = pair["identical_metrics"]
    metrics_match_fixture = (
        a["observed_cross_task_traffic"] == claimed_metrics["cross_task_traffic"]
        and a["observed_added_copy_bytes"] == claimed_metrics["added_copy_bytes"]
        and a["observed_partition_added_copy_bytes"] == claimed_metrics["partition_added_copy_bytes"]
    )

    payload = {
        "verifier": "src/adversarial/verify_ranking_fixture.py",
        "fixture": "tests/adversarial/ranking-inversion-pair.json",
        "official_entry": "multicore_cut_evaluate_problem_1.evaluate_scene_a",
        "results": results,
        "metrics_identical_between_a_and_b": metrics_identical,
        "metrics_match_fixture": metrics_match_fixture,
        "observed_delta_makespan": delta,
        "claimed_delta_makespan": fx["observed_difference"]["delta_makespan"],
        "delta_matches_claim": delta == fx["observed_difference"]["delta_makespan"],
        "all_claims_verified": (
            results["a"]["matches_claim"] and results["b"]["matches_claim"]
            and metrics_identical and metrics_match_fixture
            and delta == fx["observed_difference"]["delta_makespan"]
        ),
        "limitations": [
            "微型构造图，不代表正式用例。",
            "未使用 E1/E2 代价模型；真值只来自官方入口。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "ranking-fixture-verification.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    for key in ("a", "b"):
        r = results[key]
        print(f"  {key}: {r['label']}")
        print(f"     claimed={r['claimed_makespan']} observed={r['observed_makespan']} "
              f"match={r['matches_claim']}")
        print(f"     cross_task_traffic={r['observed_cross_task_traffic']} "
              f"added_copy_bytes={r['observed_added_copy_bytes']}")
    print(f"  metrics identical: {metrics_identical} | delta = {delta} "
          f"(claimed {fx['observed_difference']['delta_makespan']})")
    print(f"  ALL CLAIMS VERIFIED: {payload['all_claims_verified']}")
    print("evidence:", out.relative_to(ROOT))

    if not payload["all_claims_verified"]:
        raise SystemExit("fixture claims not reproduced")


if __name__ == "__main__":
    main()
