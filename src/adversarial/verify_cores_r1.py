"""响应 INDEPENDENT-REVIEW-001 R2：加核结论必须用**同图同划分**对照。

原 SPEC §4 第 6 点与 F-RESOURCE-001 用「单链 1 核 = 24」对「双链 2 核 = 44」说明加核问题——
两个输入图的工作量不同（链数不同），该对照只能展示共享 DDR 争用，
**不能**支持固定工作量下的加核结论。

本探针在同一张图上只改 `core_schedules`，复现队长的对照表。

只读调用**冻结官方函数** evaluate_scene_a；未调用队长的 oracle 适配层，未做正式基准与全量验收。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "data/raw/a/official/code"
OUT_DIR = ROOT / "results/a/form/r1-20260923-farmeruncle123"

sys.dont_write_bytecode = True
sys.path.insert(0, str(CODE))

import multicore_cut_evaluate_problem_1 as p1  # noqa: E402

BANDWIDTH = 60
CAPACITY = {"L1": 524288, "UB": 131072}
CROSS_CORE_WAIT = 1000
SAME_CORE_WAIT = 100
SIZE = 600


def two_independent_chains():
    """两条结构相同、互相独立的 COPY_IN->CONV->COPY_OUT 链（各 1 个子图）。"""
    ops, tensors, edges = [], [], []
    for k, (ob, tb) in enumerate([(1, 100), (11, 200)]):
        ops += [
            {"id": ob, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
            {"id": ob + 1, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
            {"id": ob + 2, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
        ]
        tensors += [
            {"id": tb, "pos": "DDR", "size": SIZE},
            {"id": tb + 1, "pos": "L1", "size": SIZE},
            {"id": tb + 2, "pos": "UB", "size": SIZE},
        ]
        edges += [
            {"source": tb, "target": ob},
            {"source": ob, "target": tb + 1},
            {"source": tb + 1, "target": ob + 1},
            {"source": ob + 1, "target": tb + 2},
            {"source": tb + 2, "target": ob + 2},
        ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def dependent_two_segments():
    """有真实依赖的两段：op2 产出的 t102 被 op3 消费（同 verify_time_r1 的依赖对）。"""
    ops = [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "VADD", "pipe": "PIPE_V", "cycles": 4},
        {"id": 3, "op": "VADD", "pipe": "PIPE_V", "cycles": 4},
    ]
    tensors = [
        {"id": 100, "pos": "DDR", "size": SIZE},
        {"id": 101, "pos": "L1", "size": SIZE},
        {"id": 102, "pos": "UB", "size": SIZE},
        {"id": 103, "pos": "UB", "size": SIZE},
    ]
    edges = [
        {"source": 100, "target": 1},
        {"source": 1, "target": 101},
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 102, "target": 3},
        {"source": 3, "target": 103},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def run(label, graph, plan, note):
    rec = {"case": label, "note": note, "plan": plan}
    try:
        result = p1.evaluate_scene_a(
            graph, plan, BANDWIDTH, CAPACITY, CROSS_CORE_WAIT, SAME_CORE_WAIT)
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "raised"
        rec["error"] = f"{type(exc).__name__}: {exc}"
        return rec
    rec["outcome"] = "ok"
    rec["makespan"] = result["makespan"]
    rec["num_cores"] = result["num_cores"]
    rec["cross_task_traffic"] = result["cross_task_traffic"]
    rec["added_copy_bytes"] = result["data_movement_bytes"]["added_copy_bytes"]
    return rec


def main():
    records = []

    # 组 1：两条独立链（同图同划分，只改 core_schedules）
    g1 = two_independent_chains()
    records.append(run(
        "independent chains | core_schedules=[[0,1],[]]",
        g1, {"node_to_subgraph": {"2": 0, "12": 1}, "core_schedules": [[0, 1], []]},
        "两个子图都放在 core 0"))
    records.append(run(
        "independent chains | core_schedules=[[0],[1]]",
        g1, {"node_to_subgraph": {"2": 0, "12": 1}, "core_schedules": [[0], [1]]},
        "两个子图分到两个核"))

    # 组 2：有依赖的两段（同图同划分）
    g2 = dependent_two_segments()
    records.append(run(
        "dependent segments | core_schedules=[[0,1]]  (1 core)",
        g2, {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0, 1]]},
        "只有一个核，两段同核串行"))
    records.append(run(
        "dependent segments | core_schedules=[[0,1],[]]  (add EMPTY core)",
        g2, {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0, 1], []]},
        "只添加一个空核，工作划分不变"))
    records.append(run(
        "dependent segments | core_schedules=[[0],[1]]  (split across 2 cores)",
        g2, {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0], [1]]},
        "把两段分到两个核 → 依赖跨核，触发跨核等待"))

    # 组 3：保留原观察作为「带宽争用」证据（两个图，工作量不同）
    g3 = two_independent_chains()
    records.append(run(
        "bandwidth contention: ONE chain on 1 core (half the workload)",
        {"ops": g3["ops"][:3], "tensors": [t for t in g3["tensors"] if t["id"] < 200],
         "edges": [e for e in g3["edges"] if e["source"] < 200 and e["target"] < 200]},
        {"node_to_subgraph": {"2": 0}, "core_schedules": [[0]]},
        "单链单核：仅用于展示共享 DDR 争用，不可与下面两链对比以论证加核"))
    records.append(run(
        "bandwidth contention: TWO chains on 2 cores",
        g3, {"node_to_subgraph": {"2": 0, "12": 1}, "core_schedules": [[0], [1]]},
        "双链双核：工作量是上一行的两倍"))

    by = {r["case"]: r.get("makespan") for r in records}
    indep_one = by.get("independent chains | core_schedules=[[0,1],[]]")
    indep_two = by.get("independent chains | core_schedules=[[0],[1]]")
    dep_one = by.get("dependent segments | core_schedules=[[0,1]]  (1 core)")
    dep_empty = by.get("dependent segments | core_schedules=[[0,1],[]]  (add EMPTY core)")
    dep_split = by.get("dependent segments | core_schedules=[[0],[1]]  (split across 2 cores)")

    payload = {
        "generator": "src/adversarial/verify_cores_r1.py",
        "purpose": "响应 INDEPENDENT-REVIEW-001 R2：加核论述必须用同图同划分对照",
        "group1_independent_chains": {"same_core_148_expected": indep_one,
                                      "split_two_cores_44_expected": indep_two},
        "group2_dependent_segments": {"one_core": dep_one,
                                      "add_empty_core": dep_empty,
                                      "split_two_cores": dep_split},
        "group3_bandwidth_contention_different_workload": {
            "one_chain_one_core": by.get("bandwidth contention: ONE chain on 1 core (half the workload)"),
            "two_chains_two_cores": by.get("bandwidth contention: TWO chains on 2 cores"),
            "caveat": "两者工作量不同（1 条链 vs 2 条链），只能展示共享 DDR 争用，不能论证固定工作量的加核结论",
        },
        "records": records,
        "conclusions": {
            "supported": ("具体分配方案未必因使用更多核而更快："
                          "有依赖的两段从 1 核改为跨 2 核后 makespan 由 148 升至 1048；"
                          "只添加空核则仍为 148（空核不计入有效并行）"),
            "not_supported": ("**不能**外推为『核预算增大时最优值必然变差』。"
                              "两条独立链在同一图上从同核改为分核反而由 148 降到 44"),
            "bandwidth_only": ("原 24/44 观察只作为**共享 DDR 带宽争用**的证据，"
                               "其因果解释已修正；论证加核问题必须使用同图对照"),
        },
        "limitations": [
            "微型构造图（3–6 个算子、2 核），不代表正式用例。",
            "未测 3 核及以上、也未测 workloads 不均衡的情形。",
            "本探针只调用冻结官方函数 evaluate_scene_a，未调用队长的 oracle 适配层、未做正式基准与全量验收，也不构成性能或质量结论。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "cores-observations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in records:
        if r["outcome"] == "ok":
            print(f"  {r['case']}: makespan={r['makespan']} num_cores={r['num_cores']}")
        else:
            print(f"  {r['case']}: RAISED {r['error'][:90]}")
    print("evidence:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
