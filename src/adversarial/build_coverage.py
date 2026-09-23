"""由 rules.jsonl / 样本实测 生成 formal/coverage.json。

覆盖状态只按实际拿到的证据填写；未覆盖的组显式标 gap，不写成通过。
"""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "formal/rules.jsonl"
DEV = ROOT / "tests/adversarial/dev-samples.jsonl"
DEV_OBS = ROOT / "results/a/form/r1-20260923-farmeruncle123/dev-samples-observations.json"
SPILL_OBS = ROOT / "results/a/form/r1-20260923-farmeruncle123/spill-observations.json"
TIME_OBS = ROOT / "results/a/form/r1-20260923-farmeruncle123/time-resource-observations.json"
OUT = ROOT / "formal/coverage.json"

rules = [json.loads(l) for l in RULES.read_text(encoding="utf-8").strip().splitlines() if l.strip()]
dev_samples = [json.loads(l) for l in DEV.read_text(encoding="utf-8").strip().splitlines() if l.strip()] \
    if DEV.exists() else []
dev_obs = json.loads(DEV_OBS.read_text(encoding="utf-8")) if DEV_OBS.exists() else {}
spill_obs = json.loads(SPILL_OBS.read_text(encoding="utf-8")) if SPILL_OBS.exists() else {}
time_obs = json.loads(TIME_OBS.read_text(encoding="utf-8")) if TIME_OBS.exists() else {}

by_scope = collections.Counter(r["scope"] for r in rules)
by_status = collections.Counter(r["status"] for r in rules)

# 任务卡第 5 节要求的机制组。状态按本批实际证据填写。
GROUPS = [
    {
        "group": "合法性/组合环",
        "status": "covered",
        "positive_evidence": ["F-PLAN-004", "F-PLAN-005", "F-EXEC-001",
                              "S-ROUND-QUOTIENT-CYCLE"],
        "boundary_evidence": ["S-PLAN-EMPTY-CORE", "S-PLAN-ID-LITERAL"],
        "counterexample_evidence": ["tests/adversarial/fplan-005-quotient-cycle.json"],
        "note": ("F-PLAN-005 曾被我误判为不可达分支，经队长反例纠正后由探针复现；"
                 "纠正记录保留在规则卡的 correction 字段。"),
    },
    {
        "group": "搬运统计",
        "status": "partial",
        "positive_evidence": ["F-TASK-003", "S-TASK-COPYOUT-BOUNDARY", "F-RESOURCE-002",
                              "F-TASK-006"],
        "boundary_evidence": ["S-ROUND-BOUNDARY-COPY"],
        "counterexample_evidence": [],
        "note": ("已实测：原图 COPY 字节是独立基线（128→192）；跨 Task 流量按远端消费 Task 数累加；"
                 "COPY 时长下界取整；spill 搬运按 `size*(1+int(spill_out_copies_data))`（本例 64→128）。"
                 "F-METRIC-001 五个字段之间的等式关系仍未逐字段核对。"),
    },
    {
        "group": "取整/同刻事件",
        "status": "covered",
        "positive_evidence": ["S-ROUND-BOUNDARY-COPY", "F-EXEC-003", "F-RESOURCE-001"],
        "boundary_evidence": ["S-ROUND-BOUNDARY-COPY"],
        "counterexample_evidence": [],
        "note": ("取整：size=0 与 size=1 的边界 COPY 都只占 1 cycle（max(1, ceil(size/bandwidth))）。"
                 "同刻事件：实测同一 t 上 `miss` 完成引发的 `insert` 先于同刻另一次访问生效"
                 "（t=534 先 insert 后 hit，见 F-EXEC-003），这是本组唯一决定命中与否的变量。"
                 "**未穷举**同刻的 retire/issue 其它组合顺序。"),
    },
    {
        "group": "spill/容量临界",
        "status": "covered",
        "positive_evidence": ["F-LOCAL-004", "F-LOCAL-005", "F-TASK-006"],
        "boundary_evidence": [
            "容量 192 = 峰值驻留 → 0 次 spill（触发条件为严格大于）",
            "容量 191 → 1 次 spill，victim 与插入位置见 spill2-observations.json",
        ],
        "counterexample_evidence": [
            "victim 候选必须排除当前 op 使用的 tensor：3 次失败构造的错误串中 current_tids 与 active 完全相同",
        ],
        "note": ("已取得成功运行：容量 191 触发 1 次 spill，victim=L(t102)，"
                 "seq_ext=[1,2,3,110,4,5,6,7,8,111,9]，SPILL_OUT 锚在 op3 之后、"
                 "SPILL_IN 锚在 op9 之前；victim 被重命名到携带 logical_tid=102 的 113。"
                 "**未覆盖**：同一 step 的多轮 while、L1 与 UB 同时触发、"
                 "多次 spill 的 version 递增链、next_use 并列时的稳定排序。"),
    },
    {
        "group": "Step3 固定 FIFO 与内存复用",
        "status": "partial",
        "positive_evidence": ["F-LOCAL-001", "F-LOCAL-002", "F-LOCAL-003",
                              "F-LOCAL-004", "F-LOCAL-005"],
        "boundary_evidence": [],
        "counterexample_evidence": [],
        "note": ("排序口径已实测：Step1 是确定性多源反向 DFS，key=(¬is_copy_in, depth, -id)；"
                 "同深度时较小 id 先输出、COPY 分支反而最后输出；PIPE_SLOTS=1，同 Pipe 串行。"
                 "**内存复用已部分实测**：spill 的 victim 选择与 SPILL_OUT/IN 插入位置已确认。"
                 "仍未覆盖：Step3 内部的内存依赖（memory_dependencies）与 rename 对序列的进一步影响。"),
    },
    {
        "group": "L2 同时 miss/FIFO",
        "status": "partial",
        "positive_evidence": ["F-RESOURCE-003", "F-RESOURCE-004", "F-METRIC-003",
                              "F-EXEC-003", "F-TASK-005"],
        "boundary_evidence": ["L2 capacity < 单条 tensor 大小 → 0 命中（见 F-RESOURCE-004）"],
        "counterexample_evidence": ["把命中仍计入 DDR 带宽 / 把 Cache 当 LRU 实现"],
        "note": ("已实测：只有 COPY_IN 查 Cache；命中走独立 CACHE_READ 池（250 B/cycle）"
                 "不占 DDR（60）；`size > cache_capacity_bytes` 时永不缓存；hit_rate 按**字节**加权"
                 "（不等尺寸实测 0.476 ≠ 按次数的 0.333）；同刻 insert 先于同刻访问生效。"
                 "**『同时 miss』未单独隔离**：本批两个消费者核的 COPY_IN 被源核串行 COPY_OUT 错开 10 cycles，"
                 "因此未取得两核同一时刻同时 miss 的用例；也未构造触发淘汰（evicted 非空）与 "
                 "spill/rename 产生的 logical_tid 命中路径。"),
    },
]

