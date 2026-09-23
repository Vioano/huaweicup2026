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
        "positive_evidence": ["F-TASK-003", "S-TASK-COPYOUT-BOUNDARY", "F-RESOURCE-002"],
        "boundary_evidence": ["S-ROUND-BOUNDARY-COPY"],
        "counterexample_evidence": [],
        "note": ("已实测：原图 COPY 字节是独立基线（128→192）；跨 Task 流量按远端消费 Task 数累加；"
                 "COPY 时长下界取整。F-METRIC-001 五个字段的等式关系尚未逐字段核对。"),
    },
    {
        "group": "取整/同刻事件",
        "status": "partial",
        "positive_evidence": ["S-ROUND-BOUNDARY-COPY"],
        "boundary_evidence": ["S-ROUND-BOUNDARY-COPY"],
        "counterexample_evidence": [],
        "note": ("取整已实测：size=0 与 size=1 的边界 COPY 都只占 1 cycle（max(1, ceil(size/bandwidth))）；"
                 "F-RESOURCE-001 取到了同刻并发（同一 t 两个核各发起 COPY）的日志。"
                 "同刻多事件同时退休/退出的完整判定顺序未单独构造。"),
    },
    {
        "group": "spill/容量临界",
        "status": "gap-with-mechanism",
        "positive_evidence": [],
        "boundary_evidence": ["results/a/form/r1-20260923-farmeruncle123/spill-observations.json"],
        "counterexample_evidence": [],
        "note": (spill_obs.get("open_question") or
                 "本批未取得含 >=1 spill 的成功运行，如实标为 PARTIAL。"),
    },
    {
        "group": "Step3 固定 FIFO 与内存复用",
        "status": "gap",
        "positive_evidence": [],
        "boundary_evidence": [],
        "counterexample_evidence": [],
        "note": ("未开始。已知入口：schedule_step3.prepare_step3_execution 与 PIPES/PIPE_SLOTS。"
                 "该组直接决定 Task 内序列与内存依赖，是当前最大缺口。"),
    },
    {
        "group": "L2 同时 miss/FIFO",
        "status": "gap",
        "positive_evidence": [],
        "boundary_evidence": [],
        "counterexample_evidence": [],
        "note": ("未开始。Problem 3 才引入 L2（capacity=1048576，bandwidth=250，FIFO）。"
                 "未验证 L2 带宽是否与 DDR 带宽互不占用。"),
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
        "F-LOCAL 模块尚未产出规则卡。",
    ],
}

OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

print("rules total:", len(rules), dict(sorted(by_status.items())))
print("groups:")
for g in GROUPS:
    print(f"   {g['status']:<20} {g['group']}")
print("written:", OUT.relative_to(ROOT))
