# 华为杯 A：第二次独立结构研究备忘

日期：2026-09-23。对象：《通用神经网络处理器下的多核调度问题》。

**交付性质：数学构造、文献核对、可复跑的小规模数学验证与官方验证协议；不是已通过官方评分的求解器，不含正式 100 case 成绩。**

## 0. 主判断与证据边界

最值得投入的不是再增加几种随机邻域，而是缩小“合法且值得评估”的方案空间：

1. **带锚点的偏序理想集 / 分层最小割**：把多节点归属选择化成一次精确最小割，直接构造数据只沿一个核序前进的方案。精确性针对明确写出的代理目标，不针对原题 Makespan。
2. **输入关联的乘积结构 / 矩形构造**：检测任务是否是两个输入族的笛卡尔积，把逐算子分核压缩为少数轴向切线、矩形或经证明的分支计数。结构强时，把此路线提升为第一优先级。
3. **固定执行图片段的 max-plus 端口消元**：仅压缩没有未表示资源副作用的固定时长内部计算；把昂贵仿真保留在真正的资源接口上。它首先是评估加速和小窗口构造工具，不是用最长路替代官方评估器。

没有证据支持“正式图普遍具有乘积结构 / 小树宽 / 小端口数”。这些均须先从正式图检测，不能由题目背景推断。

### 0.1 实际访问情况

