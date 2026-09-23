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
| F-IO | **4 条规则，3 条实测 + 1 条规范** | F-IO-001（CLI 与默认路径）、F-IO-003（缺省配置硬失败）、F-IO-004（错误出口）已端到端实跑；F-IO-002（结果 JSON 不得包装/改名/跨题补字段）为补充规范条款，待独立验收 |
| F-PLAN | **6 条规则，6 条探针实测** | `rules.jsonl` 的 F-PLAN-001..006；F-PLAN-005 的误判纠正保留在 `correction` 字段 |
| F-TASK | **6 条规则，均探针实测** | 来源 `multicore_cut_evaluate_problem_1.py:86-143` 与 `_3.py` 的场景 B 多播；spill 的重命名与 logical_tid 见 F-TASK-006 |
| F-LOCAL | **6 条规则，均实测** | F-LOCAL-001..006；排序口径、spill 的 victim 选择与插入位置、Step3 内存复用的虚拟额度模型 |
| F-EXEC | **3 条规则，均有实测探针** | F-EXEC-001/002 来自 `evaluation_validation.py:217-243`；F-EXEC-003 为同刻事件顺序 |
| F-TIME | **2 条规则，均实测** | F-TIME-001/002；两类等待的实测差值为 `1000-100=900` |
| F-RESOURCE | **7 条规则，均实测** | DDR 等分共享与回溯重算、DDR 端点判定、Cache 只由 COPY_IN 查询且走独立池、FIFO 不晋升 + 超容量不缓存、Cache key 跨 rename 稳定、同刻同时 miss 的幂等 insert、FIFO 淘汰 |
| F-METRIC | **4 条规则：1 规范 + 3 实测** | F-METRIC-001（搬运五字段等式，已实测）、F-METRIC-002（规范条款，待独立验收）、F-METRIC-003（hit_rate 按字节加权）、F-METRIC-004（搬运统计不足以排序） |

合计 **38 条规则**（36 条 `verified-by-probe`，2 条 `draft-sourced`；后者均为需独立验收的规范条款），
覆盖表见 `coverage.json`。

**覆盖表现状**：任务卡第 5 节要求的**六个机制组全部 `covered`**，**无 `partial`、无 `gap`**。
各组仍保留明确标注的未覆盖子项（见 `coverage.json` 的 note 字段），未被填成已完成。

**E2 排序对抗（任务卡第 5 节）**：`src/adversarial/build_ranking_adversarial.py` 在
1 张微型图 × 2 核 × 问题 1 上枚举 30 个方案（16 个合法、14 个因商图成环被拒），
用官方 makespan 作真值，找出各朴素预测器的排序反转对数。
最干净的一例（`tests/adversarial/ranking-inversion-pair.json`，由
`verify_ranking_fixture.py` 复验通过）：**切图相同、搬运统计逐字节相同，仅核心归属不同
→ makespan 1052 vs 152，差 900 = 1000 − 100**。详见 `coverage.json` 的
`e2_ranking_adversarial` 段。

补充规范（`docs/a/EVALUATOR_AMENDMENT_20260923.md`，固定提交 `ad1a2c57`）明确覆盖
`contract-v1` §2.2–2.4 与 §5.4，细化 §5.5。**其主体是 E1/E2 的数值门槛与并行探索，属
`a-r1-fast-eval` 范围，我的 FORM/对抗范围不扩大**，只登记与 F-IO、指标、开发反例相关的条款
（见 `coverage.json` 的 `spec_amendment` 段）。

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
6. **具体分配方案未必因使用更多核而更快**（F-RESOURCE-001 的对照，同图同划分）：
   同一张图上只改 `core_schedules` —— **有依赖的两段** 1 核 `[[0,1]]` → 148、
   只添加空核 `[[0,1],[]]` → 148、改分配到两核 `[[0],[1]]` → **1048**；
   而**两条独立链**从 `[[0,1],[]]` → 148 改为 `[[0],[1]]` → **44**。
   因此**不能**外推为「核预算增大时最优值必然变差」，必须区分具体方案、核预算与最优值。
   （附带更正：此前用「单链 1 核 = 24 对双链 2 核 = 44」说明加核，**混入了工作量变化**，
   该观察仅保留为**共享 DDR 带宽争用**的证据。）
   仅在微型构造图上成立，不足以外推到正式用例。
