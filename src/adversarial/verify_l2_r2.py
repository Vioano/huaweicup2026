"""L2 探针第二批：同时 miss 与淘汰路径（问题 3）。

上一批（verify_l2_r1.py）用的是「某个核产出、另几个核消费」的构造，源核的 COPY_OUT
在 PIPE_MTE3 上串行，把消费者的 COPY_IN 错开了 10 cycles，因此测不到「同刻同时 miss」。

本批改用**图输入 tensor**：这类 tensor 没有生产者，`_build_scene_b_tasks` 会为每个消费核
各自生成一个 COPY_IN，且**没有源核 COPY_OUT 来错开它们** —— 于是可以在 t=0 真正同时发起。

只读调用官方 evaluate_problem_3，不改动官方材料，不做 E0 评分。
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

import multicore_cut_evaluate_problem_3 as p3  # noqa: E402

BANDWIDTH = 60
CAPACITY = {"L1": 524288, "UB": 131072}
CROSS_CORE_COPY_DELAY = 500
CACHE_CAPACITY = 1048576
CACHE_BANDWIDTH = 250
SIZE = 600


def shared_input_graph(distinct=False):
    """一张或两张**图输入** tensor，被不同核上的算子消费。

    distinct=False：t200 被 core 0 的 op2 与 core 1 的 op3 共同消费 → 同一 cache key
    distinct=True ：t200 被 core 0 的 op2 消费、t210 被 core 1 的 op3 消费 → 两个不同 key
    """
    ops = [
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
    ]
    tensors = [
        {"id": 200, "pos": "DDR", "size": SIZE},
        {"id": 202, "pos": "UB", "size": SIZE},
        {"id": 203, "pos": "UB", "size": SIZE},
    ]
    edges = [
        {"source": 200, "target": 2},   # t200 无生产者 → 图输入
        {"source": 2, "target": 202},
    ]
    if distinct:
        tensors.append({"id": 210, "pos": "DDR", "size": SIZE})
        edges.append({"source": 210, "target": 3})
    else:
        edges.append({"source": 200, "target": 3})
    edges.append({"source": 3, "target": 203})
    plan = {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0], [1]]}
    return {"ops": ops, "tensors": tensors, "edges": edges}, plan


def run_case(label, graph, plan, cache_bytes, note):
    rec = {"case": label, "note": note, "cache_capacity_bytes": cache_bytes}
    try:
        result = p3.evaluate_problem_3(
            graph, plan, BANDWIDTH, CAPACITY, CROSS_CORE_COPY_DELAY,
            cache_bytes, CACHE_BANDWIDTH)
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "raised"
        rec["error"] = f"{type(exc).__name__}: {exc}"
        return rec
    rec["outcome"] = "ok"
    rec["makespan"] = result.get("makespan")
    stats = result.get("cache_stats") or {}
    rec["cache_stats"] = {k: stats.get(k) for k in (
        "copy_in_hits", "copy_in_misses", "hit_bytes", "miss_bytes",
        "accesses", "hits", "hit_rate")}
    events = result.get("cache_events") or []
    rec["cache_events"] = events
    # 同刻同时 miss：找出同一时刻出现 >=2 次 miss 的时间点
    by_time = {}
    for e in events:
        by_time.setdefault(e["time"], []).append(e["event"])
    rec["events_by_time"] = {str(k): v for k, v in sorted(by_time.items())}
    rec["simultaneous_miss_times"] = sorted(
        t for t, evs in by_time.items() if evs.count("miss") >= 2)
    rec["evictions"] = [e for e in events
                        if e.get("event") == "insert" and e.get("evicted_tensor_ids")]
    rec["cache_final_entries"] = result.get("cache_final_entries")
    rec["cache_used_bytes_final"] = result.get("cache_used_bytes_final")
    return rec


def main():
    records = []

    g_shared, plan_shared = shared_input_graph(distinct=False)
    records.append(run_case(
        "A) same graph-input tensor consumed by two cores, ample cache",
        g_shared, plan_shared, CACHE_CAPACITY,
        "预期：两个 COPY_IN 在 t=0 同时发起 → 同刻两次 miss，且只发生一次 insert"))

    records.append(run_case(
        "B) same, but cache smaller than one tensor (SIZE-1)",
        g_shared, plan_shared, SIZE - 1,
        "预期：size > cache_capacity_bytes → 从不 insert；两次均 miss"))

    g_distinct, plan_distinct = shared_input_graph(distinct=True)
    records.append(run_case(
        "C) two DISTINCT graph-input tensors, cache holds only one tensor",
        g_distinct, plan_distinct, SIZE,
        "预期：第二个 insert 需要淘汰第一个 → evicted_tensor_ids 非空"))

    payload = {
        "generator": "src/adversarial/verify_l2_r2.py",
        "official_entry": "multicore_cut_evaluate_problem_3.evaluate_problem_3",
        "construction_note": ("用**图输入** tensor 避免源核 COPY_OUT 串行造成的错开，"
                              "从而能观察到同刻同时 miss"),
        "constants": {
            "bandwidth": BANDWIDTH,
            "cross_core_copy_delay_cycles": CROSS_CORE_COPY_DELAY,
            "cache_capacity_bytes": CACHE_CAPACITY,
            "cache_bandwidth_bytes_per_cycle": CACHE_BANDWIDTH,
            "tensor_size_bytes": SIZE,
        },
        "cases": records,
        "limitations": [
            "微型构造图，不代表官方 case 规模。",
            "未测 >=3 个并发命中时 CACHE_READ 池的分段换算。",
            "未覆盖 spill/rename 产生的 logical_tid 命中路径（需问题 3 内同时发生 spill）。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "l2b-observations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in records:
        if r["outcome"] != "ok":
            print(f"  {r['case']}: RAISED {r['error'][:110]}")
            continue
        s = r["cache_stats"]
        print(f"  {r['case']}")
        print(f"     hits={s['copy_in_hits']} misses={s['copy_in_misses']} "
              f"hit_rate={s['hit_rate']} makespan={r['makespan']}")
        print(f"     events_by_time={r['events_by_time']}")
        print(f"     simultaneous_miss_times={r['simultaneous_miss_times']}")
        print(f"     evictions={[ (e['time'], e['tensor_id'], e['evicted_tensor_ids']) for e in r['evictions'] ]}")
        print(f"     final_entries={r['cache_final_entries']}")
    print("evidence:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