- 本轮两份附件全文可读：`01_形式化阅读包(1).md`、`EVALUATOR_AMENDMENT_20260923(1).md`。
- 当前 conversation 文件列表只返回两份附件。扩大到 Library 后，读到了题面 PDF 的全部 14 页、固定配置全文，以及“多核并行模拟执行算法”全文。
- “核内调度算法”说明读了开头与有关接口/队列的指定段落，**没有宣称其 935 行全文读完**。其中旧题号、输入 ID 与字段写法存在陈旧内容，不能覆盖题面。
- 找到了原附件 ZIP 与新增 FORM 证据 ZIP 的记录，但原始字节 materialize 均失败，提示没有授权的 raw-byte materialization 路径；ZIP 内容读取返回零行。
- GitHub 对 `huaweibei123/huaweicup2026` 的仓库读取及固定提交下文件读取均返回 404。这不证明仓库不存在，只说明本会话未能通过该连接读取。
- **未实际读取冻结的 `.py` 源码，未运行 E0 / E1 / E2，未复验 FORM 的脚本或 JSON，未检测三台游戏本和 Mac 的硬件。**
- 用户给出的官方冻结哈希为 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`；本会话未取得原字节，故没有独立重算这个哈希。

### 0.2 本文证据分层

- **[S] 题面**：S1 为 14 页题面；配置的文字值亦读到独立配置文本。
- **[D] 说明文档**：D1 为“多核并行模拟执行算法”；不是已核对字节身份的源码。
- **[M] 成员报告**：M1 为固定 FORM 阅读包，commit `9d660ffc4af9ee7d23a31a7845b81ba7f17203b9`。36 条自标 verified-by-probe 不等于本会话独立验收。
- **[T] 团队要求**：T1 为 EVALUATOR_AMENDMENT_20260923，不是题面物理定律。
- **[P] 本文推导**：证明条件在命题前给出。
- **[R] 本文实际运行**：仅 `structural_probes.py` 的有界数学验证。
- **[H] 待检验假设 / 研究设计**：正式 E0 收益、硬件加速、结构覆盖率都属于此类。

## 1. 必须纠正或保留悬而未决的假设

### 1.1 三层无环不是同一个条件

原 Op–Tensor DAG 无环，不保证按子图分组后的商图无环；商图无环，也不自动保证核内顺序、Pipe FIFO、内存复用和跨核 COPY 合成的执行图无环。后者必须使用官方展开产物检查。[S1 §1.3、附录 D；M1 F-EXEC]

### 1.2 输入域必须分开

题面原输入只允许 Tensor→Op、Op→Tensor，禁止 Op→Op。[S1 §1.2、B.3] 成员部分微图直接使用 Op→Op 边，或人工给校验函数传入 view / cross_links。这些可说明实现分支，不能直接作为题面输入域的端到端证据。

本包构造了双链的二部图反例：两条合法链 `a→b` 与 `c→d`，分组 `{a,d}`、`{b,c}`，商图产生双向边；JSON 已提供。这里只做了结构构造，**尚未用官方 validate_graph 验收**。

### 1.3 “增核变慢”的已有证据不成立为同图比较

M1 中“单链 1 核 24 cycles”与“两条链 2 核 44 cycles”同时改变了图和工作量，不能据此证明同一输入图增加核心会变慢。反过来也不能由此证明增核单调。应固定图、配置和比较口径，分别研究某个构造算法与全体可行方案最优值的单调性；两者不同。

### 1.4 Pipe 串行不等于队首不可越过

`PIPE_SLOTS=1` 只说明同 Pipe 不能同时在飞两条指令。要证明固定队首被跨核输入阻塞时后项不能越过，必须检查全局发射循环是只取 `pipe_ops[head]`，还是在 ready 项中扫描。M1 没有完成这一探针，本会话也未能取得源码。

核内准备阶段“无片上输出的 op 可绕过容量阻塞的 allocation op”，与多核执行阶段的固定 Pipe 队列不是同一个机制。不能混用。

本文在使用 FIFO 相邻边时，采用**待源码核对的严格 FIFO 合同**；任何需要该条件的精确消元必须在核对后启用。后文的“跨核边沿核序严格前进”无环证明只要求局部展开图无环，不依赖队列是否允许越过。

### 1.5 小搬运量、小逻辑前沿、高命中率都不是 Makespan 充分统计量

逻辑前沿只描述一个顺序前缀之后仍有未来用途的张量；真实内存峰值包括当前 op 的输入和输出共存、乱序执行与分配次序。官方 Step3 的虚拟额度会新增 WAR/WAW 顺序边；它不是传统带地址碎片的分配问题。[S1 C.2/C.3；M1 F-LOCAL-006]

缓存命中改变服务池、完成时刻和后续 FIFO 顺序，不能由命中率变化直接推导 Makespan。M1 的“相同搬运但 1052 vs 152”只作为成员报告，不列入本文实测。

## 2. 最小但足够准确的数学对象

### 2.1 编译—仿真，而不是自由选择启动时刻

记方案为

\[
p=(\pi,\kappa,\sigma),\quad
\pi:V_{\rm eligible}\to\{0,\ldots,S-1\},\quad
\kappa:\{0,\ldots,S-1\}\to\{0,\ldots,K-1\},
\]

其中 `sigma[k]` 是核心 k 的子图序列。这恰好对应两个公开 JSON 字段。原操作 ID 不可由求解器重写；子图编号的数值也不能未经证明按纯无名分区处理，因为编号遍历可能影响生成 ID 和并列顺序。

M1 报告 Step1 使用 `(not is_copy_in, depth, -id)` 一类键，升序压栈后按 LIFO 访问：同类同深度时较小 ID 先输出。spill 的 next_use 并列依赖稳定顺序；Step3 的释放额度 FIFO 又决定 MEMORY_REUSE 来源。这些全部留在官方展开中，不由代理重新挑选。在源码未取得前，键的完整适用位置和跨类型优先级仍按成员报告分层，不把相互冲突的文字描述合并。

\[
(G,p,C,q)\xrightarrow{\Phi_q\;\text{官方固定展开}}
(H_p,\mathcal A_p)\xrightarrow{\Psi_q\;\text{官方资源演化}}T_q(p).
\]

`H_p` 包含原数据、重建边界 COPY、spill/rename、内存复用、核内 Pipe 顺序以及跨核依赖；`A_p` 包含执行所需的时间、存储、cache key 和确定性并列规则。用户不能直接选择 `H_p` 中每条顺序边或操作启动时刻。

定义编译像等价：若两个方案生成**完全相同的语义准备产物与初始状态**，包括所有参与并列比较的 ID，那么确定性仿真输出相同。这是可用来复用评估的充分条件；“图同构”“搬运量相同”都不是该证书。

### 2.2 三个问题

- **Q1 / 场景 A**：每个子图一个 Task，同核 Task 串行，Task 间片上数据清空。跨子图边即使同核也重建 DDR 搬运。Task 的开始至少满足同核前一 Task 完成加 100，以及每个异核真实前驱完成加 1000，取最大。[S1 §1.5、D.2]
- **Q2 / 场景 B**：每个核的全部子图合成一个 Task，子图划分仍可改变官方的核内重排；同核跨子图数据可驻留。异核 `COPY_IN` 等待源 `COPY_OUT` 完成再加 500。[S1 §1.5、D.2]
- **Q3**：Q2 加共享只读 FIFO L2；仅 COPY_IN 查找，miss 完成后插入，hit 不晋升，过大张量不缓存；DDR 60 B/cycle 与 CACHE_READ 250 B/cycle 是独立的等分共享池。[S1 D.5、D1 §5]

完整资源状态至少包括：Task 活跃/完成状态、每核每 Pipe 队首及运行操作、依赖计数、跨核释放事件、分配次序、L1/UB 驻留和引用、两个带宽池的在飞工作量、FIFO Cache 的**有序条目及字节占用**、当前时刻和同刻事件阶段。

### 2.3 矩阵的行、列与含义

以下邻接矩阵均采用**行是目的节点、列是源节点**。

生产与消费关联矩阵 `P,C` 都是 `|O| × |T|`：

\[
P_{ot}=\mathbf1[o\text{ 生产 }t],\qquad
C_{ot}=\mathbf1[o\text{ 消费 }t].
\]

二部图与直接操作依赖分别为

\[
\mathcal B=\begin{pmatrix}0&C\\P^\top&0\end{pmatrix},\qquad
D=\mathbf1[CP^\top>0].
\]

可在布尔半环中跨过原 COPY 节点得到 eligible 操作的前驱关系 `D_V`。这对**偏序**保真，但不保留张量身份、COPY 数量或内存语义；不能据此丢掉原图。

`X` 是 `|V| × S` 的子图 one-hot 归属矩阵，`Y` 是 `S × K` 核心归属矩阵，`Z=XY`。则

\[
Q=\mathbf1[X^\top D_VX>0],\quad\operatorname{diag}Q=0.
\]

`W` 为 `|V| × 4`，第 `(v,r)` 项是操作 v 在 Pipe r 的给定计算周期，否则为零；`Z^T W` 给出每核每 Pipe 的非 COPY 总工作量。它是负载量和下界构件，不是预测完成时间。

**DAG 邻接矩阵的普通特征值全是 0**：拓扑置换后严格三角，所以幂零。因此不能把其最大普通特征值解释为本题吞吐或难度。

若构造边–点关联矩阵 `B`，每行尾端 −1、头端 +1，则 `L=B^T diag(w)B` 不区分一条边的方向：反向只把该行乘 −1。无向谱可以识别稠密共享结构，不能恢复被抹掉的方向。

无向超图表示可取 `H_{vt}=1[v 触达 t]`，采用 Zhou 等的

\[
L=I-D_v^{-1/2}H W_eD_e^{-1}H^TD_v^{-1/2}.
\]

这里行是操作，列是张量超边，`W_e` 是字节等权重。此矩阵的谱切割目标不是按 tensor 一次计费的边界量，也不是按目标核心计费的搬运量；方向、固定 ID、资源历史都没有进入。仅保留为构造种子/消融对照。[L6]

## 3. 合法空间的结构定理

### 命题 1：无环聚合与连续拓扑块等价 [P]

对原 DAG 的任一分区，商图无环，当且仅当存在原 DAG 的一个拓扑序，使每个分区块在其中连续。

**证明。** 商图无环时先给块排拓扑序，每块内部再排拓扑序并串接；所有跨块边都向后。反过来，连续块在某个拓扑序中出现，跨块边只能从先出现块指向后出现块，故商图无环。证毕。

这说明“某个拓扑序 + 连续切线”是完整的参数化描述；但**先固定一个拓扑序**再切线，只覆盖一个子空间。

每块偏序凸只是必要条件，不充分。`a→b,c→d` 的 `{a,d}`、`{b,c}` 每块内没有被漏掉的中间节点，商图却成环。

### 命题 2：可证安全的粗化与细化 [P]

在当前无环商图中，把某个拓扑序里相邻的块合并，商图仍无环；把块按其内部拓扑序切为连续小块，也可保持商图无环。任意跨位置合并、任意重新分组则不保证。

更一般地，只合并两个块 a,b 时，若不存在从 a 到 b 或从 b 到 a、且中间经过其他块的有向路径，合并保持无环。反例环若出现，必经合并块，展开便产生上述外部路径。多个合并要逐步重新检查，不能把独立安全条件一次并用。

这些命题只保证商图，不保证官方展开后的性能或可执行性。

### 命题 3：单调核序给出更强的跨核无环证书 [P，条件化]

给每个操作一个核序标签 `ell(v)∈{1,…,K}`，要求所有数据依赖 `u→v` 满足

\[
\ell(u)\le\ell(v).
\]

每核一个子图，或该核内按拓扑连续段再切分。假定每核官方局部展开图无环，且所有生成的跨核 COPY 依赖沿原生产者到消费者方向。则全局展开图无环。

**证明。** 局部边保持核标签，跨核边严格增加核标签。任一有向环不可能含跨核边；若完全留在一个核内，又与局部图无环矛盾。Q1 再加同核 Task 顺序边时，以 `(核标签, 核内 Task 位置)` 作字典序位势。证毕。

此条件故意排除了可能很好的 `Core A→Core B→Core A` 数据往返方案，不能称为无损限制。它只消除一类全局等待环，局部容量失败仍要由官方准备/验证发现。

核心在数学上的顺序与 JSON 的真实核心 ID 必须分开。交换物理核心 ID 可能改变同刻事件的遍历顺序，未经证明不得把全部核心置换视为同一方案。

## 4. 路线 A：偏序理想集、张量辅助节点与分层最小割

### 4.1 适用条件与特征

先看：图是否有多个可并行分支；是否存在较小、可解释的中间数据边界；大部分瓶颈是否能接受单调核序；关键链长度相对总计算工作量是否很大。若几乎纯链或明显需要核间往返，则降低本路线预算。

精确 min-cut 公式作用于有**唯一 eligible 生产者、至少一个 eligible 消费者**的内部张量。外部输入、最终输出、纯死输出须单列；不能把它们强塞进同一公式。多生产者情形先停用该公式或另证扩展。

### 4.2 从逻辑活跃前沿到一个图割

对前驱闭合的理想集 I，令 `x_v=1[v∈I]`。内部张量 t 的生产者为 p，消费者为 C_t。因 I 前驱闭合，

\[
F(I)=\sum_t s_t\left(x_{p(t)}-\min_{v\in C_t}x_v\right).
\]

它恰好计算“生产者已经完成、仍有消费者未完成”的逻辑内部字节数。是**顺序前缀完成后的逻辑值**，不是当前操作申请输出之前/之后的真实峰值。

构造 s–t 网络，源侧表示选入 I：

- 对每个原依赖 `u→v`，放反向无限容量弧 `v→u`，禁止选 v 而不选 u。
- 每个张量增加辅助点 z_t。
- 放有限弧 `p(t)→z_t`，容量 s_t。
- 对每个消费者 v 放无限弧 `z_t→v`。

若 p 在源侧但有消费者在汇侧，z 被迫留在汇侧，恰切 s_t；其他情况可不付该项。因此消去 z 后，割代价恰是 F(I)。

加入 `sum_v c_v x_v` 也可精确表示：`c≥0` 用 `v→sink`，`c<0` 用 `source→v` 并补常数 c。强制包含/排除的锚点用无限弧。实现中的“无限”取大于所有有限容量总和，并用足够宽的整数防溢出。

### 4.3 一次最小割产生 K 个单调标签

设

\[
x_{vj}=\mathbf1[\ell(v)\le j],\quad j=1,\dots,K-1.
\]

增加无限弧 `x_vj→x_v,j+1` 保证各层嵌套；依赖 `u→v` 对应每层无限弧 `x_vj→x_uj`。在每层复制张量辅助节点，有限容量为 `alpha_j s_t`，其中 `alpha_j≥0`。

任意一元标签代价可写为

\[
U_v(\ell(v))=U_v(K)+\sum_{j=1}^{K-1}[U_v(j)-U_v(j+1)]x_{vj}.
\]

故一个最小割**精确**求解

\[
\boxed{\min_{\ell\;\mathrm{monotone},\;\mathrm{anchors}}
J(\ell)=\sum_vU_v(\ell(v))+\sum_{j=1}^{K-1}\alpha_jF(I_j).}
\]

证明就是逐项的割表示，加上无限弧与可行标签的对应关系；本包代码及穷举测试实现的是这个模型。

当 `alpha_j=1` 时，张量项等于

\[
\sum_t s_t\big(\max_{v\in C_t}\ell(v)-\ell(p(t))\big).
\]

它是标签跨度，不是现实“核心距离”。在 K>2 时，可能把没有消费者的中间标签也收费，**绝不能解释为精确通信量**。构造之后应利用 K-bit 核心掩码另算 distinct destination 及真实边界类型作廉价复核。

在 **K=2、唯一生产者、每个跨核目标各一对 COPY、无其他流量项**的条件下，`2F(I)` 等于这些内部跨核 COPY 对的原始字节量。这不是全图 added_copy_bytes，更不是 Q3 的 DDR miss 字节量。[该 builder 条件当前来自 M1，尚待源码核对。]

### 4.4 锚点、负载价格与参数化：哪里精确，哪里启发式

设置 `U_v(k)` 时可包含关键路径位置偏好和每核每 Pipe 的负载价格；按超载更新价格，得到少量不同候选。这是构造策略，不是使 Makespan 自动凸化。

二分时取 `c_v(lambda)=a_v-lambda*w_v,w_v≥0`。锚点固定时，源侧容量单调增加、汇侧容量单调减少、其他容量不变，满足 Gallo–Grigoriadis–Tarjan 的参数化网络条件，可选择嵌套的规范最小割并复用残量网络。[L1]

**重要反例**：没有锚点的纯内部边界目标常使 lambda<0 时全不选、lambda>0 时全选。参数扫描并不保证得到任意指定负载。改变锚点、改变价格向量之后，也不能沿用同一嵌套性定理。严格平衡约束仍可能困难。[L2]

实际使用少量关键链上/结构分支上的锚点对及标签上下界，检测不一致的锚点并丢弃；保留不强行用满所有核心的方案。

### 4.5 可实现流程

```text
ordered_cut_candidates(G, K, price_anchor_configs):
    parse immutable op/tensor CSR; preserve all original IDs
    build eligible precedence and unique-producer internal tensor pins
    for cfg in a bounded, predetermined structural family:
        network = build_layered_cut(K, dependencies, tensor_pins, cfg)
        labels = exact_min_cut(network)
        if anchor constraints are inconsistent: continue
        plan = one_subgraph_per_nonempty_core(labels, original_ids)
        optionally split a core into contiguous local-topological chunks
        check exact coverage; quotient; task order
        prepare with official stages; check local and global execution legality
        compute only certified lower bounds and explicit proxy descriptors
        yield plan
    include previously E0-validated conservative fallback
