"""交叉复核 LYX 首批 E1（PR20 固定提交 3357d7e）—— 定向差分。

背景（队长交接 FAST-CODE-AVAILABLE-001）：E1 用 indexed Task-boundary 改写替换官方
`_build_scene_a_tasks`。队长已用 64 个保存候选 + 169 个**通用**微型输入（乱序 ID、零字节/
周期、多消费者、空核、缺失映射、非连续合并）做过有限复核，未发现差分。

本脚本不重复上述通用覆盖，而是用本人在 FORM 任务里**已由探针实测**的规则来定向构造：
  - F-METRIC-001 原图 COPY_IN/COPY_OUT 是独立流量基线
  - F-TASK-003  跨 Task 流量按「远端消费 Task 数」累加
  - F-TASK-001  边界 COPY 的新 ID 分配（避开 op/tensor 两类已占用空间）
  - F-TASK-002  Task 内 DDR tensor 被改写为 UB（`pos` 改写）
  - F-PLAN-005  商图成环的拒绝路径
  - F-LOCAL-001 Step1 排序对局部图敏感

改写的关键等价性前提已由代码阅读确认：`derive_multicore_plan` 里
`nodes_by_subgraph` 是 `mapping` 的**严格反向构造**，因此官方用 `task_op_ids`
（= nodes_by_subgraph 集合）与改写用 `mapping.get(op)` 判定「是否属于本 Task」等价。

用法（需要 LYX 检出与本人 worktree 同时存在）：
    python src/adversarial/verify_lyx_cross_r1.py

只读调用：不修改 LYX 检出的任何文件；不写其 results/。证据写入本人 results 目录。
"""
from __future__ import annotations

import collections
import json
import os
import random
import sys
from pathlib import Path

MINE = Path(__file__).resolve().parents[2]
# 被复核的 LYX 检出与固定提交可通过环境变量切换，便于对方用同一脚本自证：
#   LYX_DIR=<独立 worktree 路径> LYX_SHA=<固定提交> SKIP_OFFICIAL=1 python src/adversarial/verify_lyx_cross_r1.py
LYX = Path(os.environ.get("LYX_DIR", "C:/Users/Dora/Desktop/数学建模/Workbuddy/_a-r1/lyx-3357d7e"))
LYX_SHA = os.environ.get("LYX_SHA", "3357d7ef9c1ad443dd0799f6ecb5b813df6753b3")
SKIP_OFFICIAL = os.environ.get("SKIP_OFFICIAL", "") == "1"
# SKIP_OFFICIAL 模式下默认写到 -partial 后缀，避免把上一轮的全量产物**静默覆盖**成缩减版
# （本脚本首版即因此覆盖过一次：官方 case 由 6 条降为 3 条）。
OUT_SUFFIX = os.environ.get("OUT_SUFFIX", "-partial" if SKIP_OFFICIAL else "")
OUT_DIR = MINE / "results/a/form/r1-20260923-farmeruncle123"
CASE_DIR = MINE / "data/raw/a/official/data"
BANDWIDTH = 60
CAPACITY = {"L1": 524288, "UB": 131072}
CROSS_CORE_WAIT = 1000
SAME_CORE_WAIT = 100

sys.dont_write_bytecode = True
sys.path.insert(0, str(LYX))

from src.eval_exact._official import load_problem1  # noqa: E402
import src.eval_exact.problem1 as e1_module  # noqa: E402  加载即完成改写替换

E1 = e1_module                      # 改写版
E0 = load_problem1("_e0_reference_farmeruncle_cross_review")  # 另加载一份**未改写**的官方实例


# ---------------------------------------------------------------- 比较工具

def diff(a, b, path="$", out=None, limit=40):
    """递归比较两个对象，收集差异（含类型差异）。"""
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    if type(a) is not type(b):
        out.append({"path": path, "kind": "type",
                    "e0": f"{type(a).__name__}", "e1": f"{type(b).__name__}"})
        return out
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                out.append({"path": f"{path}.{k}", "kind": "missing_in_e0"})
            elif k not in b:
                out.append({"path": f"{path}.{k}", "kind": "missing_in_e1"})
            else:
                diff(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, (list, tuple)):
        if len(a) != len(b):
            out.append({"path": path, "kind": "length", "e0": len(a), "e1": len(b)})
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, limit)
    else:
        if a != b:
            out.append({"path": path, "kind": "value", "e0": repr(a)[:120], "e1": repr(b)[:120]})
    return out


