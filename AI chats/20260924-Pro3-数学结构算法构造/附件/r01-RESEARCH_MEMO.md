# 华为杯 A 题第三路研究备忘：编译后的行为商，而不是原图上的盲目对称

**日期：2026-09-23。状态：数学构造与工程研究方案；未做官方 E0 验证。**

固定阅读包提交：`9d660ffc4af9ee7d23a31a7845b81ba7f17203b9`。官方代码冻结哈希由用户提供为 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`，本次没有获得源码字节，未独立验证这个哈希。

## 0. 主判断与证据边界

本题最值得投入的代数路线，不是把原图中长得相似的分支直接当成等价，而是：

> 先让官方编译过程决定真正的操作、顺序、内存依赖和资源访问；再把对未来资源行为不可见的内部细节消掉，搜索合法方案的行为等价类。

建议保留三个机制，按照“综合收益潜力／实现和验证成本”排序：

| 顺位 | 机制 | 真正减少的东西 | 适用性与主要风险 |
|---|---|---|---|
| 1 | 编译后固定时长子图的 max-plus 消元、带守卫的接口等价 | 重复内部事件、重复编译结果、可替换模块的细节维度 | 三问均有潜力；要求资源接口稀疏，且官方时序能写成完整约束 |
| 2 | 合法分区语法、闭合 Task 的 min-plus 分段、失败证书定向修复 | 非法分区、指数切分词的特例、无方向的候选生成 | 直接构造方案；Q1 特例最清楚，通用多核扩展仍须 E0 排序 |
| 3 | 面向未来访问字母表的 FIFO 状态商，结合资源时钟和保守重放 | 缓存历史身份、等分服务的逐请求更新、重复后缀 | Q3 最有研究价值；全量 JSON 与内部评分等价必须分开 |

这个排序是研究判断，不是正式用例成绩。第一、三路主要买到更低的评估成本，不能仅凭评估加速宣称方案质量改善；第二路才直接提供候选构造。最终看相同 5–10 分钟内 E0 确认的最好值。

### 0.1 实际读取情况

已读取：本次两份完整 Markdown 补充，以及文末所列论文/官方硬件文档中的指定原文部分。

未读取：原题 PDF、官方原始代码/README/config 字节、正式 100 个 case、成员探针脚本与原始 JSON、其他两个并行会话全文。本次 `files.search` 和 `files.list` 只暴露两个附件；GitHub 指定提交文件读取与仓库元数据读取均返回 404。详细证据在 `access_manifest.json`。

因此本文不能独立断言三问的全部题面目标/评分、允许的核数范围，不能声称源码已审计、已跑官方样例或已复现成员结果。以下采用五层标识：

- **[材]**：成员阅读包报告的官方实现/观察，未经本次独立源码复核。
- **[规]**：团队研发规范，不是题面规律或已实现成绩。
- **[推]**：本文给出条件和证明的数学命题。
- **[检]**：本次数学模型有限检查，不是 E0。
- **[待]**：尚需官方源码、E0 或机器实测解决。

### 0.2 应纠正的旧假设

**原图 DAG、商图无环和官方执行图可执行是三道不同条件。** 同一节点集合上的拓扑等价远远不够。

**“加核变慢”的现有一项成员证据不构成同实例反例。** 阅读包 F-RESOURCE-001 与旧 §5 比较“一条链一核 24”与“两条链两核 44”，同时改变了工作量。不能据此证明固定原图增加核数会变慢。原理上不保证单调的判断仍可以研究，但需保持原图、工作量和配置不变重新构造。

**局部变快不自动形成全局优势。** 更早释放一次非关键传输，可以夺走关键传输的带宽；FIFO 命中也可能改变之后的争用。因此不能把局部时间向量的分量优势当成通用 Pareto 剪枝。

**动态带宽没有否定所有代数加速。** 它否定的是“发射时锁死结束时间”等错误模型；在连续等分服务模型中，虚拟服务时钟确实能消去大量逐请求更新。但浮点与整数退休语义可能阻止它直接成为 E1。

**“少量未来活键”不意味着可以直接清空其他缓存。** 死条目在活条目后方所占的容量仍影响未来淘汰；只有经下文的规范化才能压缩。

**E1、E2 门槛都是目标。** E1 的零差分和 ≥3×、E2 的 ≥10× E1 与误差门槛均未在本次得到验证。见补充规范 §2–§5。

## 1. 数学对象与不允许越过的接口

### 1.1 原图、分区和核序

令原始图为有类型的图 \(G=(V_O\sqcup V_T,E)\)。不要强制把所有输入都当成纯二部图：阅读包还用过直接 op→op 的构造。合法输入边型最终须由 `validate_graph` 审计决定。

令 \(V\subseteq V_O\) 是排除原始 COPY_IN/COPY_OUT 后需要划分的算子。对 \(n=|V|\)、\(t=|V_T|\)，定义生产关联矩阵 \(U\in\{0,1\}^{n\times t}\)，消费关联矩阵 \(W\in\{0,1\}^{t\times n}\)。Boolean 乘积 \(UW\) 只表达“经某 tensor 有依赖”；还要按官方规则加入直接依赖及 COPY 收缩后的依赖，得到 \(D\)。

保留 tensor 的大小、位置、生产者和所有消费者。不能用 \(D\) 的一条加权边替代 tensor 超边，因为跨核 COPY 数量按核心对生成，且不同读取可能共享 cache key。[材：F-TASK-005]

分区用 \(Z\in\{0,1\}^{n\times m}\) 表示，每行恰一个 1。其商图邻接为

\[
Q=\operatorname{offdiag}(Z^\top D Z)\quad\text{（Boolean 运算）}.
\]

选手的全部控制量记作 \(P=(\pi,\kappa,\sigma)\)：算子→子图、子图→核心、每核子图序列。这只是两个官方字段的数学展开，**不是增加新接口**：

```json
{
  "node_to_subgraph": {"<eligible_op_id>": 0},
  "core_schedules": [[0], []]
}
```

实际输出必须覆盖所有 eligible op、所有子图恰调度一次，子图号非负整数；空核是否应保留按输入核数契约处理，不能把非空核数当成外层列表长度。[材：F-PLAN-001..006]

### 1.2 编译图与执行状态

以 \(\mathcal C_q(G,P,C)\) 表示官方固定编译：局部图构造 → Step1 → spill/rename → Step3。输出的展开图 \(X\) 含实际 COPY、静态内存复用边、Pipe FIFO 顺序、跨核连接和必要的任务门控。\(X\) 不等于原图或商图。[材：F-LOCAL、F-EXEC]

模拟状态的一个保守表示是

\[
s=(\tau,\;\text{每 Pipe 指针/在飞操作},\;\text{依赖与门控状态},\;
\text{各池剩余工作},\;\text{有序缓存与待插入},\;\text{并列规则状态}).
\]

生成 ID、`logical_tid`、FIFO 次序、稳定排序所依赖的顺序，都属于编译/状态契约。它们不能未经证明被“无名化”。

### 1.3 三问的已知联系，不冒充完整题面

| 项目 | Q1：阅读包场景 A | Q2：阅读包场景 B | Q3 |
|---|---|---|---|
| 选手控制 | 同一组分区/核归属/核序字段 | 同左 | 同左 |
| 编译组织 | 子图形成 Task，局部边界搬运 | 按核心构造执行内容及跨核心 COPY 对，完整细节待源码核对 | 继承场景 B，并增加缓存行为 |
| 同步 | 前一同核 Task 完成后等待；真正跨核前驱有另一个等待 | 不得直接套用 Q1 的两种 Task 等待公式 | 同步与缓存并存 |
| 动态资源 | 共享 DDR | 共享 DDR | DDR 与 CACHE_READ 两个独立共享池 |
| 主要风险 | 过细切分的固定开销、局部 spill | Pipe 顺序和跨核 COPY 组成等待环 | 同刻 miss/insert、FIFO 淘汰与争用耦合 |

Q1 的 100/1000、Q3 的 60/250 B/cycle 等只是阅读包对配置的报告，不硬编码进求解器；本次没有读取官方 config 字节。最终还须核对原题中各问的目标与报告指标，本文主要构造围绕 makespan 与合法性。[材：F-TIME-001、F-RESOURCE-001/003]

### 1.4 队首受阻的准确状态

成员给出 `pipe_ops` 固定 FIFO、每 Pipe 单槽，并报告验证器向执行图加入 Pipe 相邻边。但本批没有探针验证运行循环是否允许越过受阻队首；本次也未能读取实际运行循环。

因此不能写“本次确认绝不越过”。工程守卫必须是：核对运行循环读取队首后遇到未满足依赖时的分支，并用“同 Pipe 的后继已就绪、队首等待跨核输入”的输入隔离它。若实际允许越过，则将 FIFO 相邻边当作时序约束的模型必须相应调整；即使验证器使用该边，也不能从验证器自动推断执行循环行为。

## 2. 路线一：固定时长子图消元，构造编译后的行为等价类

### 2.1 出发点

[max,+] 适合表达固定依赖下的最早时刻，而不适合直接表达动态共享带宽。Baccelli 等的离散事件系统教材给出 dioid 上 \(x=ax\oplus b\) 的最小解 \(a^*b\)（Theorem 4.75）。这里不照搬其全部系统假设，而只使用有限 DAG 的路径展开，再把动态资源控制留在边界。[R1]

把每个操作拆成 start/finish 事件。固定时长操作给出边权 \(d\)；依赖给出 0 或固定等待边。使用

\[
a\oplus b=\max(a,b),\qquad a\otimes b=a+b,
\]

无边值为 \(-\infty\)，单位路径值为 0。

### 2.2 可检测的消元守卫

选择保留节点集 \(B\)，内部节点集 \(I\)。以下内容必须保留或完整反映为边界状态：

1. 所有共享池操作的 **start 和 finish**；所有 cache query、miss-completion insert 及相关次序。
2. Task start/end、跨核释放和同核等待门控，以及最终 makespan sink。
3. 所有从外部进入/离开消元块的数据、FIFO 和内存复用接口。
4. 任何运行时状态分支、资源分配行为或依赖“哪一个先被扫描”的事件。

只消去满足以下条件的内部事件：持续时间固定；除完成依赖外不写动态状态；所有次序已显式表示；官方在这里按约束许可的最早时刻执行。最后一项必须源码审计和 E0 检验，不能凭 DAG 自行假定。

这通常意味着优先压缩 M/V 上的固定计算段，而不是消掉 MTE 上的共享传输。接口维度不是固定的“四条 Pipe”：还包括跨段 tensor 的就绪时刻、门控等，必须实际数出来。

### 2.3 消元命题与证明

按 \((B,I)\) 分块，将固定事件递推写成

\[
x_I=A_{II}\otimes x_I\oplus A_{IB}\otimes x_B\oplus u_I.
\]

因为内部 DAG 无环，路径最多经过 \(|I|-1\) 条内部边，闭包为有限和。代入后得到

\[
A^{\mathrm{eff}}_{BB}
=A_{BB}\oplus A_{BI}\otimes A_{II}^*\otimes A_{IB}.
\]

源项同理处理，或加入一个固定时刻为 0 的虚拟源。

**[推：固定子图消元命题]** 在上述守卫下，对任意合法边界释放时刻，消元前后保留节点的最早时刻完全相同。

**证明。** 原图中相邻保留节点之间的每条路径，要么是原有边界边，要么内部节点全部属于 \(I\)。其最强约束就是这组路径权重的最大值。将所有这类路径换成对应的一条加权边，不删除任何约束，也不加入更强约束。沿保留图的拓扑序递推，逐节点相等。若与外部资源控制器交互，则按真实资源事件的因果顺序归纳：每一步收到相同释放、产生相同资源请求，在相同控制器状态和同刻规则下得到相同下一事件。□

注意这里比较的是实际确认的事件，不能把会被后续传输推迟的 projected completion 当作已经完成。

### 2.4 数据结构、算法与成本

用 CSR 邻接表示内部图，接口矩阵 \(H\in\mathbb{T}^{b_{out}\times b_{in}}\) 的 \(H_{o,i}\) 是输入端口 \(i\) 到输出端口 \(o\) 的最大内部路径权。不要先做稠密 \(n\times n\) 闭包。

```text
compress_fixed_region(X, I, B):
    assert all guards for this region
    for each input port s:
        dist := -infinity; dist[s] := 0
        traverse relevant vertices in topological order:
            if vertex is another retained boundary:
                record coefficient; do not cross it in this sweep
            else:
                relax successors with integer max-plus
    return sparse H, boundary bindings, guards, reconstruction witness