```

保持公开输出恰为

```json
{"node_to_subgraph":{"原操作id":0},"core_schedules":[[0],[]]}
```

真实 N 个核心要保留 N 个外层元素；不往方案加价格、置信度、时间戳。

数据：CSR 前驱/后继、tensor producer/pin offsets、原 ID 映射、四维整数负载、residual edge SoA、标签上下界。设 n 为 eligible 数，m 为依赖边数，t 为内部张量数，p 为消费者 pins 数，网络规模

\[
V_H=O(K(n+t)),\quad E_H=O(K(n+m+p)).
\]

单候选成本 `T_MF(V_H,E_H)+O(n+m+p)`，内存 `O(V_H+E_H)`。一般 Dinic 可给 `O(V_H^2 E_H)` 的保守界，不能称为线性；附带递归 Python Dinic 仅供微图验证，生产版要迭代实现、控制规模。价格/锚点配置数乘进总成本。官方准备/评估另加，不可隐藏。

### 4.6 官方证伪实验

最小族：菱形链、双链交叉共享、宽叉合流、带长寿命 skip tensor 的链，以及纯链反例；每族固定原 ID 再构造另一份换 ID 的合法输入，检验对固定排序的敏感性。正式配置不变，通过多个合法张量的累计驻留使压力落在容量阈值两侧；始终保持单操作输入输出总量不超过对应片上容量。

对照：同一候选预算的单一拓扑连续切分、无向谱 seed、只按 Pipe 负载构造、整图保守方案；随机示例生成器只当格式对照，不当性能基线。

消融：去掉张量辅助节点改按边计费；去锚点；去单调核序；去四 Pipe 价格；去真实目标核掩码复核。

观测：E0 Makespan / 官方流量、局部 spill、内存复用边、全局拒绝类型、候选多样性与调用次数、总墙钟。成功标准预先冻结，例如在适用结构层上以相同总预算取得更低官方 Makespan；若只有 F(I) 下降而 E0 不改善、或吞噬评估预算，就否定该层的收益假设。不能凭 min-cut 最优值自验收。

## 5. 路线 B：从输入关联恢复乘积结构，而不是逐算子分核

### 5.1 可检测特例

设一组独立作业 `o_ij` 各消费两个输入族的 `A_i,B_j`，输出私有；或每个作业是有相同端口的、内部互不共享的有界小模板。这里不要求 op 内部执行矩阵乘法，只要求输入关系有这个形状。

对单操作、恰有两个共享输入的情况，把**输入张量当点、作业当连接两个输入的边**。检查该输入图是否二部；二部连通分量若无重边且边数为 `|A|·|B|`，就是完整笛卡尔积。BFS 二着色、计数及完整性检查为 `O(n+p)`，无需求最大 biclique。

多 op 模板只允许有界、明确的同构核对与私有内部张量检查；哈希可找候选，不能当行为等价证明。一般缺边子矩形只作为近似构造，不声称精确乘积。

### 5.2 矩阵因子化

令输入关联矩阵 H 的行是 RC 个作业、列是 R+C 个输入。按 `(i,j)` 编号，有

\[
H_A=I_R\otimes\mathbf1_C,\qquad
H_B=\mathbf1_R\otimes I_C,
\]

\[
HH^T=I_R\otimes J_C+J_R\otimes I_C.
\]

输入大小分别为 a,b 时，共享权重矩阵相应为 `a I_R⊗J_C+b J_R⊗I_C`。不必形成 `(RC)²` 的稠密操作相似度矩阵，也不必对它求谱：直接恢复两个坐标轴。

### 5.3 面积—边界下界及矩形形状

一个核心得到 m 个作业，触达 r 个 A 输入和 c 个 B 输入，则

\[
m\le rc,\qquad V=a r+b c\ge2\sqrt{ab\,m}.
\]

证明由集合包含于所触达行列的笛卡尔积，以及 AM–GM。满矩形满足 m=rc；连续松弛下最省输入量的形状满足

\[
a r=b c,\qquad r/c=b/a.
\]

**V 是该核不同输入的字节并集，不是已测 DDR 搬运。** 同核输入只需一次 ingress 且无 spill 时，它对应那部分 COPY_IN 字节；Q3 还要决定每次 ingress 走哪个池，不能直接等同 DDR。输出和源核多播也要单列。

这与数组访问映射及 HBL / 矩形 blocking 的思路相通，但本题操作不可拆，不能把论文允许的循环重排/重算直接搬来。[L4、L5]

### 5.4 构造方法和复杂度

先生成行条带、列条带、`p×q≤K` 网格；K=3、5 等情况使用递归 guillotine 切分，不强求等形矩形。切点从面积平衡、四 Pipe 负载平衡和加权输入轴前缀给出的 floor/ceil 邻域中取，候选数预先封顶。保留少量非矩形负载对照以检测大计算热点。

四个二维前缀和用于 `O(1)` 求任意矩形的四 Pipe 计算量；轴向前缀和用于输入字节量。这个方法搜索的是少量边界，不是全部 `K^(RC)` 逐点指派。

```text
product_candidates(G, K):
    identify isolated two-input product components and verify hypotheses
    build four pipe-work prefix sums + input-byte axis prefix sums
    enumerate a bounded set of stripes / grids / balanced recursive rectangles
    for layout:
        assign each original job/template intact to a rectangle/core
        retain original IDs and deterministic local ordering choices
        materialize exact node_to_subgraph, core_schedules
        compose with surrounding DAG only through explicit ports
        official-compile and validate; E0-evaluate the protected shortlist
