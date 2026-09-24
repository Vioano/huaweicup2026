# 官方映射结构：Coherent Research Glossary v1 下的研究架构判断

**角色：Pro A／研究架构师。不是最终求解器交付。**

结论：对“编译分解、分层响应与guarded macro”给Go；对具有真实盈亏验收的选择性局部评估器给Conditional-Go；对“保持完整result又大量合并不同逻辑方案”的行为商给No-Go。后者不是悲观猜测：冻结result能够恢复逻辑方案，因此保留完整输出的商原则上只能消去输入编码冗余。

证据标签按用户CRG v1：E0、E1、FORMAL、EMP、HYP、AUTHOR-REPORT。工程后端名“E1/E2”与证据等级不是一回事。本轮没有重新验收这些加速后端。

## 1. 实际读取材料与固定HEAD

| branch | 本轮读到并固定的HEAD |
|---|---|
| main | `f27ef37bb76dcf556f35d3f2328e405d92241d9c` |
| codex/q1-bounded-search-20260924 | `4dff90ef699fd51845cf482951e8477066f5f566` |
| codex/q1-exact-batch-20260924 | `5bfe53a29c1ba05167239f51ea937e602f7f85b4` |
| codex/evaluator-native-probe-20260924 | `03f02e79de4b4bd6f55241385664b154f4332454` |
| codex/evaluation-concurrency-20260924 | `abdfd31f358a035e5ecca3b0482a9d0881060ffe` |
| codex/q2-structure-nikolastarx | `74c46372faf5910b9b3cce6ad9a61a7e040b17aa` |
| codex/q2-budget-search-yuanzhifang | `0b58c123cccf02fc993b741d79dcd8511e4dd38f` |
| codex/q3-core-nikolastarx | `a4e7ee13310d693ec4fb5cc236669ceb3b172d1f` |

读取经已授权GitHub连接，不使用组织库或匿名404推断私库状态。main不存在的PRO4更新在Q1固定分支读到；并发设计的正确路径为`docs/a/e2/CONCURRENT_EVALUATION_DESIGN.md`。

Q1六入口已读：Q1_SEARCH、Q1_GUIDED_MOVES、Q1_PROFILE_REFINE、Q1_RELEASE_IDEALS_REVIEW、Q1_TRACE_EXPLANATION、Q1_TRACE_PROSPECTIVE；另读pro008机制对照summary和PRO4_Q1_AUDIT_UPDATE。

Q2已读：joint/summary.json与metrics.csv；Fang stage-b/REPORT.md、budget_search.py前210行、Q2_HANDOFF的可见主体。Q3已读：pilot/metrics.csv、REPORT.md、online/REPORT.md、src/q3/construct.py、best/manifest.json及best目录元数据。

评估器已读：P1_BATCH.md和batch.py；native-replay README/HANDOFF；并发设计§1–4、NEEDS_AND_EVIDENCE与ROUTE_COST_REVIEW；额外固定`603b0741e21c449d3db652ebd67c94f2dc014cc9`的P23_HANDOFF.md、scene_b.py。没有把设计中的共享服务当作已部署，也没有把内部评分速度写成完整JSON速度。

官方七个指定模块已从现有附件原件完整读取，另核对validation/plan builder的有关路径。重算源码集合hash仍为`de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`，与main manifest相同。`contract-v1.md`从已上传DELTA读取的blob为`65227e...`，与镜像一致，重点读§1–4.4。FORM采用65d6c0e SPEC的已读范围、e1575a1定点复核和Q1分支PRO4修订，不将旧F-TASK-006通则作为事实。不存在“已验收全部FORM”的声明。

### 本轮新增E0：峰值核对，不做搜索

为取得计划字节，先尝试连接返回的下载入口，容器传输失败；随后按实际已读`construct.py`逻辑重建。重建计划同时匹配仓库SHA256 `1935d89ad16a59a52ad62b2e00b4b43f30e783ade40fe481fc6063d905da64ce`及Git blob `9a1fd3849389fb0155d82d02a91d87c1bf967410`。因此使用的是字节一致计划，不是仅同名算法。

