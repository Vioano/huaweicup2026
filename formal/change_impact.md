# change_impact.md — 变更影响面

run：`r1-20260923-farmeruncle123`｜用途：任何改动进入共享分支前，先按本表判断会波及哪些规则、
夹具与已发布的观察数值。表里只写**已由源码或探针确认**的因果，推断项单独标注。

## 1. 官方材料变更

| 变更 | 直接影响 | 需重跑的证据 | 备注 |
|---|---|---|---|
| `data/config.txt` 任一数值 | F-TIME-001/002、F-RESOURCE-001、F-METRIC-001 | `verify_time_r1.py`、`build_dev_samples.py` | 文件首行标注"不得修改"；改则所有 makespan 数值不可比 |
| `code/contest_io.py::_common_paths` / `run_problem_cli` | F-IO-001/003/004 | `verify_io_r1.py` | 默认方案名、默认配置位置、三件产物命名、错误出口与退出码 |
| `docs/a/EVALUATOR_AMENDMENT_20260923.md` | F-IO-002、F-METRIC-002 | 无需重跑探针；需重读条款 | 补充规范明确覆盖 `contract-v1` §2.2–2.4、§5.4，细化 §5.5；改版需重新比对本表 |
| `code/schedule_step2.py::trigger_one_spill` 的候选过滤与排序 | F-LOCAL-004 | `verify_spill_r2.py` | victim 需「有未来使用」且「不被当前 op 使用」；排序按 `-next_use`（Belady） |
| `code/schedule_step2.py::step2_spill_insertion` 的插入位置 | F-LOCAL-005、F-TASK-006 | `verify_spill_r2.py` | SPILL_OUT 锚在上次使用后、SPILL_IN 锚在下次使用前；重命名化身携带 `logical_tid` |
| `code/schedule_step1.py::step1_from_adj`（key / start_key） | F-LOCAL-001/002 | `verify_local_r1.py`、`verify_ftask_r1.py`、`verify_order_r1.py` | 排序方向极易读反：`-id` 与 `¬is_copy_*` 叠加 LIFO 后效果与直觉相反 |
| `code/schedule_step3.py::_op_duration` | F-TASK、F-METRIC、搬运取整 | `verify_ftask_r1.py`、`build_dev_samples.py` | COPY 时长 = `max(1, ceil(Σsize/bandwidth))` |
| `code/schedule_step3.py::PIPES` / `PIPE_SLOTS` | F-LOCAL-003、F-TIME-002、F-RESOURCE-001 | `verify_local_r1.py`、`verify_time_r1.py` | `PIPE_SLOTS=1`，同 Pipe 串行；改值会改变所有 makespan |
| `code/schedule_step3.py::_uses_ddr_bandwidth` | F-RESOURCE-001/002、F-TIME-002 | `verify_time_r1.py` | 决定谁进 DDR 争用池 |
| `code/stub_multicore_cut_and_schedule.py::derive_multicore_plan` | F-PLAN 全部 6 条 | `verify_rules_r1.py`、`add_fplan005_fixture.py` | 商图成环判定在此 |
| `code/multicore_cut_evaluate_problem_1.py::_build_scene_a_tasks` | F-TASK 全部 4 条 | `verify_ftask_r1.py`、`verify_order_r1.py` | 生成 id 分配、DDR→UB 改写、边界判定 |
| `code/multicore_cut_evaluate_problem_1.py::evaluate_scene_a` 事件循环 | F-TIME-001/002、F-RESOURCE-001 | `verify_time_r1.py` | 等待插入与 DDR 回溯重算都在此 |
| `code/evaluation_validation.py::validate_task_order` / `validate_execution` | F-EXEC-001/002 | `verify_fexec_r1.py` | 报错串里的边标签是判据来源 |
| `docs/a/source-manifest.json` | 所有 `sources[].sha256` | `build_coverage.py` | 规则卡哈希随清单更新；哈希不符会静默失效，需显式比对 |
| `.gitattributes`（`data/raw/a/**`） | 材料解包链路 | `scripts/a_materials.py --extract` | 队长提交 `1dbca4e` 修复 CRLF；再改需重验 |

## 2. 规则变更

| 变更 | 影响 |
|---|---|
| 规则卡 `status` 由 `draft-sourced` 升为 `verified-by-probe` | 必须同步 `formal/coverage.json`（由 `src/adversarial/build_coverage.py` 重新生成），否则两处状态不一致 |
| 新增机制组覆盖 | 需同时更新 `coverage.json` 的 `mechanism_groups` 与 `formal/SPEC.md` 的模块状态表 |
| 修改 `title`/`predicted_by_contract` | 属语义变更，需在 `INCREMENT-*` 回报中说明，不能静默改 |

## 3. 方案层面的已知陷阱（改动前必须知道）

以下四条都来自实测，若代理实现或改进算法按直觉处理，会得到与官方评估器不同的结论：

1. **空核计入核数**（F-PLAN-004/005）。按"非空核"实现会系统性偏大/偏小。
2. **生成 id 的 op 与 tensor 共用同一避让集合**（F-TASK-001）。分配顺序会互相影响，
   不可把两套 id 空间分开处理。