```

若有 A 个布局，代理阶段 `O(n+p+A K)`，输出全映射本身最坏 `O(A n)`；内存 `O(n+p+RC)`。没有声称枚举所有矩形划分或得到加权 Makespan 的最优值。

纯独立乘积块每核一个子图时，操作间商图没有跨核数据边，只有共享原输入；局部准备成功后，跨核执行环问题简单。接入外部 DAG 后仍须整体展开校验，不能忽略外部生产者和汇聚消费者。

### 5.5 重复分支计数化的严格条件

若 m 个分支在**完整准备语义**下可交换：同端口依赖、时长、Pipe 顺序、资源副作用及 cache key 等价关系，且 ID 并列行为在替换下有同构证书，则指派可压缩为 `(m_1,…,m_K)`，组合数由 `K^m` 降至

\[
\binom{m+K-1}{K-1}.
\]

仍可能很大；只在可证明的纯同质计算特例才能进一步只保留平衡计数。固定 ID 相同形状、源端 COPY_OUT 顺序、共享 logical_tid 会打破朴素对称性。本轮不宣称任何正式图已经通过这个可交换性证书。

### 5.6 Q3：FIFO 的“后续准入量”，不是 LRU reuse distance

某 key 大小为 s，在插入之后、首次被淘汰之前，设后来实际成功准入的条目字节累计为 A，则它仍在 FIFO 中的条件为 `s+A≤C`。位于它之前的旧条目会先被淘汰；命中、已存在 key 的幂等 insert、超大条目跳过都不增加 A。若 key 已被淘汰并重新插入，需要从新插入时刻重算。

此观察可用于设计和分析合法 job 顺序，但 A 本身由完成事件决定，不能从原图静态访问距离准确推出。两个同时 miss 必须各占 DDR，不能把先发起当成立即插入。

不得插入人为等待或预取。只能改变允许的分块、分核、子图顺序，利用原有计算和 COPY 时序形成相位。

### 5.7 反例和实验

失败机制：少数重作业集中在矩形对角；大量私有输出盖过输入收益；固定 ID 导致所有 A 输入长期驻留而 spill；共享输入实际由某源核生成，产生逐目标串行 COPY_OUT；输入量下降但关键路径释放变迟。

最小族：完整 `R×C`、删少数边、大小比 `a/b` 改变、计算周期均匀/对角热点、共享源为图输入/内部生产者、共享输入的累计准入工作集在 1 MB 阈值附近，且每个操作的输入输出仍满足片上容量。不要用大于片上容量的单 tensor 伪造本题输入。比较条带、网格、递归矩形、棋盘、按计算负载打散。

消融：不用乘积识别而用操作相似度；去四 Pipe 平衡；用访问次数估 cache；强制合并所有同形分支。记录 E0 Makespan、实际 source COPY_OUT 排队、重复 ingress、spill、两池占用与 FIFO 事件。

若没有检测到可用乘积块，检测失败即快速退出；不能为了论文漂亮做昂贵最大 biclique 搜索。

## 6. 路线 C：保留资源端口，消去固定时长内部状态

### 6.1 可精确的模型

给定**已固定且无环的执行图**，所有留下的依赖与 Pipe 顺序为完成约束，操作时长 d_v 固定，额外延迟 delta_uv 固定，且没有未表示的动态资源约束，则

\[
x_v=\max\{r_v,\max_{u\to v}(x_u+d_v+\delta_{uv})\}.
\]

r_v 是完成时刻的外部下限，已含本节点必须的计算时长，不要把它误当开始时刻。令 `A_vu=d_v+delta_uv`（无边为 −∞），则 `x=A⊗x⊕r`；DAG 上闭包是有限最长路。[L7]

**整个官方仿真不满足固定 d 的条件**：DDR 争用改变时长，Q3 查询决定池，动态分配可能再限制发射。因此只能做认证的局部消元。

### 6.2 max-plus Schur 补式消元 [P]

保留端口 B，消去内部 I：

\[
x_I=A_{II}^*(A_{IB}x_B\oplus r_I),
\]

\[
A'_{BB}=A_{BB}\oplus A_{BI}A_{II}^*A_{IB},\qquad
r'_B=r_B\oplus A_{BI}A_{II}^*r_I.
\]

代入原方程即得端口完全等价。对所有外部释放时刻成立，不只是对一次 trace 成立。必须保留 `r'_B`：内部无前驱操作可影响出口，不能仅保存端口到端口路径。