[E0] 五次未修改官方CLI，每次预先上限30秒：

| 输入 | Makespan | scheduled COPY bytes | spill bytes |
|---|---:|---:|---:|
| case008官方singlecore | 487605 | 2654424 | 0 |
| case044官方singlecore | 154407 | 5413568 | 4438112 |
| case008／同一resource_word／Q2／4核 | 63768 | 2654424 | 0 |
| case008／同一resource_word／Q3／4核 | 63768 | 2654424 | 0 |
| case008／同一resource_word／Q1／4核 | 588824 | 26625240 | 0 |

Q3的432次COPY_IN均miss，命中字节0；所以这个见证不能被解释为Cache加速。CRG D29单核比值为7.646546857；同plan在Q1为0.828099738，反而慢于固定单核。Q1分支已有588824的作者对照，本次另立新运行身份核验了Q3已发布计划的Q1执行，未声称与旧Pro计划字节相同。

[FORMAL，实例代入] case008的M工作量250128、V工作量237168；四核资源下界62532。因此63768这份可行解的相对最优性差距上界约1.9766%。这不证明下界可达，也不证明峰值机制稳定。

[E0] 另做24次Q2函数调用：固定4个独立、无tensor计算操作、1核、固定singleton mapping，穷举24种核内顺序。此为官方API可接受的合成域，不代表正式图分布；不是24次CLI。全部原始结果保存。具体D14/D15结果见§4、§5。

[EMP] 对已有27份完整结果零新评价地恢复逻辑方案，全部相符。

本轮总计5次CLI+24次函数E0；没有E1/E2、GPU、神经训练或全100图实验。运行环境Linux x86-64、Python3.13.5；不把与仓库macOS数值吻合升格为跨平台验收。其他仓库成绩、计时和自测计数仍为AUTHOR-REPORT。

## 2. 无歧义术语表（使用CRG v1，不静默改义）

| CRG条目 | 本文工作含义 |
|---|---|
| D00 | 环境固定G/q/k/C/H；P_plan、P_task、P_exec分开。正文数值预测限定最终成功域，不给失败虚构Makespan。 |
| D01–02 | F是L0–L6完整过程；映射族必须列明哪些G/q/k/C/H轴变化。 |
| D03–04 | Φ选择观察，σ是其值；完整对象、哈希和摘要不是同一精度。 |
| D05–07 | guard是离散选择；regime由显式ρ的等值类定义；boundary是编辑改变guard，不是分数微小波动。 |
| D08–09 | primitive是带参数、适用域和合法输出条件的部分映射；改变k是跨环境continuation。 |
| D10 | 小编辑用partition/assignment/order等多维签名；一项grain参数改变全图不是小编辑的证据。 |
| D11 | J是按各数据类型定义的有限差异；不套连续链式法则，不预设可加。 |
| D12 | 耦合分别报告layer/object/distance；不造一个掩盖差异的任意总分。 |
| D13 | 敏感方向须指定ε/δ/α及稳定域；single witness不是跨图敏感规律。 |
| D14 | 当前Φ相同。 |
| D15 | 相同未来操作可用性，并在全部合法continuation下观察相同；h步是有限版本。 |
| D16 | 行为商只对D15关系使用；D14类称当前观察类。κ必须说明样本与去重方式。 |
| D17–18 | S的相等须推出D15；抽象最小类存在，不代表紧凑可计算表征存在。 |
| D19–20 | 局部专家包含D_r、预测目标、U_r；路由允许分歧、拒答、精评回退。 |
| D21–24 | Γ_A表达操作可达关系；pairwise、rooted和restricted completeness分别声明。本轮不证明全域生成完备。 |
| D25 | macro必须含图条件、regime条件、primitive composition、预期机制与rollback，不只是算法组合名。 |
| D26–27 | 1–5核是离散尺度轴；C_k复用父计划产生新核计划，不能以重新跑solver替代定义。 |
| D28–29 | B(G)为官方固定单核，不是单核最优；D29比值依此计算。Q3题面另要求同核无L2/有L2对照，不能用D29研究比值替代该交付。 |
| D30–31 | witness是特定E/P/参考/收益；mechanism是包含G、P、q、k、C、regime、操作和稳定响应的条件命题。 |
| D32 | graph feature只能是G的可计算函数；父计划、Trace和cache状态是另类state feature，不能混叫x(G)。 |
| D33–35 | structural/parameter-local需预设迁移阈值；未知机制不等于accidental。 |
| D36 | 从见证、反事实、行为diff到有预测条件的macro；不能只存最优参数。 |
| D37–38 | research solver保留可观察/归因；蒸馏需同时报告质量、时耗、内存和丢失解释能力。 |
| D39 | 少数敏感方向是假说；操作类先冻结、平衡采样，并在未用于选方向的域检验。 |