7. **Step1 排序方向易读反**（F-LOCAL-001/002）：`-id` 使同深度时**较小 id 先输出**；
   `¬is_copy_in` / `¬is_copy_out` 使 **COPY_IN / COPY_OUT 分支反而最后输出**。
   两处都与"COPY 优先"的直觉相反，照直觉实现会整体反转排序。
8. **同 Pipe 串行**（F-LOCAL-003）：`PIPE_SLOTS = 1`，同一 `(core, pipe)` 上不能并行，
   且该常量不可由选手配置。
9. **Cache 命中不占 DDR 带宽**（F-RESOURCE-003）：命中走独立的 `CACHE_READ` 池
   （250 B/cycle vs DDR 的 60），两个池互不占用。把命中计入 DDR 会高估压力。
10. **`hit_rate` 按字节加权**（F-METRIC-003）：不等尺寸实测 0.476（按字节）
   而非 0.333（按访问次数）——两种口径会给出不同结论。
11. **多播时源核串行执行 n 次 COPY_OUT**（F-TASK-005）：每个 `(源核, 目标核)` 对各自新建
    一个 DDR tensor 与一对 COPY，源核在 `PIPE_MTE3` 上串行完成；这会把各消费者错开，
    而**错开与否直接决定 L2 是否命中**。
12. **spill 的 victim 必须「有未来使用」且「不被当前 op 使用」**（F-LOCAL-004）：
    排除当前 op 的 buffer 是因为 SPILL_OUT 只能排在 op 之后，否则该 op 自身瞬时超容量。
    触发条件是 `剩余驻留 > 容量`（**严格大于**）：容量 192 = 峰值驻留时 0 次 spill。
13. **Cache key 跨 spill 重命名稳定**（F-RESOURCE-005）：重命名化身携带 `logical_tid`，
    因此换回的 COPY_IN 与原始 COPY_IN 共用同一 cache key，**spill 与 L2 命中存在耦合**。
14. **搬运统计不足以决定优劣**（F-METRIC-004）：切图相同、搬运逐字节相同的两个方案，
    仅核心归属不同即可相差 900 cycles。**仅按搬运量排序的预测器连区分都做不到**，
    这使 F-TIME-001 成为排序对抗的核心。

## 5. 复现

```sh
python src/adversarial/verify_io_r1.py           # F-IO 官方 CLI 端到端探针
python src/adversarial/verify_rules_r1.py        # F-PLAN 探针（含 F-PLAN-005 反例）
python src/adversarial/verify_ftask_r1.py        # F-TASK 探针（生成 id / DDR→UB / 输出边界）
python src/adversarial/verify_order_r1.py        # F-TASK-004 声明顺序敏感性
python src/adversarial/verify_fexec_r1.py        # F-EXEC 探针
python src/adversarial/verify_local_r1.py        # F-LOCAL Step1 排序与 Pipe 常量
python src/adversarial/verify_spill_r1.py        # spill 容量扫掠（第一次尝试，PARTIAL）
python src/adversarial/verify_spill_r2.py        # spill victim 选择与插入位置（成功构造）
python src/adversarial/verify_time_r1.py         # F-TIME / F-RESOURCE 探针
python src/adversarial/verify_l2_r1.py           # L2 Cache 探针（问题 3，命中/FIFO/字节加权）
python src/adversarial/verify_l2_r2.py           # L2 同时 miss 与淘汰路径
python src/adversarial/verify_metric_r1.py       # 搬运五字段等式核对
python src/adversarial/verify_local2_r1.py       # Step3 内存复用（虚拟额度）
python src/adversarial/build_dev_samples.py      # 首批 10 个开发反例样本
python src/adversarial/build_ranking_adversarial.py  # E2 排序对抗：枚举候选组找排序反转
python src/adversarial/verify_ranking_fixture.py     # 复验排序反转夹具（失败会非零退出）

python src/adversarial/build_coverage.py          # 由 rules.jsonl 与实测结果重算 coverage.json
```

各自输出到 `results/a/form/r1-20260923-farmeruncle123/`。
所有探针**只记录 accept/reject、官方报错原文与官方返回的数值字段**，
**只是直接调用冻结官方函数/CLI 取原始输出**；未调用队长的 oracle 适配层，未做正式基准与全量验收，也不构成任何性能或质量结论。
