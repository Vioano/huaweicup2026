# 共同求解控制层 v0：候选、确认与发布

**拟议契约，未实现。** 这里统一三问的运行边界，保留各自构造器及状态；不建立第二套 worker、账本、缓存、网站 schema 或 Atlas 调度器。[公共目标][objectives]与 [s55 设施设计][infra]优先于 Pro 建议。

## 1. 一次求解与三类对象

一次 `SolverRun` 固定 `problem / graph_bytes_hash / k / config_bytes_hash / official_code_hashes / solver_commit+source_hashes / algorithm_policy / parameters / random_seed`，以及机器资源、截止时点、调用额度、历史输入及成本边界。输出计划只能有 `node_to_subgraph`、`core_schedules`；凭据和研究元数据不进入比赛计划。

- `Seed/Proposal`：构造器产出的不可变有序计划字节、适用域/guard、来源版本、参数、构造成本与失败说明；默认没有有效分数，更没有可提交保证。已有赢家作为历史输入须绑定原证据；从图求解与利用历史 seed 的改进实验分开报告。
- `I`（confirmed incumbent）：同一求解上下文内、合法性及目标字段已经获准精确后端确认、证据和计划匹配且持久保存的最好已知方案。初值可为空，不拿未经确认的 seed 冒充 I。
- `F`（exploration frontier）：研究者保留的带来源候选与后续编辑状态；允许 Makespan 暂差、未评分或 E2 估计值。保留/淘汰依据在算法策略中记录；F 不自动取得发布资格。相同分值或当前执行行为不证明未来编辑等价。

这三类是角色，不是重复保存三份大图；可以共享只读字节/证据引用。构造器内部模型、表示和可行性分析不在本契约统一。

## 2. 身份与重复

复用 s55 的 candidate/operation 身份，不另外定义可执行协议：

| 对象 | 不可省略的绑定 |
| --- | --- |
| 候选 | 上述问题上下文、**有序且类型明确**的计划、构造器与参数、`experiment/epoch/manifest revision/proposal_seq`、不可变 `parent_plan_hash/parent_result_ref`；无父构造显式为空 |
| 评估操作 | candidate、`operation_id`、官方/引擎实现 SHA 与 ABI、输入表示、用途及输出域 `score/native_diagnostic/official_full`、资源/最大调用/截止时点 |
| 接受证据 | operation 及确切输入、成功/合法状态、结果 hash、实际后端与 fallback 路径、**逐字段**精确范围及校准依据、成本/unknown 状态 |

禁止排序 JSON mapping key、重编号或合并空核后默认等价。先冻结拟发布 JSON，再按官方读取方式解析确认；若后端消费 Python 对象，必须证明其键类型/插入顺序与该 JSON 的关系并记录，不能仅计算事后文件 hash。

同一候选的 score/full/final-confirm 是不同操作；独立确认须新 operation、新额度。P2/P3 即使同一计划，也分 problem，可以另有 pair ID。重传同 operation 只查询原状态，未知不重新执行。相同有序计划在本次算法内可按预先声明策略跳过，但保留不同父节点/编辑来源；不据此合并 F。跨实验最终评分缓存和 single-flight 不属于 s55 v1 承诺。

## 3. 精确接受与保留规则

1. 先检查 guard、输出字段、结构合法性及上下文；结构检查通过仅进入可评估状态。
2. 经 s55 许可申请评估；先到的结果可交付，算法按冻结 `proposal_seq`、轮次及同分规则提交，不让 worker 完成顺序暗改算法。
3. 精确证据门槛为未修改 E0，或**已有固定校准证据且该输入域、版本、合法性与所用字段均获准的精确 E1**。默认未获准域用 E0；E2 评分只进入 F，不能作为成绩或 I 晋升依据，须另经预登记的精确确认操作。E2 自动 fallback 需如实核算，不能仅凭回退后 `ok` 就将探索操作升级成正式确认。P1 E2 的 full=完整 E1，不等于 official E0 full。
4. 只有精确成功且输出字节绑定成立，才可首次设 I 或以严格更小 Makespan 替换 I；同分保留原 I，同批无 I 时按 proposal_seq。必须先保存新证据/计划再切换引用，失败保留旧 I。本规则是暂定的确定性策略，**不是官方指定的完整排序公式**。
5. 如需独立最终 E0 审计，候选在审计成功前保留为待确认，不提前覆盖可发布 I；审计不一致锁定问题并保留证据。不允许把原生估计最优者先发布，再把确认失败隐藏在 summary。