### Definition Amendments（待批准；正文不自动采用）

**DA-01：精确确定性的运行环境。** 原定义D00-1用H指冻结源码身份，并由D00-3断言确定过程。问题：源码hash本身没有写出Python版本、容器遍历、浮点执行及构建约束。建议H扩展为“源码身份+参考执行契约”，或E增加参考runtime字段。影响：跨平台等价声明、签名cache key、原生回退和所有严格零差分任务。未批准前，本报告的FORMAL精确性结论额外限定同一参考runtime；不把跨runtime结果纳入同E等价样本。没有声称本轮已复现跨平台分歧。

无需修改D17：本文严格将执行中checkpoint称为“重放检查点”，不把它偷换成plan上的充分状态。M仅在P_exec上取数值；官方拒绝/运行错误/外部超时分开保存。

## 3. 对官方映射结构的总体判断

### 3.1 最有价值的是分解，而不是统一低维商

[FORMAL] 固定划分的Q1存在直接源码级分解：Task/COPY与Step1–3不消费核序和100/1000等待来编译内部程序；归属、前驱外壳和全局资源必须每候选刷新。这是exact batch/native replay已利用的真实结构。

[AUTHOR-REPORT] P1原生交接中，单图64个不同候选、计准备成本的内部评分约33.7倍；只有3个候选时约0.43–1.95倍。P23手头原生路径的冷搜索仍大量花在局部编译。它们不是同输出同平台统一速度基准，但都反驳“先假设只能评价极少候选”和“原生一快就任意加预算”。

[FORMAL] 不同方案完全可以共享K而具有不同全局结果。**编译复用既不要求全局响应局部，也不要求完整行为等价。** 因而CRG关系链的若干箭头不能当逻辑蕴含：高耦合不否定缓存，低耦合不推出D15，D15无用也不否定macro。

### 3.2 全result商的关键否定

[FORMAL] 在成功域，给定G，Q1完整结果的原计算op→task_id及每核tasks/subgraphs顺序恢复原映射和core_schedules；Q2/Q3用op的subgraph_id和每核subgraph顺序同样恢复。因此去掉原JSON拼写和mapping插入次序之后，result对逻辑方案是单射。

这不是建议在生产中归一化输入！只说明：若Φ保留完整result，任何非平凡压缩至多来自输入编码冗余，而不是大量不同切分/分核/排序变成同一个行为类。由于D15包含零步观察，同样结论传播到D15及D18。

### 3.3 三问不能共享一个万能局部状态

| 问题 | 可优先共享 | 不可省略 |
|---|---|---|
| Q1 | 固定partition的局部编译；Task-order合法索引 | Task门控、同核Task链、在途DDR、完整生成ID上下文 |
| Q2 | 原图索引；相同真实local graph+prioritized seq的编译 | 合并Task的COPY附着桶、四Pipe FIFO、内存边、跨核release |
| Q3 | 可与Q2对齐的L1–L4部分 | 上述全部，再加逻辑key、FIFO有序项、在途请求/插入、两池状态 |

