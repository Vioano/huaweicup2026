"""L2 探针第三批：hit 在飞期间被淘汰 → 完成时重新插入（响应 CACHE-HIT-RETIRE-001）。

队长在冻结源码复核得到一条观察：
`cache_eligible` 只判断 op 类型是 COPY_IN，`retire` 里对**所有**完成的 COPY_IN
无条件调用 `insert_cache`（不区分该 COPY_IN 起飞时是 hit 还是 miss）。
若某个 COPY_IN 起飞时命中（key 已在 Cache），但在它**在飞期间**该 key 被别的插入淘汰，
那么它完成时会重新插入 —— 只在「miss 完成才插入」的简化规则会漏掉这条分支。

本探针构造该形态。全部构造依赖两条已由前批实测确认的机制：
  1. 图输入 tensor（无生产者）会为每个消费核**各自**生成 COPY_IN，且无源核 COPY_OUT 错开
     （verify_l2_r2.py case A）；
  2. 同刻并发的 COPY 平分 DDR 带宽（F-RESOURCE-001）。

构造（两个核、三个图输入 tensor）：
  core0: op1 = CONV(A, size=600)   → COPY_IN(A) 在 t=0 发起
         op2 = CONV(B, size=1)     → COPY_IN(B) 等 op1 完成
  core1: op3 = CONV(C, size=600)   → COPY_IN(C) 在 t=0 发起
         op4 = CONV(A, size=600)   → COPY_IN(A) 等 op3 完成（**第二次使用 A**）

时间轴（依赖实测而非推断，实际值以本脚本输出为准）：
  t=0   COPY_IN(A) 与 COPY_IN(C) 同刻 miss、平分 DDR → 各自 20 cycles，同刻 t=20 完成
  t=20  retire 按 core 顺序：insert A，再 insert C（cache_capacity = 1200 恰好装下两条）
  t=24  COPY_IN(B)（miss，DDR 独占）与 COPY_IN(A)（**hit**，走 CACHE_READ，3 cycles）同刻发起
  t=25  COPY_IN(B) 完成 → insert B 超容量 → 淘汰最旧的 A
  t=27  COPY_IN(A) 完成（它起飞时是 hit）→ A 已不在 Cache → **重新插入**  ← 目标分支

只读调用**冻结官方函数** evaluate_problem_3；未调用队长的 oracle 适配层，未做正式基准与全量验收。
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
CACHE_BANDWIDTH = 250

SIZE_A = 600   # 长寿命：被 core0 的 op1 与 core1 的 op4 两次消费
SIZE_C = 600   # 与 A 同刻并发
SIZE_B = 1     # 极短，用来在 A 的 hit 在飞窗口内完成插入
CACHE = SIZE_A + SIZE_C   # = 1200，恰好装下 A 与 C，插入 B 时必然淘汰最旧的 A


def graph():
    """图输入 tensor A/C/B，A 被两个核各消费一次。"""
    ops = [
        {"id": 1, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 4, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
    ]
    tensors = [
        {"id": 200, "pos": "DDR", "size": SIZE_A},   # A：图输入，被 op1 与 op4 消费
        {"id": 201, "pos": "DDR", "size": SIZE_B},   # B：图输入，只被 op2 消费
        {"id": 202, "pos": "DDR", "size": SIZE_C},   # C：图输入，只被 op3 消费
        {"id": 210, "pos": "UB", "size": SIZE_A},
        {"id": 211, "pos": "UB", "size": SIZE_B},
        {"id": 212, "pos": "UB", "size": SIZE_C},
        {"id": 213, "pos": "UB", "size": SIZE_A},
    ]
    edges = [
        {"source": 200, "target": 1},
        {"source": 1, "target": 210},
        {"source": 210, "target": 2},
        {"source": 201, "target": 2},
        {"source": 2, "target": 211},
        {"source": 202, "target": 3},
        {"source": 3, "target": 212},
        {"source": 212, "target": 4},
        {"source": 200, "target": 4},   # A 的第二次使用
        {"source": 4, "target": 213},
    ]
    plan = {"node_to_subgraph": {"1": 0, "2": 0, "3": 1, "4": 1},
            "core_schedules": [[0], [1]]}
    return {"ops": ops, "tensors": tensors, "edges": edges}, plan


def copy_in_facts(result):
    """从官方 timeline 里抽出每个 COPY_IN 的 (core, op_id, key, size, cache_hit, start, end)。"""
    facts = []
    for core in result.get("per_core_timeline") or []:
        for item in core.get("ops") or []:
            if item.get("op") != "COPY_IN":
                continue
            facts.append({
                "core_id": core.get("core_id"),
                "op_id": item.get("op_id"),
                "memory_path": item.get("memory_path"),
                # Cache key 取自官方 timeline 的 cache_tensor_id（= tensor.get('logical_tid', tid)）
                "key": item.get("cache_tensor_id"),
                "cache_hit": item.get("cache_hit"),
                "start": item.get("start"),
                "end": item.get("end"),
            })
    return facts


def analyse(events, facts):
    """判定是否存在『hit 的 COPY_IN 完成时重新插入自己 key』，并给出三段式证据。

    三段（缺一不可）：
      1. 起飞时 key 在 Cache —— 该 key 在 `start` 之前已有 insert 事件，且没有在起飞前被淘汰；
      2. 在飞期间被淘汰 —— `start < evict_time < end`，淘汰记录在别的 insert 的
         `evicted_tensor_ids` 里；
      3. 完成时重新插入 —— `end` 时刻存在 insert 事件且 `tensor_id == key`。
    """
    inserts = [e for e in events if e.get("event") == "insert"]
    ins_by_key = {}
    evict_by_key = {}          # key -> [被淘汰的时刻]
    for e in inserts:
        ins_by_key.setdefault(e.get("tensor_id"), []).append(e["time"])
        for k in e.get("evicted_tensor_ids") or []:
            evict_by_key.setdefault(k, []).append(e["time"])

    hits = [f for f in facts if f.get("cache_hit") is True]
    reinsert = []
    for f in hits:
        key = f.get("key")
        at_end = [e for e in inserts
                  if e["time"] == f.get("end") and e.get("tensor_id") == key]
        if not at_end:
            continue
        ins_before = [t for t in ins_by_key.get(key, []) if t <= f.get("start")]
        evicted_in_flight = [t for t in evict_by_key.get(key, [])
                             if f.get("start") < t < f.get("end")]
        reinsert.append({
            "core_id": f["core_id"], "op_id": f["op_id"], "key": key,
            "hit_copy_start": f.get("start"), "hit_copy_end": f.get("end"),
            "on_cache_at_takeoff": bool(ins_before),
            "insert_times_for_key_before_takeoff": ins_before,
            "evicted_during_flight_at": evicted_in_flight,
            "reinsert_event": at_end[0],
            "all_three_legs_confirmed": bool(ins_before and evicted_in_flight),
        })
    return {
        "hit_copy_ins": [{"core": f["core_id"], "op_id": f["op_id"], "key": f["key"],
                          "start": f["start"], "end": f["end"]}
                         for f in hits],
        "inserts_by_key": {str(k): v for k, v in sorted(ins_by_key.items(),
                                                        key=lambda kv: str(kv[0]))},
        "evictions_by_key": {str(k): v for k, v in sorted(evict_by_key.items(),
                                                          key=lambda kv: str(kv[0]))},
        "keys_inserted_more_than_once": sorted(
            [k for k, v in ins_by_key.items() if len(v) > 1], key=str),
        "hit_copy_reinserting_at_completion": reinsert,
        "branch_observed": bool(reinsert),
        "all_three_legs_confirmed": any(r["all_three_legs_confirmed"] for r in reinsert),
    }


def run_case(label, graph_obj, plan, cache_bytes, note):
    rec = {"case": label, "note": note, "cache_capacity_bytes": cache_bytes}
    try:
        result = p3.evaluate_problem_3(
            graph_obj, plan, BANDWIDTH, CAPACITY, CROSS_CORE_COPY_DELAY,
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
    rec["copy_in_facts"] = copy_in_facts(result)
    rec.update(analyse(events, rec["copy_in_facts"]))
    rec["cache_final_entries"] = result.get("cache_final_entries")
    rec["cache_used_bytes_final"] = result.get("cache_used_bytes_final")
    return rec


def main():
    records = []

    g, plan = graph()
    records.append(run_case(
        "A) hit copy-in evicted in flight by a shorter copy-in, then re-inserts on retire",
        g, plan, CACHE,
        "cache=SIZE_A+SIZE_C；B 极短 → 在 A 的 hit 在飞窗口内完成并淘汰 A"))

    records.append(run_case(
        "B) control: cache large enough to hold all three keys",
        g, plan, SIZE_A + SIZE_B + SIZE_C,
        "容量足以装下 A/B/C → 不发生淘汰，A 的 hit 完成后插入为幂等（无事件）"))

    records.append(run_case(
        "C) control: cache exactly one tensor, so A never survives to the second use",
        g, plan, SIZE_A,
        "只够一条 → 第二次使用 A 时必然 miss；对照说明 A 是 hit 需要容量条件"))

    payload = {
        "generator": "src/adversarial/verify_l2_r3.py",
        "official_entry": "multicore_cut_evaluate_problem_3.evaluate_problem_3",
        "responds_to": "a-r1-form-adversarial/NikolaStarx/CACHE-HIT-RETIRE-001",
        "claim_under_test": ("所有完成的 COPY_IN 都会调用 insert_cache（含先前 hit）；"
                             "hit 在飞期间 key 被淘汰时，完成会重新插入"),
        "constants": {
            "bandwidth": BANDWIDTH,
            "cross_core_copy_delay_cycles": CROSS_CORE_COPY_DELAY,
            "cache_bandwidth_bytes_per_cycle": CACHE_BANDWIDTH,
            "size_a": SIZE_A, "size_b": SIZE_B, "size_c": SIZE_C,
            "cache_case_a": CACHE,
        },
        "cases": records,
        "limitations": [
            "微型构造图，不代表官方 case 规模。",
            "只验证『完成时无条件 insert_cache』这一条分支形态；"
            "未覆盖 hit 在飞期间被淘汰后又因容量不足而插入失败（size > capacity）的组合。",
            "与 spill/rename 的 logical_tid 交互未在本探针覆盖。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "l2c-observations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in records:
        if r["outcome"] != "ok":
            print(f"  {r['case']}: RAISED {r['error'][:110]}")
            continue
        s = r["cache_stats"]
        print(f"  {r['case']}")
        print(f"     hits={s['copy_in_hits']} misses={s['copy_in_misses']} "
              f"hit_rate={s['hit_rate']} makespan={r['makespan']}")
        print(f"     copy_in_facts={[(f['core_id'], f['op_id'], f['key'], f['cache_hit'], f['start'], f['end']) for f in r['copy_in_facts']]}")
        print(f"     events={[(e['time'], e['event'], e['tensor_id'], e.get('evicted_tensor_ids')) for e in r['cache_events']]}")
        print(f"     keys_inserted_more_than_once={r['keys_inserted_more_than_once']}")
        print(f"     BRANCH OBSERVED={r['branch_observed']} (three_legs={r['all_three_legs_confirmed']})")
        for x in r["hit_copy_reinserting_at_completion"]:
            print(f"        key={x['key']} hit_in=[{x['hit_copy_start']},{x['hit_copy_end']}) "
                  f"on_cache_at_takeoff={x['on_cache_at_takeoff']} "
                  f"evicted_in_flight_at={x['evicted_during_flight_at']} "
                  f"reinsert={x['reinsert_event']}")
    print("evidence:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