**条件保证**：固定上下文且已有可信 I、精确评分/比较/持久化正确时，已确认 I 的 Makespan 随接受次数不增加。它不保证新算法在相同墙钟内胜过旧算法，不保证确认能在期限前完成，也不保证覆盖全部输入。实验选择集、并发、预留开销及探索路径不同，都能影响限时质量。

## 4. 次级指标先保留口径，不写作官方 lex(M,D)

冻结源码的 `data_movement_bytes` 有五项：原图 COPY、最终 scheduled COPY、额外 added COPY，以及 partition/spill 两项增加量。三题的 `added_copy_bytes = partition_added_copy_bytes + spill_added_copy_bytes`；spill 记录按 `size × (1 + spill_out_copies_data)` 累加，不能统一计双向。[P1][traffic1]、[P2][traffic2]、[P3][traffic3]

本版记录完整五字段，P1/P2 优先展示额外 COPY 字节并明确对应官方字段。P3 的这些数在 Cache 事件模拟前构造，命中 COPY 后仍在 scheduled/added 里；**不能把它直接解释成 Cache 后实际 DDR 字节**。另存 `hit_bytes/miss_bytes/hit_rate`；官方 hit_rate 是 `hit_bytes/(hit_bytes+miss_bytes)`，分母零取 0，miss_bytes 也不是包括全部写流量的总 DDR。[Cache 路径][cachepath]、[命中率][hitrate]

Pro4 的 `argmin_lex(M,D)` 中 D 尚需按用途明确；官方“首要 Makespan、兼顾搬运”未规定这个字典序。当前仅用严格 Makespan 晋升，搬运与 P3 命中率逐项报告、用于解释 Pareto 取舍；若改同分/多目标策略，冻结新的 AlgorithmSpec，不能默默换规则。

## 5. 预算、失败与发布

以下均映射 s55 的 `stage → unit → epoch` 祖先许可、资源 lease、预留/结算和结果存储。控制层只提供算法需要的边界，不自行实现事务或绕过父预算。

| 边界 | 控制层要求 |
| --- | --- |
| 首个 seed | 预留构造、可能回退、精确确认、持久化/发布和清理的资源/时间；没有足够预算就记录 `no_confirmed_plan`，不能声称必有保底 |
| 新候选 | 派发事务先检查祖先状态、剩余额度、绝对 deadline 与最坏已知 fallback；未知最大调用上界则拒绝。先留 final/发布/清理空间，不够就跳过；不通过拆 unit 重置时间/额度 |
| full 与 final | `full` 是输出域而非可信级别；独立 final reserve 仍受父期限限制。若当前已有满足本次确认策略的完整 E0 回执，不强制 native 预跑或第二次 E0；是否独立复测由实验策略提前规定 |
| 失败 | domain guard 拒绝可按声明继续；超时、崩溃、精确差异等锁定范围及继续/停止规则写入 AlgorithmSpec。不得把 error/unknown 当 0 或 +∞ 分数混入科学比较 |
| started 后不明 | 保留 UNKNOWN 与相应调用预留，无自动重投；查询/人工恢复走 s55。后到结果保存为证据，是否还可接受依冻结截止/提交规则，不能回写已封口赢家 |
| 失败后退出 | 仅在祖先停止策略仍允许最终输出时，发布已持久确认的旧 I；不为“保底”偷偷启动新确认。无 I 则显式失败，不伪造成功计划；已发布旧计划不被覆盖为未知结果 |
| 发布 | 校验 I 与证据/输出字节一致，写新临时文件、完成后原子发布；结果路径预先唯一，冲突不覆盖。原子可见、掉电持久性和截止前完成是不同能力，待平台/实现验证 |

