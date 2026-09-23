"""F-TIME / F-RESOURCE 首批探针：共享 DDR 带宽与两类等待。

只读调用官方入口 evaluate_scene_a，不改动官方材料。
证据直接取自官方返回的 ddr_contention_log 与 makespan，不依赖我自己的模型。
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))

import multicore_cut_evaluate_problem_1 as p1  # noqa: E402

OUT = ROOT / "results/a/form/r1-20260923-farmeruncle123/time-resource-observations.json"

# data/config.txt 冻结值，不做任何修改
BANDWIDTH = 60
CAPACITY = {"L1": 524288, "UB": 131072}
CROSS_CORE_WAIT = 1000
SAME_CORE_WAIT = 100

SIZE = 600  # 600 bytes / 60 bytes per cycle = 10 cycles


def ddr_user_chain(base_op, base_tid, cores):
    """一条 COPY_IN -> VADD -> COPY_OUT 链，用于制造 DDR 带宽占用。

    base_op: 起始 op id；base_tid: 起始 tensor id。
    返回 (ops, tensors, edges, 参与计划的 op id 列表)。
    """
    o_in, o_compute, o_out = base_op, base_op + 1, base_op + 2
    t_src, t_l1, t_dst = base_tid, base_tid + 1, base_tid + 2
    ops = [
        {"id": o_in, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": o_compute, "op": "VADD", "pipe": "PIPE_V", "cycles": 4},
        {"id": o_out, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
    ]
    tensors = [
        {"id": t_src, "pos": "DDR", "size": SIZE},
        {"id": t_l1, "pos": "L1", "size": SIZE},
        {"id": t_dst, "pos": "DDR", "size": SIZE},
    ]
    edges = [
        {"source": t_src, "target": o_in},
        {"source": o_in, "target": t_l1},
        {"source": t_l1, "target": o_compute},
        {"source": o_compute, "target": t_dst},
        {"source": t_dst, "target": o_out},
    ]
    return ops, tensors, edges, [o_compute]  # node_to_subgraph 只覆盖非 COPY 算子


def build_two_cores(two_chains=True):
    """两条互相独立的链；两条链分到不同核，可在同一时刻各自发起 COPY。

    two_chains=False 时只保留第一条链，用作单链路基线对照。
    """
    ops, tensors, edges, op_ids = ddr_user_chain(1, 100, 2)
    plan_nodes = {str(i): 0 for i in op_ids}
    core_schedules = [[0]]
    if two_chains:
        ops2, tensors2, edges2, op_ids2 = ddr_user_chain(11, 200, 2)
        ops += ops2
        tensors += tensors2
        edges += edges2
        plan_nodes.update({str(i): 1 for i in op_ids2})
        core_schedules = [[0], [1]]
    return (
        {"ops": ops, "tensors": tensors, "edges": edges},
        {"node_to_subgraph": plan_nodes, "core_schedules": core_schedules},
    )


def build_dependent_pair(same_core):
    """两个有真实依赖关系的非 COPY 子图；same_core 决定它们是否同核。

    op1(COPY_IN) -> t101(L1) -> op2(VADD, 子图0) -> t102(UB) -> op3(VADD, 子图1) -> t103(UB)
    op2 与 op3 之间存在真实的数据依赖，是唯一被比较的变量。
    """
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
    graph = {"ops": ops, "tensors": tensors, "edges": edges}
    if same_core:
        plan = {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0, 1]]}
    else:
        plan = {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0], [1]]}
    return graph, plan


def run_case(label, graph, plan, note):
    record = {"case": label, "note": note}
    try:
        result = p1.evaluate_scene_a(
            graph, plan, BANDWIDTH, CAPACITY, CROSS_CORE_WAIT, SAME_CORE_WAIT)
    except Exception as exc:  # noqa: BLE001
        record["outcome"] = "raised"
        record["error"] = f"{type(exc).__name__}: {exc}"
        return record
    record["outcome"] = "ok"
    record["makespan"] = result.get("makespan")
    record["num_cores"] = result.get("num_cores")
    log = result.get("ddr_contention_log") or []
    record["ddr_contention_entries"] = len(log)
    record["max_active_count"] = max([e["active_count"] for e in log], default=0)
    # 回溯重算的直接证据：同一 op 的 projected end 在不同时刻被改写过
    projected_history = {}
    for entry in log:
        for item in entry.get("projected_ends", []):
            key = f"{item['task_id']}:{item['op_id']}"
            projected_history.setdefault(key, []).append(
                {"at": entry["time"], "end": item["end"]})
    record["projected_end_history"] = projected_history
    record["task_end"] = result.get("task_end")
    record["op_end"] = result.get("op_end")
    return record


def main():
    records = []

    records.append(run_case(
        "baseline: one chain, core 1 idle",
        *build_two_cores(two_chains=False)[:2],
        note="只有一条 DDR 请求链在跑，DDR 独占",
    ))

    graph2, plan2 = build_two_cores(two_chains=True)
    rec2 = run_case(
        "contended: two independent chains on two cores",
        graph2, plan2,
        note="两条互不依赖的链分到两个核，COPY 可在同一时刻并发占用 DDR",
    )
    records.append(rec2)

    graph_same, plan_same = build_dependent_pair(same_core=True)
    records.append(run_case(
        "dependent pair on the SAME core",
        graph_same, plan_same,
        note="生产者与消费者同核：预期只加 task_same_core_wait_cycles=100",
    ))

    graph_cross, plan_cross = build_dependent_pair(same_core=False)
    records.append(run_case(
        "dependent pair on DIFFERENT cores",
        graph_cross, plan_cross,
        note="生产者与消费者异核：预期加 task_cross_core_wait_cycles=1000",
    ))

    # 单链路 vs 双链路的 makespan 对照，用于观察共享带宽是否让总时间超线性
    if records[0].get("outcome") == "ok" and rec2.get("outcome") == "ok":
        records.append({
            "case": "bandwidth sharing comparison",
            "outcome": "ok",
            "single_chain_makespan": records[0]["makespan"],
            "two_chain_makespan": rec2["makespan"],
            "note": ("两条独立链并行时，每条链自身的 DDR 请求会被平分带宽；"
                     "若总时间没有随核数下降，说明 DDR 是共享瓶颈"),
        })

    payload = {
        "generator": "src/adversarial/verify_time_r1.py",
        "official_entry": "multicore_cut_evaluate_problem_1.evaluate_scene_a",
        "config_source": "data/raw/a/official/data/config.txt（冻结值，未修改）",
        "constants": {
            "bandwidth": BANDWIDTH, "capacity": CAPACITY,
            "cross_core_wait_cycles": CROSS_CORE_WAIT,
            "same_core_wait_cycles": SAME_CORE_WAIT,
            "tensor_size_bytes": SIZE,
        },
        "observations": records,
        "limitations": [
            "构造图为微型图，每条链 3 个算子，不代表官方 case 的规模。",
            "未测 Problem 2/3 的 L2 与 cross_core_copy_delay_cycles。",
            "makespan 数值只对应当前构造与配置，不可外推到正式用例。",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in records:
        line = f"  {r['case']}: {r['outcome']}"
        if r.get("outcome") == "ok":
            line += f" | makespan={r.get('makespan')}"
            if "max_active_count" in r:
                line += f" | max_active={r['max_active_count']} entries={r['ddr_contention_entries']}"
        else:
            line += f" | {r.get('error')}"
        print(line)
    print("evidence:", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