```

构建时间 \(O(b_{in}(|I|+|E_I|))\)，空间 \(O(|I|+|E_I|+b_{in}b_{out})\)。实际边界填充量若接近原图规模甚至更大，应停止压缩。

固定宽度 \(b\) 的模块串联具有结合律；可用线段树维护矩阵乘积，局部替换后的稠密更新成本 \(O(b^3\log r)\)，而非重合成 \(r\) 个模块。稀疏结构可能更好，但每次更新都须验证接口、排序、别名和生成 ID 相关守卫没有失效。若官方编译改变了更早模块，不能只更新一个叶子。

### 2.5 等价类与可执行重写

最保守的第一版是对编译 IR 做哈希：**保留 literal ID、core ID、所有 Pipe 队列、内存边、逻辑键、时长和同刻规则**。哈希只作索引，命中后仍比较语义完整的序列化内容；对可能影响迭代的映射，保留插入顺序和类型，而不盲目按键排序。确认相等后只复用内部评分结果，方案各自的元数据和最终 E0 输出仍独立生成。

第二版才允许如下重写：

\[
\text{模块 }M_1 \longleftrightarrow M_2
\]

守卫为：相同端口绑定、相同 \(H\)、相同资源/缓存事件及别名关系、相同外部可见 ID 比较结果，并且替换后重新编译仍满足这些条件。仅仅内部图同构或总 cycles 相同，不允许合并。

这不是对原始神经网络做计算语义等价变换；选手仍提交原图算子的不同合法分区/核序。重写作用于**求解器内部的候选表示与评分计算**。

`egg` 的条件重写和 e-class analysis 可用于管理规则；但其通常的局部代价 extraction 不能直接优化全局争用下的 makespan。[R4] 第一版应是带守卫的 hash-consing，而不是先建设完整 equality saturation 框架。

### 2.6 可用与不可用的支配关系

如果两种实现只影响资源已经封闭的固定时长后缀，且 \(H_1\le H_2\) 逐项成立，则在该纯 max-plus 上下文中第一种不慢。这可由 max 和加法的单调性证明。

在仍会访问共享资源的上下文中，这个支配规则失效。一个最小连续模型反例是：容量为 1 的共享服务池；关键请求 Y 工作量 1，完成后串行计算 100；另一个请求 X 工作量 2。Y 在 0 到达。

- X 在 0 到达：Y 在 2 完成，最终 makespan 102。
- X 在 1 到达：Y 在 1 完成，最终 makespan 101。

X 更早并未使全局更快。[检：Fraction 等分服务模型；不是官方微图。] 这里的释放时间差应通过合法的分区/核序诱发，不能当成选手可以插入 1 cycle 等待。

### 2.7 最小 E0 证伪实验

先在固定 plan 上检验消元，避免把“候选变了”和“评估器变了”混在一起。输入族包含：长计算链夹在两次 COPY 之间；M/V 菱形；高边界扇出；故意出现 MEMORY_REUSE；同刻 COPY 完成与新查询；队首受阻。

对照为原版 E0 与“官方编译结果 + 压缩评分”。观察全部保留事件时刻、makespan、缓存访问次序，必要时重建内部时间线。

**成功条件：** 先零未解释差异，再测压缩准备成本和 B=1/16/64/256 新候选耗时。消元开销必须被本单例内的重用抵消。

**否定条件：** 任一保留事件不同即推翻对应守卫；边界矩阵持续变稠密或重编译成本占主导即停用性能路径。内部评分等价不自动等于 full JSON 零差分。

## 3. 路线二：合法分区语法、闭合 Task 分段与证书定向修复

### 3.1 无环商图的精确结构

**[推：分块拓扑词命题]** 一个分区的商图无环，当且仅当存在原逻辑 DAG 的一个拓扑序，使每个分区块占据连续区间。

**证明。** 商图无环时，先拓扑排列各块，再在块内拓扑排列算子并拼接。跨块边全部前向，得到所需拓扑序。反向则由区间的先后给每条商图边一个严格递增的块序号，所以不可能有商图环。□

由此获得一个不产生商图环的候选语法：选择拓扑词，再选择区间切点。固定一个词只是合法方案的一个子族，不能宣称覆盖所有最优分区。Moreira–Popp–Schulz 的论文 §5.1 也以拓扑顺序和连续块构造无环分区；其目标是有向图分区的 cut/balance，不是本题的模拟 makespan。[R2]

**一个容易误用的条件：各块独立地“序凸”并不保证整个商图无环。** 原图只有 \(a\to b,c\to d\)，令 \(A=\{a,d\},B=\{b,c\}\)。两个块均不包含缺失的中间路径点，分别是序凸的；商图却有 \(A\to B\to A\)。[检：脚本包含此例。]

### 3.2 合法粗化与细化

**[推：单集合收缩命题]** 在当前无环商图上，合并一组节点 \(S\) 后仍无环，当且仅当不存在一条路径“从 \(S\) 出发、经过至少一个 \(S\) 外部节点、再返回 \(S\)”。

**证明。** 收缩后新出现的环必须经过新节点；展开它即得到上述离开—返回路径。反之，任何这样的路径在收缩后形成环。□

实现时，从 \(S\) 的所有出界邻居出发，只遍历外部节点，检查是否重新触达 \(S\)，成本 \(O(|Q|+|E_Q|)\)。也可对较小商图维护 reachability bitset；不要为大原图盲建稠密传递闭包。

该条件必须应用于**当前商图**，不能一次在原图上给所有待合并集合发“永远安全”证书。若一个块要细化，按其局部拓扑词切连续段，并检查细化后的整体商图；若沿已有全局分块拓扑词细化，则商图无环自动保持。

### 3.3 核序合法性仍不是展开图合法性

将每核 `core_schedules` 设为同一全局块拓扑序在该核上的限制，便能保证“商图依赖 + 核内相邻子图顺序”无环：每条边都沿同一全局序严格前向。

但这不保证官方 Step3 后可执行；生成的 COPY、内存复用边和 Pipe 次序还须检查。

一个需要 E0 验证的组合环家族：逻辑依赖 \(A\to B,C\to D\)，core0 排 \([B,C]\)，core1 排 \([D,A]\)。原商图无环，也没有被直接同核依赖对禁止的局部顺序，但加入两条核序边后出现 \(A\to B\to C\to D\to A\)。此处是结构推导，不声称本次用官方入口构造成功。

### 3.4 Q1 的闭合 Task 特例：指数切分变最短路

先给严格适用条件，而不是把常规切图 DP 冒充本题解法：

- 所有这些 Task 在一个核上顺序执行；没有其他核同时占用池。
- Task 边界没有会影响下个 Task 的缓存状态或其他未被接口说明的持久动态资源。
- 每个区间 \((i,j]\) 的局部展开及执行时间 \(d(i,j)\)，只由区间内容和固定边界契约决定，与外围分区、生成 ID 比较和 Task 编号等无关。
- 相邻 Task 之间仅有固定同核等待 \(w\)；所有逻辑依赖被所选拓扑词满足。

Q1 是值得验证这些条件的第一目标。第三条尤其需要审计：新 ID 全局分配不能未经证明被忽略。可以先用同一区间处于不同前后切分中的官方编译结果对抗测试，再对 ID 比较和边界构造逐项给出代码级理由；有限一致不能替代全域证明。

在条件成立时，任一切分 \(0=i_0<\cdots<i_k=n\) 的准确时间为

\[
T=\sum_{r=1}^{k}d(i_{r-1},i_r)+(k-1)w.
\]

构造顶点 \(0,\dots,n\) 的区间 DAG，边 \(i\to j\) 权为 \(d(i,j)+w\mathbf1_{i>0}\)。最短路递推

\[
F[0]=0,\qquad
F[j]=\min_{i<j}\{F[i]+d(i,j)+w\mathbf1_{i>0}\}.
\]

**[推]** 这精确求解“固定拓扑词、一核、上述闭合条件”的最优分区。证明是把最后一个区间剥离，成本可加即有最优子结构。内部 Task 可以包含复杂 spill 和带宽模拟，只要局部时间准确且上下文独立，不要求把每个 Task 简化成 cycles 求和。

```text
closed_task_partition(word, permitted_intervals):
    dp[0] = 0; other dp = infinity
    for right endpoint j in increasing order:
        for permitted edge (i,j):
            d = exact_profile_of_closed_interval(i,j)
            if interval is illegal: continue
            relax dp[j] from dp[i] + d + (w if i > 0 else 0)
    recover cuts from backpointers
    assign increasing subgraph IDs to intervals
    put all those IDs in one core's order; preserve required empty core entries
    validate and evaluate full output plan with E0
