"""F-METRIC-001 补测：核对搬运统计五个字段之间的等式关系。

官方 `_build_scene_a_tasks` 返回的 traffic 字典含 5 个字段。本探针在多种构造下
（含/不含原图 COPY_OUT、是否发生 spill、单核/多核、是否有跨 Task 流量）
检查以下恒等式是否成立：

    I1: added_copy_bytes == partition_added_copy_bytes + spill_added_copy_bytes
    I2: added_copy_bytes == scheduled_copy_bytes - original_graph_copy_bytes
    I3: scheduled_copy_bytes >= original_graph_copy_bytes + partition_added_copy_bytes

只读调用**冻结官方函数**入口，不改动官方材料；未调用队长的 oracle 适配层，未做正式基准与全量验收。
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
CAP_FULL = {"L1": 524288, "UB": 131072}
CROSS_CORE_WAIT = 1000
SAME_CORE_WAIT = 100
SIZE = 64


def chain_graph(with_copy_out=False):
    """op1 COPY_IN -> op2 CONV -> op3 CONV [-> op4 COPY_OUT]"""
    ops = [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
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
    if with_copy_out:
        ops.append({"id": 4, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0})
        tensors.append({"id": 104, "pos": "DDR", "size": SIZE})
        edges += [{"source": 103, "target": 4}, {"source": 4, "target": 104}]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def spill_graph():
    """长寿命 L(t102) 跨链存活、末次使用推到链尾之后：UB=191 时会触发 1 次 spill。

    与 src/adversarial/verify_spill_r2.py 的 graph_v4 同构。
    """
    ops = [{"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0}]
    for i in range(2, 10):
        ops.append({"id": i, "op": "CONV", "pipe": "PIPE_M", "cycles": 4})
    tensors = [
        {"id": 100, "pos": "DDR", "size": SIZE},
        {"id": 101, "pos": "L1", "size": SIZE},
    ]
    for t in range(102, 110):
        tensors.append({"id": t, "pos": "UB", "size": SIZE})
    edges = [
        {"source": 100, "target": 1},
        {"source": 1, "target": 101},
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 102, "target": 3},
        {"source": 3, "target": 103},
        {"source": 103, "target": 4},
        {"source": 4, "target": 104},
        {"source": 104, "target": 5},
        {"source": 5, "target": 105},
        {"source": 105, "target": 6},
        {"source": 6, "target": 106},
        {"source": 106, "target": 7},
        {"source": 7, "target": 107},
        {"source": 107, "target": 8},
        {"source": 8, "target": 108},
        {"source": 102, "target": 9},
        {"source": 9, "target": 109},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def shared_consumer_graph():
    """t102 被两个核消费，产生跨 Task 流量。"""
    ops = [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 4, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
    ]
    tensors = [
        {"id": 100, "pos": "DDR", "size": SIZE},
        {"id": 101, "pos": "L1", "size": SIZE},
        {"id": 102, "pos": "UB", "size": SIZE},
        {"id": 103, "pos": "UB", "size": SIZE},
        {"id": 104, "pos": "UB", "size": SIZE},
    ]
    edges = [
        {"source": 100, "target": 1},
        {"source": 1, "target": 101},
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 102, "target": 3},
        {"source": 3, "target": 103},
        {"source": 102, "target": 4},
        {"source": 4, "target": 104},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


CASES = [
    ("chain, no original COPY_OUT, 1 core",
     chain_graph(False), {"node_to_subgraph": {"2": 0, "3": 0}, "core_schedules": [[0]]},
     CAP_FULL),
    ("chain, WITH original COPY_OUT, 1 core",
     chain_graph(True), {"node_to_subgraph": {"2": 0, "3": 0}, "core_schedules": [[0]]},
     CAP_FULL),
    ("chain split across 2 cores",
     chain_graph(True), {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0], [1]]},
     CAP_FULL),
    ("shared consumer across 2 cores (cross-task traffic)",
     shared_consumer_graph(), {"node_to_subgraph": {"2": 0, "3": 1, "4": 1},
                               "core_schedules": [[0], [1]]}, CAP_FULL),
    ("spill case: UB capacity 191 forces >=1 spill",
     spill_graph(), {"node_to_subgraph": {str(i): 0 for i in range(2, 10)},
                     "core_schedules": [[0]]}, {"L1": 524288, "UB": 191}),
]


def main():
    records = []
    for label, graph, plan, cap in CASES:
        rec = {"case": label, "capacity": cap}
        try:
            result = p1.evaluate_scene_a(
                graph, plan, BANDWIDTH, cap, CROSS_CORE_WAIT, SAME_CORE_WAIT)
        except Exception as exc:  # noqa: BLE001
            rec["outcome"] = "raised"
            rec["error"] = f"{type(exc).__name__}: {exc}"
            records.append(rec)
            continue
        t = result["data_movement_bytes"]
        rec["outcome"] = "ok"
        rec["makespan"] = result["makespan"]
        rec["traffic"] = dict(t)
        rec["cross_task_traffic"] = result["cross_task_traffic"]
        orig = t["original_graph_copy_bytes"]
        sched = t["scheduled_copy_bytes"]
        added = t["added_copy_bytes"]
        part = t["partition_added_copy_bytes"]
        spill = t["spill_added_copy_bytes"]
        rec["identities"] = {
            "I1 added == partition_added + spill_added": added == part + spill,
            "I2 added == scheduled - original": added == sched - orig,
            "I3 scheduled >= original + partition_added": sched >= orig + part,
            "I4 partition_added == scheduled - original - spill_added":
                part == sched - orig - spill,
        }
        rec["numeric"] = {
            "added-minus-(partition+spill)": added - (part + spill),
            "added-minus-(scheduled-original)": added - (sched - orig),
        }
        records.append(rec)

    all_ok = all(
        r["outcome"] == "ok" and all(r["identities"].values())
        for r in records)
    spill_cases = [r for r in records
                   if r["outcome"] == "ok" and r["traffic"]["spill_added_copy_bytes"] > 0]

    payload = {
        "generator": "src/adversarial/verify_metric_r1.py",
        "official_entry": "multicore_cut_evaluate_problem_1.evaluate_scene_a",
        "identities_checked": [
            "added_copy_bytes == partition_added_copy_bytes + spill_added_copy_bytes",
            "added_copy_bytes == scheduled_copy_bytes - original_graph_copy_bytes",
            "scheduled_copy_bytes >= original_graph_copy_bytes + partition_added_copy_bytes",
            "partition_added_copy_bytes == scheduled_copy_bytes - original_graph_copy_bytes "
            "- spill_added_copy_bytes",
        ],
        "cases": records,
        "all_identities_hold": all_ok,
        "cases_with_spill": len(spill_cases),
        "spill_added_values": [r["traffic"]["spill_added_copy_bytes"] for r in spill_cases],
        "limitations": [
            "微型构造图，不代表正式用例规模。",
            "只核对 5 个字段之间的代数关系，不核对每个字段的定义是否与题面一致。",
            "未覆盖问题 2/3 的对应统计字段。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "metric-observations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in records:
        if r["outcome"] != "ok":
            print(f"  {r['case']}: RAISED {r['error'][:90]}")
            continue
        t = r["traffic"]
        bad = [k for k, v in r["identities"].items() if not v]
        print(f"  {r['case']}")
        print(f"     orig={t['original_graph_copy_bytes']} sched={t['scheduled_copy_bytes']} "
              f"added={t['added_copy_bytes']} part={t['partition_added_copy_bytes']} "
              f"spill={t['spill_added_copy_bytes']} cross={r['cross_task_traffic']}")
        print(f"     identities: {'ALL HOLD' if not bad else 'FAILED -> ' + str(bad)}")
    print(f"ALL IDENTITIES HOLD ACROSS ALL CASES: {all_ok} | spill cases: {len(spill_cases)}")
    print("evidence:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
