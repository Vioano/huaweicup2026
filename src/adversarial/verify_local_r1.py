"""F-LOCAL 首批探针：Step1 固定排序与 Pipe 并发槽。

只读调用官方 schedule_step1.step1_schedule 与 schedule_step3 的公开常量，
不改动官方材料，不做任何 E0 评分。
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
import schedule_step3 as s3  # noqa: E402


def chain(bid, tid, op_type="CONV"):
    """一条 COPY_IN -> op -> COPY_OUT 的链，id 由 base 偏移决定。"""
    o_in, o_mid, o_out = bid, bid + 1, bid + 2
    t_src, t_mid, t_dst = tid, tid + 1, tid + 2
    ops = [
        {"id": o_in, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": o_mid, "op": op_type, "pipe": "PIPE_M", "cycles": 4},
        {"id": o_out, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
    ]
    tensors = [
        {"id": t_src, "pos": "DDR", "size": 64},
        {"id": t_mid, "pos": "L1", "size": 64},
        {"id": t_dst, "pos": "UB", "size": 64},
    ]
    edges = [
        {"source": t_src, "target": o_in},
        {"source": o_in, "target": t_mid},
        {"source": t_mid, "target": o_mid},
        {"source": o_mid, "target": t_dst},
        {"source": t_dst, "target": o_out},
    ]
    return ops, tensors, edges


def two_independent_chains():
    """两条结构完全相同、只有 id 不同的独立链。

    预测：Step1 是对 sinks 做多源反向 DFS，起始按 start_key=(¬is_copy_out, depth, -id)
    升序压栈后 LIFO 弹栈，因此**较小 id 的链先被访问**。
    """
    ops, tensors, edges = chain(1, 100)
    ops2, tensors2, edges2 = chain(11, 200)
    return {"ops": ops + ops2, "tensors": tensors + tensors2, "edges": edges + edges2}


def fork_from_shared_input():
    """单一 COPY_IN 后分叉出两个 CONV，各接一个 COPY_OUT。

    两个 CONV 深度相同，唯一区别是 id。预测主循环里同深度时 **较大 id 先访问**。
    """
    ops = [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 5, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 4, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
        {"id": 6, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
    ]
    tensors = [
        {"id": 100, "pos": "DDR", "size": 64},
        {"id": 101, "pos": "L1", "size": 64},
        {"id": 102, "pos": "UB", "size": 64},
        {"id": 103, "pos": "UB", "size": 64},
        {"id": 104, "pos": "DDR", "size": 64},
        {"id": 105, "pos": "DDR", "size": 64},
    ]
    edges = [
        {"source": 100, "target": 1},
        {"source": 1, "target": 101},
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 102, "target": 4},
        {"source": 4, "target": 104},
        {"source": 101, "target": 5},
        {"source": 5, "target": 103},
        {"source": 103, "target": 6},
        {"source": 6, "target": 105},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def join_two_preds(copy_in_branch=False):
    """一个 JOIN 节点，两个同深度的前驱。

    op7 同时消费 t102(来自 op2) 与 t103(来自 op5 或 op1)。
    copy_in_branch=False 时两个前驱都是 CONV(2 与 5)，只比 id；
    copy_in_branch=True 时把其中一个前驱换成 COPY_IN，用来观察
    key 首段 (¬is_copy_in) 的实际作用方向。
    """
    ops = [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 5, "op": "CONV" if not copy_in_branch else "COPY_IN",
         "pipe": "PIPE_MTE2" if copy_in_branch else "PIPE_M", "cycles": 4},
        {"id": 7, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 8, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
    ]
    tensors = [
        {"id": 100, "pos": "DDR", "size": 64},
        {"id": 101, "pos": "L1", "size": 64},
        {"id": 102, "pos": "UB", "size": 64},
        {"id": 103, "pos": "UB", "size": 64},
        {"id": 104, "pos": "UB", "size": 64},
        {"id": 105, "pos": "DDR", "size": 64},
    ]
    edges = [
        {"source": 100, "target": 1},
        {"source": 1, "target": 101},
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 101, "target": 5},
        {"source": 5, "target": 103},
        {"source": 102, "target": 7},
        {"source": 103, "target": 7},
        {"source": 7, "target": 104},
        {"source": 104, "target": 8},
        {"source": 8, "target": 105},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def join_copy_in_vs_conv():
    """同深度下 COPY_IN 与 CONV 竞争同一个 JOIN 节点。

    t101 没有任何生产者，op2(CONV) 直接消费它，因此 op2 的 depth 与 op1(COPY_IN) 相同，
    两者都不是对方的前驱——这才是对 key 首段 (¬is_copy_in) 的干净对照。
    """
    ops = [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 7, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 8, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
    ]
    tensors = [
        {"id": 100, "pos": "DDR", "size": 64},
        {"id": 101, "pos": "L1", "size": 64},
        {"id": 102, "pos": "UB", "size": 64},
        {"id": 103, "pos": "L1", "size": 64},
        {"id": 104, "pos": "UB", "size": 64},
        {"id": 105, "pos": "DDR", "size": 64},
    ]
    edges = [
        {"source": 100, "target": 1},
        {"source": 1, "target": 103},
        # t101 无生产者，op2 因此是源节点之一
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 102, "target": 7},
        {"source": 103, "target": 7},
        {"source": 7, "target": 104},
        {"source": 104, "target": 8},
        {"source": 8, "target": 105},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def two_sinks_one_copy_out():
    """两个同深度的 sink，其中一个是 COPY_OUT、另一个不是。

    两条链都是 3 个算子，因此 sink 深度相同：
      P: COPY_IN(1) -> CONV(2) -> COPY_OUT(3)   sink=3 是 COPY_OUT
      Q: COPY_IN(11) -> CONV(12) -> CONV(13)    sink=13 不是 COPY_OUT
    用于隔离 start_key 首段 (¬is_copy_out) 的作用方向。
    """
    ops = [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
        {"id": 11, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 12, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 13, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
    ]
    tensors = [
        {"id": 100, "pos": "DDR", "size": 64},
        {"id": 101, "pos": "L1", "size": 64},
        {"id": 102, "pos": "UB", "size": 64},
        {"id": 103, "pos": "DDR", "size": 64},
        {"id": 200, "pos": "DDR", "size": 64},
        {"id": 201, "pos": "L1", "size": 64},
        {"id": 202, "pos": "UB", "size": 64},
        {"id": 203, "pos": "UB", "size": 64},
    ]
    edges = [
        {"source": 100, "target": 1},
        {"source": 1, "target": 101},
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 102, "target": 3},
        {"source": 3, "target": 103},
        {"source": 200, "target": 11},
        {"source": 11, "target": 201},
        {"source": 201, "target": 12},
        {"source": 12, "target": 202},
        {"source": 202, "target": 13},
        {"source": 13, "target": 203},
    ]
    return {"ops": ops, "tensors": tensors, "edges": edges}


def main():
    records = []

    g1 = two_independent_chains()
    seq1 = step1_schedule(g1)
    records.append({
        "case": "two independent chains, identical structure, ids 1-3 vs 11-13",
        "graph_ops": [o["id"] for o in g1["ops"]],
        "seq": seq1,
        "note": "两条链结构完全相同，只有 id 不同；用于观察 sink 侧起始顺序",
        "first_emitted": seq1[0] if seq1 else None,
    })

    g2 = fork_from_shared_input()
    seq2 = step1_schedule(g2)
    pos2 = {op: i for i, op in enumerate(seq2)}
    records.append({
        "case": "one COPY_IN forks into op2 and op5 (equal depth, ids 2 vs 5)",
        "graph_ops": [o["id"] for o in g2["ops"]],
        "seq": seq2,
        "position_of_op2": pos2.get(2),
        "position_of_op5": pos2.get(5),
        "smaller_id_emitted_first": (pos2.get(2, 1 << 30) < pos2.get(5, 1 << 30)),
    })

    g3 = join_two_preds(copy_in_branch=False)
    seq3 = step1_schedule(g3)
    pos3 = {op: i for i, op in enumerate(seq3)}
    records.append({
        "case": "JOIN op7 with two CONV preds op2 and op5 (equal depth)",
        "graph_ops": [o["id"] for o in g3["ops"]],
        "seq": seq3,
        "position_of_op2": pos3.get(2),
        "position_of_op5": pos3.get(5),
        "smaller_id_emitted_first": (pos3.get(2, 1 << 30) < pos3.get(5, 1 << 30)),
    })

    g4 = join_copy_in_vs_conv()
    seq4 = step1_schedule(g4)
    pos4 = {op: i for i, op in enumerate(seq4)}
    records.append({
        "case": "JOIN op7 with preds op1(COPY_IN) and op2(CONV), equal depth, no ancestor relation",
        "graph_ops": [o["id"] for o in g4["ops"]],
        "seq": seq4,
        "position_of_conv2": pos4.get(2),
        "position_of_copyin1": pos4.get(1),
        "copy_in_emitted_first": (pos4.get(1, 1 << 30) < pos4.get(2, 1 << 30)),
    })

    g5 = two_sinks_one_copy_out()
    seq5 = step1_schedule(g5)
    pos5 = {op: i for i, op in enumerate(seq5)}
    records.append({
        "case": "two equal-depth sinks: op3(COPY_OUT) vs op13(CONV)",
        "graph_ops": [o["id"] for o in g5["ops"]],
        "seq": seq5,
        "position_of_copy_out_sink": pos5.get(3),
        "position_of_conv_sink": pos5.get(13),
        "copy_out_sink_branch_emitted_first": (pos5.get(3, 1 << 30) < pos5.get(13, 1 << 30)),
    })

    payload = {
        "generator": "src/adversarial/verify_local_r1.py",
        "official_entries": [
            "schedule_step1.step1_schedule",
            "schedule_step3.PIPES / PIPE_SLOTS",
        ],
        "pipe_constants": {
            "PIPES": list(s3.PIPES),
            "PIPE_SLOTS": s3.PIPE_SLOTS,
        },
        "observations": records,
        "limitations": [
            "只覆盖微型构造图；未在正式 case 上比较 Step1 序列。",
            "未验证 Step3 内存依赖与 spill 对最终序列的影响。",
            "未验证 Step2 spill 插入后序列的变化（属另一组缺口）。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "local-observations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    print("PIPES:", list(s3.PIPES), "| PIPE_SLOTS:", s3.PIPE_SLOTS)
    for r in records:
        print(f"  {r['case']}")
        print(f"     seq = {r['seq']}")
    print("evidence:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
