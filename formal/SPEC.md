# SPEC.md — a-r1-form-adversarial 形式化规范（首轮增量）

负责人：farmeruncle123　run-id：`r1-20260923-farmeruncle123`
冻结输入：`official_code_hash = de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`
代码提交：`ea25b9334a1287766b4b2ebedc9875d5d341eff6`　任务 Issue：#14

**本文件是增量骨架，不是完成的八模块规范。** 模块状态如实标注，未覆盖的不填成完成。

## 0. 总体对象

\[
E_v(G,P,C,q;R)\longrightarrow (\text{status},\text{result})
\]

- \(G\)：原图 JSON（`tensors` / `ops` / `edges`，边为 `{source,target}`，包含 tensor↔op 二部连接）
- \(P\)：方案，字段集合**恰好**为 `node_to_subgraph` 与 `core_schedules`
- \(C\)：`data/config.txt`（冻结字节，LF，341 B）
- \(q\)：问题编号 1/2/3
- \(R\)：锁定参考运行环境

已确认事实：**候选方案不能自由指定全部操作的精确启动时间**，核内启发式由 Step3 固定（见 F-EXEC）。

## 1. 词汇（首轮已用到）

| 符号 | 含义 | 来源 |
| --- | --- | --- |
| eligible | `op.op not in {COPY_IN, COPY_OUT}` 的 op id 集合 | `stub_multicore_cut_and_schedule.py:15,124` |
| mapping | `op_id -> subgraph_id`，键归一化为 int | 同上 `:132-146` |
| core_orders / core_by_subgraph | 核的子图列表 / 子图到核的映射 | 同上 `:165-186` |
| dependency_pairs | 收缩 COPY 节点后的子图依赖有序对 | 同上 `:188-196` |
| pipe_ops | 每个 Pipe 内 op 的固定 FIFO 顺序 | `evaluation_validation.py:237-238` |

## 2. 八模块状态

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| F-IO | 骨架 | 题面/实现差异见 `ambiguities.md` 第 A 节；`config.txt` 冻结字节对 Windows 检出敏感（已由队长修复） |
| F-PLAN | **6 条规则，6 条探针实测** | `rules.jsonl` 的 F-PLAN-001..006；F-PLAN-005 的误判纠正保留在 `correction` 字段 |
| F-TASK | **4 条规则，4 条探针实测** | 来源 `multicore_cut_evaluate_problem_1.py:86-143`；另两个入口 `problem_2.py:61`、`problem_3.py:69` 尚未比对 |
| F-LOCAL | 未开始 | 入口 `schedule_step1/2/3.py`；Step3 固定 FIFO 与内存复用是本批最大缺口 |
| F-EXEC | **2 条规则，均有实测探针** | F-EXEC-001/002，来源 `evaluation_validation.py:217-243`；unit-level 探针域已标注 |
| F-TIME | **2 条规则，均实测** | F-TIME-001/002；两类等待的实测差值为 `1000-100=900` |
| F-RESOURCE | **2 条规则，均实测** | F-RESOURCE-001/002；含 DDR 等分共享与回溯重算的直接日志证据 |
| F-METRIC | **1 条规则，仅读源码** | F-METRIC-001；五个搬运字段的等式关系未逐字段核对 |

合计 **17 条规则**（16 条 `verified-by-probe`，1 条 `draft-sourced`），覆盖表见 `coverage.json`。

## 3. 规则卡格式

严格按契约 v1 第 3.3 节同一张卡：`rule_id / title / scope / kind / symbols_and_units /
preconditions / transition_or_predicate / outputs / failure_behavior / tie_break_and_rounding /
sources / positive_tests / counterexample_tests / implementation_sites / status`。

`kind` 区分：题面要求、实现行为、测试观察、推导结论、团队近似假设。目前全部为**实现行为**或
**测试观察**，尚无一条被标为"题面要求"——题面 PDF 尚未逐条对齐，不预先冒充题面口径。

## 4. 已观测到的语义对抗点

1. **ID 字面表示不唯一**：`node_to_subgraph` 的键 `"02"` 与 `"2"` 都通过整数校验并判定为重复，
   说明前导零字符串键与整数键同义。可用于构造"看起来不同、实际同一 op"的方案。
2. **空核合法且计入核数**：`core_schedules=[[0],[]]` 被接受，`num_cores=2`。任何把"核数"当成
   "非空核数"的代理实现都会偏。
3. **商图成环（原为误判，已纠正）**：原图是 DAG 也可能被拒——成环来自按 `node_to_subgraph`
   **分组**这一步，而非 COPY 收缩。反例与探针见 `tests/adversarial/fplan-005-quotient-cycle.json`。
4. **生成 id 的 op/tensor 共用避让集合**（F-TASK-001）：分配顺序互相影响，新 tensor id 下界为 10000
   （实测从 10001 起）。
5. **DDR 完成时刻可被回溯推迟**（F-RESOURCE-001）：后发起的传输会推迟已在飞传输的 `op_end`，
   实测 `10→20`、`34→44`。任何"发放即定局"的增量实现都错。
6. **加核不保证提速**（F-RESOURCE-001 的对照）：单链 1 核 makespan=24，两条独立链 2 核 makespan=44。
   仅在微型构造图上成立，不足以外推到正式用例。

## 5. 复现

```sh
python src/adversarial/verify_rules_r1.py        # F-PLAN 探针（含 F-PLAN-005 反例）
python src/adversarial/verify_ftask_r1.py        # F-TASK 探针（生成 id / DDR→UB / 输出边界）
python src/adversarial/verify_order_r1.py        # F-TASK-004 声明顺序敏感性
python src/adversarial/verify_fexec_r1.py        # F-EXEC 探针
python src/adversarial/verify_spill_r1.py        # spill 容量扫掠（PARTIAL）
python src/adversarial/verify_time_r1.py         # F-TIME / F-RESOURCE 探针
python src/adversarial/build_dev_samples.py      # 首批 10 个开发反例样本

python src/adversarial/build_coverage.py          # 由 rules.jsonl 与实测结果重算 coverage.json
```

各自输出到 `results/a/form/r1-20260923-farmeruncle123/`。
所有探针**只记录 accept/reject、官方报错原文与官方返回的数值字段**，
**没有调用 E0 评分，也不构成任何性能或质量结论**。
