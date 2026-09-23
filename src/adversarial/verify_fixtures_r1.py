"""统一复验 FORM 固定用例（供独立环境回跑，单一入口）。

复验随 PR 交付的三类固定件，逐条给出机械判据；**任一条不成立即非零退出**：

  1. tests/adversarial/ranking-inversion-pair.json    E2 排序反转（2 个方案，搬运统计相同）
  2. tests/adversarial/fplan-005-quotient-cycle.json  商图成环（划分级结构拒绝）
  3. tests/adversarial/dev-samples.jsonl              10 条开发反例（正例 / 边界 / 对抗）

判据口径（不引入本方任何代价模型，真值只来自冻结官方函数）：

  - **哈希**：canonical JSON 的 sha256，
    `json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` 后 UTF-8 编码。
  - **观察**：只调用冻结官方入口重放（`derive_multicore_plan` / `_build_scene_a_tasks` /
    `evaluate_scene_a`），与固定件中记录的 `observed` 逐字段比对。
  - **不做的**：不做 E0 评分；不调用队长的 oracle 适配层；不构成验收结论。

输出：results/a/form/r1-20260923-farmeruncle123/fixtures-observations.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "data" / "raw" / "a" / "official" / "code"
FIX = ROOT / "tests" / "adversarial"
OUT_DIR = ROOT / "results" / "a" / "form" / "r1-20260923-farmeruncle123"

sys.dont_write_bytecode = True
sys.path.insert(0, str(CODE))

import multicore_cut_evaluate_problem_1 as p1  # noqa: E402
from evaluation_validation import validate_graph  # noqa: E402
from stub_multicore_cut_and_schedule import derive_multicore_plan  # noqa: E402

BANDWIDTH = 60
CAPACITY = {"L1": 524288, "UB": 131072}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def h(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def boundary_copy_cycles(task):
    """本 Task 新生成的 COPY op（id > 5）的 op 类型与 cycles。"""
    out = {}
    for oid, op in sorted(task["op_by_id"].items()):
        if oid > 5 and op.get("op") in ("COPY_IN", "COPY_OUT"):
            out[str(oid)] = {"op": op["op"], "cycles": op.get("cycles")}
    return out


def replay_derive(graph, plan):
    try:
        view = derive_multicore_plan(graph, plan)
        # JSON 往返归一化：官方返回的 dependency_pairs 是 tuple，而 jsonl 记录经序列化后是
        # list。两者语义相同；不归一化会造成**假失败**（本脚本首版即栽在此）。
        return json.loads(json.dumps({
            "outcome": "accepted",
            "num_cores": view["num_cores"],
            "subgraph_ids": view["subgraph_ids"],
            "dependency_pairs": view["dependency_pairs"],
        }, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        return {"outcome": "rejected",
                "error": "{}: {}".format(type(exc).__name__, exc)}


def replay_tasks(graph, plan):
    try:
        tasks, cross, traffic, _view = p1._build_scene_a_tasks(
            graph, plan, BANDWIDTH, CAPACITY)
        ddr_ids = {v["id"] for v in graph["tensors"] if v.get("pos") == "DDR"}
        # 同 replay_derive：JSON 往返归一化，消除 tuple/list 表示差异。
        return json.loads(json.dumps({
            "outcome": "accepted",
            "cross_task_traffic": cross,
            "traffic": traffic,
            "generated_copy_cycles": {
                str(tid): boundary_copy_cycles(t) for tid, t in sorted(tasks.items())},
            "rewritten_pos": {
                str(tid): {str(x): t["tensor_by_id"][x].get("pos")
                           for x in sorted(t["tensor_by_id"]) if x in ddr_ids}
                for tid, t in sorted(tasks.items())},
        }, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        return {"outcome": "rejected",
                "error": "{}: {}".format(type(exc).__name__, exc)}


def check_ranking():
    path = FIX / "ranking-inversion-pair.json"
    fx = json.loads(path.read_text(encoding="utf-8"))
    C, graph, pair = fx["constants"], fx["graph"], fx["pair"]

    seen = {}
    for key in ("a", "b"):
        entry = pair[key]
        result = p1.evaluate_scene_a(
            graph, entry["plan"], C["bandwidth"], C["capacity"],
            C["task_cross_core_wait_cycles"], C["task_same_core_wait_cycles"])
        traffic = result["data_movement_bytes"]
        seen[key] = {
            "label": entry["label"],
            "claimed_makespan": entry["official_makespan"],
            "observed_makespan": result["makespan"],
            "cross_task_traffic": result["cross_task_traffic"],
            "added_copy_bytes": traffic["added_copy_bytes"],
            "partition_added_copy_bytes": traffic["partition_added_copy_bytes"],
            "matches_claim": result["makespan"] == entry["official_makespan"],
        }

    a, b = seen["a"], seen["b"]
    metrics_identical = (
        a["cross_task_traffic"] == b["cross_task_traffic"]
        and a["added_copy_bytes"] == b["added_copy_bytes"]
        and a["partition_added_copy_bytes"] == b["partition_added_copy_bytes"])
    claimed = pair["identical_metrics"]
    metrics_match = (
        a["cross_task_traffic"] == claimed["cross_task_traffic"]
        and a["added_copy_bytes"] == claimed["added_copy_bytes"]
        and a["partition_added_copy_bytes"] == claimed["partition_added_copy_bytes"])
    delta = a["observed_makespan"] - b["observed_makespan"]
    delta_match = delta == fx["observed_difference"]["delta_makespan"]

    ok = (a["matches_claim"] and b["matches_claim"]
          and metrics_identical and metrics_match and delta_match)
    return {
        "fixture": path.relative_to(ROOT).as_posix(),
        "fixture_sha256": file_sha(path),
        "official_entry": "multicore_cut_evaluate_problem_1.evaluate_scene_a",
        "results": seen,
        "metrics_identical_between_a_and_b": metrics_identical,
        "metrics_match_fixture": metrics_match,
        "observed_delta_makespan": delta,
        "claimed_delta_makespan": fx["observed_difference"]["delta_makespan"],
        "delta_matches_claim": delta_match,
        "passed": ok,
    }


def check_fplan005():
    path = FIX / "fplan-005-quotient-cycle.json"
    fx = json.loads(path.read_text(encoding="utf-8"))
    graph, plan = fx["graph"], fx["plan"]

    hash_ok = (fx["graph_sha256"] == h(graph) and fx["plan_sha256"] == h(plan))

    try:
        validate_graph(graph)
        vg = "pass"
    except Exception as exc:  # noqa: BLE001
        vg = "{}: {}".format(type(exc).__name__, exc)

    replay = replay_derive(graph, plan)
    reject_ok = (replay["outcome"] == "rejected"
                 and "cycle" in (replay.get("error") or "")
                 and replay.get("error") == fx["observed"]["derive_multicore_plan"])

    ok = hash_ok and vg.startswith("pass") and reject_ok
    return {
        "fixture": path.relative_to(ROOT).as_posix(),
        "fixture_sha256": file_sha(path),
        "graph_sha256_matches": fx["graph_sha256"] == h(graph),
        "plan_sha256_matches": fx["plan_sha256"] == h(plan),
        "validate_graph": vg,
        "derive_replay": replay,
        "matches_recorded_observation": reject_ok,
        "passed": ok,
    }


def check_dev_samples():
    path = FIX / "dev-samples.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    details = []
    for rec in records:
        graph, plan = rec["graph"], rec["plan"]
        hash_ok = (rec["graph_sha256"] == h(graph) and rec["plan_sha256"] == h(plan))
        replay = (replay_derive(graph, plan) if rec["path"] == "derive"
                  else replay_tasks(graph, plan))
        observed_match = replay == rec["observed"]
        details.append({
            "sample_id": rec["sample_id"],
            "mechanism_group": rec["mechanism_group"],
            "category": rec["category"],
            "path": rec["path"],
            "outcome": replay["outcome"],
            "graph_sha256_matches": rec["graph_sha256"] == h(graph),
            "plan_sha256_matches": rec["plan_sha256"] == h(plan),
            "replay_matches_recorded_observation": observed_match,
            "passed": hash_ok and observed_match,
        })
    return {
        "fixture": path.relative_to(ROOT).as_posix(),
        "fixture_sha256": file_sha(path),
        "sample_count": len(records),
        "samples_passed": sum(1 for d in details if d["passed"]),
        "details": details,
        "passed": all(d["passed"] for d in details),
    }


def main():
    ranking = check_ranking()
    fplan = check_fplan005()
    dev = check_dev_samples()

    payload = {
        "verifier": "src/adversarial/verify_fixtures_r1.py",
        "purpose": "统一复验 FORM 固定用例：供独立环境（LYX / 队长）用一条命令回跑并取得机械判据",
        "official_code_dir": "data/raw/a/official/code",
        "hashing": 'sha256 of json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",",":"))',
        "constants": {"bandwidth": BANDWIDTH, "capacity": CAPACITY,
                      "source": "data/raw/a/official/data/config.txt (frozen)"},
        "not_done": ["未做 E0 评分", "未调用队长的 oracle 适配层", "不构成验收结论"],
        "checks": {
            "ranking_inversion_pair": ranking,
            "fplan_005_quotient_cycle": fplan,
            "dev_samples": dev,
        },
        "all_fixtures_reproduced": (ranking["passed"] and fplan["passed"] and dev["passed"]),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "fixtures-observations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8", newline="\n")

    print("=== 固定用例复验 ===")
    for key in ("a", "b"):
        r = ranking["results"][key]
        print("  ranking %s: claimed=%s observed=%s match=%s" % (
            key, r["claimed_makespan"], r["observed_makespan"], r["matches_claim"]))
    print("  ranking delta=%s (claimed %s) metrics_identical=%s -> %s" % (
        ranking["observed_delta_makespan"], ranking["claimed_delta_makespan"],
        ranking["metrics_identical_between_a_and_b"], ranking["passed"]))
    print("  fplan-005: hashes=%s validate=%s reject=%s -> %s" % (
        fplan["graph_sha256_matches"] and fplan["plan_sha256_matches"],
        fplan["validate_graph"], fplan["matches_recorded_observation"], fplan["passed"]))
    print("  dev-samples: %d/%d passed -> %s" % (
        dev["samples_passed"], dev["sample_count"], dev["passed"]))
    print("ALL FIXTURES REPRODUCED: %s" % payload["all_fixtures_reproduced"])
    print("evidence:", out.relative_to(ROOT).as_posix())

    if not payload["all_fixtures_reproduced"]:
        raise SystemExit("fixtures not reproduced")


if __name__ == "__main__":
    main()
