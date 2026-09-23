"""E2 排序对抗生成器（第一批）。

任务卡要求：对 E2 除数值差异外，能生成**同图、同问题、同核数**的候选组，
寻找「预测排序与官方优劣相反」的案例。

做法：
  1. 固定一张小图、固定问题（问题 1 / 场景 A）、固定核数；
  2. 枚举该图上的**一组**合法方案（只枚举 node_to_subgraph 与 core_schedules）；
  3. 用**官方** evaluate_scene_a 得到每个方案的真实 makespan（真值只用官方，不用任何代理代价模型）；
  4. 同时计算若干「朴素预测器」（E2 若走捷径可能采用的口径），
     找出预测排序与官方排序**相反**的候选对。

不做 E0 评分，不产生任何性能或质量结论；只记录排序是否反转。
"""
from __future__ import annotations

import collections
import itertools
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
SIZE = 256

# 一张 4 个非 COPY 算子的 fork-join 图：能体现切图/分核对传播与并行的影响
GRAPH = {
    "ops": [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 8},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 8},
        {"id": 4, "op": "VADD", "pipe": "PIPE_V", "cycles": 8},
        {"id": 5, "op": "VADD", "pipe": "PIPE_V", "cycles": 8},
        {"id": 6, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
    ],
    "tensors": [
        {"id": 100, "pos": "DDR", "size": SIZE},
        {"id": 101, "pos": "L1", "size": SIZE},
        {"id": 102, "pos": "UB", "size": SIZE},
        {"id": 103, "pos": "UB", "size": SIZE},
        {"id": 104, "pos": "UB", "size": SIZE},
        {"id": 105, "pos": "DDR", "size": SIZE},
    ],
    "edges": [
        {"source": 100, "target": 1},
        {"source": 1, "target": 101},
        {"source": 101, "target": 2},
        {"source": 2, "target": 102},
        {"source": 101, "target": 3},
        {"source": 3, "target": 103},
        {"source": 102, "target": 4},
        {"source": 103, "target": 4},
        {"source": 4, "target": 104},
        {"source": 104, "target": 5},
        {"source": 5, "target": 105},
        {"source": 5, "target": 6},
    ],
}

NON_COPY_OPS = sorted(o["id"] for o in GRAPH["ops"]
                      if o["op"] not in ("COPY_IN", "COPY_OUT"))
NUM_CORES = 2


def set_partitions(items):
    """返回 items 的所有集合划分，每个划分是若干块（每块为 id 列表）。

    用受限增长串枚举：第 i 项所属块号不超过前面已出现的最大块号 + 1。
    这样每个划分恰好出现一次，且块内保持输入顺序。
    """
    items = list(items)
    n = len(items)
    if n == 0:
        yield []
        return
    blocks_of = [0] * n

    def rec(i, used):
        if i == n:
            blocks = [[] for _ in range(used)]
            for idx, blk in enumerate(blocks_of):
                blocks[blk].append(items[idx])
            yield blocks
            return
        for blk in range(used + 1):
            blocks_of[i] = blk
            yield from rec(i + 1, max(used, blk + 1))

    yield from rec(0, 0)


def enumerate_plans():
    plans = []
    for partition in set_partitions(NON_COPY_OPS):
        k = len(partition)
        if k > NUM_CORES:
            continue
        blocks = [sorted(b) for b in partition]
        # 用子图 id 的规范顺序消除等价重排（否则同一方案被重复枚举多次）
        blocks.sort()
        mapping = {}
        for sg_id, block in enumerate(blocks):
            for op_id in block:
                mapping[str(op_id)] = sg_id
        # 把 k 个子图分到 NUM_CORES 个核（允许空核，见 F-PLAN-004/005）
        for assignment in itertools.product(range(NUM_CORES), repeat=k):
            core_schedules = [[] for _ in range(NUM_CORES)]
            for sg_id, core_id in enumerate(assignment):
                core_schedules[core_id].append(sg_id)
            plan = {"node_to_subgraph": dict(mapping),
                    "core_schedules": core_schedules}
            plans.append(plan)
    return plans


def evaluate(plan):
    result = p1.evaluate_scene_a(
        GRAPH, plan, BANDWIDTH, CAPACITY, CROSS_CORE_WAIT, SAME_CORE_WAIT)
    return result


