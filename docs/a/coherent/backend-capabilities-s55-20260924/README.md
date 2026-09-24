# D2：Coherent 评估后端能力与成本交接

**结论：可复用现有 P1 精确 E1、三题官方 E0 和 E2 探索接口；统一收据、祖先许可、持久账本与资源调度仍是待实现契约。** E2 的原生路径采用事件重放，但有限零差分不等于全域精确验收；按用户要求，E2 分值不能直接生成正式 benchmark 图表或晋升正式成绩。P2/P3 的公开 `full=True` 本身就是完整 E0，不能当作免费诊断。

负责人 `nikolastarx/s-55b66a31d7bd49019122a179563dc1d2`。本次基于 main `1ee2c271c43bb14dd6c5de6b9ca7041b55d80916`，实际开始 `2026-09-24T12:25:17Z`。只新增本目录；不实现控制器、不接管网站/成员 runner，不启动新矩阵、原生构建、被审模块 import、solver/E0/E1/E2/probe/model 测试。下列“存在”指固定源码事实，“有限已测”指已有证据；均非本轮运行验证。

## 1. 固定输入

| 简称 | 固定提交与用途 |
| --- | --- |
| E1 | `5bfe53a29c1ba05167239f51ea937e602f7f85b4`，PR30，P1 驻留精确批量 API |
| E2 | `603b0741e21c449d3db652ebd67c94f2dc014cc9`，PR46，P1/P2/P3 公开研究接口；其中 `src/eval_exact/batch.py` 与 E1 提交 Git blob 相同 |
| Audit | `09eef20b2285fadb88b2a6e2cad9b4bd9c389d88`，PR64，[LYX 路由审计](https://github.com/huaweibei123/huaweicup2026/blob/09eef20b2285fadb88b2a6e2cad9b4bd9c389d88/docs/a/e2/audit-lyx-20260924/ROUTE_COST_MATRIX.md) |
| Design | `abdfd31f358a035e5ecca3b0482a9d0881060ffe`，PR63，[有限复核](https://github.com/huaweibei123/huaweicup2026/blob/abdfd31f358a035e5ecca3b0482a9d0881060ffe/docs/a/e2/ROUTE_COST_REVIEW.md)及[共享并发设计](https://github.com/huaweibei123/huaweicup2026/blob/abdfd31f358a035e5ecca3b0482a9d0881060ffe/docs/a/e2/CONCURRENT_EVALUATION_DESIGN.md) |
| Win | `a21f7ef7111933d309f3d616b9a3f2e7e861129d`，PR67，仅 Windows full CLI 等待/退出传播补丁，未通过实机功能验收 |
| Pro4 | `a84119e65c5c817e3c4f3e2c3ce446b8616a9d55`，`AI chats/20260924-Pro4-算法方案设计/README.md` 与 `回答原文-f0ff3669-20260924T121808Z.md`；已全文读，属于研究建议，不是运行许可或实测 |

本文复用 Audit 的条件调用上界并直接核对公开入口、回退、缓存、pool 和 CLI 源码；不重新证明整个 C++/官方 helper 调用图。关键文件的字节哈希、定位行和阅读范围见 [sources.json](sources.json)。不将固定提交等同当前机器已装载该版本。

## 2. 可接入能力表

下面每行费用为**一个公开候选请求**、正常 JSON 形状、预期未替换依赖/库、无外部重入/重试时的完整评价次数上界。E0 与完整 E1 分账；准备、内存和墙钟另计。提前拒绝可能实际为 0，成功 full 为 1，进入阶段缺证据则实际数为 unknown。

| 能力 / 源版本 | 真实入口与输出 | E0 max | 完整 E1 max | 当前状态与接入边界 |
| --- | --- | ---: | ---: | --- |
| P1 exact / E1 | `src.eval_exact.P1Evaluator(graph).evaluate(plan, **config)`：完整 Python 结果；`evaluate_record(full=False/True)`：摘要/附完整结果 | 0 | 1 | 接口存在、有限校准；`full=False` 仍执行完整全局 E1，仅减少返回保留/IPC |
| P1 E1 pool / E1 | `P1BatchEvaluator(...).evaluate_batch(...)` | 0/项 | 1/项 | 有界 spawn 池存在；同实例不接受并行批次，非全机共享服务 |
| P1 E2 score / E2 | `research.a.e2_search.E2Evaluator(...).evaluate_record(full=False, ...)` | 0 | 1 | native 成功时完整 E1 实耗 0；异常/不支持会调用完整 E1，不是公共 native-only 能力 |
| P1 E2 full / E2 | 同入口 `full=True`，`route=e1_full` | 0 | 1 | 返回完整 E1；不满足要求未修改官方 E0 的 final-confirm |
| P2/P3 E2 score / E2 | `SceneBEvaluator(graph, problem=2或3).evaluate_record(full=False, ...)` | 1，本问题 | 0 | native 成功时完整 E0 实耗 0；广义 `Exception` 后尝试同问题 E0，P3 不转完整 P2 |
| P2/P3 full / E2 | 同入口 `full=True`，`route=e0_full`，完整对象在 `result` | 1，本问题 | 0 | 冻结本问题 E0；可作为事先登记的唯一 final 操作，不要求先做 E2 |
| E2 pool / E2 | `E2BatchEvaluator(graph, problem=p, ...).evaluate_batch(...)` | 逐项沿对应上界 | 逐项沿对应上界 | 批大小不能当作一次评价；chunk 全部处理后按输入顺序 yield，无跨请求预算许可 |
| 官方 E0 / E2 中冻结源码 | `data/raw/a/official/code/multicore_cut_evaluate_problem_{1,2,3}.py` CLI；函数分别 `evaluate_scene_a/evaluate_scene_b/evaluate_problem_3` | 1，本问题 | 0 | 全结果/官方 Trace/log 基准；入口/config/文件错误可能发生在完整函数之前 |
| P1 兼容 CLI / E2 | `src.eval_exact.cli`，以及 `research.a.e2_search.multicore_cut_evaluate_problem_1` | 0 | 1 | 走原 E1 单次路径，不是 P1 batch 缓存 API，也不是纯 E0 |
| P2/P3 兼容 CLI / Win | `research.a.e2_search.multicore_cut_evaluate_problem_{2,3}` → `_full_cli.main` → 对应官方脚本 | 1，本问题 | 0 | POSIX exec；Windows 补丁同步等子进程退出。实机等待、取消、退出传播仍待验；不能以补丁存在准入新运行 |
| 共享能力 / Design | durable operation、祖先许可、全机资源/费用账本、公平队列、typed receipt | 未实现 | 未实现 | 只有设计与早期有限内存模型检查；没有三算法共享生产服务，没有已验证跨平台硬资源 cap |

真实参数 reader：P1 为 `src.eval_exact.read_config`；E2 为 `research.a.e2_search.read_config(path, problem=p)`。P1 配置是 bandwidth/capacity/cross_core_wait/same_core_wait；P2 为 bandwidth/capacity/cross_core_copy_delay；P3 再加 cache_capacity_bytes/cache_bandwidth_bytes_per_cycle，另有 max_iter。使用当前固定配置，不按截图或缓存默认值补造。

**隐含成本：** `native_enabled=True` 仍允许回退，`False` 强制后备；公开接口没有 `allow_fallback=False` 或回退前预算回调。冷准备失败再后备可做至多两轮上层 prep，但只至多一次完整后备。私有 `_native_score`/debug 不作为稳定公共接口承诺。score 后另取 full、shortlist、独立 E0 复核或外部重试都新增操作；读取已持久保存的同一次 full 结果不新增评价。一次 P2/P3 成对评价是两个问题、两次操作，不能合算一次 E0。

## 3. 校准域、复用边界与失效条件

| 能力 | 已有证据与仍未证范围 | 编译缓存如何失效 |
| --- | --- | --- |
| P1 E1 | [P1_BATCH](https://github.com/huaweibei123/huaweicup2026/blob/5bfe53a29c1ba05167239f51ea937e602f7f85b4/docs/a/exact/P1_BATCH.md)记录开发者 full 对照、定向样本及有限资源测量；不是 P2/P3、全100图、全异常域、各平台或数小时运行验收 | 图和 engine 固定于实例；有序原始 mapping、bandwidth、capacity 保留类型入 key；变更即重编译。core schedule 不入 key，但每次验证依赖/顺序、刷新核归属并全局重放；wait/max_iter 每次应用 |
| P1 E2 | [HANDOFF](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/HANDOFF.md)记录 4 个 E0 标注池、256 调用/248 不同图–方案三指标零差分，非全域 full 等价；该旧交接不能代替后来某平台的验收状态 | partition key 同上；schedule/waits 每次重验重放，不存旧分数。原生不支持/库失败可触发 E1；E1 内层缓存已关，可能重复准备 |
| P2/P3 E2 | [P23_HANDOFF](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/P23_HANDOFF.md)：004/005 各16计划，每问题32唯一候选；P2/P3 分别116/76次开发者正式 E0，含重复/复核，不是116/76独立样本。逐op/P3缓存事件证据有限；未达全100图/Windows/独立终验 | **完整有序 plan**、bandwidth、capacity、P3 cache bandwidth 入 key；assignment/order 改动也重编译。copy delay/max_iter/cache capacity 每次重放；不能套用 P1 partition-only 复用 |
| P2/P3 official full | 对应冻结完整函数为参照，不使用 E2 编译缓存；direct 与 adapter 仍需按实际环境、源码身份和完整结果证据核对 | 每次完整构建/评价；E2 native hit 不使下一次 full 免费 |

原生适用域还有限制：普通 plan 容器和数值类型、整数等待/迭代参数、默认最多 2,000,000 prepared ops、1–128 核、32位索引和保守 `<2**50` 时间域；P3 另有 cache key/字节/容量约束。完整条件以固定 `_native.py/_native_b.py` 为准，不能只靠“官方 JSON 可读”判断 native 必可用。P23 有 BC ABI=1 检查；P1 loader 没有同样的版本握手，能力注册还须绑定实际库字节/构建身份。

**校准失效与编译缓存失效是两件事。** 官方 code/helper/config、engine/native build/ABI、Python/NumPy/平台、输入表示、场景/字段域或算法生成分布改变，不能自动沿用旧校准许可。新图不一定违反实现支持域，但旧两图实验不能为它代签。配置/计划全部进入评价身份，即使部分参数无需重新编译，也不可复用旧评分。P3 byte hit_rate 不改为按次数命中率；Python raw 结果的 key/数值类型比较与 JSON 序列化后比较必须分别声明。

已有冷批资源结果仅支持 P2/P3 case005、16新计划、1/2 worker 约 1.5–1.6×E0；重复同计划数百倍不代表新候选或完整求解加速。P2/P3 缺少对应已验收优化 E1，不能声称已通过 E2≥10×E1。16 MiB cache 只约束保留载荷/对象；原图、冷 prep、回放临时缓冲、full结果、父子进程另占内存。

## 4. 给共同求解控制层的三条接口约束（设计，尚未落地）

1. **评价身份与 exact acceptance receipt。** candidate 绑定 problem、graph、k、完整 config、有序计划的 frozen bytes/hash 和表示版本；operation 另绑定 purpose（seed/score/full/final）、engine/官方源码集合hash、build/ABI、deadline、费用上界。score/full/final 独立派发时必须用不同 operation_id；同 id 重传只能查询，不能再执行。收据含完整结果内容hash、required fields/精确比较域、校准证据与准入决定、终态和实耗/unknown。现有 record 仅有部分字段，**adapter 待实现**。E0或逐域获准的精确E1才可交控制层晋升 confirmed；E2评分留 frontier。P1 `e1_full` 不自动取得 E0 身份或 E1 域准入。
2. **不可变父状态和祖先许可。** 请求冻结 parent_plan_hash、parent_result_ref、epoch manifest/revision、proposal_seq 和 objective/tie-break；from-graph 显式 parent=null。stage→case×method unit→epoch 的状态/费用/截止在同一派发事务核对。strict 父阶段最多一个 active unit，需 baseline/探索/final、证据与清理回执和父控制器放行后才进下个 unit；每实验一个 worker 本身不够。结果完成顺序不决定 incumbent。首可信意外失败立即锁声明 scope；之后只允许发布此前已持久确认且身份匹配的 incumbent，不偷偷发 final-confirm。特殊“仅阻断同case”的例外由固定算法 adapter 声明，不扩大为普遍规则。
3. **最坏成本、截止与发布收尾。** seed/score 派发前圈存对应潜在完整 E1/E0；final-confirm 独立保留，不让搜索借用。生成器、Step1–3、进程/IPC 和发布收尾同计 CPU/wall/内存/磁盘；收尾资源预留不等于新的评价许可。父绝对 deadline 不因换 unit/epoch 重置，时间不足跳候选。Q1 proposal 调 `_build_scene_a_tasks` 即使完整 E0计数为0，也有局部编译成本。Q3 已有的一发 P3 E0 若本次按 final purpose 预登记、身份匹配且收据完整，可直接确认，不强加 native prepass 或第二 E0；契约另要求独立复核时才追加单独收费操作。既有程序无共享收据，不回溯宣称已接入。

算法 owner 管 constructor/seed、frontier、incumbent 与选择规则；本专项管后端能力、调度、资源和费用账。保留旧算法作为 seed/proposal 只表示可复用来源，不保证100图×1–5核全域成功；也不授权原 Pro 建议的96调用实验。

## 5. 中断记账与平台阻塞映射

| 观测 | 可记事实 | 不能推导 / 接入处理 |
| --- | --- | --- |
| 原子取消获证实发生在派发前 | 该 operation 完整调用为0 | 初始化/准备成本另计；仅这种已证未启动取消可退对应预留 |
| native 成功且来源/终态可信 | 本次完整后备为0，可结算对应预留 | 不能据此注销其他请求预留；旧 record 还不是持久原子收据 |
| full/fallback成功 | 对应一次完整 E1或本问题E0完成 | 路由字符串或累计 counter 本身不证明函数体进入；源码中 counter 在调用表达式之前增加 |
| send后超时/崩溃/取消/响应丢失 | 每请求条件上界仍为1，实际可能 unknown | 保留最坏预留、不自动重投；执行资源须另等进程退出/清理证据，不能随调用账结算提前释放 |
| pool ready、已 yield 数、进程工具退出0 | 只对应所观察事件 | ready仅初始化；可能超时判定早于读取完成响应；chunk未yield可能已执行；同步send无独立硬截止保证 |

Windows失败原件：[PR74 / 5ff92f](https://github.com/huaweibei123/huaweicup2026/blob/5ff92f36851b89ebb9278b2fdff6dc762bc0060e/results/a/review/e2_cli_window_48b1268_20260924/README.md)。固定驱动创建控制器时报203，15例均未准入；确认 E0完成0，实际入口次数及最终完整进程清理仍unknown，原8潜在额度封存。不能把这次控制器失败归咎于算法分值，也不能记为15例通过。

[PR75 / 6f91055](https://github.com/huaweibei123/huaweicup2026/blob/6f91055d37bd94d4d0b9f7789ccb36baf0d44f88/research/a/review/e2_cli_fix_validation_20260924/README.md)互操作静态修订，以及[PR80 / 1411772](https://github.com/huaweibei123/huaweicup2026/blob/14117724cbbb01c6a3ada3c13898028213a277c7/research/a/review/e2_cli_fix_validation_20260924/M_PREPARATION.md)元数据入口，均不构成新的 ABI/进程/评分运行证据。后者明确尚未运行、执行端/外部截止与终止责任未闭合。本表不重启 M/S 审查循环，不改变封存窗口；PR67/75/80 的相关 Windows 验证继续列待验/阻塞，不能外推成全部平台 E2 均不可用。

## 6. 本检查点验收与交接

- 目标：给统一控制层一个可追溯的后端选择/费用上界入口，避免误用 full、漏计回退与混淆校准。
- 输入/输出：上述固定源码、PR63/Audit、Pro4及失败交付；仅本 README 与来源字节清单。
- 限制：不改 runtime/API、原件、实验预算、网站或其他 session 文档；不导入/构建/执行被审对象。
- 检查：静态阅读、固定路径/行号/源字节SHA-256、来源JSON/Markdown链接与diff/元数据卫生；不是后端运行或性能验证。
- 交付节点：实际开始约30分钟内给固定文档/Draft PR后停止。已向 s8ee 发送上述三项约束，收到其三项接口问题并逐项静态答复；发送/回复不等于共同实现或运行验收。
- 剩余缺口：实际host/build身份、逐域 exact 准入、统一收据、完整入口阶段持久证据、祖先事务/unknown恢复、全机资源与进程树清理验证。未知能力不得填0或“已支持”；另立具体实现和有限验证范围，不能以本文启动实验。
