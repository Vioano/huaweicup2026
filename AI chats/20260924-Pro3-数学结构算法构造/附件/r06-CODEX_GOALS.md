# Codex /goal 候选：CRG v1 / Pro C

这些是候选完成契约，没有在本次创建 Goal、分支、服务或启动官方优化实验。各任务在用户/协调端选择授权后执行。不能因为上一项有剩余额度就自动启动下一项。

## 共用冻结输入与规则

完整 SHA 见 HEADS.json。别名：MAIN=f27ef37b；Q1=4dff90ef；Q2S=74c46372；Q2B=0b58c123；Q3=a4e7ee13；EXACT=5bfe53a2；NATIVE=03f02e79。实际执行必须解析并校验完整 SHA，不使用继续移动的分支 HEAD。

读取当时工作树 AGENTS.md；在独立工作树、新功能分支和不存在的输出目录执行。只修改任务列出的新路径。共同禁止：冻结 data/raw、官方代码/配置、已有结果/Trace/归档、CRG 定义、已发布 E1/E2 默认路径、其他任务文件。不能引入预取/等待/重算等官方接口没有的决策。所有内部评价、构造、首次准备、回退、确认计入任务账本；计时区分研究总成本与求解端到端成本。不能以 timeout/Unsupported 代替官方 invalid；不能用浮点容差声明零差分。所有实验先冻结输入与协议，再生成标签。阴性结论、适用域反例、可靠拒答都可以完成研究目标。

## C01 — 操作 IR 与精确回滚

**/goal 文本：** 实现 CRG v1 的 CUT/JOIN/SPLICE/RECODE 部分变换内核，使三个问题的既有构造能通过明确的方案编辑及事务日志表达；证明并测试回滚恢复原方案的有序映射、核心序列和字面子图 ID，不实现新的评分或搜索策略。

- **命题：** 三个语义编辑模式加一个表示编辑模式能表达分区、核归属、核序及当前保存的编码差异；带 receipt 的回滚恢复 L0，不能把 receipt 逆误称为裸 JOIN 的唯一逆。
- **branch / commit / 输入：** 从 MAIN 建候选分支 `codex/crg-c01-plan-ops`；只读 Q1 的 neighborhood/search/structure/release_ideals，Q2S 的 joint，Q2B 的 proposals，Q3 的 construct；CRG v1 与本报告为规范。
- **修改范围：** 新 `src/plan_ops/ir.py`、`primitives.py`、`receipts.py`、`tests/plan_ops/`、`docs/a/operations/`。
- **禁止修改范围：** 共用禁止项；不得改变任何既有 constructor 的优先级/参数/候选顺序。
- **实验协议：** 零 E0。先用小 DAG 手工方案；再只读既有候选 JSON 做 encode/decode 和 patch/reverse-patch。分别比较语义字段与编码字段；非法参数、过期 parent、ID 冲突、空核、混合长度核必须有测试。
- **输出：** 有版本的操作 schema、receipt schema、精确修改集、回滚见证、表达能力对照表；无法降低为部分变换的 constructor 单列。
- **验收：** 所有测试的回滚字面值/列表顺序/有序 mapping 一致；每个输出明确 P_plan/P_task/P_exec-known-or-unknown；错误中途不得污染 parent。
- **失败 / 停止：** 两次设计修正仍需要伪造官方控制参数，或不能恢复 ID/键序，则交反例和阻塞说明；最多一个 2 小时实现窗口，测试累计 120 秒，0 E0。
- **依赖：** 无；不等待 Pro A/B 的完整理论。
- **是否并行：** 可与 C02 的数学规格、C05 的只读 witness 整理并行；不得同时写同一 IR 文件。
- **预计资源：** 单 CPU，测试进程 2 GiB 内停止阈值，无 GPU/网络服务。
- **成功后解锁：** 统一的操作历史、比较、macro 降低、后续变换可达性测试。

## C02 — 完备性分层与插入区间证书

**/goal 文本：** 审核并实现结构合法域的 CUT/JOIN/SPLICE 可达性证明及 Task 插入区间算法；给出 P_exec 扩域所需假设或最小失败见证，不能把抽象 DAG 穷举说成官方执行完备。