E2 当前 `native_enabled=True` 仍会自动 fallback，不能当 forbid-fallback。最坏路径初始按 s55 表预留：P1 完整 E1 ≤1；P2/P3 各自 E0 ≤1，限于固定已审实现与输入域，不泛化为所有入口。预算账本核实实际执行后才释放；反过来不能靠只看最终计数断言中间没有调用。

在线墙钟从进程启动/读输入到合法计划发布，含所有 proposal、准备、排队/通信、内部评分/fallback/确认、收尾；外部最终 E0 审计单列，若用于选优就变成在线成本。编译、历史 seed 生产、离线研究、并行资源另外列出，不从成本表消失。P1 结构 proposal 内含官方每 Task Step1/2/3，须计 generator lease/wall/CPU，不能因未调用完整 evaluator 就标零工作量。

## 6. 跨问题/核数迁移与尚待确认的接口

P2 赢家可作 P3 proposal，不能凭 P2 排名硬剪 P3；P3 Cache 从官方初态开始。`k→k+1` 追加空核的等价性、合法性和成绩保持尚未在这里证明；仅作显式 guard 下的新上下文候选，重新确认。上一次 k 的在线生产成本不能在串联求解中隐藏。

已向 s55 本地任务发送三项接口问题，并在 `2026-09-24T12:35:40Z` 前收到本轮静态答复：

1. **已对齐设计**：receipt 绑定序列化计划/原始表示、上下文、官方源码集合 hash、后端/构建/ABI、所需字段精确域、校准及准入决定、完整结果 hash、operation/终态/成本/证据缺口。E2 只进 F；P1 e1_full 仍需 E1 域准入。当前后端记录不足，收据接口待实现。
2. **已对齐设计**：祖先许可事务同时圈存 seed/score 的最坏 fallback、独立 final、收尾 CPU/wall/内存/磁盘；收尾额度不含新评价。失败锁后仅发布此前持久确认且身份匹配的 I，不再发 final；时间不足跳候选，父 deadline 不重置，unknown 保留预留不重投。
3. **已对齐设计**：P1 局部准备计 generator 的 Step1–3 CPU/wall/RSS；Q3 本次输入身份匹配且按 final purpose 预登记的唯一 P3 E0 full receipt 可以直接确认。实验另要求独立复核时才另开操作/额度。现代码缺共享收据/表示绑定时标 adapter 待实现，不回溯声称已经接入。

三问 constructor、I/F 规则属于算法层；s55 只承接执行身份、后端能力、资源/预算、错误和结果证据。全部接入、故障注入、速度/质量比较均待后续授权，本文不启动。

[objectives]: https://github.com/huaweibei123/huaweicup2026/blob/1ee2c271c43bb14dd6c5de6b9ca7041b55d80916/docs/a/OFFICIAL_OBJECTIVES.md
[infra]: https://github.com/huaweibei123/huaweicup2026/blob/abdfd31f358a035e5ecca3b0482a9d0881060ffe/docs/a/e2/CONCURRENT_EVALUATION_DESIGN.md
[traffic1]: https://github.com/huaweibei123/huaweicup2026/blob/1ee2c271c43bb14dd6c5de6b9ca7041b55d80916/data/raw/a/official/code/multicore_cut_evaluate_problem_1.py#L176-L198
[traffic2]: https://github.com/huaweibei123/huaweicup2026/blob/1ee2c271c43bb14dd6c5de6b9ca7041b55d80916/data/raw/a/official/code/multicore_cut_evaluate_problem_2.py#L248-L282
[traffic3]: https://github.com/huaweibei123/huaweicup2026/blob/1ee2c271c43bb14dd6c5de6b9ca7041b55d80916/data/raw/a/official/code/multicore_cut_evaluate_problem_3.py#L256-L290
[cachepath]: https://github.com/huaweibei123/huaweicup2026/blob/1ee2c271c43bb14dd6c5de6b9ca7041b55d80916/data/raw/a/official/code/multicore_cut_evaluate_problem_3.py#L538-L568
[hitrate]: https://github.com/huaweibei123/huaweicup2026/blob/1ee2c271c43bb14dd6c5de6b9ca7041b55d80916/data/raw/a/official/code/multicore_cut_evaluate_problem_3.py#L676-L682
