# 华为杯 A：从偏序、边界状态与事件代数构造算法

日期：2026-09-23。独立研究续篇。目标是官方评估器下的高质量解，而不是增加理论名称。本文件不替代题面，不代表团队 PR/E1/E2 已验收。

## 0. 主判断

优先研究三种不同的压缩：

1. **理想集/参数最小割**：把任意集合分区压缩为满足方向约束的一族嵌套切分。最小割能精确解决一个有意义的构造代理，但不是原题 Makespan。
2. **重复分支计数/窄张量边界 DP**：把逐节点核心选择压缩成少量类型的数量和边界张量状态。严格等价需要编译器与事件规则的对称性，不能只看图同构。
3. **max-plus 端口消元 + FIFO 定向修复**：在编译结果固定后消去只传播固定时延的内部节点，把动态 COPY/Cache 交互保留给模拟器；同时用执行图定位少量值得调整的子图顺序。

目前最明确的新官方机制证据，是固定划分和核心归属只调整顺序就能将一个微图从1410降到818 cycles。最强的数学子程序证据，是理想集超图割与整数端口消元分别通过1200、2400次有界核验。它们都不构成正式100-case算法提升。

## 1. 证据边界与纠正

### 1.1 原件与旧产物

原官方附件、两份旧报告、旧证据ZIP及三份增量资料都可读取。官方114个文件逐项匹配旧manifest；FORM增量38个payload匹配其manifest。官方ZIP SHA256为`3112331344df7dcf2dcef2ff5f789669c0419e32cefbbc6e2742b9e36d5c43c9`。

