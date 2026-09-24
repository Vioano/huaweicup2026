# Pro C：可组合操作语言、表达能力与算法蒸馏

**依据：Coherent Research Glossary v1（D00–D39）。** 本报告不静默修改定义；文末列出的 Definition Amendments 仅为建议，未采用。现有仓库数值在本次属于 AUTHOR-REPORT；本次只做了纯结构有限检查，零官方 evaluator 调用、零求解优化、零仓库写入。

## 1. 实际读取 HEAD / 文件

| 分支 | 本轮冻结 HEAD |
|---|---|
| main | f27ef37bb76dcf556f35d3f2328e405d92241d9c |
| codex/q1-bounded-search-20260924 | 4dff90ef699fd51845cf482951e8477066f5f566 |
| codex/q2-structure-nikolastarx | 74c46372faf5910b9b3cce6ad9a61a7e040b17aa |
| codex/q2-budget-search-yuanzhifang | 0b58c123cccf02fc993b741d79dcd8511e4dd38f |
| codex/q3-core-nikolastarx | a4e7ee13310d693ec4fb5cc236669ceb3b172d1f |
| codex/q1-exact-batch-20260924 | 5bfe53a29c1ba05167239f51ea937e602f7f85b4 |
| codex/evaluator-native-probe-20260924 | 03f02e79de4b4bd6f55241385664b154f4332454 |

全部通过授权 GitHub connector 读取。27个文件的逐项路径、提交、实际范围在 READ_MANIFEST.json；目录树和HEAD查询另外完成。没有把分支HEAD当成所有实验的as-run提交：例如Q3报告标注实际运行源码c1ea7986，Q2联合报告标注73e40f6d，Q2 stage-B保留多个控制版本。

主读：Q1的neighborhood/search/structure/release_ideals和profile-refine记录；Q2两分支的joint/proposals及两份REPORT；Q3的construct、METHOD、pilot REPORT；EXACT的problem1/batch；NATIVE的README/HANDOFF；main的官方目标说明、单核入口、Q2构图/重标注片段、源清单头部和归档索引。没有重新计算整套官方源码哈希，没有重新解压核验所有既有结果。

**主判断：** 建立小型、带类型和守卫的方案变换内核；把既有复杂constructor作为向该语言编译的上层策略；把“评分复用”和“合并搜索状态”分成两个独立模块。数学上可证明结构合法域上的表达能力，工程上不必为完备性遍历整个空间。

有一处需要纠正我前次审计的措辞：情况A的Step2/backing由每个Task的局部图分别初始化，不应无依据引入“从前一Task继承任意backing状态”的算法自由度。固定划分的局部程序可以复用，全球完成时间仍受所有核DDR过程影响。当前EXACT的源码正是固定mapping缓存局部编译、每次重新全局模拟。

## 2. 精确术语表