```

若限制区间最长 \(L\)，表规模 \(O(nL)\)，DP 时间 \(O(nL)\)，回溯空间 \(O(n)\)；局部画像时间为 \(O(nL\,c_{profile})\)，不能漏掉。这把选定词上的 \(2^{n-1}\) 切分枚举压成多项式数量的局部画像，但只对这个特例有效。

**预算修补。** 只有 E0 时，\(nL\) 次完整评估很可能不合算。选择有限的候选切点集合，或在若干已定义的宏块上做区间 DAG；把允许的区间数 \(M\) 限制到 \(M c_{profile}\) 不超过预算。此时只对这个更小的区间边集求最优，明确报告搜索范围。不要把未测的局部时间填成“精确时间”。

**失败条件。** 跨 Task 缓存/资源状态、跨核真实并发、局部编译上下文依赖、Q2/Q3 的跨子图合并执行，都可击穿可加性。此时 DP 可以当候选生成代理，不能当原问题下界或最优证明。

### 3.5 重复分支的计数化：一个真正可证的特例

对已固定的 Task 集合，如果它们相互独立、没有共享池/缓存作用、局部时长只取决于类型，且 ID/tie 变化不影响行为，则同类型的标签置换确实可以约掉。

\(m\) 个相同 Task、时长 \(d>0\)、\(K\) 核、同核相邻等待 \(w\ge0\)，令 \(q=\lceil m/K\rceil\)。最优值为

\[
q d+(q-1)w\qquad(m\ge1).
\]

至少有一个核承担 \(q\) 个 Task，给出下界；均衡计数分配达到它。无需搜索 \(K^m\) 个标签归属，只需计数并将真实 IDs 按固定规则填回。

若有 \(R\) 种类型，各有 \(m_r\) 个，核心有标签，计数分配空间至多为

\[
\prod_{r=1}^{R}\binom{m_r+K-1}{K-1},
\]

而不是 \(K^{\sum_r m_r}\)。它仍可能很大；没有满足资源隔离与 ID 守卫时，只能作为近似模板，不能压掉真实候选。共同读取同一 tensor 的“对称分支”，尤其不能直接使用本特例。

### 3.6 一般多核：合法语法 + 有方向的少量重写

一般输入没有上述可加性时，仍可保留两个确定收益：不浪费候选在商图环上；每次精确评估尽量针对明确机制。

建议完整构造器如下：

```text
seed_words = a few topological words generated from different structural priorities
candidate seeds = legal interval partitions / a verified incumbent
while remaining budget permits:
    choose a small edit region suggested by an execution witness
    propose split / legal current-quotient merge / core move / allowed core-order edit
    reject violations of exact mapping and scheduling coverage
    check quotient + chosen core-order constraints
    run official-compatible compilation and expanded execution check
    if rejected:
        learn only a sound guarded conflict; keep exact-plan failure otherwise
        continue
    compute compiled fingerprint; skip certified score duplicates
    prune only with a proved lower bound for this candidate/domain
    score with E0, or accepted E1 + scheduled E0 confirmations
    update incumbent only with an officially confirmed feasible improvement