def call(fn, graph, plan, bandwidth=BANDWIDTH, capacity=CAPACITY):
    """调用一次评估，把结果归一化为可比对象；异常归一为 (err, type, msg)。"""
    try:
        return ("ok", fn(graph, plan, bandwidth, capacity, CROSS_CORE_WAIT, SAME_CORE_WAIT))
    except Exception as exc:  # noqa: BLE001
        return ("raised", type(exc).__name__, str(exc))


def task_summary(prepared):
    """把 `prepare_step3_execution` 的返回抽成可比较摘要（保留 graph 全集）。"""
    graph = prepared.get("graph") or {}
    return {
        "core_id": prepared.get("core_id"),
        "task_id": prepared.get("task_id"),
        "pred_tasks": prepared.get("pred_tasks"),
        "seq": prepared.get("seq"),
        "graph_ops": graph.get("ops"),
        "graph_tensors": graph.get("tensors"),
        "graph_edges": graph.get("edges"),
    }


def task_build_diff(graph, plan, bandwidth=BANDWIDTH, capacity=CAPACITY):
    """直接比较改写产物：官方 `_build_scene_a_tasks` vs `_build_scene_a_tasks_indexed`。

    比端到端更敏感——能定位到 Task 局部图（边界 COPY 的 ID、pos 改写、edges）这一层。
    """
    g0 = json.loads(json.dumps(graph))
    g1 = json.loads(json.dumps(graph))
    try:
        t0, ctt0, tr0, pv0 = E0._build_scene_a_tasks(g0, plan, bandwidth, capacity)
    except Exception as exc:  # noqa: BLE001
        return {"outcome": "e0_raised", "error": f"{type(exc).__name__}: {exc}"}
    try:
        t1, ctt1, tr1, pv1 = E1._build_scene_a_tasks_indexed(g1, plan, bandwidth, capacity)
    except Exception as exc:  # noqa: BLE001
        return {"outcome": "e1_raised", "error": f"{type(exc).__name__}: {exc}"}

    diffs = []
    diff(ctt0, ctt1, "$.cross_task_traffic", diffs)
    diff(tr0, tr1, "$.traffic", diffs)
    diff(pv0, pv1, "$.plan_view", diffs)
    s0 = {k: task_summary(v) for k, v in t0.items()}
    s1 = {k: task_summary(v) for k, v in t1.items()}
    diff(s0, s1, "$.tasks", diffs)
    return {
        "outcome": "identical" if not diffs else "DIFFER",
        "differences": diffs[:20],
        "n_task_diffs": len(diffs),
        "cross_task_traffic": ctt0,
        "traffic": tr0,
    }


def assess(label, graph, plan, note, bandwidth=BANDWIDTH, capacity=CAPACITY):
    """对同一 (graph, plan) 比较 E0 与 E1 的完整输出对象。"""
    rec = {"case": label, "note": note,
           "bandwidth": bandwidth, "capacity": capacity}
    g0 = json.loads(json.dumps(graph))
    g1 = json.loads(json.dumps(graph))
    r0 = call(E0.evaluate_scene_a, g0, plan, bandwidth, capacity)
    r1 = call(E1.evaluate_scene_a, g1, plan, bandwidth, capacity)
    rec["e0_status"] = r0[0]
    rec["e1_status"] = r1[0]
    if r0[0] != r1[0]:
        rec["outcome"] = "DIFFER"
        rec["detail"] = {"e0": str(r0)[:200], "e1": str(r1)[:200]}
        return rec
    if r0[0] == "raised":
        rec["outcome"] = "both_raised"
        rec["e0_error"] = f"{r0[1]}: {r0[2]}"
        rec["e1_error"] = f"{r1[1]}: {r1[2]}"
        rec["error_kind_agrees"] = (r0[1] == r1[1])
        rec["error_message_agrees"] = (r0[2] == r1[2])
        return rec
    d = diff(r0[1], r1[1])
    tbd = task_build_diff(graph, plan, bandwidth, capacity)
    rec["task_builder"] = tbd["outcome"]
    if tbd["outcome"] == "DIFFER":
        rec["outcome"] = "DIFFER"
        rec["differences"] = d + tbd["differences"]
        return rec
    rec["outcome"] = "identical" if not d else "DIFFER"
    if d:
        rec["differences"] = d
    rec["makespan_e0"] = r0[1].get("makespan")
    rec["cross_task_traffic"] = tbd.get("cross_task_traffic")
    return rec