- **命题：** 商图与各核块序并图无环的有序分区域连通；固定分区删除待移动块后，祖先/后继位置给出连续的精确可插入区间。
- **branch / commit / 输入：** MAIN→`codex/crg-c02-reachability`；Q1 `src/q1/neighborhood.py`；C01 的冻结 schema；本包 algebra_structural_checks.py/json。
- **修改范围：** 新 `research/plan_ops/reachability/` 与 `tests/plan_ops/reachability/`；必要时向 C01 提交接口需求，不直接修改其实现。
- **禁止修改范围：** 共用禁止项；禁止用任意 REPLACE_PLAN/RESET 把连通性做成同义反复。
- **实验协议：** 先复跑本包 150 个抽象环境；再对至多 4 个点、1–3 核扩展，最多 100000 个状态和 2000000 条边。图/分区/编码层分开。0 E0。若需要执行域反例，先提交额外协议，不自动运行。
- **输出：** 构造性证明、路径长度界、各层域定义、不可达/缺生成元见证、完整计数与路径重放。
- **验收：** 区间与暴力无环检查逐项相等；结构状态图连通；明确未证明 P_exec 全域连通；标签和 mapping order 的缺生成元单列。
- **失败 / 停止：** 任一反例立即停止相应普遍声明并最小化；达到状态/边/120秒检查上限即交有界结论，不外推。
- **依赖：** C01 schema；数学证明可提前独立进行。
- **是否并行：** 可与 C03、C05 并行，独立只读来源。
- **预计资源：** 单 CPU、2 GiB、纯标准库优先。
- **成功后解锁：** 完整表达能力与有限搜索策略分离；合法邻域生成器有可核验证书。

## C03 — 官方映射只读观测与分层响应

**/goal 文本：** 建立 L0–L6 的只读观测适配器、显式 Φ/ρ 和类型化 diff；证明测试范围内打开观测不改变未插桩官方结果，输出每个操作的 edit signature、guard crossing 与 CRG 耦合签名。

- **命题：** 固定操作与环境下，可用不修改官方字节的观察生成可靠机制证据；未经观测的层不能被填为空。
- **branch / commit / 输入：** MAIN→`codex/crg-c03-observe`；EXACT 的 problem1/batch；官方冻结源码；已归档 float 事件、混合长度环、重复 L1 incarnation、FIFO 队首见证；读取 e1575a1de5e3b921aef350e920720f0584fb1719 的 Q1 spill.graph/plan 作为机制输入。
- **修改范围：** 新 `src/plan_observe/`、`tests/plan_observe/`、新结果目录。
- **禁止修改范围：** 共用禁止项；禁止删除普通计算退休事件、改排序、合并浮点结算或把 physical tid 规范成 logical_tid。
- **实验协议：** 最多 48 次官方调用、总运行窗口 600 秒；先冻结至多 24 个环境/方案对，覆盖三问和每个核数至少一次；每对 plain/observed 比较完整值，重复基线也计调用；合成图与正式图分开。只读观测记录对运行时额外成本单独计量。
- **输出：** Φ/ρ manifest、type-aware diff、字面签名与 provenance 对齐视图、原始/观测结果、环境/代码/输入哈希、耦合计算定义及 not_observed 状态。
- **验收：** 成功/失败分类与所有已输出官方字段零未解释差异；L3 能看到 original/reused/new backing、可空 spill_out、version链、pos；L5 不漏浮点更新时间点。
- **失败 / 停止：** 首个不可解释差异停止该域，交最小输入；观测扩张造成超时/RSS停止，不退化成伪造空Trace。
- **依赖：** C01 receipt schema；可先读源码准备。
- **是否并行：** 可与 C02、C04 运行在独立进程/工作树；正式计时须隔离竞争负载。
- **预计资源：** 单 CPU、2 GiB停止阈值，无 GPU；全Trace仅保存选中比较与失败。
- **成功后解锁：** Pro A/B 的敏感方向、guard、峰值归因具有统一数据接口。

## C04 — 区分评分等价与未来操作等价

**/goal 文本：** 用 CRG D14/D15 重新审核 W，寻找同当前执行签名但不同下一步可用操作的见证；实现“共享评分、保留搜索表示”的双账本，不把 W 的一次结果缓存升级成强行为商。

- **命题：** 当前编译/评分等价通常不对完整 CUT/JOIN/SPLICE 操作集构成同余；正确缓存仍可复用数值，但不能无证据丢掉后续编辑能力不同的代表。
- **branch / commit / 输入：** MAIN→`codex/crg-c04-quotient`；按 `AI chats/20260924-Pro3-数学结构算法构造/README.md` 恢复并校验 r02 原ZIP的两片；只读 word_quotient/canonical_plan 原型；EXACT batch 源码。
- **修改范围：** 新 `research/plan_ops/quotient/`、适配器及测试；不修改归档原型。
- **禁止修改范围：** 共用禁止项；禁止把相同 Makespan、哈希相同或长度≤h 测试命中宣称 D15。
- **实验协议：** 先0 E0的 enablement反例；必要时至多16次Q2/Q3 E0确认 immediate signature。固定 Φ_oper/Φ_full 和 A 的操作参数规则；比较 score-cache hits 与 frontier-representation losses。任意h视野结果写h。
- **输出：** D14可复用条件、D15反例、operator transport/域对应义务表、双账本原型、κ与缓存内存/构造成本。
- **验收：** 能给出重分区代表被CUT或JOIN区分的明确w；缓存命中不会让另一代表的操作机会消失；不把编码重标注当完整行为不变。
- **失败 / 停止：** κ近1、签名检查成本大于节省、或必须任意重命名原图ID才能命中，则关闭该商路线而保留精确缓存；总测试120秒/16 E0上限。
- **依赖：** C01；精确行为对照需要C03。
- **是否并行：** 可与C05并行；不可同时修改C01/C03。
- **预计资源：** 单CPU、2GiB，无GPU。
- **成功后解锁：** 不丢可达性的去重；决定是否继续投入真正的最小充分表示。