return the best already confirmed plan
```

结构优先级可以选择关键依赖深度、固定等待暴露、tensor 活跃边界与源端 MTE3 扇出等；它们是少量不同拓扑词/编辑区域的**生成规则**，不是对 makespan 的充分统计量。对每条路线保留独立入口，避免同一代理把所有候选压成一种形状。

若保留 \(H\) 个词、\(M\) 个区间画像、最多 \(N\) 个候选，一份保守成本账是

\[
O(H(n+e)\log n)+M c_{profile}
+\sum_{a=1}^{N}(c_{compile,a}+c_{validate,a}+c_{score,a}).
\]

任何 \(O(nL)\) 的漂亮 DP 都不能掩盖画像/编译成本。内存保留 CSR 原图、当前小商图、有限画像缓存与有限候选；不保存全搜索空间。

### 3.7 从失败环提炼安全的禁配条件

将执行图边附上来源：原始数据、内存复用、Pipe FIFO、跨核 COPY、Task 门控。若一个环 \(C\) 的每条边都有足够条件 \(g_e(P)\) 保证其存在，则

\[
\bigvee_{e\in C}\neg g_e(P)
\]

是安全的禁配约束：若所有守卫同时成立，环仍存在，候选必不可行。

难点是“足够条件”。原始数据边容易给出；Step1 排序、内存边、新 ID 相关边可能依赖远处变化。不能只截取报错里的两个子图号便把它推广成永久禁配。若无法证明边生成的局部守卫，守卫退化为整个编译指纹，此时只缓存这个确切失败方案。

修复动作是改变产生这些边的合法决策，例如合并跨核端点、拆开导致冲突的块、改变可调核序；不是删除官方数据/内存依赖。`egglog` 的增量事实推理可管理已证明规则，但其半朴素迭代定理不自动处理方案编辑造成的事实删除。[R5]

### 3.8 可证明下界与证书的范围

在 eligible 原始算子 cycles 不变、每核每 Pipe 单槽等条件已审计后，一个安全的全局基础下界是

\[
LB_0=\max\left\{
\operatorname{CP}_{D}(d),\;
\max_p\frac{\sum_{v:\operatorname{pipe}(v)=p}d_v}{K}
\right\}.
\]

这里计算依赖链时忽略可变 COPY/等待/资源阻塞，只保留必须执行的固定计算，因此是乐观放松；每种 Pipe 的总计算量不可能被 \(K\) 个同类单槽在更短时间内完成。

对**已固定且成功编译的方案**，可进一步在执行图上给每个操作赋不超过其真实时长的乐观值，加上必需固定等待，再算最长路。Q3 为 cache-eligible COPY_IN 使用允许的最快读取时长，哪怕实际上无法全部命中，也只是放松。这个量是该候选的下界，不是未固定分区时的全局下界。

共享池总 bytes/bandwidth 常有物理直觉，但严格贴合官方还需审计 duration、是否实际搬运、取整和退休容差。当前先不把它作为无条件 E0 剪枝证书。也不把受限分段 DP 的最优值当成原问题下界：受限可行集合的精确最好值是原问题的**上界候选**，不是下界。

### 3.9 E0 实验设计

输入族：短链（所有切点穷举）、双分支汇合、同核 Task 闭合/不闭合对照、跨核心往返链、共享输入扇出，以及“各块序凸但商图成环”的四节点结构。

先测合法语法是否真的减少编译前拒绝，再测同一区间的局部编译是否上下文独立。对小图枚举合法计划集合，比较 DP 在其声明子族中是否达到 E0 最好值；不能拿子族最优替代所有计划最优。

消融：相同构造预算下，去掉合法收缩检查、去掉冲突学习、去掉 compiled-score 去重、换为只按搬运量的候选排序。观测 E0 可行率、不同编译指纹数、最终最好 makespan、完整成本。若只提高可行率却损失方案质量，应缩小语法限制或增加不同拓扑词，而不是庆祝“搜索空间更小”。

## 4. 路线三：未来可观测的 FIFO 状态商与等分服务时钟

### 4.1 不是把 FIFO 换成 LRU，也不是允许刷新缓存

成员报告：只有 COPY_IN 查缓存，命中不晋升；miss 完成后插入，已有键插入幂等，超容量单条不缓存；同刻退休插入可能影响随后查询。[材：F-RESOURCE-003..007、F-EXEC-003]

下面只压缩求解器内部表示，不改变官方缓存动作，也不允许选手插入 flush。

### 4.2 定义未来字母表

在某个已经编译并固定的剩余程序处，令 \(L\) 包含所有**将来可能查询或插入**的 logical key。尤其包括：

- 尚未发射的 COPY_IN 将使用的 logical key；
- 已发射 miss、尚未完成插入的 key；
- 可能由 spill/rename 引用的同一逻辑 key。

只有不在 \(L\) 的 resident key 才叫“死键”。不能仅按“没有未来读取”判死，因一个 pending insert 仍会测试 key 是否已存在，从而决定是否淘汰别人。\(L\) 应覆盖该固定剩余程序所有可能的资源交错，而不是只按一个预测时间线算。

### 4.3 规范化规则

设 FIFO 队列从最老到最新为 \(S\)。定义 \(N_L(S)\)：

1. 删除队首连续的死条目，即死前缀。
2. 其余活键按原顺序保留其身份和大小。
3. 活键之间及末尾的每段连续死条目，合为一个匿名 gap，记录**总字节数**。

例：

```text
[dead(4), a(2), dead(3), dead(5), b(1), dead(7)]
→ [a(2), gap(8), b(1), gap(7)]
```

若保留的活条目有 \(h\) 个，表示最多 \(h\) 个活键和 \(h\) 个 gap，大小 \(O(h)\)。当所有 resident key 都与未来无关，规范状态是空；真实缓存可以仍然装满旧条目，但对未来评分行为而言已经“空了”。

### 4.4 右同余命题与证明

用 \(\delta(S,a)\) 表示一次 FIFO 查询或插入，动作键来自 \(L\)，配置容量固定，键大小规则相同。查询只观察命中与否，不晋升；插入遵循幂等、超大跳过及从队首逐条淘汰。

**[推：未来字母表上的规范化同余]** 对上述动作，

\[
N_L(\delta(S,a))=N_L(\delta(N_L(S),a)),
\]

查询的 hit/miss 也相同。因此初始规范状态相同的两个缓存，对任意允许的未来动作词具有相同 hit/miss 序列。

**证明。** 查询 \(L\) 中的键只取决于活键是否驻留，规范化未改变它们。插入已有活键和超大条目在两边均不改变状态。考虑新活键插入：FIFO 淘汰的总是前缀。队首死条目所占字节与空闲字节对“下一个活键是否必须被淘汰”可互换；若原状态只淘汰了死前缀的一部分，剩下部分仍是死前缀，规范化会继续删掉。某个内部死 gap 被推进到队首时也同理：即使原状态停在这个死段中途，剩余部分在规范化时消失；若插入需要越过该段，那么是否还需淘汰下一个活键只取决于整段总字节。因此两边留下同一活键序列及活键之后的相同 gap 字节。对动作词长度归纳即得结论。□

这个命题给出一个**足够的行为商**，没有声称它是该输入的最小自动机。

若未来字母表缩小 \(L'\subseteq L\)，还有

\[
N_{L'}(N_L(S))=N_{L'}(S).
\]

于是可在剩余访问和待插入计数变为零后，逐步将更多身份匿名化。[检：5000 次随机缩小检查。]

### 4.5 两个必须保留的反例

**不能直接删除内部死条目。** 容量 2，\(S=[a(1),x_{dead}(1)]\)，插入 \(b(1)\)。官方 FIFO 淘汰 a；若先删 x，插入 b 不会淘汰 a。后续访问 a 的结果相反。

**不能忽略 pending insert。** 同样容量 2，\(S=[a(1),x(1)]\)，x 以后不再被读取，但有一次在飞 miss 完成后的 insert(x)。真实插入因 x 已驻留而幂等。若错误地把 x 匿名化，再执行 insert(x)，它会被误认为新键，可能淘汰 a。

这正是 `logical_tid`、在飞状态和同刻次序必须进入守卫的原因。阅读包只验证了 spill 重命名到 cache key 一层；本次的缓存定理不补造 Q3 命中观察。

### 4.6 数据结构与实际执行

可用双向链表交替存 live-entry 与 dead-gap，哈希表从活键映射链表节点。把一个活键判死时，与相邻 gap 合并；若到队首则删除死前缀。未来计数由已编译 COPY_IN 列表和 pending miss 表维护。不要在完成插入之前让其计数消失。

```text
on_query(key):
    use live-entry map to test membership
    keep official event order and select DDR/CACHE_READ accordingly
    if miss is issued: register pending insert before dropping its future-query count

