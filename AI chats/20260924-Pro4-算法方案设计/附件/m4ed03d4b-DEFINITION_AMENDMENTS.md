# Definition Amendments — D综合建议，非静默替换

版本：D-DA-v1；基础定义：用户提供的 `01_GLOSSARY_V1_SOURCE.md`。本文件不修改Glossary v1或原作者答复。下列建议由队长确认后，形成新的协议版本；未确认前，综合报告仅将这些条件作为相应命题/实验的显式附加前提。拒绝某一修订时，只阻断依赖该修订的保证，不要求停止全部研究。

## DA-D01：环境、参考runtime与输入表示

**原定义：** D00-1的环境为G/q/k/C/H，H为源码身份；D00-3默认确定行为。

**问题：** 未明确参考Python/本地库、浮点构建、遍历顺序以及入口/`max_iter`等调用参数；也未区分解析后的有序对象和原文件空白/路径元数据。相同源码不自动构成已验收的跨runtime零差分。

**建议：** 保留H为源码哈希，增加R和I侧车：R记录语义相关运行契约，I记录入口及限制、输入解析/序列化与输出投影。研究环境可显式写成：

\[
\widetilde E=(G,q,k,C,H,R,I).
\tag{SDA-01}
\]

R记录解释器及版本、相关依赖/原生库ABI和二进制哈希、浮点选项/禁止fast-math与FMA重排的声明、哈希seed与已知遍历顺序控制。宿主CPU/RSS/并发还作为性能环境记录，不声称每一项一定影响数值。未证明无关的R变化先分实验身份；不是断言所有平台都必然不同。

输入侧至少保存原bytes hash与有序解析对象身份；不将键重排、子图重命名或op键文本别名当免费归一化。输出路径等CLI元数据单列，不能无说明删字段后称full相同。

**影响：** 精确复用键、跨runtime差分、原生支持域、singlecore基准及observer。**来源：** A DA-01、C DA-03，D进一步明确入口/表示。**状态：推荐采用。**

## DA-D02：官方失败与外部删失

**原定义：** D00-2的输入合法不保证成功，D01却将F写成总映射且普遍投影Makespan。

**问题：** plan/order校验、局部编译、全局执行可分别失败；外部timeout不能推断官方本来会失败。

**建议：** 官方评价返回带类型的成功或规定失败；外部终止为未观测完的删失记录。用部分映射即可避免虚假总函数承诺：

\[
F_{\widetilde E}:\mathcal P_{\mathrm{in}}\rightharpoonup
\mathcal Y_{\mathrm{ok}}\sqcup\mathcal Y_{\mathrm{official\mbox{-}failure}},
\qquad M\text{ 仅定义于 }\mathcal Y_{\mathrm{ok}}.
\tag{SDA-02}
\]

执行记录另有`external_timeout / cancelled / service_error / not_evaluated`；不能填0、无穷或invalid。官方max_iter错误按I/H规定记录，不与外部wall超时混为一类。对于结构域上的操作，输出可为exec-unknown，不冒充P_exec中的箭头。

**影响：** D11交互缺项、D15 enabled-action解释、标签训练、budget和回退。**来源：** C DA-02。**状态：推荐采用。**

## DA-D03：D15的动作语言、空字和transport

**原定义：** 对所有双方同时合法的有限操作序列观察一致，且可用操作一致。

**问题：** “同时合法”单独使用可能忽略只在一侧可用的词；按位置/按对象的动作不相同；未明确空操作。

**建议：** 固定全局动作alphabet（schema版本＋确定参数＋地址含义）；令L(P)为可执行的有限词语言，包含空字。定义：

\[
P\sim_{\Phi,\mathcal A}Q
\iff L(P)=L(Q)\ \land\
\forall w\in L(P),\ \sigma_\Phi(w(P))=\sigma_\Phi(w(Q)).
\tag{SDA-03}
\]

“可执行”应指声明的变换域（例如P_ord），不自动指每个候选都已运行官方成功。若选择P_exec，则必须支付或证明相关成功域检查。失败/unknown输出的观察也须显式定义。

若希望在重命名代表之间翻译动作，另提供保组合、保可用性的transport；不能把字面不同动作临时当同一动作。有限h步检查只是h-view，采样不完整时结论为unknown。对一个真正封闭有限域的全部状态/动作细化到不动点，才可声明该有限域的D15。

**影响：** 商搜索、receipt、哈希去重、充分状态。**来源：** A/C一致支持，D消除形式歧义。**状态：推荐采用。**

## DA-D04：区分评分表示、运行checkpoint与未来充分状态

**原定义：** D17相对于未来动作充分，D18最小状态为行为类；聊天中曾用同名词指可重放程序。

**建议：** v1的D17/D18保留。另命名三个对象：`compiled-body representation`（重复编译复用）、`current-score representation`（只算当前投影）、`runtime checkpoint`（固定程序继续运行）。它们不能直接标成D17。

证明D17至少给出：压缩状态决定动作是否启用、可在压缩状态更新、决定当前观测。证明最小性另行要求可区分性/最粗等价；表示的“维度”改报编码字节、共享静态部分、构造和更新成本，避免把全部plan编码进一个整数。

D14评分缓存与D15 frontier去重必须是独立数据结构。完整result包含逻辑计划时，只能压缩不改变相应观察的编码冗余，不能期待大量不同逻辑切法归并。

**影响：** MAP-FACT/QUOT/STATE、C04及新D1/D2/D7。**状态：澄清保留，推荐采用。**

## DA-D05：多核指标和Q3对照

**原定义：** D29将所有q的固定baseline/M称Official Speedup，B只写作B(G)。