payload = {
    "run_id": "r1-20260923-farmeruncle123",
    "produced_by": "src/adversarial/build_coverage.py",
    "rules_source": "formal/rules.jsonl",
    "rule_counts": {
        "total": len(rules),
        "by_scope": dict(sorted(by_scope.items())),
        "by_status": dict(sorted(by_status.items())),
    },
    "rule_ids": sorted(r["rule_id"] for r in rules),
    "mechanism_groups": GROUPS,
    "group_summary": dict(collections.Counter(g["status"] for g in GROUPS)),
    "spec_amendment": {
        "file": "docs/a/EVALUATOR_AMENDMENT_20260923.md",
        "commit": "ad1a2c57fd420af4fe327c4e8bcec6c3de4bc5cb",
        "sha256": "f6b836d4289889da7295d88bd9f14525b14ed6ff2819c611bdab5220fad386d9",
        "covered_clauses": {
            "§1 公开输入输出以冻结官方接口为准": ["F-IO-001", "F-IO-002", "F-IO-003", "F-IO-004"],
            "§1 未生成字段不得补齐 / 不得伪造诊断": ["F-METRIC-002"],
        },
        "not_in_scope": ("补充规范主体针对 a-r1-fast-eval 的 E1/E2 门槛；"
                         "我的 FORM/对抗任务范围不扩大，故 §2/§3/§4 的数值门槛与"
                         "并行探索条款不转为我的规则卡。"),
    },
    "dev_samples": {
        "count": len(dev_samples),
        "covered_groups": dev_obs.get("covered_groups", []),
        "not_covered_groups": dev_obs.get("not_covered_groups", []),
        "file": "tests/adversarial/dev-samples.jsonl",
        "observations": "results/a/form/r1-20260923-farmeruncle123/dev-samples-observations.json",
    },
    "evidence_files": [
        "results/a/form/r1-20260923-farmeruncle123/fplan-observations.json",
        "results/a/form/r1-20260923-farmeruncle123/fplan-005-observation.json",
        "results/a/form/r1-20260923-farmeruncle123/ftask-observations.json",
        "results/a/form/r1-20260923-farmeruncle123/ftask-order-observations.json",
        "results/a/form/r1-20260923-farmeruncle123/fexec-observations.json",
        "results/a/form/r1-20260923-farmeruncle123/spill-observations.json",
        "results/a/form/r1-20260923-farmeruncle123/dev-samples-observations.json",
        "results/a/form/r1-20260923-farmeruncle123/time-resource-observations.json",
    ],
    "ordering_note": ("status 取值：covered=已交正例与边界；partial=部分覆盖且有明确缺口；"
                      "gap-with-mechanism=机制已定位但未取得成功运行；gap=未开始。"
                      "任何 gap 都不得当作通过。"),
    "limitations": [
        "所有实测均在微型构造图上完成，规模远小于官方 100 个 case，结论不可外推到正式用例。",
        "本批未计算任何正式 case 的 makespan，未做跨方案优劣比较。",
        "F-METRIC-001 五个搬运字段的等式关系仍未逐字段核对。",
        "Step3 内存复用、L2 的『同时 miss』与淘汰路径、spill 组仍未取得成功运行。",
    ],
}

OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

print("rules total:", len(rules), dict(sorted(by_status.items())))
print("groups:")
for g in GROUPS:
    print(f"   {g['status']:<20} {g['group']}")
print("written:", OUT.relative_to(ROOT))