# ---------------------------------------------------------------- 图构造工具

def g_of(ops, tensors, edges):
    return {"ops": ops, "tensors": tensors, "edges": edges}


def one_op_per_subgraph_plan(graph, ncores=2):
    """每个非 COPY op 一个子图，按全局拓扑序依次分核 → 保证同核顺序合法、商图无环。"""
    ops = [op for op in graph["ops"] if op.get("op") not in ("COPY_IN", "COPY_OUT")]
    op_ids = [op["id"] for op in ops]
    order = topo_order(graph, op_ids)
    mapping = {op_id: index for index, op_id in enumerate(order)}
    schedules = [[] for _ in range(ncores)]
    for index in range(len(order)):
        schedules[index % ncores].append(index)
    return {"node_to_subgraph": mapping, "core_schedules": schedules}


def topo_order(graph, node_ids):
    ids = set(node_ids)
    succs = {n: set() for n in node_ids}
    indeg = {n: 0 for n in node_ids}
    for edge in graph["edges"]:
        s, t = edge["source"], edge["target"]
        if s in ids and t in ids and s != t:
            if t not in succs[s]:
                succs[s].add(t)
                indeg[t] += 1
    ready = sorted(n for n in node_ids if indeg[n] == 0)
    out = []
    while ready:
        n = ready.pop(0)
        out.append(n)
        for m in sorted(succs[n]):
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
                ready.sort()
    if len(out) != len(node_ids):
        raise ValueError("constructed graph has a cycle")
    return out


def block_plan(graph, ncores=2, block_size=8):
    """按全局拓扑序连续切成 block_size 大小的子图，round-robin 分核。

    连续切分保证子图商图无环；round-robin 后同核内子图序号递增，故同核顺序合法。
    用于把官方大 case 压到可跑的规模（每 op 一子图会构造上千个 Task）。
    """
    ops = [op for op in graph["ops"] if op.get("op") not in ("COPY_IN", "COPY_OUT")]
    order = topo_order(graph, [op["id"] for op in ops])
    groups = [order[i:i + block_size] for i in range(0, len(order), block_size)]
    mapping = {}
    for sid, group in enumerate(groups):
        for op_id in group:
            mapping[op_id] = sid
    schedules = [[] for _ in range(ncores)]
    for sid in range(len(groups)):
        schedules[sid % ncores].append(sid)
    return {"node_to_subgraph": mapping, "core_schedules": schedules}


def single_core_plan(graph):
    mapping = {op["id"]: 0 for op in graph["ops"]
               if op.get("op") not in ("COPY_IN", "COPY_OUT")}
    return {"node_to_subgraph": mapping, "core_schedules": [[0]]}


# ---------------------------------------------------------------- 定向用例