用户给出的官方集合冻结标识为`de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。没有取得此集合哈希的计算配方，因此本轮核对的是逐文件哈希，未声称重算该聚合值。

旧包中344项运行摘要、计划及多数相关产物可读；661个存在的带哈希文件匹配。但旧索引指向的295个完整`result.json`不在ZIP内：123项问题2、93项问题3、69项单核、10项问题1。缺少完整JSON不等于运行失败，也不能用摘要补造完整Trace。逐路径缺口见`new_evidence/archived_runs_integrity.json`。

旧100-case扫描、100项四核B与问题3对照、76项单核等统计属于本轮重新读到的存档摘要，并未全体重跑。本轮重跑旧10个微型探针：7个接受结果JSON值与存档一致，3个预期拒绝的环诊断一致。

### 1.2 增量资料不能承担的结论

FORM 9d660ff的36条probe标签是成员自测；2条为团队规范。六机制covered仅代表微图，且包含人工view/link的unit测试。队首越过、logical_tid实际命中等原有缺口不能因为读到规则卡而变成已验证。本轮新增端到端夹具独立补了这两种代表性行为，范围仍是特定图。

E1的零差分/3倍、E2的10倍E1/中位1%/P95 3%全部是目标，未有本轮性能证明。

### 1.3 必须更正的假设

- 原图DAG、商图DAG、展开执行图DAG是三个不同条件。
- **每一块都是偏序凸集也不够保证整体商图DAG**：两条独立边a1→b1、b2→a2，合并A={a1,a2}、B={b1,b2}，每块内部凸性不违反，但商图A↔B。
- 无SPILL不等于无memory reuse边：先后分配会耗尽VIRGIN额度，之后复用释放额度也能引入WAR/WAW边。
- 官方“最远未来使用”是固定策略；变量大小/代价情形不能继承等大小分页的Belady最优性。容量4，驻留A大小3/B大小1，新C大小2，A比B更早再用：先逐出B再逐出A需以后重读4，逐出A即可、以后只重读3（C当前使用后释放）。此为反对一般最优性推论的抽象反例，不是改官方策略的许可。
- 固定任务、固定场景追加空核可保留原方案。不能用“一条链/一核”与“两条链/两核”对照证明最优值随核数增加变坏。
- 子图编号和原节点ID有编译顺序含义。抽象商图重标号不保证官方输出不变。
- 全局DDR/Cache耦合意味着移动一个子图可能改变所有核心时序。
- 源码问题3的retire对完成的COPY_IN调用insert_cache，而不只在miss分支调用。若命中搬运期间条目被淘汰，完成时可能重新插入。题面/说明“miss完成插入”的摘要不足以排除这一实现分支。此分支本轮是源码观察，未单独端到端构造命中期间淘汰夹具。

## 2. 精确对象与代理对象

令x表示可控的分区P、核心归属a、每核子图顺序π，κ表示固定配置。固定版本编译器与模拟器分开：

\[
\Phi_q(G,x;\kappa,\mathrm{IDs})=(H_x,\mathcal Q_x,\mathcal M_x,\mathcal S_0),\qquad
T_q(x)=\operatorname{Sim}_q(\Phi_q(G,x;\kappa,\mathrm{IDs})).\tag{M1}
\]

不能输出任意开始时间、额外等待、预取或重算。算法只输出原格式的`node_to_subgraph`和`core_schedules`。

### 2.1 矩阵

定义两个稀疏0/1矩阵，行是tensor，列是op：

\[
B^{p}_{t,o}=\mathbf1[o\to t],\quad
B^{c}_{t,o}=\mathbf1[t\to o],\quad
A=\mathbf1[(B^c)^\top B^p>0].\tag{M2}
\]

A的行是后继op、列是前驱op。对COPY路径按官方口径收缩得到计算操作邻接A0；不能简单删除COPY节点并丢掉经过它的路径。X的行是计算op、列是sgid，每行一个1，则商图为：

\[
Q=\mathbf1[X^\top A_0X>0],\qquad\operatorname{diag}(Q)=0.\tag{M3}
\]

这里只描述商图。不要把它误当展开执行图或仿真时间模型。

展开H包含数据边、局部memory reuse边、每条Pipe的固定FIFO相邻边、跨核COPY边；问题1另含Task完成/激活与顺序约束。动态状态含各Pipe队首、运行操作、带宽池剩余工作、跨核释放、Cache有序内容及同刻处理顺序。

五核时全局同时在途COPY至多10条，因为每核仅一条MTE2和一条MTE3在飞；两个带宽池的在途总数也受此限制。该小活跃集不等于整个状态低维：Cache和待执行图仍可很大。

### 2.2 通信代理何时准确

对于单生产者、非最终输出的中间tensor，场景B的编译前SPILL跨核COPY字节数可以按核心去重：

\[
D_{t,B}=2s_t\,\left|\{a(v):v\in\mathrm{cons}(t)\}\setminus\{a(\mathrm{prod}(t))\}\right|.\tag{M4}
\]

这是当前逐(src,dst)建COPY对的实现性质。输入则按消费者核心去重读取；最终输出另算。两核切分时，中间tensor的这部分代价是all-or-nothing超边割。M4本身适用于上述条件下的多核去重计数，但推广到多块不能把二分all-or-nothing目标原样相加；问题1、SPILL以及问题3的实际DDR服务字节也不能直接套用M4。即使字节数精确，仍不是Makespan。

无向谱代理可取顶点–超边关联H及标准归一化超图Laplacian：

\[
L=I-D_v^{-1/2}HWD_e^{-1}H^\top D_v^{-1/2}.\tag{M5}
\]

H行是操作/宏块、列是共享tensor net；W为net权重，De为net基数，Dv为顶点加权度。L8的目标是归一化割，不是M4；它消失了生产/消费方向、同步、时序、FIFO、Cache状态。因此只保留作种子。实际乘法按H、H转置两次稀疏扫描完成，不构造稠密HH转置。

## 3. 路线A：在理想集格上求参数最小割

### 3.1 观察与可证结构

理想集S的定义是：

\[
v\in S,\ u\leadsto v\quad\Longrightarrow\quad u\in S.\tag{M6}
\]

**命题A1（抽象分区）**：商图无环，当且仅当存在原图一个拓扑序，使每个分区块在此序中连续。

证明：商图拓扑排序后串接各块内部拓扑序，得到所需序；反方向上，块之间的依赖只向后，故无环。这是存在性结论。固定某一条拓扑序后只切连续片段，会限制可表示分区。对子图数值ID的重标号也未必保持官方编译性能。

因此可搜索一串嵌套理想集，差集构成有序块。和“随便聚类后修环”相比，合法性在构造时就成立。合法粗化可以沿当前商图拓扑序合并连续区间；更灵活的单次合并需检查更新后商图，不能并发地把若干单独可合并块一起合并而跳过复检。

### 3.2 精确可解的构造代理

对非负超边割权、固定一元偏好d和正工作权w，定义：

\[
F_\lambda(S)=\sum_t c_t\,\mathbf1[0<|e_t\cap S|<|e_t|]
+\sum_{v\in S}(d_v+\lambda w_v),\qquad S\in\mathcal I(G).\tag{M7}
\]

c可以由两核字节代价换算为独占带宽时间，但固定同步仍非可加字节代价。d可以取一个已冻结的关键路径/释放优先偏好，w取Cube/Vector工作的非负组合。只保留少量事先定义的资源方向，不把新参数再次扩张为大规模搜索。

**最小割网络**：用源侧表示S。原DAG边u→v加入逆向边v→u，容量M；每个net加入两个辅助点a、b，所有net内v加入v→a和b→v的容量M边，a→b容量c。一元项为正时连v→汇，为负时连源→v并补常数。M大于全部有限容量之和。可强制少量入/出锚点避免空解，但锚点也限制候选族。

证明：逆向无限边强制前驱闭包；net两侧都有点时a必须源侧、b必须汇侧，恰支付c；全在一侧则无需支付。故有限割精确等于M7加常数。此处精确的是M7，不是M1。

**非平凡性必须检查**：若没有入/出锚点且全部d为零，正价格时空集最优、负价格时全集最优，参数化本身不会神奇地产生好切分。初版可选关键依赖链上一前一后的操作为强制入/出锚点，并使用随剩余关键路径变化的固定一元偏好；锚点须先检查闭包一致性。一个可实施的启发式是用正的Cube/Vector混合工作量作w，令d为负的“w乘归一化剩余关键路径优先度”。这给出可计算候选，而不是其Makespan最优性证明。跨不同锚点或一元偏好时，嵌套性只分别适用于各自固定的参数族。

**命题A2（嵌套性）**：价格增加时最优理想集缩小。

\[
\lambda_1<\lambda_2,\ A\in\arg\min F_{\lambda_1},\ B\in\arg\min F_{\lambda_2}
\quad\Longrightarrow\quad B\subseteq A.\tag{M8}
\]

证明：理想集对交并封闭，非负all-or-nothing割函数子模。把A与A并B、B与A交B分别比较，最优性和子模性给出：

\[
(\lambda_2-\lambda_1)\sum_{v\in B\setminus A}w_v\le0.\tag{M9}
\]

正权推出结论。相同价格的并列需固定取最小源侧等确定性规则。不同价格的主节点集合至多经过节点数加1次变化。这是参数最大流能压缩候选族的原因，不是“能达到每一个目标负载”。强耦合net会造成大跳跃，精确平衡仍可能不在该族中。

### 3.3 可实现步骤

```text
IDEAL-CUT-CANDIDATES(G, incumbent, budget):
    Build eligible DAG and tensor nets without clique expansion
    Choose a small frozen set of resource-price directions / anchors
    For each direction:
        Sweep or adaptively bracket lambda; reuse residual graph when correct
        Get minimal source-side min-cuts; deduplicate primary-node sets
        Keep a few useful load/communication breakpoints
        Recursively split selected blocks using ideals of the residual DAG
        Form ordered blocks and select core assignment
        Emit original-format plan; compile through official semantics
        Check quotient and full execution graph; reject/repair failures
        Evaluate a diverse shortlist under E0; update incumbent
    Stop before reserved E0-confirmation budget is exhausted
