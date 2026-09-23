# A-formal：官方评估过程的形式化方法与语义对抗

本节属于 A 题第一轮的 FORM 交付，任务 Issue [#14](https://github.com/huaweibei123/huaweicup2026/issues/14)，
run-id `r1-20260923-farmeruncle123`。内容为**形式化规范与语义对抗样本**的工作记录，
不包含任何方案质量或性能结论。

## 1. 目标与边界

**目标**：把官方评估过程写成能指导实现与测试的规范，并构造能揭露等价实现偏差与筛选失效的
语义对抗样本。规则、夹具、生成器与反例形成对应关系。

**不做的**：不重写整个官方评估器；不调用 E0 评分；不产出任何性能、加速比或质量结论；
不改动冻结官方材料（`data/raw/a/official/**` 全轮零改动）。

**冻结输入**：`official_code_hash = de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`，
派发提交 `ea25b9334a1287766b4b2ebedc9875d5d341eff6`，配置取自 `data/config.txt`（341 B LF，
`dcd10de5…`）。每条规则卡都记录所引源码文件的 SHA-256。

## 2. 方法

### 2.1 形式化对象

评估过程记为 \(E_v(G,P,C,q;R)\to(\text{status},\text{result})\)，其中 \(G\) 为原图 JSON
（`tensors`/`ops`/`edges`，边为 `{source,target}`，含 tensor↔op 二部连接），
\(P\) 为方案且字段集合**恰好**为 `node_to_subgraph` 与 `core_schedules`，
\(C\) 为 `data/config.txt`，\(q\in\{1,2,3\}\)，\(R\) 为锁定环境。

已确认的关键事实：**候选方案不能自由指定操作的精确启动时间**，核内序列由 Step1/Step2/Step3 固定。

### 2.2 规则卡的字段口径

每条规则按契约 v1 §3.3 的同一张卡记录：`rule_id / title / scope / kind / symbols_and_units /
preconditions / transition_or_predicate / outputs / failure_behavior / tie_break_and_rounding /
sources / positive_tests / counterexample_tests / implementation_sites / status`。
`status` 三态：`draft-sourced`（仅读源码）、`verified-by-probe`（有可复跑实测）、
（规范条款单独标注来源为补充规范文件）。

**规则只按实测证据升级状态**，读源码得到的结论不写成已验证。

### 2.3 探针驱动的验证流程

对每条候选规则，流程固定为三步：

1. **变量隔离**：构造两个只差单一变量的对照，且两个候选**互不为祖先**，
   避免顺序被依赖关系强制而失去隔离意义；
2. **以官方输出为证据**：优先使用官方返回的结构化字段（`ddr_contention_log`、
   `cache_events`、`per_core_timeline`、`spill_records`、`overflow_log`）或官方报错串里的
   边标签，而不是自建模型推算；
3. **结论由探针产出**：结论作为探针的输出写入 `results/`，不手工补写产物——
   手工补写的内容会在重跑时被覆盖。

真值只取自官方入口（`evaluate_scene_a`、`evaluate_problem_3`、`step1_schedule`、
`step2_spill_insertion`），**未使用任何 E1/E2 内部代价模型充当真值**。

### 2.4 覆盖表

`formal/coverage.json` 由 `src/adversarial/build_coverage.py` 从 `rules.jsonl` 与实测产物
**重算**，不由人工维护。机制组状态分四档：`covered` / `partial` / `gap-with-mechanism` / `gap`。

## 3. 主要结果

截至本批，`rules.jsonl` 共 **35 条**（32 条 `verified-by-probe`，3 条 `draft-sourced`），
八个模块均已产出规则卡（F-PLAN 6、F-TASK 6、F-LOCAL 5、F-RESOURCE 5、F-IO 4、
F-METRIC 4、F-EXEC 3、F-TIME 2），其中 `F-LOCAL` 的内存依赖部分与 `F-METRIC-001`
的字段等式仍未实测。以下列出对实现与筛选有直接影响、且已由探针复现的语义点。

### 3.1 排序与内存（F-LOCAL，5 条）

Step1 是**确定性的多源反向 DFS 拓扑排序**，`key = (¬is_copy_in, depth, -id)`，升序压栈 + LIFO 弹栈。
两处方向与直觉相反，均经干净对照隔离：

- 同深度时 **id 较小者先输出**（第三段是 `-id`）；
- 同深度下 **COPY_IN / COPY_OUT 分支反而最后输出**（首段 `False` 只让它排在升序列表前面，
  而先入栈者后出栈）。实测 `seq`：JOIN 前驱 `op1(COPY_IN)` 与 `op2(CONV)` → `[2,1,7,8]`；
  两个同深度 sink `op3(COPY_OUT)` 与 `op13(CONV)` → `[11,12,13,1,2,3]`。

`PIPE_SLOTS = 1`，同一 `(core, pipe)` 上串行，且该常量不对外开放。

spill 的 victim 必须**同时**满足「有未来使用」与「不被当前 op 使用」，按 `-next_use` 取最远者（Belady）。
触发条件是 `剩余驻留 > 容量`（严格大于）：容量 192 = 峰值驻留时 **0 次 spill**，191 时 **1 次**。
`seq` 原为 `[1..9]`，插入后 `seq_ext = [1, 2, 3, 110, 4, 5, 6, 7, 8, 111, 9]`：
SPILL_OUT 锚在 victim 上次使用之后，SPILL_IN 锚在下次使用之前。

### 3.2 时间与资源（F-TIME 2 条、F-RESOURCE 5 条）

- 场景 A 两类等待：同核 `task_same_core_wait_cycles = 100`，跨核
  `task_cross_core_wait_cycles = 1000`，**且跨核等待只对真实前驱的异核项生效**。
  实测同一图只改核心归属：同核 makespan **148**、异核 **1048**，差恰为 `1000 − 100 = 900`。
- DDR 带宽（60 B/cycle）由所有在用带宽的 op **等分共享**，且完成时刻会被后来发起的传输
  **回溯重算**：官方 `ddr_contention_log` 中同一 op 的 `projected_end` 由 10 改写为 20、
  由 34 改写为 44。任何「发放即定局」的增量式实现都会算错在飞传输的完成时间。
- 只有端点含 DDR 位置 tensor 的 COPY 进入共享 DDR 带宽池。
- L2（问题 3）：**只有 COPY_IN 查询 Cache**；命中时 `effective_bandwidth = 250`
  而 DDR 为 60，且命中走**独立的 `CACHE_READ` 池**，两个池互不占用。
  实测 600 字节 tensor：miss 时长 10、命中时长 3。
- Cache 为 FIFO：已存在的 key **直接返回、不重排**（无 LRU 晋升）；
  `size > cache_capacity_bytes` 时永不缓存（599 < 600 → 0 命中）。

### 3.3 指标与筛选（F-METRIC 4 条）

- `cache_stats['hit_rate']` **按字节加权**：把两个可缓存 COPY_IN 的尺寸做成 60 与 600 字节后，
  上报值 `0.47619 = 600/1260`，而按访问次数会得到 `0.3333`。
- 同刻事件顺序：未命中 COPY_IN 完成引发的 `insert` **先于**同刻另一次访问生效
  （`t=534` 先 `insert(tensor 102)` 再 `hit(tensor 102)`）；顺序颠倒会让命中数由 1 变 0。
- **搬运统计不足以决定优劣**。在同一张图、同一问题、同为 2 核的候选组中，
  两个方案切图相同、`cross_task_traffic` 与 `added_copy_bytes` **逐字节相同**（256 / 768），
  仅核心归属不同，官方 makespan 却为 **1052 与 152**，差 900。
  在该图的 30 个方案（16 个合法）中，各朴素预测器的排序反转对数为：
  `max_subgraphs_per_core` 72、`cross_task_traffic` 26、`added_copy_bytes` 22、
  `partition_added_copy_bytes` 22、`num_nonempty_cores` 20。

### 3.4 接口与执行（F-IO 4 条、F-EXEC 3 条、F-PLAN 6 条、F-TASK 6 条）

- 官方 CLI：省略时自动读 `<stem>_multicore_res.json` 与图目录下 `config.txt`，
  产出 `<stem>_problem_<n>_{res.json,trace.json,log.txt}`；显式 `-o` 则不写默认名。
  缺省配置缺失时**硬失败**（rc=1、`[EVALUATION ERROR]` 前缀、不写结果、不暴露 traceback），
  不回退到内置默认值。
- 方案校验：空核合法且计入核数；`node_to_subgraph` 键的字面表示不唯一
  （`"02"` 与 `"2"` 同义且判为重复）；原图是 DAG 也可能被拒——
  **成环来自按 `node_to_subgraph` 分组（商图）**，而非 COPY 收缩。
  在 3.3 节那张 6 算子的小图上，30 个分区中有 **14 个**因此被拒。
- Task 构造：生成的新 tensor id 下界为 10000（实测自 10001 起），且 op 与 tensor
  **共用同一避让集合**；Task 局部图中原 `pos = DDR` 的 tensor 一律改写为 `UB`；
  输出边界判定中「存在原 COPY_OUT 消费者」是**独立分支**。
- 场景 B 多播：每个 `(源核, 目标核)` 对各自新建一个 DDR tensor 与一对 COPY，
  两侧写向同一 `local_tid`；源核在 `PIPE_MTE3` 上**串行**执行这 n 次 COPY_OUT，
  使各消费者的 COPY_IN 被错开（实测 524 vs 534），而**这个错开直接决定 L2 是否命中**。

### 3.5 形式化与 L2 的一处耦合

spill 会把 victim 重命名到新化身并携带 `logical_tid`（实测 `{id: 113, logical_tid: 102}`）。
由于 Cache key 取 `tensor.get('logical_tid', tids[0])`，重命名化身的 key 仍为 **102**，
与原始 tensor 相同。**该结论只验证到 key 计算层面**：本批未在问题 3 的端到端运行中
观察到由此产生的命中，故不声称已观测到该行为后果。

## 4. 假设

以下为本次工作**依赖但未独立验证**的前提，列出以便复核：

1. **微图可代表机制**：所有实测都在 6–9 算子的构造图上完成，假设这些图足以暴露
   官方实现的分支结构；不对正式 100 个 case 的数值作任何外推。
2. **配置恒定**：全部实测使用 `data/config.txt` 的冻结值（带宽 60、L1 524288、UB 131072、
   等待 1000/100、L2 1048576/250），未做配置敏感性分析。
3. **官方入口为真值**：假设官方评估器的输出即为语义真值，本文不评价其合理性。
4. **单类型容量**：spill 实测只用了 UB 一种类型；假设 L1 与 UB 的容量检查逻辑同构，
   但**该假设未验证**。
5. **确定性**：Step1 与整个评估过程是确定性的，因此枚举式对抗无需固定随机种子；
   3.3 节的候选组枚举为确定性穷举，不含随机成分。
6. **模块覆盖**：`F-LOCAL` 的排序部分与 spill 部分已实测，但 **Step3 内部的内存依赖
   （`memory_dependencies`）未覆盖**；该缺口已登记，不视作已完成。

## 5. 局限

1. **规模**：全部实测限于微型构造图。3.3 节的排序对抗只覆盖 1 张图 × 2 核 × 问题 1；
   问题 2/3、核数 > 2、Cache 命中率类分层指标均未覆盖。
2. **未观测项**：`logical_tid` 与 Cache 的耦合只见于 key 计算层面；
   spill 的多轮 while、L1 与 UB 同时触发、多次 spill 的 version 递增链均未测。
3. **不充分性断言的边界**：3.3 节只声称「搬运统计不足以为这两个候选排序」，
   **不声称任何具体 E2 实现会犯此错**；表中的预测器是本工作自选的粗糙口径。
4. **规范条款不自签**：F-IO-002 与 F-METRIC-002 引自补充规范
   `docs/a/EVALUATOR_AMENDMENT_20260923.md`（提交 `ad1a2c57`），
   属**团队规范要求**，需由实现者提交逐字段兼容表并由队长指定的独立会话核对。
5. **未做 E0**：本批不包含任何 E0 评分或验收结论；E0 与队长验收不能由实现者代签。
6. **规则状态**：3 条规则仍为 `draft-sourced`（仅读源码），未冒充已验证。

## 6. 复现

```sh
# 形式化探针（各自输出到 results/a/form/r1-20260923-farmeruncle123/）
python src/adversarial/verify_io_r1.py               # 官方 CLI 端到端
python src/adversarial/verify_rules_r1.py            # F-PLAN（含商图成环反例）
python src/adversarial/verify_ftask_r1.py            # F-TASK
python src/adversarial/verify_order_r1.py            # 声明顺序敏感性
python src/adversarial/verify_fexec_r1.py            # F-EXEC
python src/adversarial/verify_local_r1.py            # Step1 排序与 Pipe 常量
python src/adversarial/verify_spill_r1.py            # spill 第一次尝试（失败留档）
python src/adversarial/verify_spill_r2.py            # spill victim 与插入位置（成功构造）
python src/adversarial/verify_time_r1.py             # F-TIME / F-RESOURCE
python src/adversarial/verify_l2_r1.py               # L2 Cache（问题 3）

# 对抗样本与排序对抗
python src/adversarial/build_dev_samples.py          # 首批 10 个开发反例样本
python src/adversarial/build_ranking_adversarial.py  # 候选组枚举找排序反转
python src/adversarial/verify_ranking_fixture.py     # 复验排序反转夹具（失败非零退出）

# 覆盖表重算
python src/adversarial/build_coverage.py
```

全部命令已在原生 Windows、Python 3.13 下实际运行通过。