3. **DDR 完成时刻可被回溯推迟**（F-RESOURCE-001）。任何增量式"发放即定局"实现都错。
4. **只有端点含 DDR 的 COPY 进争用池**（F-RESOURCE-002）。一律计 DDR 会高估压力。

## 4. 方案变更的最小失效面（服务于缓存/增量更新）

来源材料（`AI chats/讲解A题调度.md` 第 4335 行）特别点名：**把一个子图从 Core1 移到 Core2，
不能直接假定只有这两个核心受影响**。本批的规则支持把失效面写得更具体：

| 方案变更 | 必然失效 | 依据 |
|---|---|---|
| `node_to_subgraph` 改一个 op 的归属 | 该子图与受影响子图的**全部** Task 构造；商图成环检查；边界 COPY 的插入与计数 | F-PLAN-005、F-TASK-002/003/005 |
| `node_to_subgraph` 改动（即使核心分配不变） | **生成的新节点 ID**——op 与 tensor 共用同一避让集合，分配顺序会互相影响 | F-TASK-001 |
| `core_schedules` 改归属（切图不变） | 跨核 COPY 对的数量与 `cross_task_traffic`；两类等待的取值；DDR 争用的时间重叠 | F-TASK-005、F-TIME-001、F-RESOURCE-001 |
| 仅改同核内的子图顺序 | 同核等待序列；可能的绝对时间；**F-TASK-004 实测该规模下 Task 局部结果不变**（范围化结论，不可外推） | F-TASK-004 |
| 任一改动 | `makespan`、`data_movement_bytes` 各分项、`memory_peak_by_core`、`per_core_timeline`、`ddr_contention_log` | F-METRIC-001、F-RESOURCE-001 |

**三点必须强调**：

1. **搬运统计相同不代表结果相同**（F-METRIC-004）：切图与搬运逐字节相同的两个方案，
   仅核心归属不同即可相差 900 cycles。**不能以"搬运量未变"作为复用缓存结果的依据。**
2. **生成 ID 会随切图变化**（F-TASK-001），因此以 ID 为键的任何缓存都要一并失效。
3. **DDR 争用是全局回溯重算的**（F-RESOURCE-001）：局部改动可能改变**其它核**已在飞传输的
   完成时刻，所以"只重算受影响的两个核"在原理上不成立。

## 5. 禁止的推断方向（限制条件第 4 条要求的对偶面）

任务卡明确要求"重编号、交换核心、加核、增 Cache 等变换不得未经证明断言指标不变或改善"。
本批可提供的**反例**仅一条：

- **加核不保证提速**：单链 1 核 makespan=24；两条独立链 2 核 makespan=44（见
  `results/a/form/r1-20260923-farmeruncle123/time-resource-observations.json`）。
  该反例只在微型构造图上成立，**不足以**证明正式用例也如此。

**交换核心、重编号、增 Cache 三类变换我尚未构造任何反例或正例**，因此在本批中不对其
做任何断言。凡后续规则或论文段落涉及这三类变换，都必须先补对应探针。

## 6. 未验证项（不得在改动说明中当作已知）

以下均为**当前仍未覆盖**的项，逐条对应规则卡的 `blocked_reason` 或 `coverage.json` 的 note。
（本表已按最后一轮实测更新：`PIPE_SLOTS` 取值、L2 带宽独立性、spill 触发条件、
搬运五字段等式此前列为未知，现均已实测。）

1. **Pipe 队首阻塞时的可越过性**：来源材料（`讲解A题调度.md` 第 4296–4298 行）要求回答
   「已经固定的队首操作在等待跨核输入时，后面的操作能否越过它」。本批**未构造该探针**；
   F-LOCAL-003 只证明 `PIPE_SLOTS=1` 与同 Pipe 串行。
2. **spill/rename 的 `logical_tid` 命中路径**：只验证到 cache key 计算层面
   （F-RESOURCE-005），未在问题 3 的一次运行中观察到由此产生的命中。
3. **`>=3` 个并发命中时 `CACHE_READ` 池（250 B/cycle）的分段换算**。
4. **spill 的多轮 while、L1 与 UB 同时触发、多次 spill 的 version 递增链**；
   `next_use` 并列时的稳定排序行为。
5. **一次插入淘汰多个 Cache 条目**；以及同刻不同 key 的混合插入顺序。
6. **问题 2/3 的对应统计字段**（`transfers`、`memory_peak` 等）的取值口径；
   `data_movement_bytes` 各字段定义与题面口径的一致性（本批只核对字段间的代数关系）。
7. **Step3 额度被拆分/合并的复杂情形**，以及容量恰为 1 个 tensor 时的复用行为
   （该容量在本批构造下被 Step2 的 spill 检查提前拦下）。
8. **正式 100 个 case 上的任何数值结论**——本批全部实测都在微型构造图（6–9 算子）上完成，
   不可外推。
9. **交换核心、重编号、增 Cache 三类变换**：本批未构造任何正例或反例（第 5 节已声明不做断言）。
10. **未读完的讨论材料中若有评估器行为断言**，需逐条与本批规则核对（见
    `paper/sections/a-formal.md` §7.3 的补读回执）。