```

网络节点数为原节点加两倍net数，边数为依赖边加两倍pin数等线性项。令其为Vf/Ef、查询数L，初版重复Dinic最坏：

\[
O(LV_f^2E_f)\ \text{时间},\qquad O(V_f+E_f)\ \text{空间}.\tag{M10}
\]

不要把本轮小图Python Dinic当大型生产实现；可用C++邻接数组/复用网络。L4的完整参数算法不是当前原型已实现能力。做参数残量复用时，M须在整个有界价格区间内固定。可为每个一元项增加一个足够大的常数偏置：源→v的容量固定为Kv，v→汇的容量为Kv+d_v+λw_v，令全部容量非负；割值只多一个常数。参数换号后满足源/汇单调条件。不能一边改变内部M或锚点、一边冒称同一参数网络。

**强可执行特例**：使用单调核心归属，每条计算依赖的核心编号不下降，每个非空核一个子图。局部编译成功时，全部跨核边只向更大核心号，局部memory/FIFO边不跨核心，故全局执行图不会出现跨核环。任一路径的跨核边数至多核数减1。该特例非常适合做安全候选，但不允许跨阶段返回原核心，可能损失复用/并行优势。

一般阶段块可重复使用核心，按统一块序输出`core_schedules`只能保证计划层顺序；仍须检查展开H。`node_to_subgraph`必须覆盖所有非COPY且恰好一次，sgid只出现于一条核心列表。

### 3.4 适用、否定与实验

适合：存在少量瓶颈接口、同步层次重要、简单聚类频繁成环、普通负载均衡破坏共享输入。三问都可作为候选生成，问题1用Task代价，B用核心复用域。

击穿它：同一个大共享输入连所有分支，使参数割从空跳到整块；或最优方案需要前后阶段回到同核，单调核心构造过度限制。低cut也可能造成单Pipe瓶颈。

最小实验：固定配置生成链、fork–join、两阶段共享输入三族；比较无方向net-cut+修环、固定拓扑连续切、理想集参数切三种相同预算构造。观察完整合法率、候选数、E0次数、生成/编译/评估时间、Makespan、重复输入与同步关键路径。参数割如果只减少非法候选却在相同端到端预算下持续丢失最优池候选，应降为安全初始解而非主方法。

本轮数学核验：240个随机DAG、每图5价格、1200次对照穷举理想集，0差异；不包含官方性能验证。

## 4. 路线B：重复分支计数与窄张量边界动态规划

### 4.1 从节点选择到类型数量

先通过操作类型、Pipe、cycles、张量大小/位置、内外接口、阶段位置的签名识别候选重复区域，再作结构校验。哈希相同不是同构证明；外部消费者关系相同才有机会互换。

m个真正可交换分支分到N核时，考虑有标号核心上的数量：

\[
(n_1,\ldots,n_N),\quad\sum_kn_k=m;\qquad
N^m\ \longrightarrow\ {m+N-1\choose N-1}.\tag{M11}
\]

计数组合仍可能很大，不能对几千分支暴力枚举全部组合。只扫描接近资源平衡的数量范围，或按类型做DP；正式复杂度取实际状态数，不称“常数维所以免费”。

**严格等价的充分条件**：两种分配有同一类型计数，且存在展开操作/张量的双射，保持Pipe FIFO位置、计算/COPY工作、数据与memory边、Cache-key相等关系、核心编号和同刻事件优先关系，并保持初始状态，则事件递推逐步相同，Makespan相同。证明对每次settle/retire/issue/advance归纳即可。

原图对称不充分，因为固定ID和全局生成ID、Cache身份关系可能破坏上述双射。不满足时只作为构造代理；为同一计数保留少数不同的原ID实现，不修改原图ID。

本轮官方Q2微图：5条独立、等长、私有输入/输出的COPY_IN–RELU–COPY_OUT链，2核每核一个子图，枚举32种赋值；相同计数组结果一致，按core0分支数0…5为502、403、303、303、403、502cycles。另一个相同局部操作标签但外部接口不同的两分支反例，相同数量交换后823变1326。两者同样重要：计数化有特例，也确实会因漏外部接口而失效。

### 4.2 窄边界DP具体状态

固定一个合法参考拓扑序σ，处理其前缀。frontier保留已引入而仍与未处理操作有关的tensor。输入无计算producer时另设标志。核心位掩码只需N个位。

\[
\mathcal Z_j=\bigl((p_t,C_t)_{t\in F_j},\ (L^M_k,L^V_k)_{k=1}^N,\ D_j\bigr).\tag{M12}
\]

p是已分配producer的核心，C是已出现消费者核心集合；L为两类Pipe累计工作量，D为已经结算的编译前COPY代理成本。D是每个状态键保存的最优标签代价，不作为额外穷举维度。处理下一个操作时，枚举其核心，更新输入net的首次消费核心bit和新输出producer；只在第一次跨到某个核心时增加相应通信；tensor在末次涉及后从状态中忘掉。

这里每次引入/忘记的边界必须包括**共享输入**，不能只看计算DAG弱连通分量。根据M4可精确累计场景B、单生产者、无SPILL前的相关COPY字节分量。这个DP精确解决的是固定序/构造族上的通信与Pipe负载代理，而非完整官方时序。

一个保守状态上界（单生产者，整数负载，不作量化）是：

\[
H\le((N+1)2^N)^b(U_M+1)^N(U_V+1)^N,\tag{M13}
\]

b为最大frontier tensor数，U为负载总量。它是伪多项式/指数宽度的界，显示何时应该停用，而不是保证大图必快。以实际保留状态H、单操作涉及tensor数d计算，转换成本可写为：

\[
O(nNH(b+d+N)),\qquad O(H(b+N))\text{滚动状态空间，另加回溯存储}.\tag{M14}
\]

上述时间为数组状态复制/哈希键比较的平均字长模型；完整回溯表最坏另需O(nH)个父指针，正式实现可用检查点重算控制内存，并把重算计时。相同精确接口和相同负载向量下，只保留最小D是该代理上的安全剪枝。负载/字节量化或beam cap会丢状态，只能称启发式。对于有L2的真实系统，“负载更少、完成更早”的标量支配不保证后续更好，Cache序列可不同。

### 4.3 构造和原格式输出

```text
COUNT-FRONTIER(G, region, fixed_context):
    Detect verified types; keep identity-sensitive branches separate
    Choose a small set of legal reference orders
    For each order:
        Run exact frontier DP while width/state budget permits
        For large repeated groups use count transitions, not per-node permutations
        Retain interface-distinct and load/traffic-distinct terminal states
        Recover concrete original op IDs; do not rename source graph
        Use singleton subgraphs or safe topological-interval groups
        Project a common block order to each core
        Compile, globally validate, then E0-confirm the shortlist