def predictors(result, plan):
    """朴素预测器：E2 若走捷径可能采用的口径。"""
    traffic = result["data_movement_bytes"]
    preds = {
        "added_copy_bytes": traffic["added_copy_bytes"],
        "cross_task_traffic": result["cross_task_traffic"],
        "partition_added_copy_bytes": traffic["partition_added_copy_bytes"],
    }
    # 只用子图数与核数做的粗粒度估计：核上子图数越多越慢
    core_schedules = plan["core_schedules"]
    preds["max_subgraphs_per_core"] = max(len(c) for c in core_schedules)
    preds["num_nonempty_cores"] = sum(1 for c in core_schedules if c)
    return preds


def main():
    plans = enumerate_plans()
    records, skipped = [], []
    seen = set()
    for plan in plans:
        key = (tuple(sorted(plan["node_to_subgraph"].items())),
               tuple(tuple(c) for c in plan["core_schedules"]))
        if key in seen:
            continue
        seen.add(key)
        try:
            result = evaluate(plan)
        except Exception as exc:  # noqa: BLE001
            skipped.append({
                "plan": plan,
                "error_type": type(exc).__name__,
                "error": str(exc)[:200],
            })
            continue
        records.append({
            "plan": plan,
            "official_makespan": result["makespan"],
            "predictors": predictors(result, plan),
        })

    # 官方最优
    best = min(r["official_makespan"] for r in records)
    worst = max(r["official_makespan"] for r in records)

    # 对每个预测器，统计与官方排序相反的候选对数量，并给出一个具体反例
    inversions = {}
    for name in records[0]["predictors"]:
        count = 0
        example = None
        for a, b in itertools.combinations(records, 2):
            pa, pb = a["predictors"][name], b["predictors"][name]
            ma, mb = a["official_makespan"], b["official_makespan"]
            if ma == mb:
                continue
            # 预测：值小的更好。若预测偏好 A 而官方偏好 B，即为反转
            pred_prefers_a = pa < pb
            official_prefers_a = ma < mb
            if pred_prefers_a != official_prefers_a:
                count += 1
                if example is None:
                    better_by_pred = a if pred_prefers_a else b
                    better_by_official = a if official_prefers_a else b
                    example = {
                        "predictor_says_better": {
                            "plan": better_by_pred["plan"],
                            f"{name}": better_by_pred["predictors"][name],
                            "official_makespan": better_by_pred["official_makespan"],
                        },
                        "official_says_better": {
                            "plan": better_by_official["plan"],
                            f"{name}": better_by_official["predictors"][name],
                            "official_makespan": better_by_official["official_makespan"],
                        },
                    }
        inversions[name] = {"inverted_pairs": count, "example": example}

    payload = {
        "generator": "src/adversarial/build_ranking_adversarial.py",
        "purpose": ("同图/同问题/同核数生成方案候选组，寻找预测排序与官方优劣相反的案例。"
                    "真值只用官方 evaluate_scene_a，未使用任何 E1/E2 内部代价模型"),
        "graph_non_copy_ops": NON_COPY_OPS,
        "num_cores": NUM_CORES,
        "constants": {"bandwidth": BANDWIDTH, "capacity": CAPACITY,
                      "cross_core_wait_cycles": CROSS_CORE_WAIT,
                      "same_core_wait_cycles": SAME_CORE_WAIT,
                      "tensor_size_bytes": SIZE},
        "plans_evaluated": len(records),
        "plans_skipped_illegal": len(skipped),
        "skipped_details": skipped,
        "skipped_by_error": dict(collections.Counter(
            s["error_type"] for s in skipped)),
        "official_makespan_range": {"best": best, "worst": worst},
        "inversion_summary": inversions,
        "candidates": [
            {"plan": r["plan"], "official_makespan": r["official_makespan"],
             "predictors": r["predictors"]}
            for r in sorted(records, key=lambda x: x["official_makespan"])
        ],
        "limitations": [
            "单张微型图、2 核、问题 1，结论不可外推到正式用例。",
            "反转的『预测器』是我自选的粗糙口径，不代表 lyx0217 的实际 E2 实现。",
            "未做固定随机种子（枚举是确定性的，无随机成分）。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "ranking-adversarial.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"plans evaluated: {len(records)} | skipped: {len(skipped)}")
    if skipped:
        print("  skip reasons:",
              dict(collections.Counter(s["error_type"] for s in skipped)))
        print("  first skip:", skipped[0]["error"][:150])
    print(f"official makespan range: {best} .. {worst}")
    for name, info in sorted(inversions.items()):
        print(f"  {name:<28} inverted pairs: {info['inverted_pairs']}")
    print("evidence:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
