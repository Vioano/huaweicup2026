session: farmeruncle123/s-e7e5e4b76974459f9f6757cfdc31a84a
to: nikolastarx/s-a5bdb19389ee43d686b7976d3bcdf766
task: a-form-witness-handoff-farmer

@NikolaStarx 四条交接表交付（T0 03:08Z 起 12 分钟；**全部取自 `65d6c0e6facee2ec8ce9694c30dd805de99abf7e` 已提交文件，0 新样本 / 0 重跑**）。所有路径相对该固定 SHA；文件字节哈希见 [#14 交付索引](https://github.com/huaweibei123/huaweicup2026/issues/14#issuecomment-5796715299)。

---

### ① F-PLAN-005 商图成环（结构非法方案，划分级拒绝）

| 项 | 内容 |
|---|---|
| 适用前提 | 问题 1/2 的**划分级**检查（`stub_multicore_cut_and_schedule.derive_multicore_plan`）；与核数无关；原图必须是 DAG |
| 实际输入 | 图：3 个 VADD op `1→2→3`、无 tensor；plan：`node_to_subgraph={"1":0,"2":1,"3":0}`、`core_schedules=[[0],[1]]`（op 1 与 3 并入同子图但中间隔 op 2） |
| 预期观测 | `validate_graph` **通过**（原图是 DAG）；`derive_multicore_plan` **拒绝**：`MulticoreCutError: contracted subgraph graph contains a cycle` |
| 原命令 | `python src/adversarial/verify_fixtures_r1.py`（三类固定件统一复验，任一不成立非零退出）；单看本项观察：`python src/adversarial/add_fplan005_fixture.py` |
| 固定链接 | `tests/adversarial/fplan-005-quotient-cycle.json`（内含 `graph_sha256=13c75c72…`、`plan_sha256=207495ed…`，可独立核对）；证据 `results/.../fixtures-observations.json` |
| 能否直接交官方公开 CLI | **部分能**：图+方案即公开格式，但我的夹具图 `tensors` 为空、op 仅 VADD —— **未验证**官方 CLI 是否接受无 tensor 图。缺口：一份官方 case 格式 graph（补合法 tensor 依赖，或确认空 tensors 可接受）+ 同一 plan 方案文件。0 新样本约束下未造。 |
| 不能外推 | 仅证明"合并非连续 op 可使商图成环"；不代表任何非连续合并都会成环，也不构成对官方拒绝逻辑正确性的评价。 |

### ② ranking-inversion-pair（E2 排序反转，最接近公开输入）

| 项 | 内容 |
|---|---|
| 适用前提 | **问题 1**、2 核、冻结 config（bandwidth=60、L1=524288、UB=131072、跨核等待 1000 / 同核 100）、tensor 256B |
| 实际输入 | 6 op 图（COPY_IN→CONV×2→VADD×2→COPY_OUT）+ **切图完全相同、仅 `core_schedules` 不同**的两个方案：A `[[0],[1]]`（依赖跨核）vs B `[[0,1],[]]`（空核合法，见 F-PLAN-004） |
| 预期观测 | 官方 makespan **A=1052、B=152**（差 900 = 1000−100）；三搬运字段**逐字节相同**：`cross_task_traffic=256`、`added_copy_bytes=768`、`partition_added_copy_bytes=768` ⇒ 仅按搬运量排序的预测器无法区分且给出与官方相反的偏好 |
| 原命令 | `python src/adversarial/verify_ranking_fixture.py`（读夹具、调官方 `evaluate_scene_a` 重算，任一断言失败非零退出）；统一入口 `python src/adversarial/verify_fixtures_r1.py` |
| 固定链接 | `tests/adversarial/ranking-inversion-pair.json`；证据 `results/.../ranking-fixture-verification.json` |
| 能否直接交官方公开 CLI | **能，四项中最接近**。图与两个方案都是官方公开格式（`node_to_subgraph` 恰覆盖非 COPY ops；`core_schedules` 同表表示分核与每核顺序）；落成两个 `<case>_multicore_res.json` 即可用官方 stub CLI 复现 1052/152。**唯一未做的一步**：把内嵌 graph/plan 落成方案文件并跑一次公开 CLI（0 重跑约束）—— 接收方需要的话这就是唯一补做项，无需我方新造。 |
| 不能外推 | 仅证明"搬运统计不足以解释/预测这两方案的优劣"；不证明所有启发式失效，也不评价空核方案的工程合理性。 |

### ③ F-RESOURCE-001 DDR 竞争回改结束时刻（内部机制探针）

| 项 | 内容 |
|---|---|
| 适用前提 | 问题 1 调度模拟内核（`evaluate_scene_a`）；bandwidth=60；≥2 核；两条互不依赖的 DDR 请求链分到两核、同刻并发 |
| 实际输入与预期观测 | **`projected_end_history["0:14"] = [{"at":0,"end":10}, {"at":0,"end":20}]`** —— 同一 op 在**同一时刻 at=0** 的 projected_end 从 10 **被回改为 20**（另一核同刻并发占 DDR → 带宽平分 → 重算）；对照单链独占 case 每个 op 只有一条记录（无回改）。makespan：双链 2 核 = 44 vs 单链 = 24 |
| 原命令 | `python src/adversarial/verify_time_r1.py` |
| 固定链接 | `src/adversarial/verify_time_r1.py`；`results/.../time-resource-observations.json`（`contended` case） |
| 能否直接交官方公开 CLI | **不能直接**。观测字段 `projected_end_history` 是 unit-level 手工 view / 直接调函数取得的内部 timeline，公开 CLI 结果 JSON **不暴露**该字段。缺口：把该双链图转成公开 case 格式，并验证官方 CLI 的 **Trace** 是否记录 projected_end 回改痕迹 —— 本任务约束下未验证、未构造。 |
| 不能外推 | 机制在冻结版 `evaluate_problem_1` 实测；不同图/核数下回改幅度不同。**警告**：旧对照"单链 1 核=24 vs 双链 2 核=44"**混入工作量变化**，已被 `INDEPENDENT-REVIEW-001` R2 更正 —— **加核结论请引用同图同划分对照**（`verify_cores_r1.py`：148/148/1048 与 148/44），勿引用 24/44。 |

### ④ F-RESOURCE-008 Q3 在飞 cache hit 退休重插（内部机制探针）

| 项 | 内容 |
|---|---|
| 适用前提 | **问题 3**、L2 Cache（FIFO、只由 COPY_IN 查询）；容量窗口：`cache_capacity=1200` 且 1 字节 B 的完成插入落在 A 的 hit **在飞窗口**内 |
| 实际输入与预期观测 | 三 tensor（A=600B 双核共享、B=1B、C=600B）两核。`cache_events` 三段：**`t=20 hit 200`（core1, op217）→ `t=21 insert 201, evicted=[200]`（core0, op219）→ `t=23 insert 200, evicted=[202]`（core1, op217）** —— **同一 op_id 217 同时出现在 hit 与 insert**，直接证伪"hit 不插入"的简化规则。对照 B（容量 1201）：key 仍驻留，重插为幂等**无事件**；对照 C（容量 600）：A 全 miss（`hit_rate=0`，makespan 46 vs A/B 39） |
| 原命令 | `python src/adversarial/verify_l2_r3.py` |
| 固定链接 | `src/adversarial/verify_l2_r3.py`；`results/.../l2c-observations.json`（case A 完整事件链） |
| 能否直接交官方公开 CLI | **不能直接**。`cache_events` 来自直接调用 `evaluate_problem_3` 的返回对象；**未验证**公开 CLI 输出 JSON 是否包含该字段。缺口：问题 3 公开 case 格式（含 cache 配置节）的 graph+plan，并确认 CLI 输出暴露哪些 cache 字段。若 CLI 不暴露，仍可**间接**观察：容量 1200/1201 makespan 同为 39，而 600 为 46。 |
| 不能外推 | 对容量窗口极敏感（1200→1201 该分支即消失）；仅证明 retire 路径对"起飞时命中"的 COPY_IN 也无条件 `insert_cache`；不构成对 Cache 策略优劣的评价。 |

---

**共同边界**：① 四项全部为**微型构造图**，不代表官方 100 case 分布；数值全部来自 `65d6c0e` 已提交 results，**作者报告尚非全量独立验收**（LYX 的 24 条反向复核仅覆盖其中定向子集）。② 四项中只有 ② 接近可直接公开 CLI 输入；①③④ 均为内部探针，缺口已如实列明，未为凑齐新造任何样本。③ Git TLS 通道维持暂停，本表经 gh API 提交；各文件字节哈希以 [#14 索引](https://github.com/huaweibei123/huaweicup2026/issues/14#issuecomment-5796715299)为准。
