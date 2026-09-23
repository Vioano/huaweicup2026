"""F-LOCAL-006 探针：Step3 的内存复用边（virtual quota / free_credits）。

机制（读源码得到，本探针负责实测）：
  - 每个被释放的 tensor 变成一笔“可复用额度”（free_credits），带字节数与 sources；
    sources = 该 tensor 的消费者（kind=WAR）；若无消费者则取生产者（kind=WAW）。
  - 分配新输出时从额度里扣减；对每笔 sources 中 != 当前 producer 的 source_op，
    记一条 (source_op -> producer_op) 的内存依赖。
  - 额度按 FIFO 取用（credits[0] / pop(0)）；初始未用容量记为 kind=VIRGIN、sources 为空，
    因此不产生依赖边。
  - 这些依赖随后被物化成 execution_graph 的普通边，带 `dependency: 'MEMORY_REUSE'`。

只读调用**冻结官方函数** schedule_step2/3，不改动官方材料；未调用队长的 oracle 适配层，未做正式基准与全量验收。
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

from schedule_step1 import step1_schedule  # noqa: E402
from schedule_step2 import step2_spill_insertion, _build_extended_graph  # noqa: E402
import schedule_step3 as s3  # noqa: E402

BANDWIDTH = 60
SIZE = 64


def graph_wa_w_and_war():
    """同时制造 WAW 与 WAR 两种复用来源。

      op1 COPY_IN        t100 -> t101(L1)
      op2 CONV           t101 -> t102(UB)   死输出（无消费者）→ 释放时 kind=WAW, sources=(op2,)
      op3 CONV           t101 -> t103(UB)   消费 t102? 不——见下
      op4 CONV           t101 -> t104(UB)

    为了让 WAR 出现，再让 t102 有一个消费者 op5：
      op5 CONV 消费 t102 -> t106(UB)          t102 释放时 sources=(op5,) kind=WAR
    op3 / op4 与 t102 无数据依赖，因此它们与 op2/op5 之间的复用边是**新增**边。
    """
    ops = [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 4, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 5, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
    ]
    tensors = [
        {"id": 100, "pos": "DDR", "size": SIZE},
        {"id": 101, "pos": "L1", "size": SIZE},
        {"id": 102, "pos": "UB", "size": SIZE},   # 被 op5 消费 → WAR 来源
        {"id": 103, "pos": "UB", "size": SIZE},
        {"id": 104, "pos": "UB", "size": SIZE},
        {"id": 106, "pos": "UB", "size": SIZE},   # 死输出
    ]
    edges = [
        {"source": 100, "target": 1},
        {"source": 1, "target": 101},
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 101, "target": 3},
        {"source": 3, "target": 103},
        {"source": 101, "target": 4},
        {"source": 4, "target": 104},
        {"source": 102, "target": 5},     # t102 有消费者 → WAR
        {"source": 5, "target": 106},     # t106 无消费者 → WAW
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def run_case(label, graph, capacity):
    rec = {"case": label, "capacity": capacity}
    seq = step1_schedule(graph)
    rec["seq"] = seq
    try:
        step2 = step2_spill_insertion(graph, seq, capacity=capacity)
        ext = _build_extended_graph(graph, step2)
        sim = s3.step3_simulation(ext, capacity=capacity, bandwidth=BANDWIDTH)
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "raised"
        rec["error"] = f"{type(exc).__name__}: {exc}"
        return rec
    rec["outcome"] = "ok"
    deps = sim.get("memory_dependencies") or []
    rec["memory_dependencies"] = deps
    rec["n_memory_dependencies"] = len(deps)
    rec["memory_peak"] = sim.get("memory_peak")
    rec["makespan_local"] = sim.get("makespan")
    # 物化后的 execution_graph 中带 MEMORY_REUSE 标记的边
    exec_graph = sim.get("execution_graph") or {}
    rec["memory_reuse_edges"] = sorted(
        (e["source"], e["target"]) for e in exec_graph.get("edges", [])
        if e.get("dependency") == "MEMORY_REUSE"
    )
    rec["real_data_edges"] = sorted(
        (e["source"], e["target"]) for e in exec_graph.get("edges", [])
        if e.get("dependency") != "MEMORY_REUSE"
    )
    return rec


def main():
    g = graph_wa_w_and_war()
    records = [
        # 容量刚好 1 个 UB tensor：强制复用，应出现内存依赖
        run_case("UB capacity == 1 tensor (forces reuse)", g, {"L1": 524288, "UB": SIZE}),
        # 容量 2 个：仍可能复用一部分
        run_case("UB capacity == 2 tensors", g, {"L1": 524288, "UB": 2 * SIZE}),
        # 容量充裕：全部走 VIRGIN 额度，不应产生内存依赖边
        run_case("UB capacity large (VIRGIN credits only)", g, {"L1": 524288, "UB": 131072}),
    ]

    reused_any = any(r.get("n_memory_dependencies", 0) > 0 for r in records)
    virgin_only = [r for r in records
                   if r.get("outcome") == "ok" and r.get("n_memory_dependencies", 0) == 0]

    payload = {
        "generator": "src/adversarial/verify_local2_r1.py",
        "official_entries": [
            "schedule_step3.step3_simulation",
            "schedule_step2._build_extended_graph",
        ],
        "mechanism_from_source": {
            "add_free_credit": "sources = consumers if consumers else producers; "
                               "kind = 'WAR' if consumers else 'WAW'",
            "virgin_credit": "{'kind': 'VIRGIN', 'sources': ()} —— 初始未用容量",
            "consume_free_credit": "FIFO 取 credits[0]；对每个 source_op != producer_op "
                                   "记 (source_op -> producer_op) 依赖",
            "materialization": "memory_dependencies -> execution_graph 边，"
                               "带 dependency='MEMORY_REUSE'；已存在的边不重复添加",
        },
        "cases": records,
        "reuse_observed": reused_any,
        "cases_without_memory_dependency": len(virgin_only),
        "limitations": [
            "微型构造图；未覆盖额度被拆分/合并的复杂情形。",
            "未核对 memory_peak 的取值口径是否与题面一致。",
            "未覆盖跨多类型（L1 与 UB 同时）复用的交互。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "local2-observations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in records:
        if r["outcome"] != "ok":
            print(f"  {r['case']}: RAISED {r['error'][:100]}")
            continue
        print(f"  {r['case']}")
        print(f"     seq={r['seq']} n_mem_deps={r['n_memory_dependencies']} peak={r['memory_peak']}")
        for d in r["memory_dependencies"]:
            print(f"       dep {d['source']} -> {d['target']} kind={d['kind']} "
                  f"reused={d['reused_bytes']} prev_tensors={d['previous_tensor_ids']} "
                  f"pos={d['positions']}")
        print(f"     MEMORY_REUSE edges: {r['memory_reuse_edges']}")
    print(f"reuse observed: {reused_any} | cases with 0 mem-dep: {len(virgin_only)}")
    print("evidence:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