| 术语 | 本报告使用的工作定义 |
|---|---|
| 官方映射 | D01：固定E下plan到完整B的映射，不是Makespan标量。|
| 映射族 | D02：明确允许G/q/k/C/H哪些轴变化的一组官方映射。|
| 行为观测/签名 | D03/D04：显式Φ与其作用于完整行为的结果；哈希需说明碰撞与丢失信息。|
| guard/切换边界 | D05/D07：明确的离散选择及一次编辑使其取值改变；时间变化本身不是guard。|
| regime | D06：相对于明确ρ的等值集合；不能不说明分辨率。|
| primitive | D08：固定E内带类型的部分方案映射，含完整适用域和合法层级。|
| 编辑大小 | D10：分区、归属、顺序、表示变化组成的向量，不把少参数等同小编辑。|
| 离散雅可比 | D11：primitive对显式Φ的类型化有限响应，不强迫为普通实矩阵。|
| 耦合度 | D12：层变化覆盖、局部邻域外对象变化比例、指定图上的传播距离；分别报告。|
| 敏感方向 | D13：同时指定小编辑阈值、响应阈值与稳定度；单见证只支持候选。|
| 当前观测等价 | D14：当前Φ签名相同，不保证未来操作。|
| 强行为等价/商 | D15/D16：相同未来操作可执行性与所有合法continuation的相同观测；h-step不是全域。|
| 最小充分状态 | D17/D18：相对于Φ和未来操作集的等价类；紧凑可计算表示是否存在仍待研究。|
| 局部评估器集 | D19/D20：detector、预测器、目标、不确定性及routing/abstention组成，不是无条件代理。|
| 完备性 | D22任意对可达；D23从固定seed生成；D24必须限定域。表达能力不等于在线遍历。|
| macro | D25：图guard、regime guard、primitive policy、允许操作集、可观察机制预期，以及rollback。|
| 多核轴/continuation | D26/D27：k是映射族轴；改变k是跨环境映射，不是固定E primitive。|
| 峰值见证/机制 | D30是具体环境和显式参考下的高收益；D31是跨条件可预测的结构命题。|
| Peak-to-Mechanism Distillation | D36：见证→反事实→分层diff→guard/原因→结构条件→迁移试验→宏候选。|
| 算法蒸馏 | D38：压缩已验证操作、guard、macro、routing和索引，并报告质量/时间/内存/解释损失。|

所有Makespan比较限成功运行的方案；官方失败与研究外部timeout分别记录，不填写假分数。运行环境另存Python/平台/编译器/浮点选项，跨运行环境的等价不默认成立。

## 3. 推荐数学对象

推荐**带守卫的typed partial transformation system**。方案是对象，实际应用的编辑是带参数、前后条件与receipt的箭头。合法组合形成路径；路径有结合律和恒等，但未必有全局逆。

不是群：JOIN丢失原划分，不是裸方案上的单射；不是环：无自然加法/乘法满足需求。保存历史receipt后可以逆转具体应用，这属于带见证的可逆编辑层，不证明整个系统是groupoid。rewrite system只用来简化已证明等价的编辑程序；graph grammar适合实现CUT/JOIN的数据结构，不必成为整体理论。

设研究使用的结构域为：

\[
\mathcal P^{ord}_E=\{P:\text{字段/覆盖有效，商图及所有核内相邻块序边的并图无环}\}.
\tag{COPS-01}
\]

另明确P_plan、Q1的P_task、成功执行域P_exec。对Q2/Q3，式COPS-01可以是保守构造域，但不是一般官方执行合法性的充要条件；不能把Q1整Task等待强加到场景B。

操作作用于subgraph。仅Q1里subgraph就是Task；Q2/Q3的Task是整个核上的合并程序。因此Q2/Q3的subgraph move会改变两个核的Task内容，且生成ID变化可能影响更远的编译对象。

## 4. 最小 primitive set 候选

“最小”指易审查的独立编辑模式，不是任意编程语言上的最少符号定理。一个REPLACE_PLAN就可以平凡地覆盖一切，但没有研究价值。

**三类语义编辑＋一类表示编辑：CUT、JOIN、SPLICE、RECODE。**

严格区分有限模式与有限具体映射：这是四种带参数的模式；在不限制子图整数标签时，它们的全部参数实例并不是一个有限集合。若要求字面有限的primitive实例集合，先把研究域限制为标准十进制op键和子图标签0至n−1，再展开所有合法参数；此时实例集合有限。这个受限域仍覆盖所有抽象分区/归属/核序，但不声称覆盖官方允许的所有字面编码或保持重编码前的行为。

每个具体参数实例都是部分映射：

\[
 a_\theta:D_{a,\theta}^{\ell}\subseteq\mathcal P_E^{\ell}\longrightarrow\mathcal P_E^{\ell},
\quad \ell\in\{plan,ord,exec\}.
\tag{COPS-02}
\]

exec级别只有实际编译/执行检查或相应已证明证书支持时才能标注。构造器无需为每个内部结构编辑调用E0；但不能把未评估的中间方案叫作exec-certified。