**端口判定**至少保留全部 DDR/CACHE 请求和完成、cache 插入/淘汰关联、跨核释放、Task gate、边界 Pipe 占用关系；分配/释放/引用计数若没有被完整编码进固定依赖，也须作为资源事件保留。若这使几乎每个计算 op 都成端口，就停用，不声称仍有大量压缩。

对 b 个端口，通过 b 次 DAG 最长路计算转移矩阵，预处理 `O(b(n_I+m_I))`，矩阵存储和一次应用 `O(b²)`，矩阵合成 `O(b³)`。填充效应使 b 大时比原稀疏图更差。

重复的纯固定计算片段若端口语义也完全相同，可以算 max-plus 矩阵幂，m 次串接降为 `O(b³ log m)`；不能把带 cache 查询的重复片段当常数矩阵。

### 6.3 小窗口方案构造 / 窄接口 DP

对若干具有窄资源接口的区域，生成少量实际可提交的局部划分、同核顺序、核心归属选项。每个选项先用官方核内阶段固定其语义，再建立端口转移，保存能还原原方案的回指。

```text
port_option_DP(regions):
    states = {initial exact interface state}
    for region in regions:
        next = []
        for state in states:
            for compiled option with matching interface:
                append(transition(option, state), plan_backpointer)
        merge identical complete states
        prune by componentwise dominance ONLY under certified max-plus conditions
        otherwise retain full resource/cache state or mark beam approximation
    reconstruct exact public plan; official validate; E0 confirm
```

若未来只依赖同一端口时钟向量，且转移全为单调 max-plus 映射，则分量不晚的向量支配分量较晚的向量：单调性对所有未来串接保留该关系。证明逐层应用 `max` 与 `+` 的单调性即可。

**在 PS / FIFO Cache 下，较早不自动支配较晚**：相位可改变争用和命中。必须要求相同未来依赖、同缓存有序状态、同在飞剩余工作及其他资源状态，或退回上述无共享事件特例。

若每层 D 个状态、F 个选项，转移 `O(D F b²)`，朴素支配检测可达 `O((DF)²b)`。整数时钟上界 H 会带来伪多项式状态数；连续资源工作量、FIFO key 队列又可扩大它。原图树宽小不保证这里状态小。截断 D、量化时钟、合并相近状态都要标为近似。

### 6.4 特例、失败机制、实验

适用：长的纯计算段、少数资源事件连接大量内部固定计算、重复串联 motif。Q1/2/3 都可作为评估内部优化，但 Q3 最难取得小端口数。

击穿：隐藏的 alloc/free 事件、同刻事件顺序改变、串行 Pipe 跨区域相接漏边、输入依赖少但输出/内存接口多、密集端口导致矩阵填满。若压缩后 event_count 没下降或 preprocessing 无法摊销，CPU 原始稀疏 DAG 更好。

最小验证：先对固定带权 DAG 的各种释放向量逐点相等；再在 E0 下分别加入跨区 Pipe、固定容量下驻留量达到容量或刚多一字节、两路不等长 DDR、同时 miss / 不同 key 同刻完成。端口化前后比较全部完成时刻和合法性；任何一次不一致即撤销该消元类别，而不是增大容差。

## 7. 只保留能证明的下界和停止证书

### 7.1 所有方案都适用的便宜下界

\[
LB_{\rm global}=\max\left\{
CP_{\rm original,compute},\;
\max_r\frac{\sum_{v:\,pipe(v)=r}c_v}{K}
\right\}.
\]

第一项忽略 COPY、同步及资源竞争，只累积必需计算依赖路径；第二项由同 Pipe 在 K 核上最多 K 条并行的工作守恒得到。两项都只是下界，不能相加。要再加最终写出 / 带宽下界，必须明确哪些写出是原题所有合法方案都不可消除的。

### 7.2 固定方案的下界更强

用完整准备图的**必需边**构造乐观时长：每条计算用给定周期，每条 COPY 用它在任一合法路径中可能达到的最快时长；Q3 可以乐观假定所有 eligible COPY_IN 都命中，以放松约束。保留不可消除的同步延迟。

任意真实执行都满足这些逐边完成不等式，因此

\[
LB(p)=\max\{CP(H_p,d^{min},\delta),
\max_{k,r}\sum_{v\in(k,r)}d_v^{min},
B_{\rm forced\ DDR}(p)/60\}\le T_{E0}(p).
\]

Q1 的 task start/end gate 与 100/1000 延迟要显式进入 H_p。`B_forced DDR` 仅含必走 DDR 的字节，如输出 COPY_OUT、不可缓存访问；不能把所有 Q3 COPY_IN 都算 miss。

证明来自实际执行必须满足的约束，而**不是**“给一个贪心调度器缩短时长后，它一定跑得更早”的直觉。后者在资源耦合调度中不够。

`LB(p) ≥ 当前已验证 incumbent` 可以剪掉该候选 p；不能排除与它相近的其他方案。只有覆盖全部待选方案的合法下界，才可报告原问题最优性差距。

### 7.3 可严谨停止的链式特例

限定为一条输入 COPY_IN、线性的计算链、一个最终 COPY_OUT；每个计算只依赖链上前一个数据，无共享分支或旁路，任一时刻必要两缓冲适配容量，整图官方局部展开没有 spill 或额外等待。此时整链依赖已经强制所有必要操作串行。额外跨 Task/核切分不能创造并行，只会增加非负搬运或同步。因此整图单核方案达到该特例的串行下界。正式调用仍应由 E0 确认局部条件确实成立。

### 7.4 不应称为原问题下界的量

min-cut 代理最优值、无向谱能量、一个允许自由重排的 pebbling 最优峰值、理想调度器生成的一条可行日程、只按字节估计的 makespan，都不能未经单独证明用来剪掉原题好方案。

## 8. 增量失效、processor-sharing 与失败环定向修复

### 8.1 失效从最早语义差异开始，可能传播到所有核心

划分变动可能改变边界 COPY 与生成 ID，进而改变另一个核的固定并列顺序。任一请求发起改变 DDR 活跃集合，会影响其他核已在飞的剩余时间；完成事件变化又会改变 Cache 插入和未来 miss。不能限定为两核。

安全缓存分两级：不依赖 plan 的原图 CSR/输入矩阵可共享；plan 相关准备产物必须按完整语义指纹复用。指纹需覆盖原 ID、生成 ID、顺序、memory_dependencies、COPY lineage、config 和官方代码版本。

精确增量回放：找到最早发生语义分歧的事件，从其前的**全局快照**恢复，回放整个受影响全局后缀；只有“完整状态 + 未来已排队输入/事件”与旧运行重新一致时才能复用后缀。图上的局部邻域不足以证明一致。动态影响闭包可加入数据/FIFO/内存边、带宽区间相交、Cache 后续同 key 查询，但闭包最坏就是全图。

### 8.2 PS 的虚拟服务坐标：理论正确，收益未必高

对连续等分共享池，定义

\[
V(t)=\int_0^t\frac{\mathbf1[n(u)>0]}{n(u)}du.
\]

