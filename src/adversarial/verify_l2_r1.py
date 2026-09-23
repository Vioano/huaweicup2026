"""L2 Cache 探针（问题 3）。

只读调用**冻结官方函数** evaluate_problem_3，不改动官方材料；未调用队长的 oracle 适配层，未做正式基准与全量验收。

关键构造：场景 B 里同一个 tensor 被多个核消费时，各核各自生成一个写向
**同一 local_tid** 的 COPY_IN；Cache key 取 COPY_IN 的 out_tid，
因此这些 COPY_IN 共用同一个 key —— 这是官方语义下自然产生 Cache 命中的路径。
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

# data/config.txt 冻结值
BANDWIDTH = 60
CAPACITY = {"L1": 524288, "UB": 131072}
CROSS_CORE_COPY_DELAY = 500
CACHE_CAPACITY = 1048576
CACHE_BANDWIDTH = 250

SIZE = 600  # ceil(600/60)=10 cycles（miss），ceil(600/250)=3 cycles（hit）


def three_core_shared_consumer(extra_delay_op=False):
    """t102 由 core 0 产出，被 core 1 与 core 2 各自消费。

    两个消费者核各自生成一个写向 local_tid=t102 的 COPY_IN，
    因此两者共用同一 Cache key。

    extra_delay_op=True 时在 core 2 上先放一个长算子，
    用来把 core 2 的 COPY_IN 推到 core 1 的 COPY_IN 完成之后。
    """
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
    if extra_delay_op:
        # core 2 上先做一个不依赖 t102 的长算子，用来推移它自己的 COPY_IN
        ops.append({"id": 7, "op": "CONV", "pipe": "PIPE_M", "cycles": 400})
        tensors.append({"id": 107, "pos": "UB", "size": SIZE})
        edges.append({"source": 7, "target": 107})
        edges.append({"source": 107, "target": 4})
        plan_nodes = {"2": 0, "3": 1, "4": 2, "7": 2}
    else:
        plan_nodes = {"2": 0, "3": 1, "4": 2}
    plan = {"node_to_subgraph": plan_nodes,
            "core_schedules": [[0], [1], [2]]}
    return {"ops": ops, "tensors": tensors, "edges": edges}, plan


def unequal_sizes():
    """把两个 Cache 可命中的 COPY_IN 的 tensor 尺寸做成不等，用来区分
    hit_rate 是『按字节』还是『按访问次数』。

    t101（core 0 那条原图 COPY_IN 的输出）取 60 字节；
    t102（被两个核共享、能命中的那个）取 600 字节。
    若按字节：hit=600 / total=(600+60+600)=1260 -> 0.4762
    若按次数：1 / 3 -> 0.3333
    """
    graph, plan = three_core_shared_consumer()
    for tensor in graph["tensors"]:
        if tensor["id"] == 101:
            tensor["size"] = 60
    return graph, plan


def run_case(label, graph, plan, cache_bytes, note):
    record = {"case": label, "note": note, "cache_capacity_bytes": cache_bytes}
    try:
        result = p3.evaluate_problem_3(
            graph, plan, BANDWIDTH, CAPACITY, CROSS_CORE_COPY_DELAY,
            cache_bytes, CACHE_BANDWIDTH)
    except Exception as exc:  # noqa: BLE001
        record["outcome"] = "raised"
        record["error"] = f"{type(exc).__name__}: {exc}"
        return record
    record["outcome"] = "ok"
    record["makespan"] = result.get("makespan")
    stats = result.get("cache_stats") or {}
    record["cache_stats"] = {
        k: stats.get(k) for k in (
            "copy_in_hits", "copy_in_misses", "hit_bytes", "miss_bytes",
            "accesses", "hits", "hit_rate")
    }
    record["cache_events"] = result.get("cache_events")
    record["cache_used_bytes_final"] = result.get("cache_used_bytes_final")
    record["cache_final_entries"] = result.get("cache_final_entries")
    paths = {}
    for entry in result.get("per_core_timeline", []):
        for item in (entry.get("ops") or []):
            if item.get("op") in ("COPY_IN", "COPY_OUT"):
                paths.setdefault(item.get("memory_path"), []).append(
                    {"core": entry.get("core_id"), "op": item.get("op"),
                     "op_id": item.get("op_id"), "cache_hit": item.get("cache_hit")})
    record["memory_paths"] = paths
    # 逐核 COPY 时间线：用于验证多播时源核 COPY_OUT 串行、消费者被错开
    record["copy_timeline"] = [
        {"core_id": entry.get("core_id"),
         "copies": [
             {"op_id": item.get("op_id"), "op": item.get("op"),
              "start": item.get("start"), "end": item.get("end"),
              "memory_path": item.get("memory_path")}
             for item in (entry.get("ops") or [])
             if item.get("op") in ("COPY_IN", "COPY_OUT")
         ]}
        for entry in result.get("per_core_timeline", [])
        if any(item.get("op") in ("COPY_IN", "COPY_OUT")
               for item in (entry.get("ops") or []))
    ]
    return record


def main():
    records = []

    graph, plan = three_core_shared_consumer()
    records.append(run_case(
        "3 cores, one tensor consumed by two cores, cache big enough",
        graph, plan, CACHE_CAPACITY,
        "预期：两个消费者核的 COPY_IN 共用 key=102，先到者 miss、后到者 hit"))

    records.append(run_case(
        "same graph, cache capacity smaller than one tensor",
        graph, plan, SIZE - 1,
        "预期：size > cache_capacity_bytes 时 insert_cache 直接返回，永不命中"))

    graph_d, plan_d = three_core_shared_consumer(extra_delay_op=True)
    records.append(run_case(
        "same graph + a long preceding op on core 2",
        graph_d, plan_d, CACHE_CAPACITY,
        "用长算子把 core 2 的 COPY_IN 推后，检验能否让第二次访问变成 hit"))

    graph_u, plan_u = unequal_sizes()
    rec_u = run_case(
        "unequal tensor sizes: 60 vs 600 bytes",
        graph_u, plan_u, CACHE_CAPACITY,
        "区分 hit_rate 是按字节还是按访问次数")
    if rec_u.get("outcome") == "ok":
        s = rec_u["cache_stats"]
        total = s["hit_bytes"] + s["miss_bytes"]
        rec_u["byte_weighted_hit_rate"] = (s["hit_bytes"] / total) if total else 0.0
        rec_u["count_weighted_hit_rate"] = (
            s["copy_in_hits"] / s["accesses"] if s["accesses"] else 0.0)
        rec_u["reported_hit_rate"] = s["hit_rate"]
        rec_u["which_weighting"] = (
            "bytes" if abs(s["hit_rate"] - rec_u["byte_weighted_hit_rate"]) < 1e-9
            else ("counts" if abs(s["hit_rate"] - rec_u["count_weighted_hit_rate"]) < 1e-9
                  else "neither"))
    records.append(rec_u)

    payload = {
        "generator": "src/adversarial/verify_l2_r1.py",
        "official_entry": "multicore_cut_evaluate_problem_3.evaluate_problem_3",
        "config_source": "data/raw/a/official/data/config.txt [problem_3]（冻结值）",
        "constants": {
            "bandwidth": BANDWIDTH,
            "cross_core_copy_delay_cycles": CROSS_CORE_COPY_DELAY,
            "cache_capacity_bytes": CACHE_CAPACITY,
            "cache_bandwidth_bytes_per_cycle": CACHE_BANDWIDTH,
            "tensor_size_bytes": SIZE,
        },
        "observations": records,
        "limitations": [
            "只覆盖读只读 Cache 的 COPY_IN 路径；spill/rename 产生的 logical_tid 命中未构造。",
            "微型构造图，不代表官方 case 规模。",
            "未测 CACHE_READ 池在 >=3 个并发命中时的分段换算。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "l2-observations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    for r in records:
        if r["outcome"] != "ok":
            print(f"  {r['case']}: RAISED {r.get('error')}")
            continue
        s = r["cache_stats"]
        print(f"  {r['case']}")
        print(f"     makespan={r['makespan']} hits={s['copy_in_hits']} misses={s['copy_in_misses']}"
              f" hit_bytes={s['hit_bytes']} miss_bytes={s['miss_bytes']} hit_rate={s['hit_rate']}")
        print(f"     memory_paths={ {k: len(v) for k, v in r['memory_paths'].items()} }")
    print("evidence:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
