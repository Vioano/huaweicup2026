# ambiguities.md — 未知项与题面/实现差异

run：`r1-20260923-farmeruncle123`｜范围：A 题第一轮 F-PLAN/F-TASK/F-EXEC/F-TIME/F-RESOURCE/F-METRIC
原则：**只登记有来源的分歧**。凡我尚未验证的，写"未验证"，不写结论。

图例：`[差异]` 题面/讨论与实现不一致；`[疑问]` 实现行为清楚但语义动机不明；`[缺口]` 我还没测。

---

## A. 题面·讨论文档 vs 官方实现

### A-1 `[差异]` tensor id 的起点约定
- **讨论文档**（`AI chats/A题方法.md`）：tensor id 从 `10001` 起、边带 `data_size`。
- **实现/样例**：`case_001.json` 的 tensor id 从 **1** 起，边只有 `source`/`target`，无 `data_size`。
- **实测**（F-TASK-001）：`10000` 是**生成的新** tensor id 的下界（实测新 id 从 `10001` 开始），不是输入约定。
- **风险**：把两者读混，会写出"输入 id 必须 ≥10001"的错误校验。
- **状态**：已分辨，F-TASK-001 已实测。

### A-2 `[差异]` 场景配置不在 case 文件里
- `case_*.json` 只有 `tensors`/`ops`/`edges` 三个顶层键。
- 带宽、容量、两类等待、L2 参数全部来自 `data/config.txt`（`[capacity]`/`[bandwidth]`/
  `[multicore_scene_a]`/`[multicore_scene_b]`/`[problem_3]`），该文件首行写明"不得修改"。
- **影响**：做任何指标对比前必须确认 config 一致，否则数值不可比。
- **状态**：已确认（F-TIME-001、F-RESOURCE-001 的常量来源）。

### A-3 `[差异]` 「分区合法」不等于「官方展开后可执行」
- 讨论文档给的 4 节点微图：分区校验通过，官方展开时以等待环拒绝。
- **实测**：F-PLAN-005。原图是 DAG，但按 `node_to_subgraph` **分组**后的商图可成环，
  `derive_multicore_plan` 抛 `contracted subgraph graph contains a cycle`。
- **我的纠正**：我最初判断该分支"不可达"，是错的；队长给出反例后由探针复现。
- **状态**：已实测，`correction` 字段保留在规则卡中。

### A-4 `[差异]` 同刻事件与"等分带宽"的可加速性
- 直觉（也见于部分讨论）：搬运时间可分摊累加。
- **实现**：DDR 带宽等分且**每个在飞 op 的完成时刻会被后来者回溯重算**；后发起的传输
  会推迟已在飞传输的 `op_end`（实测 10→20、34→44）。
- **影响**：任何"发放即定终局"的增量式实现都会算错。
- **状态**：已实测（F-RESOURCE-001）。

### A-5 `[差异]` 空核是否计入核数
- **实测**：`core_schedules=[[0],[]]` 被接受，`num_cores=2`。**空核计入核数**。
- **风险**：把"核数"实现成"非空核数"会直接偏。
- **状态**：已实测（F-PLAN-004/005 批次）。

### A-6 `[差异]` id 字面表示不唯一
- 键 `"02"` 与 `"2"` 都通过整数校验，且被判为**重复**目标。
- **含义**：存在"看起来不同、实际同一 op"的方案表示，是现成的语义对抗点。
- **状态**：已实测。

### A-7 `[差异]` 跨核等待只在"真实前驱 + 异核"时生效
- 讨论文档强调"不是所有不同核上的子图都互相等"。
- **实现**：确认。`release` 只对 `pred_tasks` 中的异核项加 `cross_core_wait`；
  同核等待则由"该核上一个 Task"触发，与依赖无关。
- **实测**：同核 148 vs 异核 1048，差值恰为 `1000-100`。
- **状态**：已实测（F-TIME-001）。

---

## B. 实现行为清楚但动机/边界待明确

### B-1 `[疑问]` spill 触发时不允许"无可淘汰对象"
- `schedule_step2` 在超容量且当前 step 无空闲存活 tensor 时，**硬报错**
  `Step2SchedulingError: no spill victim`，而不是降级或放宽。
- **我的观察**：3 种拓扑都撞到这个分支，说明"能发生 spill"本身有前提。
- **未验证**：正式 case 里 31 个样例出现了 SPILL 新增搬运，说明该分支在真实规模可避开；
  触发条件的完整刻画未做。
- **状态**：机制已定位，未取得 `>=1 spill` 的成功运行（见 F-*/coverage 的 `gap-with-mechanism`）。

### B-2 `[疑问]` 非 COPY op 缺 `cycles` 时的默认值
- `_op_duration`：非 COPY op 返回 `max(1, op.get('cycles', 1))`。
- **未验证**：样例是否恒带 `cycles`；若缺失，默认 1 是否会掩盖数据问题。

### B-3 `[已解答]` `PIPE_SLOTS` 不对外开放
- 源码常量：`PIPES = ('PIPE_MTE2','PIPE_MTE3','PIPE_M','PIPE_V')`，**`PIPE_SLOTS = 1`**，
  注释明示"不对外开放"。
- **含义**：同一 `(core, pipe)` 上串行，选手方案无法改变。
- **状态**：已由 F-LOCAL-003 实测（import 官方模块后直读常量）。