请求 i 到达 a_i、独占工作 w_i，设置服务标签 `f_i=V(a_i)+w_i`，其剩余工作是 `f_i−V(t)`。共同减量变成更新一个 V；最小标签决定下一完成。可用堆，但只有极小活跃集时数组扫描往往更合适。

本题 K≤5，若 DDR COPY 只占 MTE2/MTE3 且每 Pipe 一条在飞，则全池同时活跃至多 2K≤10；保守按四 Pipe 也仅 4K≤20。这个低维度来自被模拟的机器，不来自主机 GPU 大小。故即使数学上能把每次更新由 O(n) 改成 O(log n)，也可能不抵常数和排序成本。

本包仅验证连续 Fraction 模型。官方整数时刻、ceil(...−1e−9)、同刻 retirement 阶段仍必须逐项核对，不能宣称此内核已是 E1 的零差分替代。

### 8.3 从环得到修复，不删除物理约束

对错误 trace 提取 witness：原数据 / 同核 Task 顺序 / Pipe FIFO / MEMORY_REUSE / 跨核 COPY。原输入是 DAG，环必须使用至少一种由分组、核序或展开产生的约束。

选择能改变这些边的**公开决策**：合并或细化相关块、调整相关核内子图序、改变核心归属；重新运行官方展开。不能直接从 H 删 FIFO 或 memory 边。

若能证明一小组具体决策共同迫使该环，可记录 no-good，阻止同组决策再次出现；否则只禁当前精确方案指纹。不能把一次环的节点集合粗暴推广为“这些节点永远不能同核”。修复次数要有界，超额回退到已验证方案。

## 9. 研发和最终 5–10 分钟预算

### 9.1 只有 E0 时

先做一次不依赖 plan 的结构扫描，选择路线而不是跑全套算法。构造小而机制不同的候选池，先用覆盖/商图、条件化证书、明确下界和结构指标减少浪费。E0 实际每次耗时必须在目标主机测量。

\[
T_{parse}+T_{construct}+N_0t_0+N_1t_1+N_2t_2+
T_{validation}+T_{transfer/sync}+T_{IO}\le B.
\]

B 取题面建议的 300–600 秒。所有 plan 相关准备、代码加载/实际回退都计入。根据保守的 t0 分位数动态估计还能确认多少候选，预留最后一次完整 E0 及输出预算。没有 E1 时，不能默认 64 候选的 E0 全池标注能进入正式单例时间。

### 9.2 E1 / E2 接入

E1 通过相应范围的独立零差分验收后，可替代该范围内的精确内循环，仍用 E0 做正式结果。E2 首先用于排序，不把点预测当下界。保留 incumbent、每条机制的代表、容量/缓存临界方案和一定比例的随机审计名额；这些是研究设计，不是 E2 已达指标。

E2 必须按题号、图族、核数、spill 和争用风险校准，报告短名单 recall 和 regret；总体中位数好不能掩盖某类图系统性被筛掉。风险子域保留直接 E0/E1 通路。

T1 的 E1≥3×、E2≥10×E1、误差中位数≤1%/P95≤3% 和短名单质量都是目标。不得将数值兼容的 E2 makespan 与另一个引擎时间线拼接，元数据另放 run.json。

### 9.3 开发期吞吐不等于单例速度

三台游戏本和 Mac 可独立跑不同图族、不同候选和审计；这是研发吞吐。正式算法不要依赖远程节点或常驻服务。最终应给目标机上 B=1 新实例的冷启动和完整预算结果，同时另列 batch=16/64/256 的吞吐。

论文按题面报告**各 case 加速比的算术平均**，不是单核总时长除多核总时长。固定单核基准是官方整图启发式，不是优化后最好单核；超线性比值不能解释成超过物理算力上限。[S1 问题1脚注]

## 10. 数学与主机硬件共同设计

### 10.1 两种“多核”不可混同

赛题机器是被模拟的 K=2…5 个核、四 Pipe、规定 L1/UB、DDR 与 L2。主机的 CPU/GPU/统一内存只影响求解器耗时，不能改变模拟器的核数、带宽、事件顺序或 Cache 行为。

本队游戏本 GPU 型号未知；Mac 的具体 M5 变体、CPU/GPU 核数、RAM、macOS/Xcode 未实测。2026-03-03 Apple 官方说明存在 M5 Pro / M5 Max 配置差异，不能拿某个系列上限当成本机配置。[H4]

### 10.2 CPU 是必须击败的真实基线

- 原图 CSR、tensor pins、原 ID 和四维负载使用连续 SoA；immutable 数据共享，每个候选独立 scratch arena。
- 每个实际 CPU 工作线程运行一个候选，避免一个候选内部的全局事件循环加锁。
- 小活跃池使用固定长度数组、确定性排序；哈希 key 只在必要处使用，不能为省时丢弃原 ID 顺序。
- 块化的 max-plus 端口矩阵使用 64 位整数和 SIMD；一阶比较次数很少时，单线程缓存友好循环通常是更合理的待比较对象，而不是 Python dict 的慢基线。
- CPU 的线程数、编译优化、内存布局也列为实验变量。纯 Python E0 可进程隔离，但新 C++/Rust 内核仍需独立零差分。

### 10.3 哪些部分值得 CUDA / Metal

| 内核 | 并行维度与布局 | 主要阻碍 | 决策 |
|---|---|---|---|
| 矩形输入并集、四 Pipe 负载 | 候选×矩形；共享前缀数组，连续输出 | 本来 O(1)，工作过少 | 单例优先 CPU；大批才试 GPU |
| 同形端口矩阵应用/合成 | 候选×端口×端口；按 b 和模板分桶 | 小 b 启动成本，大 b 填充/寄存器压力 | 最有意义的 GPU 原型 |
| 固定层次的 DAG/标签特征 | 同层节点×候选；GPU 可用 [vertex][candidate] | 度数偏斜、依赖层很多 | 只在层宽足够时试 |
| 残量最大流 | 活跃点/边 | 反向边更新、原子竞争、分支不规则 | 本轮保留 CPU |
| 原始 PS+FIFO 全事件模拟 | 候选间并行；每 block/warp 一个候选 | 单候选强顺序、小活跃集、不同事件数、Cache 不规则 | 不列首要 GPU 方向 |

CPU 通常适合 `[candidate][vertex]` 以顺序遍历候选；GPU 若每线程处理一个候选的同一操作，采用 `[vertex][candidate]` 合并访存。不同 prepared 图应按拓扑模板、端口数、资源事件数分桶，减少 padding。不要为了“矩阵化”显式建 n² 稠密矩阵。

### 10.4 SDK 核对与精度

NVIDIA 当前 CUDA 13.4 文档列出 `__viaddmax_s32(a,b,c)=max(a+b,c)`，正好匹配 max-plus 更新。**可调用该 intrinsic 不等于设备原生加速**：当前 Programming Guide 的能力表区分 Native 与 Multiple Instr.，新语言扩展文档要求按 compute capability 查询；不能沿用旧版“所有 CC≥9 都原生”的笼统句子。测实际设备、编译目标、生成指令及端到端收益。[H1/H2]

只有证明所有有限路径和加法都不溢出 int32，且正确处理 −∞ 时，才考虑 s32 DPX；否则用 int64。不要用 ReLU 变体把 −∞ / 负权截为零。普通 Tensor Core 的乘加不是 max-plus。

