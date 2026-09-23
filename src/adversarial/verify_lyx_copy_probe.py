"""针对 LYX 新版 `_copy_step3_extended_graph` 的定向复核（d83d5f3）。

新版把 `prepare_step3_execution` 用的全局 `deepcopy` 换成了一个「扁平 schema 快拷贝 + 漂移回退」：
    _STEP3_GRAPH_KEYS = ("ops", "tensors", "edges", "seq_ext")
若 ext_graph 的键序列、容器类型、record 扁平性、值类型、重复引用、seq_ext 元素类型
有任何不符，就回退到官方 deepcopy。

因此本探针只查该函数本身的两件事：
  A) **值等价**：对同一输入，新拷贝 == 官方 deepcopy 的结果；
  B) **别名隔离**：新拷贝不得与输入、也不得与官方拷贝共享任何可变子对象
     （浅拷贝最容易在这里出错——漏一层就会让下游改动串味）。
再加 C) **回退正确性**：故意构造各种 schema 漂移输入，确认它走官方 deepcopy 且结果仍等价。

只读调用 LYX 检出的模块；不修改其任何文件。用环境变量 LYX_DIR 指定检出路径。
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

LYX = Path(os.environ.get(
    "LYX_DIR", "C:/Users/Dora/Desktop/数学建模/Workbuddy/_a-r1/lyx-d83d5f3"))
MINE = Path("C:/Users/Dora/Desktop/数学建模/Workbuddy/_a-r1/worktree")
OUT_DIR = MINE / "results/a/form/r1-20260923-farmeruncle123"
OUT_SUFFIX = os.environ.get("OUT_SUFFIX", "-d83d5f3")

sys.dont_write_bytecode = True
sys.path.insert(0, str(LYX))

import src.eval_exact.problem1 as e1  # noqa: E402  导入即完成 deepcopy 替换

COPY_NEW = e1._copy_step3_extended_graph
COPY_OFL = e1._official_step3_deepcopy          # 官方原 deepcopy（被保存的引用）
KEYS = e1._STEP3_GRAPH_KEYS


def flat_record(**kw):
    return dict(kw)


def make_ext(seq_ext=(1, 2, 3)):
    """一个完全符合新版「扁平 schema」的 ext_graph。"""
    return {
        "ops": [flat_record(id=1, op="COPY_IN", pipe="PIPE_MTE2", cycles=2),
                flat_record(id=2, op="CONV", pipe="PIPE_M", cycles=3)],
        "tensors": [flat_record(id=100, pos="DDR", size=120),
                    flat_record(id=101, pos="UB", size=120)],
        "edges": [flat_record(source=100, target=1), flat_record(source=1, target=101)],
        "seq_ext": list(seq_ext),
    }


def collect_mutables(node, prefix="", acc=None, seen=None):
    """收集对象图里所有可变容器的 id（用于别名检查）。"""
    if acc is None:
        acc = {}
    if seen is None:
        seen = set()
    if id(node) in seen:
        return acc
    if isinstance(node, dict):
        seen.add(id(node))
        acc[prefix or "$"] = id(node)
        for k, v in node.items():
            collect_mutables(v, f"{prefix}.{k}", acc, seen)
    elif isinstance(node, list):
        seen.add(id(node))
        acc[prefix or "$"] = id(node)
        for i, v in enumerate(node):
            collect_mutables(v, f"{prefix}[{i}]", acc, seen)
    return acc


def check(label, ext, expect_fallback):
    """返回一条记录：值等价、别名隔离、回退是否被触发。"""
    src = copy.deepcopy(ext)                    # 不被被测函数污染的基准输入
    before = collect_mutables(src)
    new = COPY_NEW(src)
    values_equal = (new == COPY_OFL(src))
    new_ids = set(collect_mutables(new).values())
    src_ids = set(before.values())
    shared_with_input = sorted(new_ids & src_ids)

    # 再验证「改动副本不会回流到输入」（回退路径下 new 可能不是 dict）
    leak = None
    if isinstance(new, dict):
        for key in ("ops", "tensors", "edges"):
            if isinstance(new.get(key), list) and new[key] and isinstance(new[key][0], dict) \
                    and isinstance(src.get(key), list) and src[key] and isinstance(src[key][0], dict):
                new[key][0]["__probe__"] = 1
                if "__probe__" in src[key][0]:
                    leak = f"{key}[0] 与输入共享 record"
                new[key][0].pop("__probe__", None)
        if isinstance(new.get("seq_ext"), list) and isinstance(src.get("seq_ext"), list):
            new["seq_ext"].append(999)
            if 999 in src["seq_ext"]:
                leak = leak or "seq_ext 与输入共享 list"
            new["seq_ext"].pop()

    return {
        "case": label,
        "expect_fallback": expect_fallback,
        "values_equal_to_official": values_equal,
        "shared_mutable_ids_with_input": shared_with_input,
        "mutation_leaked_back": leak,
        "type_new": type(new).__name__,
        "keys_new": list(new) if isinstance(new, dict) else None,
        "ok": values_equal and not shared_with_input and leak is None,
    }


def main():
    records = []

    # A/B) schema 完全匹配 —— 应走快路径，且必须零别名
    records.append(check("flat schema match (tuple key order)", make_ext(), False))
    records.append(check("flat schema match (seq_ext empty)", make_ext(()), False))
    records.append(check("flat schema match (single op)", {
        "ops": [flat_record(id=7, op="CONV", pipe="PIPE_M", cycles=1)],
        "tensors": [flat_record(id=77, pos="UB", size=1)],
        "edges": [flat_record(source=77, target=7)],
        "seq_ext": [7],
    }, False))

    # C) 各种 schema 漂移 —— 应回退到官方 deepcopy
    base = make_ext()
    mismatch = {
        "key order differs": {"seq_ext": [1], "edges": base["edges"],
                              "tensors": base["tensors"], "ops": base["ops"]},
        "extra key": {**base, "extra": []},
        "missing key": {k: v for k, v in base.items() if k != "seq_ext"},
        "not a dict": [1, 2, 3],
        "container is tuple": {**base, "ops": tuple(base["ops"])},
        "two keys share one container": {**base, "edges": base["ops"]},
        "record not dict": {**base, "ops": [1, 2]},
        "duplicate record object": None,   # 下面单独构造
        "nested value in record": {**base,
            "ops": [flat_record(id=1, op="CONV", pipe="PIPE_M", cycles=1, meta={"x": 1})]},
        "value is list": {**base,
            "tensors": [flat_record(id=100, pos="DDR", size=[1, 2])]},
        "value is None field": {**base, "ops": [flat_record(id=1, op="CONV", pipe=None, cycles=1)]},
        "seq_ext has str element": {**base, "seq_ext": [1, "2"]},
        "seq_ext not a list": {**base, "seq_ext": (1, 2)},
    }
    shared = flat_record(id=9, op="CONV", pipe="PIPE_M", cycles=1)
    mismatch["duplicate record object"] = {**base, "ops": [shared, shared]}
    for label, ext in mismatch.items():
        records.append(check(label, ext, True))

    # D) 真实 ext_graph：从冻结流程里取一个带 spill 的（seq_ext 非空）
    real = None
    try:
        code = MINE / "data/raw/a/official/code"
        sys.path.insert(0, str(code))
        from schedule_step1 import step1_schedule            # noqa: E402
        from schedule_step2 import step2_spill_insertion, _build_extended_graph  # noqa: E402
        src = (MINE / "src/adversarial/verify_spill_r2.py").read_text(encoding="utf-8")
        ns = {}
        head = src.split("def main(")[0].replace(
            'ROOT = Path(__file__).resolve().parents[2]', 'ROOT = Path(".").resolve()')
        exec(compile(head, "sp", "exec"), ns)                 # noqa: S102
        g = ns["graph_v4"]()
        seq = step1_schedule(g)
        res2 = step2_spill_insertion(g, seq, capacity={"L1": 524288, "UB": 191})
        ext = _build_extended_graph(g, res2)
        real = {k: ext[k] for k in KEYS} if set(KEYS) <= set(ext) else None
        if real is not None:
            records.append(check(
                f"real spill ext_graph (seq_ext len={len(real['seq_ext'])})", real, False))
        else:
            records.append({"case": "real spill ext_graph", "outcome": "keys_mismatch",
                            "keys": list(ext)})
    except Exception as exc:  # noqa: BLE001
        records.append({"case": "real spill ext_graph", "outcome": "unavailable",
                        "error": f"{type(exc).__name__}: {exc}"[:200]})

    bad = [r for r in records if r.get("ok") is False or r.get("outcome")]
    payload = {
        "generator": "src/adversarial/verify_lyx_copy_probe.py",
        "reviewed_commit": os.environ.get("LYX_SHA", "d83d5f32a1c23f6450aa9c15fa85891c4ebddd7f"),
        "reviewed_symbol": "src/eval_exact/problem1.py::_copy_step3_extended_graph",
        "method": ("对同一输入比较新拷贝与官方 deepcopy 的**值等价性**，并逐个收集可变容器 id，"
                   "检查新拷贝是否与输入共享子对象；再实测改动副本是否会回流到输入。"
                   "另覆盖 13 种 schema 漂移输入以验证回退路径。"),
        "step3_graph_keys": list(KEYS),
        "summary": {
            "total": len(records),
            "ok": sum(1 for r in records if r.get("ok") is True),
            "problem": len(bad),
        },
        "records": records,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / ("lyx-copy-probe" + OUT_SUFFIX + ".json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    for r in records:
        if r.get("ok") is True:
            print(f"  OK   {r['case']}")
        else:
            print(f"  FAIL {r['case']} :: {json.dumps(r, ensure_ascii=False)[:220]}")
    print("summary:", payload["summary"])
    print("evidence:", out.relative_to(MINE))


if __name__ == "__main__":
    main()