[FORMAL] 官方Q3局部builder仍只接收DDR带宽和L1/UB容量；L2容量/带宽影响全局Cache路径。原生pack若预计算hit工作量，cache-bandwidth进入pack key是实现需要，不能倒写成“官方Step3使用L2带宽”。

## 4. 八条可证伪命题

以下成功/失败条件均是建议实验判据，不是已达性能。

| ID / 命题 | 当前证据 | 最强反例/失效条件 | 最小实验 | 成功价值；失败应砍掉什么 |
|---|---|---|---|---|
| P01：完整result上没有有用的逻辑方案商 | FORMAL：恢复证明；EMP：27份恢复成功 | JSON别名/顺序冗余可以合并，但不是不同逻辑方案；改变Φ后另议 | 对Q1/2/3完整输出恢复两字段，检查全覆盖 | 尽早停止通用full-result quotient；恢复失败先定位具体字段域，不贸然泛化 |
| P02：Q1有广泛编译复用域，Q2/Q3域更窄 | FORMAL源码参数依赖；AUTHOR-REPORT exact/native | split导致后续generated ID变动；B的priority改变Step2/3 | 同partition move/reorder与split/merge分组比较L1–L4 | 精确批次提效；失败砍“只改两Task就只失效两Task”而非全部复用 |
| P03：小编辑可以低编译耦合而高时间耦合 | HYP待测；共享DDR全局更新代码支持可能性 | 一次局部发射改变其他弱连通分量时间；只有整体平移不代表持续时间重组 | 同规模同类编辑，分开测编译、Δstart、Δduration、远端影响 | 找低成本域；失败砍“局部图距离足以局部重评” |
| P04：D14压缩经未来编辑可能迅速消失 | E0：24态时间类4→h1的20→h2的24；仅此有限域D15可穷尽 | 限制A后可能保留大类，不可用本例否定全部restricted quotient | Φ/A双轴，保留最短区分continuation | 真正安全去重；κ接近1时停止该域商优化 |
| P05：通用紧凑D17状态未必存在 | FORMAL：Φ_full的恢复性；HYP：受限Φ/A可压缩 | 相同占用量但FIFO次序不同；相同总余量但按请求分布不同；同K不同操作适用性 | 字段消融加同S异continuation区分对 | 找有证明的状态闭合；失败砍总负载/命中率式“充分状态” |
| P06：选择性Δ/排序专家只有在真实精评成本前占优才值得 | AUTHOR-REPORT：入口特征新池无收益，P23冷准备占主成本 | detector自己跑完Step3，或ABSTAIN占满预算 | 与exact-only同池同总时间对照，计特征+fallback | 降低达到同质量时间；失败移除专家而保留exact batch |
| P07：少数敏感操作类跨域稳定仍未知 | E0：008强witness；不是稳定方向 | 原生动作类重分组制造能量集中；大macro冒充小编辑；跨k符号翻转 | 冻结编辑度量/操作类，按图留出测能量和显著事件覆盖 | 提炼guarded macro；失败删除全局稀疏假说 |
| P08：空核嵌入可行不等于使用新核必改善 | FORMAL源码可证明活动投影保持；E0同plan跨q峰值反转 | 重编号核、重新分配、强迫使用新核会改变事件序；不同q本来不是同E | k=1…5末尾空核+固定局部continuation，逐q检查 | 保留父解的跨k起点；失败停止相应无条件延拓，不改固定单核基准 |

### 本轮有限商实验细节

固定Q2、1核、四个独立无tensor操作，M耗时2/5、V耗时3/11，固定singleton编号；A只有三个“交换相邻槽位i,i+1”的部分映射，在这个24态域全部可用且域闭合。

- Φ_M：24态同为14 cycles，D14有1类；所有未来仍14，D15也1类。κ大但没有可优化的M差异。
- Φ_op-times：D14有4类，κ=6；1步细化20类，2步24类，下一次稳定。故这个闭合有限域的完整D15为单例，不只是“测了两步就猜全部”。
- Φ_full：起点就24类。