Apple 当前 Metal 4 文档与 2026-05-21 feature tables 已核对：不同 Apple GPU family 的 SIMD、64 位整数能力和原子能力要逐项查表，不能从“支持 Metal”推断全部可用；本轮未取得可读的最新 MSL 规范全文，因此不作未经核对的 FP64 支持承诺。M5 的 Neural Accelerators 面向 tensor 运算，不证明对 graph cut、队列或 max-plus 有专门加速。[H5/H6]

Metal 统一内存可以避免某些显式复制，但不能消除 CPU–GPU 访问完成和同步要求。Apple 的 shared resource / event 文档明确区分共享存储与同步；即使没有数据复制，同步仍可能有成本。[H7]

E1 时间和字节用 int64；仿真浮点剩余工作保留与官方一致的精度、运算次序、取整和同刻事件序，不开改变语义的 fast-math。GPU FP32 仅可作为声明近似的 E2/特征，不因 makespan 碰巧相同就算 full JSON 零差分。[T1；H1 §7]

### 10.5 成本模型、盈亏点和退出规则

\[
T_{GPU}(A)=T_{init}+L_{launch}+Q/\beta_{transfer}
+\max(F/P_{GPU},M/\beta_{GPU})+T_{sync}+T_{fallback}.
\]

T_CPU 使用同口径已优化 CPU 的实测耗时。若摊到候选的 GPU 计算+搬运成本为 g、CPU 为 c，则在 c>g 时才存在近似盈亏点 `A > (T_init+L_launch+T_sync)/(c-g)`。本轮没有测 c、g 或启动微秒数，所以不编造具体阈值。

b=32 的一次矩阵–向量端口更新仅约 1024 次 max-plus 更新；b=32 的矩阵合成约 32768 次。它们说明一个小候选不足以自动摊销 GPU，并不是实测运行时间。

按 batch=1/16/64/256、冷/热、端口 b、事件比例、是否跨 PCIe，分别测时间、内存、失败回退、确定性。只有 `构造+E2全池+精确短名单+E0确认+所有开销` 在单例预算下降时才启用。数学压缩若把候选从数百个降为几个，反而更可能让 CPU 胜出，这是成功，不是硬件路线失败。

### 10.6 测试输入域的统一约束

正式收益实验始终使用固定 config。容量阈值由改变合法输入图的累计活跃工作集来跨越，而不是修改配置；每个计算操作自身的输入输出仍须符合题面容量保证。故测试 L2 容量效应时优先使用多个小张量累计准入接近 1 MB，不把超大单输入构造当作正式数据域。修改 config 的机制单测可以另做，但必须标为非正式配置，不能进入论文正式平均加速比。

## 11. 已执行的有界数学验证 [R]

环境：Python 3.13.5，Linux x86_64，标准库，无 GPU。随机种子 20260923。完整原始结果在 `probe_results.json`；代码哈希在该 JSON 中。

| 验证 | 规模 | 结果 | 不包含 |
|---|---:|---|---|
| 分层最小割 vs 标签穷举 | 120 随机微图，1814 个可行标签向量 | 0 mismatch | 官方展开、Makespan |
| 参数扫描源侧嵌套 | 120 扫描族，固定锚点 | 0 违例 | 多参数变化、精确平衡 |
| 无环商图 iff 某拓扑序连续块 | 1024 个 5 点前向 DAG × 52 分区，共 53248 对 | 0 mismatch | 官方全局执行图 |
| max-plus 端口消元 | 100 DAG，1000 释放向量，累计移除 563 点 | 0 mismatch | 共享带宽、Cache、动态分配 |
| PS 虚拟服务时钟 | 200 实例，Fraction 精确算术 | 0 mismatch | 官方整数 retirement |
| 4×4 输入乘积，2 核各 8 作业 | 12870 平衡指派 | 最佳输入并集 12，最差 16；条带 12，棋盘 16 | DDR 实际字节、Makespan |

还验证了不设锚点会全选/全不选的退化例。上述实验不是定理的替代，也不是正式数据性能；总运行时间记录只是复现信息，不能当成 E0/E1 加速比。

## 12. 三张优先研究卡

### A-CUT：一次最小割能否成为低评估成本的强候选发生器？

- 入口：唯一生产者内部 tensor，K≤5，前驱 CSR；输出单调核序方案。
- 数学验收：gadget 代价与穷举相等，锚点冲突明确拒绝，商图/强无环证书成立。
- 官方验收：与相同总时间预算的拓扑连续切分及负载方案比较 E0；统计 span 代理与真正目标核计费的排序反转。
- 停止条件：纯链、核往返需求强、候选退化或 min-cut 吃掉确认预算。

### B-PRODUCT：正式图能否从算子集合还原为输入轴？

- 入口：输入关联、可验证的私有作业/模板；先做线性检测，不做一般 biclique 搜索。
- 数学验收：产品完整性、矩形覆盖不重不漏、每核输入并集公式与逐项集合相同。
- 官方验收：条带/矩形/打散比较，分别测试图输入与内部生产者，追踪源 MTE3 和 FIFO 相位。
- 停止条件：覆盖率低、重作业破坏平衡、私有输出/内存峰值主导。

### C-PORT：能否在不删除资源事件的条件下消掉大量内部节点？

- 入口：官方 prepared 执行图，明确副作用清单与精确事件顺序。
- 数学验收：全部端口释放向量上方程等价；隐藏资源事件一律保留。
- 官方验收：完整结果逐项比对，按 b/事件比例测真实新候选端到端速度。
- 停止条件：b 接近原节点数、矩阵填充、任何零差分失败或摊销不足。

## 13. 一手文献、实际阅读范围与适配限制

以下只把实际读取的原文部分作为依据；没有宣称每篇全文逐页读完。

### L1 — 参数化最小割