def cases():
    out = []

    # 1) 单核线性链：改写的最小正例
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 11, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "DDR", "size": 120},
         {"id": 101, "pos": "UB", "size": 120},
         {"id": 102, "pos": "UB", "size": 120}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101},
         {"source": 101, "target": 11}, {"source": 11, "target": 102}])
    out.append(("linear_single_core", g, single_core_plan(g),
                "基础正例：输入边界 + 输出边界各一处"))

    # 2) 两个独立链、两核（F-TASK-003 的跨核场景）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 11, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 20, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 21, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "DDR", "size": 60}, {"id": 101, "pos": "UB", "size": 60},
         {"id": 102, "pos": "UB", "size": 60},
         {"id": 200, "pos": "DDR", "size": 60}, {"id": 201, "pos": "UB", "size": 60},
         {"id": 202, "pos": "UB", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101},
         {"source": 101, "target": 11}, {"source": 11, "target": 102},
         {"source": 200, "target": 20}, {"source": 20, "target": 201},
         {"source": 201, "target": 21}, {"source": 21, "target": 202}])
    out.append(("two_independent_chains_2cores", g,
                {"node_to_subgraph": {10: 0, 11: 0, 20: 1, 21: 1},
                 "core_schedules": [[0], [1]]},
                "两条独立链分到两核：跨 Task 边为零"))

    # 3) 同一 DDR tensor 被两个核消费 → cross_task_traffic 累加（F-TASK-003）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 20, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "DDR", "size": 60},
         {"id": 101, "pos": "UB", "size": 60},
         {"id": 200, "pos": "UB", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101},
         {"source": 100, "target": 20}, {"source": 20, "target": 200}])
    out.append(("shared_ddr_input_two_cores", g,
                {"node_to_subgraph": {10: 0, 20: 1}, "core_schedules": [[0], [1]]},
                "同一图输入被两核消费：每条核各自 input_boundary"))

    # 4) 同一 tensor 被**本子图内**与**远端**同时消费
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 11, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 20, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "UB", "size": 60},
         {"id": 101, "pos": "UB", "size": 60},
         {"id": 102, "pos": "UB", "size": 60},
         {"id": 200, "pos": "UB", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101},
         {"source": 101, "target": 11}, {"source": 11, "target": 102},
         {"source": 101, "target": 20}, {"source": 20, "target": 200}])
    out.append(("tensor_consumed_local_and_remote", g,
                {"node_to_subgraph": {10: 0, 11: 0, 20: 1}, "core_schedules": [[0], [1]]},
                "t101 被本子图的 11 与远端子图的 20 同时消费"))

    # 5) 产出 tensor 无任何消费者 → output_boundary 走 not eligible_consumers 分支
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "DDR", "size": 60},
         {"id": 101, "pos": "UB", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101}])
    out.append(("output_boundary_no_consumers", g, single_core_plan(g),
                "t101 无消费者 → 必须补 COPY_OUT"))

    # 6) 原图自带 COPY_OUT 作为消费者（F-METRIC-001 的独立基线口径）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 30, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 2}],
        [{"id": 100, "pos": "DDR", "size": 60},
         {"id": 101, "pos": "UB", "size": 60},
         {"id": 150, "pos": "DDR", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101},
         {"source": 101, "target": 30}, {"source": 30, "target": 150}])
    out.append(("original_copy_out_consumer", g, single_core_plan(g),
                "原图自带 COPY_OUT → original_graph_copy_bytes 非零，且 has_copy_out 为真"))

    # 7) 原图自带 COPY_IN 提供输入
    g = g_of(
        [{"id": 30, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 2},
         {"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 150, "pos": "DDR", "size": 60},
         {"id": 101, "pos": "UB", "size": 60},
         {"id": 102, "pos": "UB", "size": 60}],
        [{"source": 150, "target": 30}, {"source": 30, "target": 101},
         {"source": 101, "target": 10}, {"source": 10, "target": 102}])
    out.append(("original_copy_in_producer", g, single_core_plan(g),
                "原图自带 COPY_IN → 该 tensor 有 producer，故不再补 input_boundary"))

    # 8) 大 tensor id / 大 op id：触发 new_boundary_ids 的 while 跳过（F-TASK-001）
    g = g_of(
        [{"id": 100001, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100000, "pos": "DDR", "size": 60},
         {"id": 100002, "pos": "UB", "size": 60}],
        [{"source": 100000, "target": 100001}, {"source": 100001, "target": 100002}])
    out.append(("ids_share_one_space_large", g, single_core_plan(g),
                "op id 100001 与 tensor id 100000/100002 同处一个 ID 空间 → 新 ID 必须同时避开两类"))

    # 9) op id 与 tensor id 交错占位（合法但 ID 空间重叠）
    g = g_of(
        [{"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 5, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 4, "pos": "DDR", "size": 60},
         {"id": 6, "pos": "UB", "size": 60},
         {"id": 7, "pos": "DDR", "size": 60}],
        [{"source": 4, "target": 3}, {"source": 3, "target": 6},
         {"source": 6, "target": 5}, {"source": 5, "target": 7}])
    out.append(("ids_interleaved", g, single_core_plan(g),
                "op/tensor id 交错占用 → 新 ID 分配顺序敏感"))

    # 10) plan 用字符串键（官方 int() 归一化路径）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "DDR", "size": 60}, {"id": 101, "pos": "UB", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101}])
    out.append(("plan_string_keys", g,
                {"node_to_subgraph": {"10": 0}, "core_schedules": [[0]]},
                "node_to_subgraph 用十进制字符串键"))

    # 11) core_schedules 含空子图（空核的另一形态：子图为空列表而非核为空）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 20, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "DDR", "size": 60}, {"id": 101, "pos": "UB", "size": 60},
         {"id": 200, "pos": "DDR", "size": 60}, {"id": 201, "pos": "UB", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101},
         {"source": 200, "target": 20}, {"source": 20, "target": 201}])
    out.append(("two_subgraphs_one_core_empty", g,
                {"node_to_subgraph": {10: 0, 20: 1}, "core_schedules": [[0, 1], []]},
                "子图 1 排在核 1 且该核只有这一个 → 两核但其中一核空"))

    # 12) 同一子图内多消费者（eligible_consumers - task_op_ids 为空）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 11, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 12, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "DDR", "size": 60},
         {"id": 101, "pos": "UB", "size": 60},
         {"id": 102, "pos": "UB", "size": 60},
         {"id": 103, "pos": "UB", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101},
         {"source": 101, "target": 11}, {"source": 101, "target": 12},
         {"source": 11, "target": 102}, {"source": 12, "target": 103}])
    out.append(("multi_consumer_same_subgraph", g,
                {"node_to_subgraph": {10: 0, 11: 0, 12: 0}, "core_schedules": [[0]]},
                "t101 同子图内被 11 与 12 消费 → 不需要跨 Task COPY_OUT"))

    # 13) tensor 缺 pos 字段
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "size": 60}, {"id": 101, "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101}])
    out.append(("tensor_pos_missing", g, single_core_plan(g),
                "tensor 无 pos 字段 → 不做 DDR→UB 改写"))

    # 14) tensor pos 为 L1（非 DDR/UB）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "L1", "size": 60}, {"id": 101, "pos": "L1", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101}])
    out.append(("tensor_pos_l1", g, single_core_plan(g),
                "pos='L1' 不是 DDR → 不改写，且入边界仍由 producer 缺失决定"))

    # 15) op→op 直接依赖边（direct_edges）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 11, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "DDR", "size": 60}, {"id": 101, "pos": "UB", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 11},
         {"source": 11, "target": 101}])
    out.append(("direct_op_to_op_edge_same_task", g,
                {"node_to_subgraph": {10: 0, 11: 0}, "core_schedules": [[0]]},
                "op→op 直接边落在同一 Task 内 → 必须保留"))

    # 16) 零字节 tensor（F-TASK-002 的 max(1, ceil(size/bw)) 边界）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 0}],
        [{"id": 100, "pos": "DDR", "size": 0}, {"id": 101, "pos": "DDR", "size": 0}],
        [{"source": 100, "target": 10}, {"source": 10, "target": 101}])
    out.append(("zero_size_zero_cycles", g, single_core_plan(g),
                "size=0 与 cycles=0 → 边界 COPY 时长应为 1"))

    # 17) 重复边（同一 (source,target) 出现两次）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "DDR", "size": 60}, {"id": 101, "pos": "UB", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 100, "target": 10},
         {"source": 10, "target": 101}, {"source": 10, "target": 101}])
    out.append(("duplicate_edges", g, single_core_plan(g),
                "同一对 (src,dst) 重复出现"))

    # 18) 一个 op 消费同一 tensor 两次（edges 去重/多次入边）
    g = g_of(
        [{"id": 10, "op": "CONV", "pipe": "PIPE_M", "cycles": 3},
         {"id": 11, "op": "CONV", "pipe": "PIPE_M", "cycles": 3}],
        [{"id": 100, "pos": "DDR", "size": 60}, {"id": 101, "pos": "UB", "size": 60},
         {"id": 102, "pos": "UB", "size": 60}],
        [{"source": 100, "target": 10}, {"source": 101, "target": 11},
         {"source": 100, "target": 11},
         {"source": 10, "target": 101}, {"source": 11, "target": 102}])
    out.append(("op_with_two_inputs_one_shared", g,
                {"node_to_subgraph": {10: 0, 11: 0}, "core_schedules": [[0]]},
                "op11 有两个输入，其中一个与 op10 的输入相同"))

    return out