| primitive | 参数、domain与前置条件 | 输出、字段、检查 | 逆与provenance |
|---|---|---|---|
| CUT | 当前块B，非空真子集I，fresh sgid；I为D[B]的序理想；parent在指定合法域 | B替换成I及B\I，同核相邻，更新mapping；检查覆盖和商图/核序。不能假设Step2成功 | JOIN两子块可恢复；receipt保留原块、原标签、键序、插入位置与完整参数 |
| JOIN | 同核相邻块A,B；收缩后仍在指定合法域 | 两块合并，保留显式选择的标签，删一个核序项；当前并图不得有通过外部的A→…→B路径 | 裸JOIN多对一；有成员分割/标签receipt才可反向CUT |
| SPLICE | 块B、目标core、删除B后的目标gap；参数为确定地址而非随机意图 | 删除再插入；同核实现reorder/adjacent swap，异核实现assignment change；mapping不变；Q1使用精确插入区间 | 记录旧core/gap可逆；不重排其他块、不重编号 |
| RECODE | 子图标签的单射重编码、mapping条目排列；不改G中的op/tensor ID | 更新mapping值及core_schedules标签，必要时换mapping序列化次序；属于可能改变F的操作，不是免费规范化 | 单射逆与条目排列逆；保留字面ID与原始键序 |

所有receipt记录E、父/子plan hash、schema版本、参数、读写集、guard结果、合法层级、inverse patch和来源。CAS父版本检查用于事务安全；若把父hash检查本身列入D15的未来动作语义，则会人为把商细化至每个plan，必须说明操作集的选择。

已有“priority/granularity修改”不是新增硬件primitive。priority先生成期望的合法子图序，再降低为SPLICE；granularity降低为CUT/JOIN；resource-word和affine是生成编辑程序的上层构造，不是提交的精确启动时刻。

在已给定COPY收缩DAG的前提下，理想检查线性于块内点边；重编码/完整输出线性于方案大小；单次全局结构检查线性于商图规模。若缓存移动块的祖先/后继，枚举目标区间后每个槽位只需构造而无需重复遍历。

\[
T_{edit}=T_{construct}+T_{legality}+T_{compile}+T_{simulate}+T_{route}+T_{record}.
\tag{COPS-03}
\]

上式用于不重叠阶段的顺序基线；并行时另记外层墙钟，不能把worker服务时间相加冒充wall time。任何局部结构复杂度都不能隐去后四项；没有“改一个块只重算两个核”的通用保证。

## 5. 生成完备 / 可达完备

### 5.1 结构域上的构造性连通定理（FORMAL）

固定有限原始依赖DAG、至少一个核。把方案限制为标准十进制op键（mapping顺序仍保留），并使用式COPS-01的结构合法域。忽略标签差异时，CUT/JOIN/SPLICE任意对可达；需要匹配具体标签/键序时加入RECODE。

**证明。** 对任意P、Q：

1. 在P的每个块内部选拓扑词，逐次CUT序理想前缀，得到singleton。原商图无离开再返回同一块的路径；块内沿拓扑序细化，因此所有中间并图仍无环。
2. 取该singleton并图的一个线性扩展L。按L扫描，把节点移到core0的已打包前缀后；所有剩余核序仍是L的子序列，所以每一步合法。
3. 取Q的块并图拓扑序，并在每块内部拓扑排列，拼成目标词L_Q。把core0词变成L_Q：依次把目标下一节点向左SPLICE到已匹配前缀后。被跨过的每个节点都与它不可比，否则两个词不可能都是线性扩展；因此每一步合法。
4. 按L_Q把singleton移至目标核，得到各核目标子序列。
5. 在每个目标块内JOIN相邻子块。每个中间方案都是目标无环块图的拓扑细化，因此合法。最后RECODE匹配目标标签与键序。

每个阶段只有线性数量编辑；不必把一次长SPLICE展开成所有相邻交换：

\[
L_{path}\le (n-m_P)+n+n+n+(n-m_Q)+2\le5n+2.
\tag{COPS-04}
\]