**问题：** 官方Q1/Q2单核展示点固定1；Q3要求同核数no-L2/cache。基准还依赖官方配置、代码及参考runtime。优化单核研究结果不能顶替固定分子。

**建议：** CRG-19保留为`Baseline-normalized Speedup`，基准带baseline_id。另定义：

\[
S_{q,k}(G,P)=\frac{B_{C_0,H,R}(G)}{M_{q,k}(G,P)},
\quad
\overline S_{q,k}=\frac1N\sum_i S_{q,k}(G_i,P_i),
\quad
\mathrm{CacheGain}_{k}(G;P_2,P_3)=\frac{M_{2,k}(G,P_2)}{M_{3,k}(G,P_3)}.
\tag{SDA-04}
\]

Q1/Q2官方曲线单核点1；算法优化的一核plan和其S值另表。Q3的一核Cache对照不强制1。CacheGain必须标记同plan机制对照或分别优化的solver对照；后者包含算法改变，不称纯硬件因果收益。诊断配置属于独立实验，不混入正式固定配置平均。

`data_movement_bytes`是官方计划搬运统计；Q3命中字节不能擅自从scheduled字段扣掉。字节命中率与访问次数命中率也不互换。Makespan优先，墙钟是另一优化轴，不自行发明官方权重。

**来源：** C DA-01、官方目标规范优先。**状态：推荐采用。**

## DA-D06：传播耦合、交互耦合与“少数方向”

**原定义：** D12以改变层数/远端对象比例/距离为耦合；D13/D39给显著响应及少数类解释能量的假说。

**问题：** 改变许多层可能只是ID平移或整体起始时刻平移；分层变化比例不是可加性或统计条件独立。操作类别可事后设计成看似稀疏；大退化也可占据响应能量。

**建议：** D12原三量改明确称`propagation signature`，保留字面/对齐两版；另加四臂的非加性交互。敏感性必须注明环境/父计划/动作分布μ、编辑尺度、阈值及收益符号，并分别报改善、退化、无响应及未定义。选择敏感类和测试解释率必须图/父计划分组隔离。

低参数宏、大响应宏、局部小编辑敏感方向三者分开。跨guard既非显著收益的充分条件，也非全部敏感性的必要条件；regime分辨率由ρ决定。少数敏感类失败不否定需要协同大编辑的宏。

**影响：** D6的测量设计、局部专家特征与峰值归因。**状态：推荐采用。**

## DA-D07：有限模式、表示域与结构完备

**原定义：** D08部分变换；D22–24完备性未固定表示范围。

**建议：** `CUT/JOIN/SPLICE/RECODE`是有限操作schema，不是默认有限个具体映射。完备性声明需带P_ord/编码域/k和非空条件。RECODE仅子图标签及mapping排列；不改G中的op/tensor ID。不覆盖的op键文本别名、JSON空白不计入当前生成定理。

用规范十进制键定义研究域，不构成规范化后评分不变的定理。对P_ord的线性路径数不升级为P_exec连通、在线线性复杂度或必须先拆成singleton的实际策略。JOIN裸操作不可逆，receipt保存前态才可回滚。宏可以原子提交终态，过程中exec-unknown必须显式保留。

**来源：** C §4–6，D补目标联合拓扑序/编码范围。**状态：推荐采用。**

## DA-D08：纯图guard、机制候选与参数局部性

**原定义：** D32纯图特征，D31机制为多条件命题；D25宏要求机制预期。

**建议：** `graph_feature(G)`、`plan_feature(G,P)`、`environment_feature(G,P,C)`和`observed_feature(F(P))`类型分开。未读取候选结果前不能使用其真实ρ当免费detector输入。

当前resource-word只证计算串行模板一致，不叫完整Op–Tensor同构。一个macro可先登记为`candidate/HYP`，不要求为部署而先假装有稳定机制；原有启发式可作为构造基线而不强冠“已证宏”。

parameter-local机制可能有高价值；不能只保留跨所有图/q/k都稳定的机制。“尚未找到解释”只记unclassified；不能用它证明accidental。

**影响：** D3/D4/D5图匹配、迁移样本和线上guard。**状态：推荐采用。**

## DA-D09：多轴证据与实际路由

**原定义：** 第26节E0/E1/FORMAL/EMP/HYP/AUTHOR-REPORT混合引擎类别、核验程度及命题性质。

**建议：** 保留原标签作为来源字段，新增：

`producer / artifact_completeness / reviewer_verification / claim_kind / scope / runtime_id / input_hashes / output_level`。

例如A-produced E0的完整结果本轮读回，标`full-readback`，不是`D-rerun`。另一个Pro引用同一报告不增加独立重复数。文件CRC/SHA只保证所给字节一致，不保证作者推理正确。

Backend capability按q/k/H/R、数值域、输出级别、精确性证据、fallback实际调用定义。E2是历史名称，不自动近似；native也不自动已验收全结果精确。ABSTAIN不删除候选；模型分歧只是不确定性特征之一，不能代替独立校准。

**影响：** 所有表格、预算、路由和验收。**状态：推荐采用。**

## DA-D10：关系链改为有条件DAG

**原定义：** 第25节以长链连接敏感方向、商、状态、族、专家、操作与蒸馏，允许箭头被否定。

**建议：** 明确取消必须依次通过的解释。操作/身份/观测是底座；机制宏、编译复用、受限状态压缩并行；映射族贯穿每条线；局部专家可选。没有D15大商仍可以有优秀求解器，没有稀疏小编辑响应仍可以有大协同宏。

**影响：** Research DAG和任务依赖。不改变任何已归档数学定义本身。**状态：推荐采用。**
