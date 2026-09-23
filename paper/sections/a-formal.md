# A-formal：官方评估过程的形式化方法与语义对抗

本节属于 A 题第一轮的 FORM 交付，任务 Issue [#14](https://github.com/huaweibei123/huaweicup2026/issues/14)，
run-id `r1-20260923-farmeruncle123`。内容为**形式化规范与语义对抗样本**的工作记录，
不包含任何方案质量或性能结论。

## 1. 目标与边界

**目标**：把官方评估过程写成能指导实现与测试的规范，并构造能揭露等价实现偏差与筛选失效的
语义对抗样本。规则、夹具、生成器与反例形成对应关系。

**不做的**：不重写整个官方评估器；不调用队长的 oracle 适配层；不做正式基准与全量验收；不产出任何性能、加速比或质量结论；
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

截至本批，`rules.jsonl` 共 **38 条**（36 条 `verified-by-probe`，2 条 `draft-sourced`），
八个模块均已产出规则卡（F-PLAN 6、F-TASK 6、F-LOCAL 6、F-RESOURCE 7、F-IO 4、
F-METRIC 4、F-EXEC 3、F-TIME 2）。任务卡第 5 节要求的**六个机制组全部覆盖**。
以下列出对实现与筛选有直接影响、且已由探针复现的语义点。

### 3.1 排序与内存（F-LOCAL，6 条）

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

### 3.2 时间与资源（F-TIME 2 条、F-RESOURCE 7 条）

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
6. **模块覆盖**：八个模块均已产出规则卡。`F-LOCAL` 的排序、spill 与 Step3 内存复用
   （`memory_dependencies`，见 F-LOCAL-006）均已实测；**仍未覆盖**的是「Pipe 队首阻塞时
   能否被越过」等子项，逐条见 §5 第 6 项与 `coverage.json` 的 `limitations`。

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
5. **术语说明**：本批探针**直接调用冻结官方函数/CLI**（即队内所称 E0 的代码本体）取原始输出；**未调用队长的 oracle 适配层**，**未做正式基准与全量验收**，也不包含任何验收结论——独立验收不能由实现者代签。
6. **规则状态**：38 条规则中 **36 条 `verified-by-probe`**、**2 条 `draft-sourced`**（F-IO-002、F-METRIC-002，均为需独立验收的团队规范条款），未冒充已验证。

## 6. 复现

`src/adversarial/` 共 **20 个 `.py` 文件**，全部列出如下，与文件数一一对应（便于核对计数口径）。

```sh
# A) 形式化探针：17 个，每个产出 1 份 results/ JSON（verify_spill_r1 的产物为 PARTIAL 记录）
python src/adversarial/verify_io_r1.py               # F-IO 官方 CLI 端到端
python src/adversarial/verify_rules_r1.py            # F-PLAN（含商图成环反例）
python src/adversarial/verify_ftask_r1.py            # F-TASK（生成 id / DDR→UB / 输出边界）
python src/adversarial/verify_order_r1.py            # F-TASK-004 声明顺序敏感性
python src/adversarial/verify_fexec_r1.py            # F-EXEC（Task 顺序环检查）
python src/adversarial/verify_fexec_r2.py            # F-EXEC-001 量词回归（混合长度核）
python src/adversarial/verify_local_r1.py            # Step1 排序与 Pipe 常量
python src/adversarial/verify_local2_r1.py           # Step3 内存复用（虚拟额度）
python src/adversarial/verify_spill_r1.py            # spill 第一次尝试（失败留档，PARTIAL）
python src/adversarial/verify_spill_r2.py            # spill victim 与插入位置（成功构造）
python src/adversarial/verify_time_r1.py             # F-TIME / F-RESOURCE
python src/adversarial/verify_cores_r1.py            # 同图同划分的加核对照（R2）
python src/adversarial/verify_l2_r1.py               # L2 命中 / FIFO / 字节加权
python src/adversarial/verify_l2_r2.py               # L2 同时 miss 与淘汰路径
python src/adversarial/verify_metric_r1.py           # 搬运五字段等式核对
python src/adversarial/verify_ranking_fixture.py     # 复验排序反转夹具（失败非零退出）
python src/adversarial/build_dev_samples.py          # 首批 10 个开发反例样本

# B) 生成器：1 个（同样产出 results/ JSON，但耗时较长，故与上面 15 条分开列）
python src/adversarial/build_ranking_adversarial.py  # E2 排序对抗：候选组枚举找排序反转

# C) 一次性夹具生成：1 个（产物在 tests/adversarial/，不写 results/）
python src/adversarial/add_fplan005_fixture.py       # 生成商图成环反例夹具

# D) 覆盖表重算：1 个（只写 formal/coverage.json，不写 results/）
python src/adversarial/build_coverage.py
```

**计数口径**：20 = 17（A，各产出 1 份 results/ JSON）+ 1（B）+ 1（C）+ 1（D）。
**`results/a/form/r1-20260923-farmeruncle123/` 共 19 份 JSON** = A 组的 17 份 + B 的 1 份
+ `fplan-005-observation.json`（C 的产物）。
**文件数与运行次数是两个口径**，不混用。
（本轮响应 INDEPENDENT-REVIEW-001 新增 `verify_fexec_r2.py` 与 `verify_cores_r1.py`，
故由 18/17 变为 20/19。）

全部命令已在原生 Windows、Python 3.13 下实际运行通过。

## 7. 与来源材料的对照，及补读回执

### 7.1 与 `AI chats/讲解A题调度.md` §二 的对应

该节（第 4255–4336 行）给出了形式化任务的直接定义。本批交付与之对应如下：

| 该节要求 | 本批对应 |
|---|---|
| 必须覆盖的**八部分** | 八个模块一一对应：输入与配置→F-IO、切图与调度合法性→F-PLAN、Task 构造→F-TASK、核内展开→F-LOCAL、全局可执行性→F-EXEC、时间与同步→F-TIME、共享资源→F-RESOURCE、输出指标→F-METRIC |
| 规则卡字段（含**文件哈希**） | 每条规则的 `sources[]` 均带所引源码文件的 SHA-256；另记录行区间与符号 |
| **五类产物** | `SPEC.md`、`rules.jsonl`、`coverage.json`、`ambiguities.md`、`change_impact.md` 均已交付 |
| 重点一：基础切图校验通过 ≠ 最终可执行 | F-PLAN-005 实测商图成环（6 算子小图上 30 个分区中 14 个被拒） |
| 重点二：Step3 不只算局部时间，还输出固定 Pipe 顺序与内存复用依赖 | F-LOCAL-003/005/006 |
| 重点三：问题三的搬运统计**不得自行重定义**（不得把 Cache 命中字节从 `data_movement_bytes` 里扣掉） | 本批未改动该字段的任何定义；F-METRIC 系列只**描述**官方口径。该条作为**约束**被遵守，未作为可改动项 |
| `change_impact.md` 要服务于缓存与增量更新（移动一个子图不能假定只有两个核心受影响） | 见 `formal/change_impact.md` |

### 7.2 一个独立复现的锚点

`讲解A题调度.md` 第 4510 行记录：共享输入小图在问题三中得到的是「**两个 COPY_IN 都 miss，
而不是一个 miss、一个 hit**，因为两次查询都发生在数据进入 L2 之前」。

**本批 F-RESOURCE-006 独立复现了同一现象**：改用图输入 tensor 构造后，
`events_by_time = {'0': ['miss','miss'], '20': ['insert']}`——同刻两次 miss、仅一次 insert。
机制相同：命中判定发生在任何 insert 之前。

**需要说明的是**：该节提到的「两个人工小图和六份原版输出」锚点**不在本批冻结材料内**
（`data/raw/a/official/` 只含 100 个 `case_*.json`、`config.txt` 与 10 个源码文件），
因此本批**无法**直接复跑那两个锚点，只能以自构造图独立复现同一现象。

### 7.3 补读状态与对本批的影响

**已全文读完**（与本任务直接相关）：`AI chats/A题方法.md`（1363 行全文）、
`docs/a/contract-v1.md`、`docs/a/READ_AUDIT.imported.md`、`docs/TEAM_WORKFLOW.md`、
`AGENTS.md`、`docs/a/SYNC_UPDATE_20260923.md`、`docs/a/EVALUATOR_AMENDMENT_20260923.md`、
`讲解A题调度.md` 第 4219–4611 行（形式化任务定义、E1/E2 验收与交叉测试）。

**未全文读完**（截至本批）：

| 材料 | 行数 | 已读范围 | 对本批的影响 |
|---|---|---|---|
| `讲解A题调度.md` | 4611 | 251–500、606–805、935–1085、2310–2520、**4219–4611** | 未读段落主要是题目讲解与 E1/E2 背景；**形式化任务定义段已读完**。未读段落中若含评估器行为断言，本批可能尚未对照 |
| `选择建模题目策略.md` | 4094 | 仅章节标题 | 属选题策略与论文写法，与 FORM 语义规则无直接关系 |
| `paper/template-2026/`（**当前共享模板**，已替换 2025 社区模板） | — | **未读** | 不影响本批 FORM 语义规则。注意：本分支基于派发提交 `ea25b933`，其 `paper/` 下仍是 `template-2025`；main 已替换为 `template-2026`（GMCM2026-LaTeX-Template v1.7）。**本分支未修改任何模板文件**，PR 差异中不含 `template-2025`（已核验 0 条） |
| 新版 `docs/a/ATLAS.md`、`CANVAS.md`、`output/pdf/` | — | 未读 | 不影响本批 FORM 语义规则 |

**交接待办（未覆盖项，不以覆盖率掩盖）**：

1. `讲解A题调度.md` 第 4296–4298 行明确要求形式化必须进一步回答：
   **「多个操作都满足依赖时，谁先进入 Pipe？已经固定的队首操作在等待跨核输入时，
   后面的操作能否越过它？」**——本批**未构造该探针**。
   已有规则 F-LOCAL-003 只证明了 `PIPE_SLOTS=1` 与同 Pipe 串行，**未覆盖「队首阻塞时能否被越过」**。
2. 未读段落的**完整比对**（若其中有对评估器行为的断言，需逐条与本批规则核对）。
3. 并列 `next_use` 时的稳定排序行为（F-LOCAL-004 的 `blocked_reason` 已列）。

## 8. 独立复核发现的两处修订（响应 INDEPENDENT-REVIEW-001）

队长在独立环境（macOS / Python 3.12.13）复跑本批 18 个脚本（当时版本）后提出两项修订。
**两项都是我方的实质错误**，已修正并各自补了回归证据。修订只涉及规则文字、说明与新增探针，
**未改动官方代码、未改 E0/阈值、未改任何已发布的观察数值**。

### 8.1 R1：`F-EXEC-001` 的量词写反

- **原文（错）**：谓词字段写「若**任一核**的 order 长度 <= 1 则直接返回」。
- **源码（对）**：`evaluation_validation.py:219` ——
  `if not any(len(order) > 1 for order in view['core_orders'].values()): return`，
  即**所有核的 order 长度均 <= 1 才提前返回**。
- **后果**：按错误量词重写实现，会在「一个核有多个子图、另一个核为空」时错误跳过检查，
  漏判顺序环。
- **已修**：谓词改为正确量词，并新增 `verify_fexec_r2.py` 覆盖 6 个用例，并逐个标注**是否能否区分两种量词**：
  **能区分（充要形态 = 混合长度核，即至少一个核长度 > 1、且至少一个核长度 <= 1）**：
  A `core0=[1,0], core1=[]` → 拒绝；B `core0=[1,0], core1=[2]` → 拒绝。错误量词会在 A/B 上因『某个核长度 <= 1』而提前返回、从而**错误接受**；
  **分支条件不同但最终结果相同**：C 正向顺序 + 空核（两者都接受）；
  **不能区分**：D 全单子图核、E 单核单子图、F 单核长度 2（`any(len<=1)=False` 且 `all(len<=1)=False`，两种量词都不提前返回）——F 只作单核逆序的拒绝对照。
- **边界**：全部为 **unit-level 手工 view**，属非正式输入域；
  **不声称**官方入口可产出同一情形（入口可能更早拒绝逆序）。

### 8.2 R2：加核结论的原对照混入了工作量变化

- **原文（错）**：用「单链 1 核 = 24」对「双链 2 核 = 44」说明加核问题。
  两者**工作量不同**（1 条链 vs 2 条链），不能支持固定工作量下的加核结论。
- **已修**：保留该观察作为**共享 DDR 带宽争用**的证据，并改用**同图同划分**对照
  （`verify_cores_r1.py`，数值与本队长的独立复核一致）：

| 图与划分 | `core_schedules` | makespan |
|---|---|---:|
| 两条独立链、两个子图 | `[[0,1],[]]` | 148 |
| 同上 | `[[0],[1]]` | 44 |
| 有依赖的两段 | `[[0,1]]`（1 核） | 148 |
| 同上，只添加空核 | `[[0,1],[]]` | 148 |
| 同上，改分配到两核 | `[[0],[1]]` | 1048 |

- **修正后的结论范围**：支持「**具体分配方案**未必因使用更多核而更快」——
  **不能**外推为「核预算增大时最优值必然变差」（同图上的两条独立链分核后反而 148 → 44）。
  必须区分具体方案、核预算与最优值。

**未受影响的项**：F-EXEC-002/003、F-RESOURCE-001 的 projected_end 回溯重算观察、
排序夹具 1052/152、以及其余全部规则与数值均未被这两项修订触及。