```

两阶段重复分支优先让同一输入的前后消费者同核，但分成不同阶段子图；中间归约树保持原运算和原依赖，不能重新结合算术。任意核心赋值即使配统一拓扑投影，也不能跳过展开图检查。若某状态反复生成执行环，回退到路线A的单调核心或小范围顺序修复。

### 4.4 何时值得、何时停止

适合：大量重复分支；真正少量跨区域张量；强共享输入但接口可分组；有短阶段和可计数批次。对问题1必须同时决定批次数量，避免每条小分支一个Task造成同步层次过多；问题2重点是跨阶段数据归属；问题3保留Cache访问身份和时序多样性。

停用：frontier爆炸、共享tensor贯穿全图、状态数远超预算、原ID实现差异明显、局部最优与外部干扰高度耦合。

最小实验：重复分支数量按小到大递增，先穷举小m验证计数分组；逐项加入异质分支、跨区域消费者、两阶段复用、容量临界输入、ID并列，测压缩率/生成时间/池最优遗憾。正式实例从旧存档显示“整体分量法好”和“拆分法好”的双方各选代表，不能只选case_051这种受益例。

L6的dominant-profile线性化保持peak memory而不保持本题时间；L7的小树宽FPTAS允许容量放宽，不能继承。2025年的L9可提供SPILL重时的分组/释放优先种子，但其忽略树处理临时内存的gain必须补本题alloc瞬态检查。上述文献是限定条件下的工具，而不是新的并列主算法清单。

## 5. 路线C：固定时延端口消元与FIFO定向修复

### 5.1 对象先编译再压缩

每个操作拆成开始/完成事件；计算时长、固定同步和已编译的数据/FIFO/memory边成为固定时延边。COPY的服务时长仍由动态池决定，不能固定。

保留全部动态COPY开始/完成、Cache查询/插入、外部交互以及Task门控为端口B；只消去没有动态资源副作用的内部事件I。所有依赖边都必须进入压缩模型，不能遗漏memory reuse。

令A的行是目标事件、列是源事件；元素是固定时延，缺边为负无穷。max-plus中加法取max、乘法取普通加法：

\[
x=A\otimes x\oplus b,\qquad
A^*=I\oplus A\oplus\cdots\oplus A^{r-1}.\tag{M15}
\]

DAG使闭包有限。增加零时刻常数端口容纳初始释放。按B/I分块，消去内部节点得到：

\[
K=A_{BB}\oplus A_{BI}\otimes A_{II}^{*}\otimes A_{IB}.\tag{M16}
\]

**命题C1**：固定整数时延DAG、内部无额外外源释放/动态状态时，M16对任意给定端口释放向量保持全部端口最早时刻。

证明：每条端口到端口、内部经过I的路径贡献其边权和；闭包取全部此类路径最大值。代入内部最早事件方程与路径枚举一致。也可逐点消元，对所有前驱u/后继v加入权重(u,i)+(i,v)的边，与现有边取max。

它不是普通Schur补：普通加减乘逆求和响应，不能替代“所有前驱都完成”对应的max操作。无向Laplacian消元保留的是另一类算子，不是事件到达时刻。

**命题C2（限定支配）**：固定端口意义、固定非动态单调后续网络中，如果两个内部实现的响应矩阵逐项有K1≤K2，则对任意同一输入释放，K1不会产生更晚的端口输出。故可按矩阵支配删掉劣模式。涉及动态Cache/抢占带宽改变时，此支配不能直接升级为原题的安全剪枝。

### 5.2 算法与成本

```text
PORT-COMPILE-AND-REPAIR(plan):
    H = official_compile(plan)
    Validate all data/memory/FIFO/cross edges globally
    Retain every event that interacts with dynamic pools/cache/task control
    Identify fixed-lag interiors with few boundary ports
    Eliminate interiors, stopping when fill-in exceeds a preset budget
    Use integer max-plus responses to propagate fixed events
    Keep the official DDR/Cache transition order in the remaining simulator
    From baseline trace/critical FIFO edges identify a small order window
    Generate only legal block swaps/splits or a consumer-owner change
    Recompile affected structure; globally re-evaluate survivors