on_miss_completion(key, size):
    execute official FIFO insert using live entries and byte gaps
    decrement pending-insert count
    if no possible future query/insert of key:
        anonymize resident key, merge neighboring gaps, drop dead prefix
```

单次链表操作为常数成本，实际淘汰的链表节点总量可按每个插入/匿名化节点摊销；每次从头重建规范状态则是 \(O(|S|)\)，可能得不偿失。状态哈希可按整个 \(O(h)\) 表示计算，或做持久结构，但增量哈希须保留精确碰撞核验。

**full JSON 边界。** 规范状态不保留死键 ID、实际 used_bytes、被淘汰死键列表、真实 final_entries。它首先是评分路径的商，不是官方完整结果的替代。完整诊断需要保留原始队列/紧凑见证，或按得到的精确资源事件流重放一次原 FIFO，或者整份回退 E0/E1。不得用压缩缓存的 used_bytes 冒充官方字段，也不得把一个引擎的 makespan 拼进另一个引擎的时间线。

### 4.7 全局状态归并与增量重放

两个候选的状态只有在以下全部一致时，才能复用未来评分：相同的剩余编译程序/接口和 ID 规则、相同的 Pipe 与门控状态、相同的在飞工作与完成约束、相同 \(N_L(S)\)、相同同刻控制状态。只比较缓存规范形还远远不够。

这可以在“真缓存不空，但所有旧条目都死”的边界合并后缀，是本路线比要求物理缓存清空更宽的地方。若需要完整指标，历史累计指标也要保存并正确拼接；若两个前缀的分项不同，不可直接复用整份旧结果。

对于局部 plan 编辑，首先比较**重新编译后的最早差异**，而不是把被移动子图的预计开始时间当成差异起点。生成 ID、Step1 顺序、spill 与内存边可能改变更早内容。

从差异前的可靠快照重放，传播范围包含真实依赖、Pipe、共享池的重叠忙期、缓存查询/淘汰。一直到整个规范状态和未变的程序后缀重新一致才可停止。最坏情况仍是全局重跑；不能保证只影响两个核，也不能保证一定遇到可合并状态。

### 4.8 无法通用压成小常数状态的理由

若缓存中 \(h\) 个单位大小键全部可能再次使用，容量为 \(h\)，并允许足够的新单位键插入，那么不同 FIFO 排列可以被未来动作区分：找到两排列首次出现不同集合的前缀长度，插入相同数量的新键，再查询两前缀对称差中的旧键。命中不同。

因此在这个缓存自动机动作域上，最坏至少有 \(h!\) 个可区分的有序状态。该结论针对允许这些后缀的动作域，不是说每一张固定赛题图都会达到这个下界。它足以否定“只存驻留集合/总字节/命中率便是通用精确摘要”。

### 4.9 等分服务的虚拟时钟

对连续等分服务模型，将传输工作量用独占池时的工作单位表示。设同时活跃请求数 \(N(t)\)，定义

\[
V(t)=\int_0^t\frac{\mathbf1_{N(s)>0}}{N(s)}\,ds.
\]

请求 i 在 \(a_i\) 到达，工作量 \(w_i\)，终点标签

\[
f_i=V(a_i)+w_i.
\]

它的剩余工作量为 \(f_i-V(t)\)。没有新到达时，下一个连续完成时间是

\[
t+N(t)(\min_i f_i-V(t)).
\]

所以可用最小堆存标签；到达只更新一个时钟并入堆，完成弹出最小标签，不必每次修改全部在飞请求。Demers–Keshav–Shenker §2.2 的 round-number 和 finishing tag 提供了这类构造的原始依据；这里只使用其流体参考过程，不把官方服务改成论文的分组公平排队。[R3]

连续精确模型中，m 次请求、最多 a 个并发，成本 \(O(m\log a)\)，状态 \(O(a)\)，而逐到达修改/重排所有剩余量可能为 \(O(ma)\) 或更高。DDR 和 CACHE_READ 独立维护时钟。

**E1 守卫。** 阅读包报告官方使用 float 剩余量、`ceil(cursor - 1e-9)`、整数事件退休。`remaining -= delta` 与 `finish_tag - V` 的浮点重结合不保证逐项一致；数学上更精确的 Fraction 也不保证等于官方浮点结果。末尾统一 ceil 也不能直接代替逐事件整数退休，因为退休时刻可能改变下一段 active_count。因此本次只证明流体模型等价，不能给这项路径贴 E1 零差分标签。

一个可研究的保守精确子域是：所有服务扣减都是整数（每个相关时间差可被活跃数整除），所有中间整数都处于准确表示范围，并且同刻控制和投影日志完全镜像官方。离开该子域前物化剩余量并回退参考更新。它是否值得实现须由守卫命中率决定。

如果必须输出每一次到达时全部在飞请求的 projected_ends，输出规模本身就是 \(\Omega(ma)\) 量级；内部堆的速度不代表完整诊断接口同倍加速。并发 a 很小时，缓存友好的小数组也可能比堆更快，应实测选择。

### 4.10 E0 实验设计与停用条件

先做缓存自动机同余单元验证，再用官方 Q3 输入族串起：冷键流、活键夹死 gap、同 key 同时 miss、同刻不同 key 插入、容量临界、在飞重复插入、spill alias、第三个无关核改变争用时刻。

对照四种摘要：完整 FIFO、仅驻留集合、错误删除全部死键、本文规范形。前两种错误摘要必须被反例击穿；本文规范形须在其守卫域内逐事件保持查询结果及评分时序。测 \(h/|S|\)、快照内存、后缀归并次数、全局重放长度，不只测 hit rate。

若大多数缓存键长期未来活跃，\(h\approx|S|\)，关闭规范化以避免额外开销；若几乎没有状态再会合，不投入复杂后缀缓存。若程序未来 key 集无法保守计算，保留全键，不凭猜测判死。

## 5. 其他代数、矩阵与张量工具：明确适配边界

### 5.1 三个半环分工，不混成一个万能模型

| 运算体系 | 对象 | 在本题中的合法用途 | 不能替代的部分 |
|---|---|---|---|
| Boolean：OR/AND | 依赖、可达性、商图 | 无环与收缩守卫、来源约束 | cycles、带宽、缓存 |
| max-plus：max/+ | 固定事件的路径约束 | 保留资源接口后的时间传播、候选乐观最长路 | 动态共享池、缓存路径选择 |
| min-plus：min/+ | 可组合的候选选择 | 闭合 Task 区间最短路 | 一般相互争用模块的全局代价 |

合法前缀是依赖偏序的理想集（包含一个节点即包含其所有前驱）。但完成前缀相同不意味着资源状态相同；不能只以理想集作为一般 DP 的全部状态。同样，理想集数量本身也可能指数大。

### 5.2 部分交换与核心对称

Flanagan–Godefroid 的 DPOR 明确要求：交换两个独立动作不改变对方的使能性，且两种执行顺序得到相同状态；其证明针对所定义的执行系统和安全性探索。[R6]

对本题，原图无依赖不代表动作独立：同一 Pipe、同一 DDR/CACHE_READ 池、可能改变 FIFO 的插入、共用内存额度/ID 比较，都可能破坏交换。官方事件遍历本来是固定的，不需要把一个确定模拟器的全部交错再搜索一次。部分序约简更适合减少语义对抗测试的冗余，或在已证明无相互作用的候选构造里规范化标签。

若想约去核心置换群，必须证明包括同刻事件排序在内的编译—模拟映射对该群等变。当前没有这种源码证明；交换核心号在同刻插入两个不同 key 时可能改变 FIFO。应将“核心号置换”作为反例搜索，而不是默认免费的对称性。

### 5.3 稀疏、分块、低秩的区别

对接口矩阵 H，如果所有相关路径都经过 r 个完整保留的连接端口，则可以构造

\[
H=U\otimes V,
\quad U\in\mathbb T^{b_{out}\times r},\quad V\in\mathbb T^{r\times b_{in}},
\]

成本由 \(b_{in}b_{out}\) 降为 \(r(b_{in}+b_{out})\)。这是**经过端口的 max-plus 因子分解**，不是普通实数 SVD。端口必须确实截断全部路径；旁路不能忽略。

低宽/低秩不自动存在。b 条互不相连的输入—输出链给出 max-plus 对角有限、非对角为 -infinity 的 H。一个 max-plus rank-one 因子若同时生成两个有限对角项，就会生成不该有限的交叉项，所以至少需要 b 个这样的因子。图再稀疏，也不保证小因子数。

重复结构还有一个比“低秩”更稳妥的用法：\(\operatorname{diag}(H,\ldots,H)\) 可表示为 tropical 单位阵与 H 的块 Kronecker 结构。存一份系数 H，同时保留每个实例自己的端口绑定、状态向量、时刻和 ID。它压缩代码/系数存储，不把不同分支误认为一个状态。r 个实例仍有 \(\Omega(rb)\) 的独立输入/输出信息，但适合共享系数的 CPU SIMD/GPU 批量 max-plus 运算。这个结构可以高秩而仍值得共享。

### 5.4 无向谱方法只作提案器

若从 tensor 关联构造非负对称 W，\(L=\operatorname{diag}(W\mathbf1)-W\)，谱向量反映的是这个无向二次型的低代价割。必须明确 W 如何由字节/生产消费关系生成，超边展开是否重复计数。

这种近似丢掉方向、真实跨核等待、源端多次 COPY_OUT、Pipe 次序和缓存访问时间。可将谱分组投影回合法拓扑区间或逐步通过当前商图收缩守卫，作为一个候选种子；不能直接作为 makespan 最小化的等价降维。没有测得稳定收益，就不增加这条依赖与调参成本。

### 5.5 张量网络/因子图为什么暂不列入主线

若每个决策变量有 D 个取值，因子图消元的最大中间作用域宽度为 w，朴素精确表规模可能为 \(D^{w+1}\)。全局共享带宽和 FIFO 不能凭空删除：要么形成大作用域因子，要么引入一个携带足够资源历史的状态变量，代价从图宽转移到状态域。

Markov–Shi 将张量网络收缩复杂度联系到线图树宽（Proposition 4.2），其量子模拟中的有界局部维度等条件不自动成立于本题。[R7] 原文部分“rank”是中间张量索引个数，不是矩阵 SVD 秩；不要混用。

因此没有测得小作用域和小状态域时，拒绝把一般调度做成一个巨大张量再近似截断。截断误差可能改变离散事件顺序或可行性；局部范数误差不能直接换算成 makespan 的 1% 误差。本文的 FIFO 规范化若成功减小未来状态，可以成为后续因子化的前置工具，但不承诺整个问题低宽。

## 6. 只有 E0 时如何起步，E1/E2 成熟后如何接入

### 6.1 E0-only 最小路径

先恢复材料和可重复的 E0 调用。没有原题配置时不填默认值；已有通过 E0 的合法基线可以作为 incumbent，但“把所有 op 合成一个 Task”不保证 Step2 容量检查一定通过。

优先以少量固定候选验证：映射/商图/核序/执行图四层检查、闭合 Task 画像条件、消元保留事件一致、FIFO 同刻和 pending-insert 规则。语义守卫过关之后，再扩大正式 case。

对单例预算 B，先测官方新 plan 的耗时分布与最终完整输出成本。候选数量受

\[
T_{prepare}+T_{construct}+\sum T_{compile+evaluate}+T_{final}\le B
\]

限制，而不是固定喊“评估几千个”。最后一次 E0 复算需预留；超时不应把尚未验证的新候选覆盖旧的合法 incumbent。

### 6.2 E1 接入

先让 E1 承担同一候选的准确内部评分，再逐渐启用已独立通过的编译缓存、消元或资源内核。E1 的测试矩阵 full JSON/status 零未解释差异与 ≥3× 是团队联合目标，不是本次结果；也不能用有限测试归纳全输入域正确。[规：补充规范 §2]

纯时间消元若只实现内部 makespan，先以“内部精确候选”身份接入；直到完整诊断能正确重建才声明 full interface compatible。原始 ID、事件列表顺序和错误出口继续遵循冻结接口。

### 6.3 E2 接入与防止选择偏差

E2 可以批量评估合法语法产生的候选，但不得把估计值当下界。保留多个来源的短名单：结构路线内最优、缓存/争用临界样本、高不确定样本，以及分层随机抽样。随机审计比例由剩余预算与实测漏选率调整，不设无依据的固定保证。

开发/校准/封存按图隔离，不能同一图的相似计划同时充当独立泛化验证。用 E0 给完整池标真值，报告短名单遗憾和各风险子域。规范要求每池至少 64 候选、保留 min(n,max(8,ceil(0.1n)))、95% 池保留距池中最好值不超过 1% 的候选等；它不是对未知全局最优的保证。[规：补充规范 §3]

高风险域至少分开：同步主导、DDR 高重叠、CACHE_READ 高重叠、同刻 cache 插入、spill、执行环附近、ID/核心号置换。总体误差中位数不能掩盖某一子域持续丢好解。

正式方案与论文成绩都由 E0 复算；E2 日志单独标 estimate。没有时间线就不造时间线，不混合不同引擎的输出。

## 7. 数学压缩与主机硬件共同设计

### 7.1 已知与未知硬件

已知的是本次用户说明的三台游戏本和一台 Mac，以及希望探索 NVIDIA CUDA 和 M5/Apple Silicon。未知的是每台实际 GPU、显存、功耗限制、CPU/内存、操作系统、驱动和具体 M5 配置。本次数学检查是在 x86_64 Linux 容器运行，不是这些机器，更没有 GPU 实测。

2026-03 的 Apple 官方 M5 Pro/Max 公告确认这些产品与对应硬件能力；2026-05-21 的 Metal Feature Set Tables 将 M5-series 列为 Apple10，支持 Metal 3/4，并列出 64-bit integer math 等能力。不能把产品系列的最高配置当成用户机器配置。[H1,H2]

Apple 2026-03-16 的 MPP 指南描述 Metal 4 tensor API、M5 GPU neural accelerator 与标准 GEMM 的实现，并讨论数据复用、tile 与同步。它没有使普通乘加等价于 max-plus 运算。[H3]

NVIDIA 当前官方 CUDA 13.4 文档强调设备/工具链验证、合并访存、减少和批量化传输，以及浮点次序差异。具体驱动和工具链用目标机 deviceQuery、bandwidthTest、版本输出确定，不从“游戏本”推断。[H4,H5]

### 7.2 先部署可竞争的 CPU 基线

数据布局优先 SoA：op 类型/pipe/core/cycles、前驱 CSR、各 Pipe 索引范围、tensor 大小与 logical key、跨核 links 分开存放。用紧凑整数索引替代热点路径上的 Python 对象和嵌套哈希查找；把固定计算与动态资源状态分开。

小商图 reachability 用机器字 bitset；固定时长部分用有溢出守卫的 int64 max-plus；缓存规范状态用活键表和 gap 链；动态共享池先比较短数组和堆。CPU 多核用于**独立候选**并行，不任意并行化单个官方事件循环。线程数固定并防止 E0、E1、E2 嵌套超额线程。

### 7.3 哪些适合 GPU，哪些不适合

| 内核 | CUDA / Metal 判断 | 先决条件 |
|---|---|---|
| 相同 H 对许多候选/重复模块的 max-plus matvec | 最值得测 | 候选/实例维度足够大，系数和图常驻，接口宽度适中 |
| 固定 DAG 分层的整数时间松弛 | 可测 | 层宽足够、层数不太深、可合并多个小层的启动 |
| 小商图 bitset 批量检查 | 视规模 | CPU SIMD 常是强竞争基线，不能只看 GPU 峰值 |
| 固定区间代价已知后的 DP | 通常 CPU 更直接 | 外层 j 有依赖，GPU 只能并行化候选 i 或多个独立 DP |
| 单候选事件堆、动态 FIFO、精细 shared-bandwidth 循环 | 暂以 CPU 为主 | 不规则访问、顺序因果和分支多；GPU batch 可能改善吞吐，但未必改善 B=1 |
| 原版完整 JSON/Trace 生成 | CPU | 输出规模与序列化通常不能靠张量核心解决 |

GPU 布局可采用 `[event_or_port][candidate]`，让相邻 lane 读取相邻候选的同类状态；重复块 H 系数共享，边界向量独立。对于候选结构不同的批次，按编译骨架/边界形状分桶；桶形成和 padding 成本一起计时。不要为了凑 batch 延迟已经足够好的单例最终确认。

CUDA 用自定义整数 max-plus kernel；Metal 用普通 compute kernel 和目标设备已确认的整数能力。普通 cuBLAS/MPP GEMM 不是 max-plus GEMM。将 max 换成 log-sum-exp 后借普通矩阵乘法，需要指数缩放与数值误差控制；它会放大本题同刻离散事件风险，本轮不列为优先方向。

### 7.4 可测的盈亏点

设独立新候选批量为 B，CPU 有效并行度为 p，单候选热成本 c_C；GPU 每候选成本 c_G，共享开销 A 包括装载、编译、打包、启动、传输、同步和实际回退，则

\[
T_C(B)\approx Bc_C/p,\qquad T_G(B)\approx A+Bc_G.
\]

仅当 \(c_C/p>c_G\) 时存在盈亏点

\[
B> A/(c_C/p-c_G).
\]

这里 A 和 c 都必须实际测量；统一内存减少某类拷贝需求，不代表打包、调度和 CPU/GPU 同步为零。应单列首次运行与热路径，不把开发期已常驻的大批量吞吐冒充最终单例速度。

对整条程序，可加速比例为 f、该部分加速 s 时，上限为 \(1/(1-f+f/s)\)。例如仅 10% 部分提速 10 倍，理论整机上限也仅约 1.10 倍；这是代数算例，不是本队实测。[H4 的 strong-scaling 原理；算例为本文代入。]

开发期三台游戏本与 Mac 可以分别跑独立实验/输入族提高探索吞吐；正式单例自包含求解器不能依赖这些机器同时在线，更不能把四机对照一机的吞吐写成算法加速。

### 7.5 数值、确定性与回退

固定时间和下界尽量用 int64，先检查所有可能路径和是否溢出；-infinity 使用显式标记或饱和安全加法，不能让哨兵参与溢出。并列 witness 用固定 ID/序号，不能由 GPU 线程竞态决定。

带宽池必须复现官方浮点与整数退休语义。CUDA 的 FMA、表达式重结合可能改变结果；禁用不受控 fast-math 也不等于已经证明零差分。[H4] 本次没有成功读取完整当前 MSL 语言规格中的 double 支持契约，因此不对 Apple GPU 的 FP64 细节作未经核实的承诺；E1 动态资源内核先留 CPU，Metal 先做整数固定时间子问题。

设备不支持、批量不足、守卫失败、桶太碎、传输成本过高或数据接近取整/同刻风险时，回退 CPU。回退成本归入单例预算。发布默认开关由端到端配对测试决定，不为“用了 GPU”保留亏损路径。

## 8. 本次实际检查与可证伪范围

可复跑文件为 `probes.py` 和 `probe_results.json`；Python 标准库，无第三方包。环境为 Python 3.13.5、x86_64 Linux，容器可见 5 个逻辑 CPU；程序为串行数学检查，非团队硬件性能基准。

| 检查 | 实际规模 | 本次结果 | 不代表什么 |
|---|---:|---|---|
| 分块拓扑词与无环商图 | n≤5 的所有前向边 DAG 与所有集合分区，54,253 组 | 所有断言通过 | 未跑官方 plan 校验 |
| 单集合合法收缩 | 32,767 组 | 所有断言通过 | 不包括官方编译依赖 |
| max-plus 消元 | 500 张随机 DAG，2500 组源时刻 | 保留节点值相同 | 不含官方资源循环 |
| 虚拟服务时钟 | 1000 组到达流，10,587 个请求 | Fraction 精确比较相同 | 不含官方 float/ceil 退休 |
| FIFO 规范化 | 199,584 次小状态插入穷举；100,000 次随机转移 | 查询和规范后状态相同 | 不保留 raw cache 诊断字段 |
| 未来字母表缩小 | 5000 次 | 规范化组合恒等式通过 | 无官方 spill/pending 全链路 |
| 闭合 Task 分段 DP | 500 张随机区间代价表 | 与全部切点子集枚举相同 | 区间成本没有来自 E0 |

固定随机种子 `20260923`。脚本 SHA-256：`f0b6e4331c3288e9cc9e1e9a37bc8de37e073b592793de59440fc5f8f911cf12`。容器运行耗时仅保存在 JSON 的 `elapsed_seconds_nonbenchmark`，不作为加速结果引用。

这些是实现检查，不是对无限输入域的证明；数学证明在正文另给。没有正式 case 的 makespan、质量改善百分比、E1/E2 加速比或 CUDA/Metal 结果。

## 9. 原文阅读记录：论文—机制—失配—修补

以下只把实际读到的段落作为依据，不声称全文精读每一本书。链接是作者/机构、arXiv 原文或出版社 DOI。公开文献检索截至 2026-09-23。

### R1. 固定时序的代数基础

F. Baccelli, G. Cohen, G. J. Olsder, J.-P. Quadrat. **Synchronization and Linearity: An Algebra for Discrete Event Systems.** Wiley, 1992. ISBN 0-471-93609-X.

原文：[作者公开 PDF](https://www.rocq.inria.fr/metalau/cohen/documents/BCOQ-book.pdf)，[作者说明页](https://www.rocq.inria.fr/metalau/cohen/SED/book-online.html)。实际读 §4.5.3、Theorem 4.75（印刷页 190，PDF 第 206 页），并检查对应页面。

用处：闭包与最小解；本文另证有限 DAG 边界消元。失配：动态资源竞争与缓存不是固定 max-plus 系统。修补：保留所有动态资源动作，只消固定内部节点。

### R2. 无环分区构造

Orlando Moreira, Merten Popp, Christian Schulz. **Graph Partitioning with Acyclicity Constraints.** 2017, arXiv:1704.00705.

原文：[PDF](https://arxiv.org/pdf/1704.00705)，[记录](https://arxiv.org/abs/1704.00705)。实际读 §5.1 的拓扑序构造、§5.2 的移动条件和 cycle-check；检查 PDF 第 6 页。

用处：拓扑词连续块和无环移动。失配：论文 cut/balance 不等于本题目标，也未包含官方展开产生的依赖。修补：仅借用合法构造；执行图再验证，成本交 E0。

### R3. 等分服务的虚拟时间

Alan Demers, Srinivasan Keshav, Scott Shenker. **Analysis and Simulation of a Fair Queueing Algorithm.** ACM SIGCOMM, 1989.

原文：[机构课程保存的论文 PDF](https://web.stanford.edu/class/cs244/papers/demers-queueing.pdf)。实际读 §2.2 的 round number、活动连接数与 finishing tag；检查 PDF 第 3 页。

用处：流体服务时钟消去逐请求剩余量更新。失配：分组 FQ 与赛题 processor-sharing 不同，官方还有整数/浮点细节。修补：只使用流体参考过程的等价式；精确官方路径另做守卫和差分。

### R4. 条件重写与等价类管理

Max Willsey, Chandrakana Nandi, Yisu Remy Wang, Oliver Flatt, Zachary Tatlock, Pavel Panchekha. **egg: Fast and Extensible Equality Saturation.** POPL / Proceedings of the ACM on Programming Languages, 2021. DOI: [10.1145/3434304](https://doi.org/10.1145/3434304), arXiv:2004.03082.

原文：[PDF](https://arxiv.org/pdf/2004.03082)。实际读 §4.1 e-class analysis 的半格/幂等条件、§4.2 条件重写、§4.3 extraction 的局部成本条件。

用处：守卫、规范形、相同接口实现共享。失配：本题 makespan 非局部，不能将低局部成本提取等同全局最优。修补：先 exact hash-consing，只有已证明的行为等价才 union；成本仍外部评估。

### R5. 规则执行的增量计算

Yihong Zhang, Yisu Remy Wang, Oliver Flatt, David Cao, Philip Zucker, Eli Rosenthal, Zachary Tatlock, Max Willsey. **Better Together: Unifying Datalog and Equality Saturation.** PLDI, 2023. arXiv:2304.04332.

原文：[PDF](https://arxiv.org/pdf/2304.04332)，[记录](https://arxiv.org/abs/2304.04332)。实际读 §3 和 §4.3，检查 Theorem 4.1 与 Algorithm 1（PDF 第 12 页）：半朴素求值与朴素求值的结果一致。

用处：管理已证明事实/守卫的增量推出。失配：单调加事实的结论不自动适用于计划编辑引起的删边/别名变化。修补：维护来源与失效，或重新编译；不据此宣称局部改动只需局部重算。

### R6. 部分交换的严格标准

Cormac Flanagan, Patrice Godefroid. **Dynamic Partial-Order Reduction for Model Checking Software.** ACM POPL, 2005.

原文：[作者 PDF](https://users.soe.ucsc.edu/~cormac/papers/popl05.pdf)。实际读 Definition 1（PDF 第 3 页）、算法及 Theorem 1 的 persistent-set 条件。

用处：动作交换需要保使能性且两种顺序同状态。失配：原图不相邻的操作仍可能共享池、FIFO、内存与排序；官方调度本已确定。修补：用于有严格独立守卫的测试约简，而非任意交换官方操作。

### R7. 张量网络的成本条件

Igor L. Markov, Yaoyun Shi. **Simulating Quantum Computation by Contracting Tensor Networks.** SIAM Journal on Computing 38(3):963–981, 2008. DOI: [10.1137/050644756](https://doi.org/10.1137/050644756), arXiv:quant-ph/0511069.

原文：[PDF](https://arxiv.org/pdf/quant-ph/0511069)，[记录](https://arxiv.org/abs/quant-ph/0511069)。实际读 Proposition 3.6、Proposition 4.2 及其证明、局部维数/度数与线图关系，检查 PDF 第 10 页。

用处：要求明确中间张量作用域与 contraction width。失配：缓存/带宽因子可全局耦合，状态域还可能很大。修补：先证明资源状态的可观测压缩；无小域/小宽就不用张量网络。

### R8. 近期实现经验，不作为结构定理

Hiromi Ishii. **Optimizing Optimizations, Declaratively: Optimizing the Higher-Order Functions in Mathematical Optimization with egglog.** 2026 preprint, arXiv:2605.17884.

原文：[PDF](https://arxiv.org/pdf/2605.17884)。实际读 §4 侧条件传播及 §4.1 大表达式预处理/查询成本，检查 PDF 第 5 页。

用处：提醒守卫与表达式准备本身可能占主成本。失配：不是本题调度压缩的正确性或性能证据。修补：先写小型专用规则核，只有反复出现可复用表达式时再考虑通用框架。

### H1–H5. 实际读取的官方硬件与 SDK 来源

- **H1 Apple, 2026-03-03.** [Apple debuts M5 Pro and M5 Max to supercharge the most demanding pro workflows](https://www.apple.com/newsroom/2026/03/apple-debuts-m5-pro-and-m5-max-to-supercharge-the-most-demanding-pro-workflows/)。只用于核对产品系列存在与公开规格范围，不用作团队配置证据。
- **H2 Apple, 2026-05-21.** [Metal Feature Set Tables](https://developer.apple.com/metal/Metal-Feature-Set-Tables.pdf)。读取并检查 GPU family 表及 64-bit integer math/SIMD 能力页面。
- **H3 Apple, 2026-03-16.** [Metal Performance Primitives Programming Guide](https://developer.apple.com/download/files/Metal-Performance-Primitives-Programming-Guide.pdf)。实际读 §1–§2、§3 和算术强度附录的有关部分；其 GEMM 不被当作 max-plus。
- **H4 NVIDIA CUDA 13.4.** [CUDA C++ Best Practices Guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html)。读取 strong scaling、floating point、host-device transfer 和 coalesced access 相关节。
- **H5 NVIDIA CUDA 13.4.** [Windows installation guide](https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/index.html)，[Linux installation guide](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html)。用于部署前提与工具链/设备验证，不表示在本队机器上安装或测试过。

当前 MSL 语言规格 PDF 的读取失败，因此没有以其未读内容支撑 FP64 断言。

## 10. 收敛标准

如果正式输入的编译后图有大比例固定计算、较小资源接口，优先推进路线一；若 Q1 闭合 Task 的上下文独立性成立，路线二的分段模型能提供一块干净的可证算法成果；若 Q3 在阶段边界的未来活键显著少于真实缓存条目，路线三可以提供比“清空缓存才可归并”更强的状态压缩。

三种特征都不存在时，也应接受结果：保留合法候选语法、保守证书与 CPU 精确执行，不强上等价饱和、谱方法或张量网络。研究价值由“可说明的结构收益 + 官方一致性 + 单例预算内质量”三项共同决定，不由术语数量决定。