这是编辑次数，不是wall-time界；写出每个完整中间plan就可能产生二次数据量。算法只需存稀疏patch/持久序列。可达路径不以Makespan单调改善为条件。

**删除生成元后的障碍：** 无CUT无法增加块数；无JOIN无法减少；无跨核SPLICE无法改变归属；无RECODE时，单节点图也可能无法到达另一合法子图标签/键序表示。这是在本报告明确的原子定义下的必要性，不是对所有可能DSL的最小性定理。

### 5.2 不能外推到P_exec

Step2失败、Step3内存依赖、场景B的跨核FIFO执行环、以及运行器限制可能使结构路径经过执行失败点。并且某些P2/P3官方方案可能在本保守并图域之外。本次没有证明整个官方P_exec连通，也没有证明它不连通。

“有界原子事务在draft中同时改多字段、只检查最终plan”可作为另一个工程入口，但若中间不在选定合法域，就不能把它写成D22中的primitive路径。不能用任意全局replace掩盖这个缺口。

### 5.3 本次实际有限检查（EMP）

algebra_structural_checks.py枚举至多4个点的所有前向标号DAG、1/2核、所有抽象分区和核序：150个环境、9676个合法状态；检查121834个插入槽位与81928条生成边。区间与暴力无环检查一致，状态图全部连通。2.581秒是该纯组合测试本次耗时，不是solver性能。0 E0/E1/E2/native调用；不包含COPY、memory、float或实际P_exec。有限检查不替代上述证明。

## 6. operation interaction / commutation / inverse

### 插入区间（FORMAL，固定分区/结构域）

移除B的核序关联，保留数据边，并连接原核剩余相邻块。在这个图上计算B的祖先A和后继D。目标核删除B后的序列为v_0…v_(r−1)。

\[
\ell=1+\max\{i:v_i\in A\},\qquad
u=\min\{i:v_i\in D\};\qquad j\in[\ell,u].
\tag{COPS-05}
\]

空集合分别取−1、r。插在所有目标核祖先后、所有后继前恰好避免新环；若有环必经B，反推违反某一端条件。当前Q1 neighborhood.py采用这个机制，并明确不声称它是全执行判定。

### 可交换性要分两层

方案级交换需要两种顺序都合法且产生同一个字面plan：

\[
 b(a(P))=a(b(P)).
\tag{COPS-06}
\]

足够的工程守卫包括读写互不冲突、相同gap锚点解释、ID分配独立，以及对方不会改变本操作的合法guard。仅“不同核”或“不同原图分支”不够。即使COPS-06成立，单步Makespan响应也未必可加；共享DDR/Cache/关键路径可能导致二阶交互：

\[
 I_{a,b}^{M}(P)=M(b(a(P)))-M(a(P))-M(b(P))+M(P).
\tag{COPS-07}
\]

四个方案必须来自同一环境/parent；不合法项记未定义，不能填零。交换性未成立时该式是有序交互，不可叫对称Hessian。

### 编辑大小和CRG耦合

