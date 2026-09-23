"""spill 探针（第二次尝试）：构造出「当前 op 不使用的存活 tensor」作为可淘汰对象。

第一次尝试（verify_spill_r1.py）的三种拓扑都失败，原因是触发超容量的那个 step 上
「所有驻留 tensor 都被当前 op 使用」，victim 候选集为空，于是抛
Step2SchedulingError: no spill victim。

本探针针对性地构造：
  t102(A) 与 t103(B) 都是长寿命驻留项；
  触发 step 的 op4 只消费 A、只产出 C；
  B 在 op4 处**不被使用**但仍有未来使用（op5），因此是可淘汰候选。

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
from schedule_step3 import prepare_step3_execution  # noqa: E402

BANDWIDTH = 60
SIZE = 64  # 每个 UB tensor 64 字节


def graph_v1():
    """第一次针对性构造（**失败**，保留作为记录）。

    设想 op4 只消费 t102、t103 在 op4 处闲置。实际 seq=[1,2,4,3,5]，
    op3 排在 op4 之后，所以 op4 那一刻 t103 还没被产出，active 只有 [102,104]，
    victim 候选为空。教训：可淘汰对象必须在触发 step **之前**就已经产出。
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
        {"id": 102, "pos": "UB", "size": SIZE},
        {"id": 103, "pos": "UB", "size": SIZE},
        {"id": 104, "pos": "UB", "size": SIZE},
        {"id": 105, "pos": "UB", "size": SIZE},
    ]
    edges = [
        {"source": 100, "target": 1},
        {"source": 1, "target": 101},
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 101, "target": 3},
        {"source": 3, "target": 103},
        {"source": 102, "target": 4},
        {"source": 4, "target": 104},
        {"source": 103, "target": 5},
        {"source": 5, "target": 105},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def graph_v2():
    """第二次构造：t102 是**跨步多次消费**的长寿命项。

    t102 被 op4（早）与 op6（晚）各消费一次，因此在 op5 那一刻它仍然驻留
    且 **op5 不使用它** —— 这是真正的可淘汰候选。
      op2 -> t102 (A)          A 被 op4 与 op6 使用
      op4 使用 A -> t104
      op5 使用 t103 -> t105    ← 触发 step，不使用 A
      op6 使用 A 与 t104 -> t106
    """
    ops = [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 4, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 5, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 6, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
    ]
    tensors = [
        {"id": 100, "pos": "DDR", "size": SIZE},
        {"id": 101, "pos": "L1", "size": SIZE},
        {"id": 102, "pos": "UB", "size": SIZE},   # A：跨步多次消费 → 长寿命
        {"id": 103, "pos": "UB", "size": SIZE},   # B
        {"id": 104, "pos": "UB", "size": SIZE},   # op4 的产出
        {"id": 105, "pos": "UB", "size": SIZE},   # op5 的产出
        {"id": 106, "pos": "UB", "size": SIZE},   # op6 的产出
    ]
    edges = [
        {"source": 100, "target": 1},
        {"source": 1, "target": 101},
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 101, "target": 3},
        {"source": 3, "target": 103},
        {"source": 102, "target": 4},     # A 的第一次使用
        {"source": 4, "target": 104},
        {"source": 103, "target": 5},
        {"source": 5, "target": 105},
        {"source": 102, "target": 6},     # A 的第二次使用 → 保持存活
        {"source": 104, "target": 6},
        {"source": 6, "target": 106},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def graph_v3():
    """第三次构造（**失败**，保留作为记录）。

    让长寿命 L(t102) 的最后一次使用与链尾 op8 重合。结果 op8 那一步
    active={102,107,108} 而 current 也是这三项，victim 候选为空 →
    'no spill victim: step=7 op=8'。
    教训：**链尾不能同时消费 L 与上一环**。
    """
    ops = [{"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0}]
    for i in range(2, 9):
        ops.append({"id": i, "op": "CONV", "pipe": "PIPE_M", "cycles": 4})
    tensors = [
        {"id": 100, "pos": "DDR", "size": SIZE},
        {"id": 101, "pos": "L1", "size": SIZE},
    ]
    for t in range(102, 109):
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
        {"source": 102, "target": 8},
        {"source": 107, "target": 8},
        {"source": 8, "target": 108},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def graph_v4():
    """第四次构造（**成功**）：把 L 的最后一次使用推到链尾**之后**。

      op1 -> t101(L1)
      op2 -> t102(L)            L 的使用：op3、op9
      op3..op7: 环形链 t103..t107
      op8: t107 -> t108         链尾，只消费 t107、只产出 t108（三项全当前？不——L 此时已不在驻留）
      op9: t102 -> t109         L 的末次使用，是 L 唯一的 future use

    关键：链尾 op8 只消费上一环，因此那一步的 active 里不会有"全是被当前 op 使用"的三项。
    L 在 op4 首次溢出时被换出，之后直到 op9 才换回，于是中段驻留量回落到 2 个 tensor。
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
        {"source": 2, "target": 102},   # L
        {"source": 102, "target": 3},   # L 第一次使用
        {"source": 3, "target": 103},
        {"source": 103, "target": 4},
        {"source": 4, "target": 104},
        {"source": 104, "target": 5},
        {"source": 5, "target": 105},
        {"source": 105, "target": 6},
        {"source": 6, "target": 106},
        {"source": 106, "target": 7},
        {"source": 7, "target": 107},
        {"source": 107, "target": 8},   # 链尾：只消费上一环
        {"source": 8, "target": 108},
        {"source": 102, "target": 9},   # L 末次使用，晚于链尾
        {"source": 9, "target": 109},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def main():
    g = graph_v4()
    seq = step1_schedule(g)
    ub = [t for t in g["tensors"] if t["pos"] == "UB"]
    total_ub = sum(t["size"] for t in ub)

    records = []
    # 扫掠 UB 容量：链上峰值驻留为 3 个 UB tensor（192），中段回落到 2 个（128）
    for cap_ub in (131072, 256, 192, 191, 128, 64):
        rec = {"capacity_ub": cap_ub, "capacity": {"L1": 524288, "UB": cap_ub}}
        try:
            result = step2_spill_insertion(g, seq, capacity={"L1": 524288, "UB": cap_ub})
        except Exception as exc:  # noqa: BLE001
            rec["outcome"] = "raised"
            rec["error"] = f"{type(exc).__name__}: {exc}"
            records.append(rec)
            continue
        spills = result.get("spill_records") or []
        rec["outcome"] = "completed"
        rec["n_spills"] = len(spills)
        # 原样保留官方 spill 记录的全部字段，避免漏掉判据
        rec["spill_records"] = [dict(s) for s in spills]
        rec["overflow_log"] = result.get("overflow_log")
        rec["seq_ext"] = result.get("seq_ext")
        rec["new_tensors"] = result.get("new_tensors")
        rec["new_ops"] = result.get("new_ops")
        rec["n_rename_records"] = len(result.get("rename_records") or [])
        rec["_has_rename_records_key"] = "rename_records" in result
        # 验证重命名化身是否保留 logical_tid，从而决定 L2 的 cache key 是否跨 rename 稳定
        if spills:
            victim_tid = spills[0]["tid"]
            ext = _build_extended_graph(g, result)
            renamed = [
                t for t in ext["tensors"]
                if t.get("logical_tid") is not None and t.get("logical_tid") != t["id"]
            ]
            rec["renamed_tensors"] = renamed
            prepared = prepare_step3_execution(
                ext, capacity=rec["capacity"], bandwidth=BANDWIDTH)
            keys = {}
            for t in prepared["graph"]["tensors"]:
                if t["id"] == victim_tid or (t.get("logical_tid") == victim_tid):
                    keys[str(t["id"])] = {
                        "pos": t.get("pos"), "size": t.get("size"),
                        "logical_tid": t.get("logical_tid"),
                        "cache_key_if_copy_in_out_tid": t.get("logical_tid", t["id"]),
                    }
            rec["victim_and_renamed_cache_keys"] = keys
        records.append(rec)

    payload = {
        "generator": "src/adversarial/verify_spill_r2.py",
        "purpose": ("取得含 >=1 spill 的成功运行。关键构造：长寿命 L 必须"
                    "(a) 在触发 step 之前已产出、(b) 在触发 step 有 future use、"
                    "(c) **不被触发 step 的 op 使用**；且链尾不能同时消费 L 与上一环"),
        "victim_selection_rule": ("trigger_one_spill 取 type_active 中 next_use 非 None 的项，"
                                  "再排除 current_step_tids，最后按 -next_use 排序取第一个"
                                  "（Belady：换出最远未来才用到的）"),
        "v1_failure_note": "seq=[1,2,4,3,5]：op3 排在 op4 之后，op4 时 active 只有 [102,104]",
        "v2_failure_note": "seq=[1,2,4,6,3,5]：触发点是 op6，active 三项全被 op6 使用",
        "v3_failure_note": "L 的末次使用与链尾 op8 重合，该步 active 与 current 完全相同",
        "graph_ops": [o["id"] for o in g["ops"]],
        "seq": seq,
        "ub_tensor_count": len(ub),
        "ub_bytes_total": total_ub,
        "records": records,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "spill2-observations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    print("seq:", seq, "| UB tensors:", len(ub), "total bytes:", total_ub)
    for r in records:
        if r["outcome"] == "completed":
            print(f"  capUB={r['capacity_ub']:<7} spills={r['n_spills']:<3} "
                  f"overflow={r['overflow_log']}")
            for s in r["spill_records"]:
                print(f"        victim tid={s['tid']} size={s['size']} "
                      f"prev_use_step={s['prev_use_step']} next_use_step={s['next_use_step']} "
                      f"prev_use_op={s['prev_use_op']} next_use_op={s['next_use_op']} "
                      f"to_tid={s['to_tid']} v{s['version']} "
                      f"copies_data={s['spill_out_copies_data']}")
            print(f"        seq_ext={r.get('seq_ext')}")
            print(f"        new_ops={[(o.get('id'), o.get('op')) for o in (r.get('new_ops') or [])]}")
            print(f"        renamed={[(t.get('id'), t.get('logical_tid'), t.get('version')) for t in (r.get('renamed_tensors') or [])]}")
            print(f"        cache_keys={r.get('victim_and_renamed_cache_keys')}")
        else:
            print(f"  capUB={r['capacity_ub']:<7} RAISED {r['error'][:110]}")
    print("evidence:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