# ---------------------------------------------------------------- 随机定向用例

def random_cases(n, seed=20260923):
    """固定种子随机微型图。用「层」模型生成，天然无环、无重复边。

    每个 op 依次有一个输出 tensor；它的输入取自 (a) 无生产者的「图输入」tensor，
    或 (b) **更早** op 的某个输出 tensor。因此边永远从早到晚，不可能成环，
    也不会出现重复 (src,dst)。
    """
    rng = random.Random(seed)
    out = []
    for index in range(n):
        n_ops = rng.randint(2, 7)
        op_ids = rng.sample(range(1, 40), n_ops)
        order = sorted(op_ids)
        ops = [{"id": op_id, "op": "CONV", "pipe": "PIPE_M",
                "cycles": rng.choice([0, 1, 3, 7])} for op_id in order]

        edges = []
        tensors = []
        next_tid = 41
        produced = []          # 已产出的 tensor id（按产出顺序）
        graph_inputs = []      # 无生产者的图输入 tensor
        for position, op_id in enumerate(order):
            n_inputs = rng.randint(0, 2)
            chosen = set()
            for _ in range(n_inputs):
                if graph_inputs and (not produced or rng.random() < 0.45):
                    pool = [t for t in graph_inputs if t not in chosen]
                    src = rng.choice(pool) if pool else None
                elif produced:
                    pool = [t for t in produced if t not in chosen]
                    src = rng.choice(pool) if pool else None
                else:
                    src = None
                if src is None:
                    tid = next_tid
                    next_tid += 1
                    tensors.append({"id": tid, "pos": rng.choice(["DDR", "UB", "L1"]),
                                    "size": rng.choice([0, 1, 60, 600, 4096])})
                    graph_inputs.append(tid)
                    src = tid
                if src in chosen:
                    continue
                chosen.add(src)
                edges.append({"source": src, "target": op_id})
            out_tid = next_tid
            next_tid += 1
            tensors.append({"id": out_tid, "pos": rng.choice(["DDR", "UB"]),
                            "size": rng.choice([0, 1, 60, 600, 4096])})
            edges.append({"source": op_id, "target": out_tid})
            produced.append(out_tid)

        # 保证至少有一个图输入，且 id 不与 op id 冲突
        if not graph_inputs:
            tid = next_tid
            next_tid += 1
            tensors.append({"id": tid, "pos": "DDR",
                            "size": rng.choice([0, 1, 60, 600])})
            edges.append({"source": tid, "target": order[0]})

        g = g_of(ops, tensors, edges)
        try:
            plan = one_op_per_subgraph_plan(g, ncores=rng.choice([1, 2, 2, 3]))
        except ValueError:
            continue
        out.append((f"random_{seed}_{index:03d}", g, plan,
                    "固定种子的随机微型图（层模型生成，每 op 一子图，拓扑序分核）"))
    return out