### B-4 `[已解答]` L2 带宽与 DDR 带宽互不占用
- **实现**：`bandwidth_pools` 有 `DDR` 与 `CACHE_READ` 两个**独立池**；命中时
  `effective_bandwidth = cache_bandwidth (250)`，且该 op **只**进 `CACHE_READ` 池，
  `if cache_hit ... elif _uses_ddr_bandwidth(...)` 是互斥分支。
- **实测**：600 字节 tensor，miss 时长 10（=ceil(600/60)）、命中时长 3（=ceil(600/250)）；
  `memory_paths = {'DDR': 6, 'CACHE_READ': 1}`。
- **状态**：已由 F-RESOURCE-003 实测。**未测** ≥3 个并发命中时 `CACHE_READ` 池的分段换算。

### B-5 `[部分解答]` Step1 排序方向容易读反（已实测）
- **实现**：`key = (¬is_copy_in, depth, -id)`，升序压栈 + LIFO 弹栈。
- **实测方向**：同深度时 **id 较小者先输出**（第三段是 `-id`）；
  **COPY_IN / COPY_OUT 分支反而最后输出**（首段为 `False` 只让它排在升序列表前面，
  先入栈者后出栈）。两处都与直觉相反。
- **未验证**：Step3 内存依赖与 rename 对序列的影响；内存复用部分未开始。
- **状态**：已由 F-LOCAL-001/002 实测；**内存复用仍是缺口**。

### B-6 `[已解答]` Cache 命中率的口径
- **实现**：`hit_rate = hit_bytes / (hit_bytes + miss_bytes)`，**按字节加权**。
- **实测**：把两个可缓存 COPY_IN 的尺寸做成 60 与 600 字节后，上报值
  `0.47619 = 600/1260`（按字节），而按访问次数会是 `0.3333`。二者可区分。
- **状态**：已由 F-METRIC-003 实测。

### B-7 `[疑问]` `logical_tid` 的缓存键语义
- Cache key = `tensor.get('logical_tid', tids[0])`；`logical_tid` **只由 Step2 的
  spill/rename 机制写入**（`schedule_step2.py:315-419`），普通 tensor 退化为物理 id。
- **含义推断**：同一逻辑 tensor 的多个物理化身（spill 重命名后）**会共用同一 Cache 条目**，
  即 spill 与 L2 命中存在耦合。这是官方语义下最微妙的耦合点之一。
- **未验证**：我没有构造出触发 rename 的运行（见 spill 组 `gap-with-mechanism`），
  因此**只登记字段来源与推断，不声称已观测到该耦合的行为**。

---

## C. 工程环境（影响复现，不属于算法语义）

### C-0 `[已澄清]` 补充规范与 `contract-v1` 的优先级
- `docs/a/EVALUATOR_AMENDMENT_20260923.md`（固定提交 `ad1a2c57`，
  SHA-256 `f6b836d4289889da7295d88bd9f14525b14ed6ff2819c611bdab5220fad386d9`）
  明确覆盖 `contract-v1` §2.2–2.4 的公开接口优先级、§5.4 的校准 Makespan 门槛，
  细化 §5.5 的计时口径；**其余一致性、来源、封存与失败处理约定继续生效**。
- 其数值门槛（E1 ≥3×、E2 ≥10×、中位数 ≤1% / P95 ≤3%）是**队内研发标准**，
  不是官方要求，也不是已达成结果；`AI chats/` 导入原件与 `contract-v1` 保持未改。
- **与我的范围的关系**：补充规范主体针对 `a-r1-fast-eval`；**我的 FORM/对抗范围不扩大**。
  我只登记与 F-IO（§1）、指标（§5）、开发反例（§1 末段）相关的条款。
- **状态**：已读并登记为 F-IO-001..004、F-METRIC-002。

### C-1 `[差异]` 冻结材料的换行被 Git 改写
- `.gitattributes` 的 `* text=auto` 使 `data/config.txt` 在 Windows 检出为 CRLF（360 B），
  与清单的 341 B / `dcd10de5…` 不符，`scripts/a_materials.py --extract` 直接失败。
- **已由队长修复**（提交 `1dbca4e`）；我在原生 Windows 默认配置下实测通过。
- **状态**：已解决。

### C-2 `[差异]` 本机建不了嵌套本地分支
- `git branch codex/x/y` 返回 0 但不写 ref；扁平名正常。两套 Git、多个目录位置均复现。
- **影响**：本地分支名需用扁平形式；远端 GitHub HTTPS 不受影响。
- **状态**：已绕开，已报队长。

### C-3 `[差异]` Atlas 同步受本机 TLS 拦截影响
- `NODE_OPTIONS` 注入的删除守卫会拦 Atlas 清理临时索引；需 `env -u NODE_OPTIONS`。
- transport 仓库继承不到项目的 `http.sslverify=false`，需在 transport 仓库内单独设置。
- **状态**：已绕开，均已报队长；**不提议推广为团队配置**。

---

## D. 本批未覆盖（不得当作通过）

| 组 | 状态 | 说明 |
|---|---|---|
| spill/容量临界 | `gap-with-mechanism` | 机制已定位，无可复现的成功运行；连带阻塞 B-7 的 `logical_tid` 命中验证 |
| Step3 内存复用 | `partial` 的未覆盖部分 | 排序口径已实测，内存依赖与 rename 未构造 |
| L2「同时 miss」与淘汰路径 | `partial` 的未覆盖部分 | 命中/FIFO/超容量/字节加权已实测；同刻同时 miss 与 evicted 非空未构造 |
| F-METRIC 搬运算式 | 部分 | 仅读源码，未逐字段核对 |

**说明**：以上缺口已写入 `formal/coverage.json`，与规则卡状态一一对应。