显式区分对：顺序[0,1,2,3]与[0,2,1,3]当前逐op时刻相同；执行同一个“交换前两个槽位”，前者交换两个M操作、后者交换M/V，逐op时刻不同。这不是连续Jacobian，也不是“同一分数即可合并”。

## 5. 必要的数学形式化

### 5.1 行为观测：类型化对象，不混成一个浮点向量

| 层/机制 | 保存的对象 | 差异运算与关键边界 |
|---|---|---|
| L0 partition/assignment/order | 原始有序plan及逻辑成员关系 | raw差异另存；co-membership差、迁移成员数、共同对象的顺序逆转；不把ID改名视为免费语义变换 |
| L1 Task/COPY | 有序局部图、每个COPY的原tensor与端点、生成ID | 节点/边增删、按角色对齐；精确字节分量与COPY数量分开 |
| L2 Step1 | raw_seq、B的prioritized_seq、tie顺序 | 完整序列差异与原计算投影同时保留；计算投影不能替代全序 |
| L3 Step2 | overflow、victim、有/无backing、from/to/version/pos、改接边 | ordered records差异；原backing/首次写出/复用写出分别标识，不能固定2×size |
| L4 FIFO | 四Pipe完整序列，含COPY与spill | 分Pipe逆序/相邻边变化；计算词相同不够 |
| L4 memory | WAR/WAW sources、reused bytes、position、前tensor | 边与属性diff；无spill不代表无内存边 |
| L5 release | Q1 Task前项/前驱控制项；B跨COPY实际release | 记录全部并列最大项、slack与切换；父Trace值只作冻结特征 |
| L5 DDR | 带身份在途集合、余量、更新时间、busy intervals、投影/实际结束 | 精确事件对齐和因果边；仅总字节/平均并发不足 |
| L5 Q3 cache | hit/miss、插入/驱逐、逻辑key、最终FIFO、两带宽池 | 不丢队列顺序；同刻访问/完成次序与在途同key分别记录 |
| L6 | Makespan、完整正式result、各分项 | 数值difference/ratio；全字段保留原值，不归一化掉“难比”的时间和ID |

用原计算ID作为稳定锚；生成COPY/spill以原tensor、父成员集、源/目标角色、occurrence与锚点对齐，同时保存实际ID。对齐用于解释，**不是已证明等价的cache key**。未匹配对象记新增/删除/unknown，不猜对应。

### 5.2 编辑、局部响应与耦合

可用编辑签名：

