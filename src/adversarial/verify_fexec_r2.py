"""F-EXEC-001 量词修订的回归探针（响应 INDEPENDENT-REVIEW-001 R1）。

冻结源码 evaluation_validation.py:217-220：

    def validate_task_order(view):
        if not any(len(order) > 1 for order in view['core_orders'].values()):
            return
        ...

即 **所有核的 order 长度均 <= 1 才提前返回**，而不是"任一核 <= 1"。
本探针覆盖：混合长度核（一个空核 + 一个多子图核）、独立单子图核、以及正向对照。

unit-level：把手工构造的 view 直接喂给校验器，属**非正式输入域**，
不声称官方入口可达（入口可能更早拒绝逆序）。
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

from evaluation_validation import validate_task_order  # noqa: E402


def run(label, core_orders, dependency_pairs, subgraph_ids, note):
    view = {
        "core_orders": {str(k): v for k, v in core_orders.items()},
        "dependency_pairs": [list(p) for p in dependency_pairs],
        "subgraph_ids": list(subgraph_ids),
    }
    rec = {"case": label, "note": note, "view": view}
    try:
        validate_task_order(view)
        rec["outcome"] = "accepted"
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "rejected"
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def main():
    records = []

    # A) 队长给出的混合长度核反例：一个核 2 个子图、另一个核为空
    records.append(run(
        "A) core0=[1,0] (len 2), core1=[] (len 0); dependency 0->1",
        {0: [1, 0], 1: []}, [(0, 1)], [0, 1],
        "只有 core1 满足 <=1，core0 不满足；按正确量词应**不**提前返回，故仍应拒绝"))

    # B) 把空核换成独立单子图核（len 1）
    records.append(run(
        "B) core0=[1,0] (len 2), core1=[2] (len 1, independent); dependency 0->1",
        {0: [1, 0], 1: [2]}, [(0, 1)], [0, 1, 2],
        "所有核都 <=1 不成立（core0 为 2），故仍应拒绝"))

    # C) 正向对照：正确顺序 + 空核
    records.append(run(
        "C) control: core0=[0,1] (forward), core1=[]; dependency 0->1",
        {0: [0, 1], 1: []}, [(0, 1)], [0, 1],
        "顺序边为 0->1，与依赖同向，应接受"))

    # D) 正向对照：所有核均 <=1（两个核各 1 个子图）
    records.append(run(
        "D) control: core0=[0], core1=[1]; dependency 0->1",
        {0: [0], 1: [1]}, [(0, 1)], [0, 1],
        "所有核均 <=1 → 源码直接 return，应接受"))

    # E) 全体核均 <=1 的另一种形态：单核单子图
    records.append(run(
        "E) control: single core, one subgraph",
        {0: [0]}, [], [0],
        "任何核都不超过 1 → 直接 return，应接受"))

    # F) 反向量词会漏判的最小情形：core0 有 2 个子图且逆序，另一个核完全不存在
    records.append(run(
        "F) core0=[1,0] only (no other core); dependency 0->1",
        {0: [1, 0]}, [(0, 1)], [0, 1],
        "只有 1 个核且长度 2；按任一核<=1 的错误量词会误判为直接返回（接受），实际应拒绝"))

    payload = {
        "generator": "src/adversarial/verify_fexec_r2.py",
        "purpose": "响应 INDEPENDENT-REVIEW-001 R1：验证 validate_task_order 的量词方向",
        "source_condition": ("evaluation_validation.py:219 —— "
                             "if not any(len(order) > 1 for order in view['core_orders'].values()): return"),
        "correct_reading": "所有核的 order 长度均 <= 1 才提前返回",
        "wrong_reading_under_test": "任一核的 order 长度 <= 1 就提前返回",
        "records": records,
        "limitations": [
            "unit-level 手工 view，非官方输入域；不声称官方入口可达（入口可能更早拒绝逆序）。",
            "未穷举核数、子图数与顺序长度的组合。",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "fexec2-observations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in records:
        print(f"  {r['case']}")
        print(f"     -> {r['outcome']}" + (f" | {r['error'][:110]}" if r.get("error") else ""))
    print("evidence:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