VARIANTS = [
    ("nominal", 60, {"L1": 524288, "UB": 131072}),
    ("tight_capacity", 60, {"L1": 128, "UB": 64}),      # 触发 spill 分支
    ("tiny_bandwidth", 7, {"L1": 524288, "UB": 131072}),  # 让边界 COPY 时长变化
]


def main():
    records = []
    base = cases()
    random_pool = random_cases(200)

    # 1) 定向用例：标称参数 + 两组变体（覆盖 spill 与取整分支）
    for tag, bw, cap in VARIANTS:
        for label, graph, plan, note in base:
            records.append(assess(f"{label}__{tag}", graph, plan, note, bw, cap))

    # 2) 随机图：标称参数全量 + 紧容量取样
    for label, graph, plan, note in random_pool:
        records.append(assess(label, graph, plan, note))
    for label, graph, plan, note in random_pool[:80]:
        records.append(assess(f"{label}__tight", graph, plan, note, 60, {"L1": 128, "UB": 64}))

    # 3) 官方开发例：连续块切分（block_size=8、2 核），跨 100 个 case 等距取样 20 个
    official = []
    all_cases = [] if SKIP_OFFICIAL else sorted(CASE_DIR.glob("case_*.json"))
    picks = ["case_001", "case_019", "case_080"]
    if all_cases:
        step = max(1, len(all_cases) // 17)
        picks += [p.stem for p in all_cases[::step][:17]]
    seen = set()
    for name in picks:
        if name in seen:
            continue
        seen.add(name)
        path = CASE_DIR / f"{name}.json"
        if not path.exists():
            official.append({"case": name, "outcome": "skipped_missing_case"})
            continue
        graph = json.loads(path.read_text(encoding="utf-8"))
        for ncores, block_size in ((2, 8), (3, 16)):
            try:
                plan = block_plan(graph, ncores=ncores, block_size=block_size)
            except ValueError as exc:
                official.append({"case": f"{name}_c{ncores}_b{block_size}",
                                 "outcome": "plan_build_failed", "error": str(exc)[:120]})
                continue
            official.append(assess(
                f"official_{name}_c{ncores}_b{block_size}", graph, plan,
                "官方开发例 + 拓扑序连续块切分（非官方候选池方案，仅作差分输入）"))

    differ = [r for r in records if r.get("outcome") == "DIFFER"]
    diverged_errors = [r for r in records
                       if r.get("outcome") == "both_raised" and not r.get("error_message_agrees")]
    payload = {
        "generator": "src/adversarial/verify_lyx_cross_r1.py",
        "responds_to": "a-r1-form-adversarial/NikolaStarx/FAST-CODE-AVAILABLE-001",
        "reviewed_commit": LYX_SHA,
        "reviewed_component": "src/eval_exact/problem1.py::_build_scene_a_tasks_indexed",
        "official_code_sha256_problem3": "eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0",
        "method": ("对同一 (graph, plan) 分别调用未改写的官方 evaluate_scene_a 与 E1 的 "
                   "evaluate_scene_a，比较**完整返回对象**（递归、含类型与容器长度），"
                   "不使用容差或字段白名单"),
        "constants": {"bandwidth": BANDWIDTH, "capacity": CAPACITY,
                      "cross_core_wait": CROSS_CORE_WAIT, "same_core_wait": SAME_CORE_WAIT},
        "variants": [{"tag": tag, "bandwidth": bw, "capacity": cap}
                     for tag, bw, cap in VARIANTS],
        "targeted_records": len([r for r in records
                                 if not r["case"].startswith("random_")]),
        "random_records": len([r for r in records if r["case"].startswith("random_")]),
        "total_records": len(records),
        "summary": {
            "identical": sum(1 for r in records if r.get("outcome") == "identical"),
            "both_raised": sum(1 for r in records if r.get("outcome") == "both_raised"),
            "differ": len(differ),
            "error_message_divergence": len(diverged_errors),
            "task_builder_identical": sum(
                1 for r in records if r.get("task_builder") == "identical"),
            "task_builder_differ": sum(
                1 for r in records if r.get("task_builder") == "DIFFER"),
        },
        "rejection_paths": dict(collections.Counter(
            (r.get("e0_error") or "").split(":")[0] for r in records
            if r.get("outcome") == "both_raised")),
        "official_cases": official,
        "differences": differ,
        "error_message_divergences": diverged_errors,
        "records": records,
        "limitations": [
            "只覆盖 Problem 1（E1 仅实现 P1）；未涉 P2/P3。",
            "官方例子用的是本人构造的『每 op 一子图、2 核』方案，不是官方候选池方案，",
            "故这里只作差分输入，不代表候选池上的结论。",
            "微型构造图与 60 个固定种子随机图，不代表 100 个 case 全域。",
            "未做计时与加速比核对（本次只关心输出等价性）。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / ("lyx-cross-review-observations" + OUT_SUFFIX + ".json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    print("E0 reference:", E0.__name__, "| E1 alias:", E1.__name__)
    print("targeted:", payload.get("targeted_records"), "| random:", payload.get("random_records"),
      "| official:", len(payload.get("official_cases") or []))
    print("summary:", payload["summary"])
    for r in differ[:5]:
        print("  DIFFER:", r["case"], json.dumps(r.get("detail") or r.get("differences"), ensure_ascii=False)[:220])
    for r in diverged_errors[:5]:
        print("  ERR-MSG-DIFF:", r["case"], r.get("e0_error", "")[:80], "||", r.get("e1_error", "")[:80])
    for o in official:
        print("  official:", o.get("case"), o.get("outcome"),
              o.get("makespan_e0"), o.get("error_kind_agrees"))
    print("evidence:", out.relative_to(MINE))


if __name__ == "__main__":
    main()