\[
e(P,P')=(\#\text{co-membership changed pairs},\ \#\text{op-core changes},\ \#\text{common-object order inversions},\ \#\text{edited original ops}).\tag{OMA-01}
\]

不必枚举所有操作对：partition contingency计数可计算第一项；但本轮没有实现通用度量器。报告原始值和按对象总数归一化值，不把一个全图grain参数修改算成一个“小动作”。

遵循D11，数值相减、集合对称差、序列逆转、图边差与轨迹对齐并存。时间响应至少分开Δstart与Δduration，避免把一条后缀的统一平移当作全部Task服务机制变化。

D12的C_layer使用L1–L6的预注册分层、默认等权，同时给出零容差变化与实用显著阈值版本。C_object优先以原计算op为固定分母；新增COPY只在生成对象层另报。局部邻域在运行前由被编辑原成员定义，不能看到响应后扩张邻域来降低耦合。

C_distance同时报计算/Task图中的最远可达距离和“原图不可达但受影响比例”；不可达记∞/disconnected，不删除。可增列共享资源交互图距离，但不能替代原图距离。

两个动作的非加性交互仅在四个计划均有定义时计算：

\[
I_{a,b}(P)=M_E(b(a(P)))-M_E(a(P))-M_E(b(P))+M_E(P).\tag{OMA-02}
\]

它依赖执行次序，不声称对称；a/b的成员参数须在组合中仍有意义。较大的I会否定独立相加的局部成本模型，不否定单步Δ预测。

### 5.3 guard crossing与稀疏性

ρ必须预先选取离散结果，不使用“时刻差了一点”代替guard。局部编辑不天然给出ρ之间的稳定对应；新增/删除的对象应先记存在性guard。建议两个分辨率：细ρ记录对齐的COPY存在、overflow/victim/backing分支、FIFO、release并列控制项、池活跃次序、cache事件；粗ρ只保留预先声明的聚合类别。缺失事件的存在性单列guard。

真实ρ通常事后才能算出。线上detector只是预测/证书，不得把事后ρ免费输入模型。可用已知确切域（如Q1固定partition）以及便宜的风险特征；一旦必须先完成与E1同成本编译才能detect，应把这部分成本计入并考虑直接精评。

冻结K个操作类并按类平衡采样，以归一化ΔM的平方定义每类响应能量：

\[
E_c=\mathbb E_{(P,a)\sim\mu_c}\left[(\Delta M/M_E(P))^2\right],\qquad
\eta_r=\frac{\sum_{c\in\mathcal C_r}E_c}{\sum_{c=1}^K E_c}.\tag{OMA-03}
\]

μ_c、类别划分与选前r类的数据必须冻结；在另一图/核数域评估η_r，并同时报告显著事件覆盖、改善与退化。零总能量记不适用，不能除零后报“完美稀疏”。D13稳定度α按预定域统计，单个008不得代表跨图稳定。

### 5.4 行为等价最有价值的截断点

[FORMAL] 数值逻辑方案规范形记canon(P)，只用于陈述恢复性，不作为生产改写。存在从完整结果恢复两字段的函数D：

\[
D_G(\pi_{L6}F_E(P))=\operatorname{canon}(P),\quad P\in\mathcal P_{\rm exec}.\tag{OMA-04}
\]

理由：原eligible ID已由G确定，Q1 op.task_id或B op.subgraph_id恢复成员；每核有序subgraphs恢复core_schedules。故完整result相等必然逻辑plan相等；加入未来操作不可能让关系更粗。

更有价值的截断候选是**消费端所需的L4执行程序**，另保留输出metadata。但这首先是函数分解/复用，不是D15关系。逐层注意：

- Task/COPY“数量相同”不足；需有序图、ID、属性和后续优先信息。
- Step1“序列相同”不足；需相同局部tensor/edges/size/pos/capacity。
- Step2“spill记录相同”不足；需完整extended graph/seq与数值语义。
- Step3“计算FIFO相同”不足；需全部四Pipe、内存边、COPY工作、跨核links。
- 全局“op时刻相同”不保证Cache/metadata相同，更不保证未来编辑可用性。

[FORMAL] Q1固定有序mapping与局部编译参数时，可以写成：

\[
F_E(P)=\operatorname{Render}\bigl(\operatorname{Replay}(K_{\pi},A(P));\mu(P)\bigr).\tag{OMA-05}
\]

K包含真实官方Step1–3产物；A是核序/归属/门控外壳；μ是输出所需统计与标签。Replay仍是全局，不能把Task时间求和。Q2/Q3的K通常依赖同核优先序；相同完整输入和优先后序列才可引用确定性继续复用。

### 5.5 D17需要操作闭合，不只需要能重放

一个表征S被证明充分的实用充分条件是：

\[
P\in D_a\iff d_a(S(P)),\qquad
S(a(P))=\bar a(S(P)),\qquad
\sigma_\Phi(P)=o(S(P)).\tag{OMA-06}
\]

由操作长度归纳，三式保证可用性与全部continuation观察一致，因而满足D17。把整个plan编码成一个大整数并不构成有用压缩；要比较信息位数、共享静态程序成本、构造和更新成本。它不证明最小性。只证明第三式（能算当前结果）远远不够。

| 目标/未来A | 当前可合理提出的表征 | 结论 |
|---|---|---|
| Q1固定partition的move/reorder；Φ=M | 共享Kπ + 当前core_orders +验证所需Task图 | 可减少重复存储/编译；core_orders仍承载全部可变选择，不叫最小商 |
| Q2固定归属的priority/grain；Φ=M | 完整优先/桶信息及可重建的local graph；必要时K | perPipe投影可给当前M，却未必支持未来priority操作；本轮24态是反证 |
| Q3同类A；Φ=M+cache events | 上述信息加逻辑key/size与真实缓存/双池语义 | 总命中率、占用量、总剩余工作不是充分状态；紧凑闭合表征尚待证明 |
| 任意q、全split/merge/move；Φ=full | 至少能恢复逻辑plan；还须保持构造语义 | 通用低维D17压缩No-Go；可做紧凑编码，不是行为合并 |

运行时checkpoint是另一对象：Q1需活跃Task、核链位置、完成门控与在途DDR；Q2需FIFO位置、依赖释放和DDR；Q3另需有序cache、在途命中/未命中插入、两池余量与最后更新时间。L5不重算L1/UB容量，相关约束已编进L4；完整输出还需要历史日志/渲染metadata。删除日志可能加快评分，但不代表保留完整F。

### 5.6 哪些正式结构适配

- **Partial order：Go。** 计算DAG、Task+核链、完整执行DAG三层各有自己的合法性域；cover和理想集是构造工具，不保证时延。
- **Max-plus：受限Go。** 固定依赖、固定时长、给定释放的事件图服从max-plus递推；任意动态DDR/Cache不能直接塞入同一个固定矩阵。
- **Piecewise affine：只对明确的实数影子模型。** 固定E的P是离散对象；必须先指定数值坐标/允许变化的参数轴，不能用任意one-hot查表使“分段仿射”变成空话。固定事件顺序/活跃集合后，服务余量更新对工作量和等待可呈仿射；对带宽本身有倒数，官方还含ceil/EPS/binary64。不能把这个影子模型的等价当E1零差分。
- **Finite-state：局部Go。** 固定有限key/size/容量下的Cache子机是有限有序状态，但状态数可巨大；加上全局时钟/剩余量不自动成为小有限自动机。
- **Bisimulation/Nerode：作为问题定义与反例工具Go。** 可以在封闭有限方案图上做精确划分细化；不能从采样碰撞推全域D15。
- **普通timed automata的region theorem：不直接移植。** 公平共享服务的速率随活跃请求数变，且有动态生成和浮点结算。需要新证明，而不是套一个现成有限商结论。

本轮只作定点一手来源核对，不开展长综述：Baccelli等《Synchronization and Linearity》（1992）本轮进一步读了§3.2.3中Theorem 3.17/3.20与证明的路径解释，本轮进一步读了§3.2.3中Theorem 3.17/3.20与证明的路径解释，用于固定事件图/max-plus背景；Paige–Tarjan《Three Partition Refinement Algorithms》（SIAM J. Comput. 16(6),1987,973–989，DOI10.1137/0216062）核对元数据，并通过原稿前两页截图读了关系最粗细化问题的定义，本实现是简单逐轮细化而非该论文优化算法；Alur–Dill《A Theory of Timed Automata》（TCS126(2),1994,183–235，DOI10.1016/0304-3975(94)90010-8）仅核对摘要/元数据，全文下载未成功，不援引具体定理。所有本题命题以上述代码或本报告证明为依据。

### 5.7 核数轴

[FORMAL] 固定图、q、C、H和参考runtime，在末尾增加空核不改变旧操作的执行/带宽参与次序；Q2/Q3新增空Task只改变元数据。故对有效操作与M的投影：

\[
M_{E_{k+1}}(C_k^{\rm empty}(P))=M_{E_k}(P),\qquad
\inf_{P'\in\mathcal P_{\rm exec}(E_{k+1})}M_{E_{k+1}}(P')
\le\inf_{P\in\mathcal P_{\rm exec}(E_k)}M_{E_k}(P).\tag{OMA-07}
\]

这里不是完整result相等，因为num_cores/空核条目/task_count可变；也不是使用新核后必改善。不得以核心任意重编号代替末尾嵌入；同刻迭代顺序可能受影响。q变化则属于另一轴，008的Q1/Q2/Q3反例已经说明不能统一移植。

## 6. 局部评估器集：明确决策

| 预测任务 | 判定 | 原因 |
|---|---|---|
| 跨所有G/q/k的单一绝对Makespan代理 | No-Go作为当前主线 | 结构切换与基线尺度混合；可靠分域成本未证实；现在已有精确重放路线 |
| 直接预测同父计划primitive/macro的Δ | Conditional-Go | 对齐目标最直接；但差分不会自动抵消系统误差，也不能组合相加 |
| 同池pair ranking | Conditional-Go，优先小试 | 可避免过度数值精度；仍须留住近优候选，不能只看相关系数 |
| 只决定值得不值得精评 | Conditional-Go | 与预算直接对应；误杀峰值最危险，必须有挑战槽和拒答 |
| 预测明确机制量：精确边界字节、合法域、冻结门控 | Go作为特征/证书 | 有直接结构依据；不能把机制量当Makespan替代 |

routing建议：先确认q/版本/输出能力与预算→做便宜的适用域检测→若已有便宜精确重放则直接用它→否则请求最多两个局部专家→域外、guard风险、模型冲突、宽不确定区间则ABSTAIN→按声明回退E1/E0；ABSTAIN不是丢弃候选，跨guard的高收益方向仍可获得精评。预算不足记deferred/unevaluated并保留父解。

P1固定partition的密集新调度池优先exact batch/native；split/merge需要重新编译。P23当前native分数虽叫E2，实际路线是官方/优化局部编译+原生事件重放，不应按旧近似回归误差描述。其full=True或fallback可能直接调用该q完整E0；P1可能回退完整E1。要在派发前分别圈存，不凭native_enabled=True承诺0完整评价。

专家输入只能用运行前可得特征：G特征与(P,a)状态特征分开。实际guard签名只用于事后诊断/训练标签；detector耗时计入。误差校准按图/父计划整组留出，报告覆盖率、近优集合召回、shortlist regret、拒答原因及回退成本。模型一致也可能共享偏差，因此冻结一部分精评槽为随机/新机制挑战者。

总成本为：

\[
T_{\rm routed}=T_{\rm features}+T_{\rm detector}+T_{\rm models}
+T_{\rm abstain/fallback}+T_{\rm selected\ exact}+T_{\rm final\ E0}.\tag{OMA-08}
\]

只有在同预算官方质量或同质量时间上优于真实exact-only路径，才接入；不能用旧慢Python基线或热重复吞吐制造收益。当前结论是Conditional-Go而非已实现local evaluator集。

## 7. 建议 /goal 候选任务

完整卡在`GOAL_CARDS.md`，每卡含核心命题、固定输入、允许/禁止修改、协议、产物、验收、停止、依赖、并行性、资源和解锁内容。这里只给研究依赖概览，不代最终综合者调度：

1. MAP-OBS-01：L0–L6只读观测与provenance对齐。
2. MAP-FACT-02：编译可复用边界与冷/新候选成本。
3. MAP-QUOT-03：D14类经未来操作是否存活；full商先停。
4. MAP-STATE-04：D17闭合条件、字段必要性与checkpoint区分。
5. MAP-SENSE-05：类平衡的耦合/guard/敏感方向证伪。
6. MAP-LOCAL-06：带ABSTAIN的Δ/排序器对真实精评路径的盈亏。
7. MAP-SCALE-07：空核continuation与峰值的q/k边界。

最重要的交付不是一幅必须全成立的理论链，而是三份可分开验收的证据：哪些编译可复用、哪些操作在何条件下可靠改变机制、哪些预测/去重值得花成本。行为商失败但精确批次和guarded macro成功，同样是本轮研究的成功结果。