\[
e(P,P')=(|\Pi(P)\triangle\Pi(P')|,
\#\{v:core_P(v)\ne core_{P'}(v)\},
|O(P)\triangle O(P')|,e_{repr}).
\tag{COPS-08}
\]

Π为同块op无序对；O为同核、不同块、由提交核序确定的有序op对；e_repr记录标签/键序改变。少量affine参数可改变线性规模的O，不能因此称“小编辑敏感方向”。

Φ按L1–L6分组，初版离散结构差异阈值0、权重均等；时间响应另外用绝对cycles/相对变化。对象局部邻域固定为直接编辑块及原图一跳邻域；远端变化占所有可观察对象比例。依赖图断开的资源耦合报告距离∞/disconnected，同时可另报事件因果图距离，不能偷偷改距离定义。

字面diff与provenance对齐的因果候选diff分开：生成ID整体偏移在字面层是真变化，但不应在机制图中被误解为所有远端计算都变了。后者不能替代前者来声明E1零差分。

### normal form与强行为商

只能在证明域内消去identity、紧邻edit/undo、相同块连续SPLICE等冗余记录。JOIN/CUT不会天然有全局confluence；重新分配标签可能改变官方行为，禁止无证据自动重编号。

关键分离：**W是固定编译上下文中一次操作性评分的复用条件，不自动是D15强行为商。** 粗/细两个plan可能有相同Φ_oper，但只有细方案具有某个JOIN动作，或只有粗方案具有某个CUT参数。下一步可用动作不同，已经违反D15，无需再等未来Makespan差异。

\[
P\equiv_\Phi Q\ \centernot\Longrightarrow\ P\sim_{(\Phi,\mathcal A)}Q.
\tag{COPS-09}
\]

因此维护两个账本：评分缓存按经过证明的当前签名；搜索frontier保留完整plan及future capabilities。要真正商搜索，必须证明启用操作集对应、操作结果仍同类。只验证h步则只发布h-step。

## 7. macro层设计与峰值机制

现有证据均为本次AUTHOR-REPORT，不是新复跑：

| 来源 | 观察 | 对宏设计的约束 |
|---|---|---|
| Q3 pilot case008 | component 123060；affine 64686；resource-word 63768；三者Q2/Q3相同，0hit/0spill、COPY字节相同 | 以component为参考，48.18%下降是见证；不能归因Cache，仍须查COPY时序与M/V空闲 |
| Q2 stage-B case008 | M1/M2都未胜过123060，最坏候选375521/220442 | 表达力不同于参数池规模；需要能表达重入次序的模式，而非继续扩大旧枚举 |
| Q2 joint case002 | full-ready critical 72056；earliest_start 92004；父72415 | 计算最早开始代理并非通用宏guard |
| Q3 case080 | component P2/P3为111466/90736；affine为112445/83124，且增加spill | Q2排名、零spill不能硬筛Q3 |
| Q1 case044 | seed116227；某split清零spill却123363；merge(8,10)126094；merge(6,8)114443 | “消spill”“省边界”不是性能证书 |
| Q1 case051 | seed338698；两个split为337672、336057；较少搬运的merge339356 | 应检查release/门控变化，而非仅流量 |

### M-A：Q1 ReleaseIdealSplit候选

g_G：精确定义的块内DAG和外部前驱关系；g_R：绑定当前parent的真实/保守release标签，存在早晚门控差异。π：算阈值理想或受限min-cut理想→CUT→必要时SPLICE。Ω：减少某部分工作对晚前驱的整Task等待，并记录新增边界、100/1000等待、spill及全局资源变化。不是承诺减Makespan。release_ideals.py已经明确自身为构造kernel，不继承旧局部调度/backing、不把精确cut/work子问题当时间下界。失败回滚到原plan。

### M-BC：Q2/Q3 ReentrantWord候选

g_G：真实链、M(a)–V*(b)–M(a)、同构、b≤2a；每核作业数作为显式feature。g_R：固定owner/键序/子图编号比较契约，candidate经过真实L3/L4检查；若欲引用理想结论，必须另有其无额外资源干扰条件。π：把目标M/V先后词编译为合法priority，再CUT/SPLICE降低。Ω：减少关键重入pipe空闲；同时观察COPY排序、spill和cache，而非只看总字节。少作业、异构、分叉、COPY瓶颈是必留反例。

### M-C：Q3 SharedInputPhase候选（HYP）

g_G：可计算的输入消费超边、大小、每核访问集合；g_R：当前cache请求顺序及guard信息有可用来源。π：仅用SPLICE/CUT/JOIN改变合法请求优先级，不能提交显式等待或预取。Ω：改变同刻miss、后续命中、FIFO淘汰与两池重叠；pending insert包括in-flight hit。guard不确定就走精确评价，不把命中率提高写成Makespan必降。

每个macro保存D25五元组、反例、适用q/k、预测响应区间、后置检查与rollback。它是候选还是已验证必须有状态字段。常见heuristic可以继续作为baseline generator，但不能因为封装成功就冠以峰值机制。

若Pro B给出“结构S＋regimeR→操作模式O”的命题，接口应接收可运行detector、ρ版本、edit program、Φ响应预测、已检验与未检验的q/k/G/C域和反例；Pro C验证降低正确与事务性，Pro A验证观测/guard能力。不能只接收一份赢家JSON。

## 8. research solver架构

支持先做可研究版，但只做能回答假设的最小系统：

```
FrozenEnvironment / PlanIR
        ↓
PrimitiveKernel + Draft + Receipt
        ↓
ConstructorCompiler / GuardedMacroRegistry
        ↓
LegalityCertificates → EvaluatorRouter
        ↓
L0…L6 ObservationStore → typed Response/Coupling
        ↓
ConfirmedIncumbent + Frontier + ScoreCache
```

官方输入仍只有两个字段；日志均为sidecar。候选、父子关系、guards、合法层级、compile signatures、路由、预算和失败保留。Tier0仅必要哈希/receipt/精确指标；Tier1记录相关机制摘要；Tier2对见证、反例和抽样记录完整轨迹。未观测≠为空。

研究版方案：先建立已确认保底；允许少量变差但合法的中间候选，以免把“改进单调性”强加到表达语言；最后只提交已确认合法结果。需要隔离“研究探索保留”与“当前提交赢家”。

阶段门槛是建议研发值，不是官方标准：

1. **S0（一次实现窗口）**：操作/receipt/域明确；现有constructor降低后plan一致；纯结构测试通过。
2. **S1（至多48次E0）**：只读观测开关零差异；三问与五核数均有触达；能解释指定负例的首个变化层。
3. **S2（最多两轮有界机制实验）**：至少一个宏得到可迁移预测或一个明确失效域；同时评价guard成本和保底胜率。不以一直完善术语为目标。
4. **S3**：做同预算研究版/蒸馏版比较；无改进就保留薄IR+exact evaluator，删除无收益商/局部模型。

## 9. core-count continuation

追加末尾空核是跨环境操作，不是SPLICE：

\[
C_k(P)=\bigl(mapping(P),\ schedules(P)\mathbin{+}[\,[]\,]\bigr).
\tag{COPS-10}
\]

结构合法性保持：没有新块或依赖边。执行M不变还需对应H的空核分支不改变非空编译、事件和浮点结算；full result的num_cores/空核记录当然会变化，不能直接复制旧JSON。本轮未做新的跨k E0验收。

由精确保值嵌入可条件性推出最优值不增：

\[
M_{E_{k+1}}(C_k(P))=M_{E_k}(P)
\ \forall P\in\mathcal P^{exec}_{E_k}
\Longrightarrow
\inf_{\mathcal P^{exec}_{E_{k+1}}}M\le\inf_{\mathcal P^{exec}_{E_k}}M.
\tag{COPS-11}
\]

这与某个使用更多非空核的具体分配变慢完全兼容。

流程：旧方案保底→少量重Task/链/分量SPLICE到新核→必要CUT释放并行→重新检查q相关gate/cache/word guard→精确确认。Q1整个Task move能命中固定mapping编译缓存；Q2/Q3改变owner通常跨越编译上下文，不能假设只影响两核。word的每核作业数减少可能失去重入重叠；跨k宏不能无条件继承。保留一个独立cold结构seed，防止warm continuation锁定错误组织。

固定B(G)不能被优化后的k=1方案替代。CRG D29的B/M工作量继续计算；官方Q1/Q2固定单核点及Q3无L2/有L2对照另外保存，见文末amendment。

## 10. evaluator routing

首版默认exact-first；local evaluator首先返回精确结构量或ABSTAIN，未准备好不强行引入拟合器。

| 阶段 | 允许动作 | 不能据此做什么 |
|---|---|---|
| 0 schema/coverage/商图 | 便宜精确检查，确定invalid可拒绝 | timeout/不支持不等于invalid |
| 1 Q1 Task-order区间 | 固定partition精确结构证书 | 不把此充要性搬给Q2/Q3整个执行 |
| 2 local set | 每个模型声明D_r、T_r、U_r；冲突/域外/guard风险ABSTAIN | boundary bytes模型不能硬剪Makespan |
| 3 E2 | 只有能力manifest匹配域才软排序；保留不同宏族和审计配额 | 不把预测当下界，不用P2排序删P3 |
| 4 Q1 exact batch | 每个plan重新检查；固定mapping复用官方L1–L4 | 缓存局部编译不是缓存全局答案 |
| 5 native replay | 先shadow；完成独立域验收才实路由；所有打包和回退计时 | 当前原型不是完整JSON/生产错误回退，不声称通用3问支持 |
| 6 E0 | 新域、冲突、最终/抽样复核，完整官方输出 | 不能把确认成本移到solver计时之外然后称端到端 |

EXACT batch key实际包含有序raw mapping、bandwidth、capacity，graph/engine在实例固定；每次重验Task-order，更新core/preds并重新全局运行。它实现的是**编译产物复用，不是D15方案行为商**。

NATIVE报告：三张图9个候选及另64候选已做作者对照；三候选时含准备相对E1约0.43–1.95倍，64候选约33.7倍。当前应按复用密度和支持域决定是否尝试，不直接承诺吞吐。Q2/Q3本次未核验通用exact batch能力，默认E0而非把Q1引擎换一个q参数。

将操作分成“留在可复用编译上下文”与“跨上下文”。研究版允许同context批量评分，但固定保留跨context宏的探索配额；否则评分器快的方向会压制更有价值的split/merge。这个配额是研究政策，不是最优性定理。

## 11. algorithm distillation

优先蒸馏正确性不变的部分：typed IR静态检查、已冻结宏降低、增量结构索引、不可变编译程序、能力路由和量化小批次。保留全部官方事件及精确浮点程序。

| 处置 | 具体对象 |
|---|---|
| 编译掉 | 通用解释器调度、宏参数解析、重复合法前提检查（仅有有效证书时） |
| 缓存 | 图索引、真实局部编译、经过证明的当前评分对象；有界且类型/顺序/版本敏感 |
| 内联 | 热路径CUT/SPLICE、已证明guard、固定序列更新 |
| 删除 | 无预测力的feature/local模型、κ近1且昂贵的商、每候选全Trace、无收益候选族 |
| 变成macro | 通过反事实/迁移检查的有效操作模式，而非只保存赢家参数 |
| 变成静态规则 | 确定的域检测/合法变换；没有证明的质量判断仍需精确确认 |

\[
\Delta Q=\left\{\frac{M_{dist}-M_{research}}{\max(1,M_{research})}\right\},\quad
\Delta T=\{T_{dist}/T_{research}\},\quad
\Delta M=\{RSS_{dist}/RSS_{research}\}.
\tag{COPS-12}
\]

解释损失另列“失去哪些Φ分量/重放能力”，不能伪装成一个可加标量。建议门槛：固定候选流零语义差异；搜索最终质量恶化中位数≤0.5%、最差≤2%；保底不退化；端到端几何平均至少1.5倍。它们是候选验收值，必须执行前冻结，不是已取得成绩。

## 12. 十条可证伪关键命题

| ID/等级 | 命题与域 | 证伪/否定动作 |
|---|---|---|
| P01 FORMAL | 三编辑模式在P_ord上任意对可达，具体编码加RECODE | 输出两个结构合法节点及不可达证据；检查证明或实现guard遗漏 |
| P02 FORMAL | 固定partition的插入位置由COPS-05恰好给出 | 暴力逐槽验证，尤其混合长度/空核/shortcut |
| P03 HYP | 某声明图族的P_exec仍有可用连通子域 | 找结构合法但Step2/全局执行失败的阻断路径；不能只测赢家 |
| P04 FORMAL | W当前等价不自动给D15，启用集差异即否定 | 相同Φ_oper的粗/细plan，查CUT/JOIN可用性 |
| P05 FORMAL+待实现验收 | Q1固定有序mapping可复用局部编译、全局须重放 | 新归属/顺序/等待与无缓存E0全字段比较；加入L1重复reload |
| P06 HYP | 不同核编辑的Makespan响应可以强交互 | 四臂交互实验，预选同刻DDR/Cache边界；零交互只在该面板成立 |
| P07 条件FORMAL/待验收 | 末尾空核embedding保结构，若保事件则保M | 所有q和1→2…4→5比较旧非空事件及float-hex，full元数据单列 |
| P08 HYP | ≤20%操作类可解释≥80%预定义显著响应 | 平衡抽样且图级验证；若需要近完整基则放弃少数敏感方向假说 |
| P09 HYP | case008word模式在预注册guard域可迁移 | 同构破坏、短作业数、b/a边界、tensor大小/ID次序、跨q/k反事实 |
| P10 HYP | 蒸馏达到COPS-12的预注册质量–成本门槛 | 同预算端到端对照，计所有准备和回退；不达标即不采用 |

## 13. Codex /goal候选

完整13字段任务契约见 CODEX_GOALS.md：

C01操作IR与回滚；C02可达性与插入区间；C03只读观察/响应；C04 W当前等价vs强商；C05峰值机制宏；C06routing；C07多核continuation；C08蒸馏。

这些是候选，不是自动开始的流水线。C01/C02可先做0E0；C03后才有共同可归因证据。C05必须等Pro B的机制命题明确后才能升级稳定宏。C08等schema/guard/route稳定；不因想追求完美形式化而阻塞已有exact+constructor方案。

# Definition Amendments（仅建议，未采用）

## DA-01：D29 “Official Speedup”覆盖Q3与k=1的命名

1. 原定义：所有q/k统一以B(G)/M称Official Speedup。
2. 问题：原题Q1/Q2固定单核点为1；Q3还明确要求同核数无L2/有L2曲线和比值。仅B/M不足以完成这些官方对照。
3. 建议：保留CRG-19作为共同Baseline-normalized Speedup；另定义官方Q1/Q2汇总口径与Q3CacheGain，并写明是同plan机制对照还是各自solver的比较。
4. 影响：多核面板、峰值reference、C05/C07/C08的指标与验收表；不改变primitive/连通性。未批准前正文继续使用D29定义，Q3对照作为额外独立观测保存。

## DA-02：D01失败行为与Makespan投影

1. 原定义：F_E从P_E到完整B；D00-2未保证最终执行成功。
2. 问题：通过plan检查后仍可出现官方运行错误；这时Makespan不能作为普通成功分数处理。
3. 建议：B明确为成功行为与官方失败前缀/错误的带标签并集；π_M仅在成功分支定义。进程外timeout/服务故障不是官方失败分支，另存观测状态。
4. 影响：local response缺失值、route/abstention、C02/C03/C06/C08失败处理；连通性需明确合法域。未批准前所有数值命题已限P_exec，避免未定义值。

## DA-03：D00-1中H与运行环境

1. 原定义：H是evaluator冻结代码身份。
2. 问题：同源码跨Python/运行库/浮点编译选项不能预设为同一个零差分映射。
3. 建议：把H细化为源码身份加语义相关runtime contract，或给E增加显式R；不必把CPU型号的所有细节都视为语义参数。
4. 影响：exact/W缓存身份、跨平台等价、C03/C06/C07/C08实验元数据。未批准前仍使用E=(G,q,k,C,H)，但所有严格等价结论明确限制于同一记录运行环境，不宣称跨环境。

# 最后判断

最值得尽快实现的不是一个庞大“操作代数平台”，而是：**四个明确编辑模式、分层合法性、精确receipt、L0–L6签名接口、评分缓存与搜索frontier的分离、以及能把现有三个场景constructor降低为这些编辑的薄层。**

这能检验哪些理论环节值得继续：强商可能没有压缩，但macro可能很好用；local evaluator可能无收益，但compile-context复用仍有效。任何一种阴性结论都不应迫使系统继续背负无收益复杂性。