Giorgio Gallo, Michael D. Grigoriadis, Robert E. Tarjan. **A Fast Parametric Maximum Flow Algorithm and Applications.** SIAM Journal on Computing 18(1), 30–55, 1989. DOI: [10.1137/0218003](https://doi.org/10.1137/0218003).

可访问版本：[Princeton TR633 入口](https://www.cs.princeton.edu/research/techreps/633)；[作者上传全文](https://www.researchgate.net/publication/220616489_A_Fast_Parametric_Maximum_Flow_Algorithm_and_Applications)。实际读取作者上传原文 §2.3 的参数网络容量条件、嵌套割和复用机制；不是依赖 ResearchGate 的二手摘要。Princeton 直接 PDF 获取未成功。

映射：固定锚点与单调 lambda 的候选族。失配：本文 Makespan 不是该最小割目标；多维价格变化不保嵌套；附带 Dinic 也没有实现原论文的全部参数化性能界。

### L2 — 无环划分及平衡困难

Orlando Moreira, Merten Popp, Christian Schulz. **Graph Partitioning with Acyclicity Constraints.** 2017, arXiv:[1704.00705](https://arxiv.org/abs/1704.00705). [全文 PDF](https://arxiv.org/pdf/1704.00705)。

读取定义、Theorem 1 的平衡二分困难、拓扑初始构造及多级方法的相关段落。本文采用 arXiv 出处，不补写未核对的会议元数据。

映射：合法聚合、拓扑连续块对照。失配：论文目标是带平衡的割，不含官方核内编译、DDR/Cache。其困难性不能不经归约就改称华为题的困难性定理。

### L3 — 峰值内存的结构化调度

Ce Jin, Manish Purohit, Zoya Svitkina, Erik Vee, Joshua R. Wang. **New Tools for Peak Memory Scheduling.** 2023, arXiv:[2312.13526](https://arxiv.org/abs/2312.13526). [v1 原文 HTML](https://arxiv.org/html/2312.13526v1)。

读取 §§1–3、§5 isolated subgraph / exchange / linearization、§7 参数化与困难性，以及 Appendix C 的部分展开。Theorem 3.1 的 dominant schedule 构造要调用峰值最优 oracle；不是普适免费多项式算法。相关 SP 图算法有 out-degree 参数条件。

映射：区域接口、内存 profile、可交换性边界。失配：其优化者可以选择调度顺序；本题的 Step1–3 固定，且目标是多核 Makespan。故不直接用该线性化替代官方核内算法。

### L4 — 超图关联与按连通分区计通信

Ümit V. Çatalyürek, Cevdet Aykanat. **Hypergraph-Partitioning-Based Decomposition for Parallel Sparse-Matrix Vector Multiplication.** IEEE Transactions on Parallel and Distributed Systems 10(7), 673–693, 1999. DOI: [10.1109/71.780863](https://doi.org/10.1109/71.780863). [作者全文](https://www.cs.bilkent.edu.tr/~aykanat/papers/99IEEETPDS.pdf)。

读取 §3 的 cut-net/connectivity 度量与行/列 net 的通信对应。关键是按 net 触达分区数计费，不把一个共享 tensor 展成大量独立付费的普通边。

映射：输入并集、每个 tensor 的目标核心掩码。失配：SpMV 通信模型不含本题逐目标源端 COPY_OUT、固定同步、spill 或 FIFO 相位，不能直接把 connectivity 当 Makespan。

### L5 — 数组访问映射、通信下界与矩形块

Michael Christ, James Demmel, Nicholas Knight, Thomas Scanlon, Katherine Yelick. **Communication Lower Bounds and Optimal Algorithms for Programs That Reference Arrays — Part 1.** UCB/EECS-2013-61；2013, arXiv:[1308.0068](https://arxiv.org/abs/1308.0068). [全文 HTML](https://arxiv.org/html/1308.0068)。

读取 Loomis–Whitney / HBL 相关建模、§7.2 Theorem 7.1 的矩形块构造和证明、§7.3 适用限制。访问矩阵行是数组映射、列是循环坐标，LP 指数给出块边长尺度。

映射：由输入关联恢复轴，选择矩形形状。失配：本题不能重排或细分 op 内的循环，不能假设其所有 blocking 自由度；二维并集不等式是本文单独给出的受限特例。

### L6 — 超图谱的正确用途与边界

Dengyong Zhou, Jiayuan Huang, Bernhard Schölkopf. **Learning with Hypergraphs: Clustering, Classification, and Embedding.** NIPS 2006, Advances in Neural Information Processing Systems 19, 1601–1608. [官方全文](https://papers.nips.cc/paper_files/paper/2006/file/dff8e9c2ac33381546d96deea9922999-Paper.pdf)。

读取 §§2–6，并查看第 5 页公式和 Theorem 1：归一化超图割松弛与特征值关系。它证明的是该无向目标的松弛性质。

映射：结构种子和谱对照。失配：输入方向、严格 FIFO、内存依赖、等分带宽、Cache 次序都不在矩阵中；谱下界不是本题下界。

### L7 — max-plus 与离散事件系统

François Baccelli, Guy Cohen, Geert Jan Olsder, Jean-Pierre Quadrat. **Synchronization and Linearity: An Algebra for Discrete Event Systems.** Wiley, 1992. ISBN 0-471-93609-X. [作者在线书入口](https://www.rocq.inria.fr/metalau/cohen/SED/book-online.html)；[TU Delft 全文](https://repository.tudelft.nl/file/File_681d1849-7274-4560-a103-aeb57d4d87ee)。

读取 §3.2.3.1 Theorems 3.17 / 3.20 的闭包、最小解及证明，和后续相关 max-plus 线性系统段落。DAG 情况闭包有限。

映射：固定执行图的端口传递、消元、组件组合。失配：共享带宽请求到达和 FIFO hit/miss 会改变转移，因此整个题目不是一个常系数 max-plus 系统。

### 没有当作已读定理使用的文献

检索到但未成功取得原文相关部分的 multilevel acyclic partitioning、closure、fair queueing 文献没有拿来补定理。近年 M5 专项第三方论文只见检索摘要的，也不作为硬件收益证据。所列结构构造不宣称已完成新颖性检索或独创性证明。

## 14. 官方硬件 / SDK 来源

访问日期统一为 2026-09-23。

- **H1** NVIDIA, CUDA C++ Best Practices Guide 13.4：<https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/>。实际核对 profiling、数据搬运/批量、浮点非结合性与端到端收益原则。
- **H2** NVIDIA, CUDA Programming Guide 当前版本：能力表 <https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/compute-capabilities.html>；DPX <https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/cpp-language-extensions.html#dynamic-programming-extension-dpx-instructions>；Math API <https://docs.nvidia.com/cuda/cuda-math-api/cuda_math_api/group__CUDA__MATH__INTRINSIC__SIMD.html>。原生/多指令映射须按当前表和实际目标验证。
- **H3** NVIDIA 设备能力查询：<https://developer.nvidia.com/cuda/gpus>。目标机可运行 `nvidia-smi --query-gpu=name,compute_cap`，再记录驱动、显存等；本会话没有运行目标机查询。
- **H4** Apple, 2026-03-03, M5 Pro/M5 Max 官方发布：<https://www.apple.com/newsroom/2026/03/apple-debuts-m5-pro-and-m5-max-to-supercharge-the-most-demanding-pro-workflows/>。系列规格不能当成本机配置。
- **H5** Apple, Metal What's New：<https://developer.apple.com/metal/whats-new/>。Metal 4 和 M5 tensor 加速用途。
- **H6** Apple, Metal Feature Set Tables, 2026-05-21：<https://developer.apple.com/metal/Metal-Feature-Set-Tables.pdf>。读取 SIMD/64 位整数/原子与同步相关表格，并实际查看相应 PDF 页截图。
- **H7** Apple, Resource synchronization：<https://developer.apple.com/documentation/metal/resource-synchronization>；CPU/GPU events <https://developer.apple.com/documentation/metal/synchronizing-events-between-a-gpu-and-the-cpu>；managed vs shared resource <https://developer.apple.com/documentation/metal/synchronizing-a-managed-resource-in-macos>。

## 15. 交付结论

有严格数学支撑的收益首先是：**合法候选的构造、输入关联维度的压缩、固定片段的状态消元与可审计下界**。这些支撑不等于已有官方优化成绩。

下一项最有价值的证据不是再写一个理论名称，而是：在冻结源码上，用这三条路线各自最有判别力的输入族，测量“相同总预算下的 E0 最好 Makespan / 合法率 / 精确评估次数”，同时保留会击穿代理的失败例。若官方收益不成立，应替换该路线，而不是换包装。