## C05 — case008 峰值见证到受守卫操作模式

**/goal 文本：** 将resource-word与affine构造降低为可重放的primitive program，按CRG D36检验case008峰值候选机制；保存044/080反例，输出guarded macro candidate或明确否定，不寻找新的最优参数表。

- **命题：** 同构串行M–V*–M结构与适当每核作业数，可能使某类重入资源次序稳定降低关键管线空闲；当前008只是witness，COPY时序仍须纳入归因。
- **branch / commit / 输入：** MAIN→`codex/crg-c05-word-macro`；Q3 construct/METHOD/pilot REPORT；Q2B stage-B regressions与Q2S joint报告；原始case008/044/080。
- **修改范围：** 新 `src/plan_macros/resource_word.py`、lowering tests、`research/plan_ops/peak_word/`；Q3 constructor只读适配。
- **禁止修改范围：** 共用禁止项；禁止case ID硬编码、把affine坐标当提交启动时间、扫完参数后倒写guard、把pipeline理想定理等同官方最优。
- **实验协议：** 预冻结最多96次E0、运行窗口1200秒：008的三种构造、044/080的两种构造，分别Q2/Q3、1–5核最多70次；其余额度用于6个成对合成反事实和有限完整重复确认，余量不用来开新族。当前已公开图属于开发集；跨新图泛化另需封存协议。
- **输出：** primitive程序与原constructor plan的字面一致性；L1–L6diff；作业长度/数量/异构/容量边界反例；g_G、g_R、Ω、rollback和适用q/k范围。
- **验收：** 能明确区分pipeline/COPY/spill/cache的已观察变化；收益方向预测在预定范围被支持或被否定；无论结果均不给未检验新图冠以structural peak。
- **失败 / 停止：** plan不能保持已有owner/键序控制、guard跨界后无预测力、或预算耗尽；不因失败启动参数搜索。
- **依赖：** C01与C03；需要Pro B明确witness reference与迁移阈值才能升级已验证macro。
- **是否并行：** 可与C06独立开发；运行预算、输出和代码范围独立。
- **预计资源：** 1 CPU，2GiB停止阈值；无GPU；一次性有界研究面板。
- **成功后解锁：** 一个机制驱动macro，或有证据地保留为仅特定域的constructor基线。

## C06 — 成本感知 evaluator routing 与拒答

**/goal 文本：** 为PlanOp添加能力声明与按编译上下文分组的路由，在固定候选流上比较exact-first和local-abstain策略；原生重放先shadow，不扩大E2或原生“精确”声明。

- **命题：** 在固定划分的Q1编辑批中，复用真实局部编译并重放全局过程能节省成本；当构图变化、guard风险或域不匹配时拒答/回退比强行代理更可靠。
- **branch / commit / 输入：** MAIN→`codex/crg-c06-routing`；EXACT batch/problem1；NATIVE README/HANDOFF/replay_api；Q1 neighborhood/release_ideals；已归档Q2退化与Q3反转。
- **修改范围：** 新 `src/plan_routing/` 与能力manifest、独立测试；不修改现有evaluator实现。
- **禁止修改范围：** 共用禁止项；不得用Q1 exact batch评分Q2/Q3，不以native score填完整JSON，不按P2名次硬删P3候选，不以代理值当下界。
- **实验协议：** 冻结相同候选流；比较B=1/8/32，固定分区与变化分区各一批；至多64次新增E0，其他回放已有标签但明确非新评测。所有prepare/pack/IPC/guard/fallback/输出计时。E2只有验收能力manifest时才可启用，否则走ABSTAIN。第一次支持域差异即停原生shadow域。
- **输出：** route decision traces、能力矩阵、缓存hit/miss成本、abstention覆盖、短名单遗漏/反转审计、端到端成本表。
- **验收：** 每条路由与q/k/H/输出级别匹配；所有fallback可靠；实验未显示净节省也可按证据选择exact-first。
- **失败 / 停止：** 准备/检测吃掉节省；未经校准局部模型冲突；系统性漏掉反转类好方案；全窗口600秒或64 E0到达即停。
- **依赖：** C01、C03；C04提供不能合并frontier的约束。
- **是否并行：** 可以与C05并行开发；正式计时顺序独占。
- **预计资源：** CPU-only，1worker基线；至多2worker另列，父子总内存4GiB停止阈值。
- **成功后解锁：** 低成本、保持探索覆盖的精确评价层；明确是否需要局部模型。