```

一个区域有r节点/e边/b端口，可用每端口一次DAG最长路预处理，成本约b(r+e)，响应矩阵空间最多b平方。一般消元会fill-in，不应无条件形成全图稠密闭包。大量COPY或接口过宽时直接保留原稀疏图。

**数值边界**：固定整数部分的等价不等于E1零差分。官方binary64剩余带宽工作会在每个事件点结算；跳过中间计算完成事件可能改变浮点运算分组，从而改变ceil阈值。必须保持这些语义事件的结算效果，或者把该压缩先限定为E2/筛选器，再做独立零差分验收。完整Trace也需要一致重建；不能用快引擎Makespan拼旧Trace。

### 5.2a 共享带宽的虚拟服务时钟（可选数学内核，未实现）

对单个等分带宽池，把剩余正工作量请求数记为n_pos。在实数流体模型中定义：

\[
V(t)=\int_0^t \frac{\mathbf1[n_{\mathrm{pos}}(u)>0]}{\max(1,n_{\mathrm{pos}}(u))}\,du,
\qquad f_i=V(a_i)+w_i.\tag{M21}
\]

这里wi是官方独占带宽参考周期（先按官方方式取整），不是未经取整的字节/带宽。请求i在虚拟时钟到达fi时服务完成。因为所有正剩余请求的工作量以同一速率下降，剩余量可表示为fi减V；用一个时钟和各请求固定虚拟截止值替代每次对全部请求扣减。下一虚拟完成与下一个外部到达/计算事件取较早者。

证明是对相邻到达/完成区间积分；其中并发数恒定，所减服务恰为时段长度除以并发数。该坐标变换仍保留全局耦合，绝不等于对不同核心分别计算。

**两个边界**：连续服务完成和官方整数cycle的retire不是同一件事；正工作量已为零而尚未在整数刻retire的项不能继续分走服务。epsilon、ceil、同刻Cache处理及binary64分组也必须另外一致。因此这只是待实现/待差分检验的数学内核，不是已达成的E1。池内至多10项，实际用小数组而非堆可能更快，不能用渐近复杂度代替测量。

### 5.3 如何变成实际求解改进，而非只有加速器

对当前有效计划的Trace，识别Pipe空闲但队首未就绪、队首后已有独立工作、额外memory边阻塞、跨核COPY串联等情况。把关键边反映射回可控制的sgid顺序/分组/核心归属。只在小窗口内比较合法顺序，保持图运算不变。

本轮新夹具：core1上的M计算D在12结束，独立V计算C此时数据已齐，但V队首B等待远端数据。原顺序B→C使C到609才开始；调整两个独立子图顺序后C从12开始。问题2和3均1410→818，全部搬运统计相同，且没有增加/删除原操作。

该实验否定“同Pipe串行就足以建模”而支持显式FIFO等待分析；它不证明任意把就绪工作前移都更好，因为前移也可能推迟真正关键的COPY/计算。

### 5.4 失效范围与反例

移动一个子图可能改变边界生成ID、源/目标COPY个数、Step1并列、SPILL和额度来源，编译变化不保证只在两个核。然后PS会改变全体在途完成时间、Q3又改变Cache插入顺序，最终可传播全图。

可以缓存的：完全相同输入上下文、原/生成ID规则、顺序和边界的局部编译；固定H上纯固定时延响应；同一计划完整评估结果。

可以精确拼接后缀的充分条件：在某一切点，完整离散状态、剩余工作、浮点池状态、FIFO Cache有序内容、未来队列和映射完全相同。仅“两个核都空闲”或“剩余工作相等”不够。

失败环提供修复方向而非任意删除依赖的许可。整计划nogood安全；把环缩成几个分配文字再永久禁用，需要证明那些文字足以强制相同编译边。memory/生成ID的上下文依赖可能使这种泛化错误。

本轮端口数学核验：300个固定整数DAG×8释放向量，2400次端口比较0差异；没有模拟器加速测量或binary64零差分结论。

## 6. 下界、正式预算与近似筛选

原问题有效下界优先取忽略限制后的资源/依赖下界。计算时长按源码最少1cycle；Q3必需DDR流量应只放可证明必需部分，不能使用当前计划的SPILL/重复读取作为全局必需量。

更强的头尾窗口下界：h为忽略通信的最长前置计算时间，q为不含自身的最长后续计算时间。对于某Pipe的非空集合U，所有其成员的h≥α、q≥β，则：

\[
T^*\ge \alpha+\beta+\frac{1}{N}\sum_{v\in U}c_v.\tag{M17}
\]

证明：这些操作只能在[α,T−β]中完成，该窗口至多提供N条同类Pipe的工作容量。可以扫描有限阈值给证书；不必遍历全部阈值以保持下界合法，只会影响紧度。

当前合法解与原问题下界的证书为：

\[
0\le\frac{T_{\rm inc}-T^*}{T^*}\le\frac{T_{\rm inc}}{LB}-1.\tag{M18}
\]

若LB只针对固定候选/编译图，证书也只针对该候选或已证明的候选族，不能用于全局最优声明。代理DP的最优值不是自动下界。

只有E0时：先预估每例真实编译/评价成本，保留合法incumbent，仅将几个机制不同的终点计划送E0。不能默认每次需要64个正式评估：64是E2候选池验收要求，不是数学探针/最终求解器的物理要求。

E1验收后：用于准确候选比较/接口检查，但论文正式值仍按团队要求E0确认。E2验收后：用估计筛选，保留各结构路线代表、风险样本和随机审计。总体中位/P95误差不是逐样本上界；未经证明的代理不得硬剪掉所有非top预测候选。监控短名单遗憾、接近最优池候选覆盖和最坏子域，不只测平均误差。

所有构图、分型、DP、最大流、内部评估、GPU传输、回退、选择和确认时间均计入5–10分钟端到端预算。无高速引擎时先发展构造，不等待E1/E2的目标实现。

## 7. 数学结构与主机硬件共同设计

已知：三台游戏本和一台Mac；本轮CPU环境为Linux/x86_64、Python3.13.5、Intel Xeon Platinum8272CL，5个可见逻辑CPU。未查询本队GPU型号/VRAM/驱动；未确定Mac具体M5型号、GPU核数、macOS/Xcode版本；未跑GPU测试。

官方资料确认当前CUDA文档与Metal M5能力表，但不能由此推算用户设备。M5对应Apple10、支持表列Metal3/4；64位整数不等于原生FP64。稳妥路径是整数max-plus/计数/bitmask在GPU可选，binary64事件池先保留CPU。

### 7.1 数据布局

- CPU：紧凑CSR/CSC或双向邻接数组；原ID与稠密index分开；op属性SoA；核心标签/最多5位消费者mask；时刻64位整数；剩余池工作binary64；稳定明确的并列序。
- 多候选：共享只读图与结构预处理，候选差异以标签、分桶顺序、计数参数保存；计划相关的重新构图仍计时。
- GPU：同一个压缩拓扑的候选成批，候选作为连续维度，便于coalescing；按同类型/相近大小分组，减少分支发散。层内frontier状态转换并行，层间同步不能省略。
- 不使用Tensor Core/Neural Accelerator的普通GEMM替代max-plus。log-sum-exp近似既改变目标又有舍入风险，不作为精确构造。

### 7.2 值得与不值得上GPU的部分

| 内核 | CPU竞争基线 | CUDA/Metal判断 |
|---|---|---|
| 超图incidence乘、许多候选的掩码/负载归约 | 向量化稀疏扫描、多核候选并行 | 批大、图驻留时值得试 |
| 小而规则的DP层/整数max-plus响应 | SIMD及cache-resident数组 | 同形大批更适合；单例很小常不值得 |
| 一次不规则最大流 | C++残量网络、复用网络 | 分支/不规则访存较重，不预定GPU更快 |
| 官方Step1/Step2/虚拟额度 | 紧凑数组、事件/未来使用索引 | 依赖、稳定并列多，CPU优先 |
| 单候选的动态DDR/Cache事件循环 | 至多10在途COPY的小数组 | 活跃并行太少；GPU每事件launch尤其不合算 |
| 大量独立完整候选模拟 | CPU多进程/线程批处理 | 开发吞吐实验可做，不能代替单例速度证明 |

### 7.3 可测成本模型

对同一图的K个新候选：

\[
T_{CPU}=P_C+Kc_C,\quad
T_{GPU}=P_G+L_{launch}+\frac{D_{transfer}}{B_{link}}+Kc_G+T_{sync}.\tag{M19}
\]

只有cC大于cG且固定/传输开销能摊销时才可能盈利。若把固定差额记为F：

\[
K>\frac{F}{c_C-c_G}.\tag{M20}
\]

示例仅用于实验设计：CPU每候选80微秒、GPU10微秒、附加固定200微秒时，至少3个候选才可能盈亏平衡；这些数字没有实测。真实P、传输、批次、E0确认成本可能改变结论。Mac统一内存不等于零同步或零带宽竞争。

必须分别测批量1/16/64/256、冷/热、kernel/完整CLI、候选吞吐/最终单例。最终只有几个结构候选时，数学压缩本身可能让GPU失去价值，这是成功而不是失败。

### 7.4 精度与回退

整数max-plus使用检查溢出的64位整数与安全负无穷哨兵；不要让FP32承载所有整数时间戳。浮点池严格保持顺序、epsilon、ceil和同刻事件规则，禁止为快而重排归约或打开改变语义的fast-math。CUDA可查询实际double能力/吞吐；Metal不以FP64为默认前提。

无GPU、SDK不匹配、内存不足、batch太小、图过窄、精度风险或加速未覆盖完整成本时，都使用CPU。E1零差分门槛不因“数学上实数等价”而降低。

## 8. 优先研究卡

### CARD-A：理想集最小割
- 目标：减少非法分区和昂贵候选，获得有方向约束的切分族。
- 已有：1200个代理子问题核验；无正式case收益。
- 下一证据：固定预算下与无向切+修环/连续拓扑切比较；确认参数跳跃、负载失衡反例。
- 停止条件：候选族持续排除好的均衡方案且无端到端收益；保留安全初始解即可。

### CARD-B：计数与frontier
- 目标：重复块不再逐节点搜索；局部只记对未来有影响的张量接口。
- 已有：5分支32赋值按数量一致；接口不同的823/1326反例。
- 下一证据：原ID并列、两阶段复用、输入大小和frontier宽度扫掠；测实际压缩/遗憾/时间。
- 停止条件：状态爆炸或身份效应强；退回类型启发式，不称严格商状态。

### CARD-C：端口消元与FIFO顺序
- 目标：减少固定计算事件；从等待链定位真正有价值的少量顺序修复。
- 已有：2400个整数端口核验；官方微图1410/818；logical spill实际hit3490/2670。
- 下一证据：不同端口比率/fill-in下的E0数值与完整成本；同刻/ceil/命中期间淘汰反例。
- 停止条件：浮点零差分不成立则仅作为E2；端口过密/成本不划算则保留CPU全事件。

## 9. 复现与来源

原题页码：第3–4页控制对象/指标，第5–6页问题与预算，第12–14页展开、同步、共享池和Cache。注意附带Markdown有旧题编号等不一致，代码行为不自动升级为题面要求。

本轮源码定位、实验环境、结果文件和缺口列表见`EVIDENCE_INDEX.md`与`new_evidence/`。外部文献完整作者、年份、出处、读取范围、适用限制与链接见`LITERATURE.md`。

本文件中的算法构造和证明为本轮推导，尚未经过另一独立研究会话的证明审查；尤其参数价格选择、计数代理外推与端口引擎数值实现，需要各自证伪实验。没有完整新求解器、没有GPU成绩、没有新100-case提升结论。