## C07 — 1–5 核 continuation 与旧方案保险

**/goal 文本：** 实现追加末尾空核的跨环境continuation，再用固定小额SPLICE/CUT/macro预算释放并行度；检验旧非空事件的保持条件和完整求解成本，不替换官方固定单核基准。

- **命题：** 可行空核嵌入可以复用旧方案结构；性能改善需要操作，不能由核数本身推出；warm seed可能降低达到同质量的时间，但可能陷入旧分配结构。
- **branch / commit / 输入：** MAIN→`codex/crg-c07-continuation`；C01/C06；原始008/044/080、固定singlecore_evaluate.py；Q3固定constructor与Q1旧合法方案。
- **修改范围：** 新 `src/plan_continuation/`、测试与报告。
- **禁止修改范围：** 共用禁止项；不得在中间插入核并假定ID/同刻顺序不变；不得将优化后的k=1方案代替B(G)；不得复制旧num_cores/full JSON。
- **实验协议：** q=Q1/Q2/Q3，k从1到5。先冻结小面板，最多60次新E0、600秒；每个q覆盖1→2和4→5，并覆盖中间两步。warm与cold同预算；记录嵌入/操作/最终确认各自耗时；持有已确认旧方案作为新k的保底候选。
- **输出：** 每步环境、父子方案、empty-core投影对照、guard翻转、warm/cold质量–时间、B-normalized speedup及另列Q3无Cache/有Cache对照。
- **验收：** k改变不冒充同环境primitive；对已证明空核嵌入域保留旧Makespan；新改进必须E0确认；明确所有仍未覆盖组合。
- **失败 / 停止：** 非空图/事件变化先定位嵌入语义；warm持续输cold则保留二者小型种子池，不无限重启；到预算即停。
- **依赖：** C01/C06；若采用宏则依赖C05相应guard。
- **是否并行：** 可独立于C05非宏版本；不与同机器正式计时竞争。
- **预计资源：** 单CPU、2GiB、无GPU。
- **成功后解锁：** 核数轴复用及经过检查的跨k宏适用区间。

## C08 — 有损信息保留、无损语义的竞争版蒸馏

**/goal 文本：** 将已通过阶段门槛的PlanOp、guard、macro和route压缩为竞争候选solver；先证明固定候选流语义不变，再测完整搜索质量–时间–内存及解释能力损失，未通过就保留研究版。

- **命题：** 去除无收益instrumentation、专门化热点、复用上下文和编译宏，能在预声明质量损失内降低端到端成本；不是简单重写语言或增加调用量。
- **branch / commit / 输入：** MAIN→`codex/crg-c08-distill`；输入必须是C01/03/05/06/07已冻结产物提交及manifest，不能直接跟踪移动HEAD。
- **修改范围：** 新 `src/solver_distilled/`、独立thin CLI、质量–成本报告；保留研究版作为oracle/debug路径。
- **禁止修改范围：** 共用禁止项；不能删除基线保底/官方确认/错误分类/事件语义；不能用更多预算掩盖算法损失或把GPU吞吐当单例速度。
- **实验协议：** 两步：固定候选流比较完整结果；随后预冻结图级独立的最多12个q/k环境，研究版/蒸馏版相同预算。最多96次E0、1800秒测试窗口，额外训练/代码开发另记；冷启动和确认计入。
- **输出：** ΔQ、ΔT、ΔM、被删除解释字段清单、剩余最小决策日志、回退率、每图每q/k失败和分布尾部。
- **验收：** 建议预注册门槛：固定候选流零语义差异；相对研究版最终M的恶化中位数不超过0.5%、最差不超过2%；不能比已确认保底方案差；端到端几何平均至少1.5倍、P95内存不高于研究版。门槛是候选研发标准，不是官方要求。任一质量损失需明示。
- **失败 / 停止：** 任一语义差异停止相应快路径；无净收益则不合入竞争版；最多两轮有界蒸馏修正，不转入无限调参。
- **依赖：** 前述通过门槛的模块；Definition Amendments未通过的部分继续按CRG v1命名。
- **是否并行：** 不宜早于schema/guard/route稳定；可按不相交模块并行编译，最终测试串行。
- **预计资源：** 首版1CPU/4GiB；设备探测后才考虑额外并行，无默认GPU依赖。
- **成功后解锁：** 单例自包含、三问/核数参数化、可追溯且保留E0确认的竞争版候选。
