# Coherent Research Glossary v1 · 已发送原文

来源：第四路回答3a0cc3b9及A/B/C本轮补充提问；三路所收文本逐字一致。此文件保存本轮共同工作定义，后续amendment仍须单列。

【补充协议：Coherent Research Glossary v1 —— 本轮所有术语的唯一工作定义】

请暂停当前推导，先完整读取本补充协议。

从现在起，本轮研究中以下术语均以本协议为共同工作定义。不要依赖你对这些词的一般理解，也不要依据其他 session 中可能存在的不同表述自行换义。

如果你认为某个定义数学上不合适，可以提出 Definition Amendment，但不得静默修改含义。提出修改时必须明确写出：

1. 原定义；
2. 发现的问题；
3. 建议的新定义；
4. 修改会影响哪些已有命题、实验和 Codex 任务。

在没有完成 amendment 之前，继续使用本协议定义。

本协议的目的不是提前断言这些数学结构一定存在，而是保证三个并行 Pro 在研究同一个对象。

==================================================
0. 基础对象与符号
==================================================

【D00-1：研究环境 / Evaluation Environment】

定义一个冻结研究环境：

E = (G, q, k, C, H)

其中：

G：
一张具体 case JSON 所定义的原始计算图，包括 ops、tensors、edges 以及所有官方语义需要的原始字段。

q：
问题语义，q ∈ {Q1,Q2,Q3}。

k：
核数。

C：
官方配置，包括容量、DDR 带宽、Task wait、cross-core delay、Q3 Cache 参数等所有会影响官方执行语义的配置。

H：
官方 evaluator 的冻结代码身份，例如 commit/hash/源码集合 hash。因为 evaluator 实现版本发生变化时，即使 G,q,k,C 相同，也不能默认是同一个数学映射。

因此后续说“固定环境”时，默认以上五项均固定。

--------------------------------------------------

【D00-2：合法方案空间】

记

P_E

为环境 E 下所有能够通过官方方案合法性检查的提交方案集合。

方案至少由官方允许的：

node_to_subgraph
core_schedules

确定。

这里“合法”只表示属于官方允许的方案输入域。

不要把：

“plan JSON 格式合法”

“Task-order 合法”

“最终执行一定成功”

“性能良好”

混成同一个概念。

如果研究需要，可进一步定义分层合法域：

P_plan
P_task
P_exec

但必须说明具体使用哪一层。

--------------------------------------------------

【D00-3：官方完整行为】

对 P ∈ P_E，官方程序执行后产生的不仅是 Makespan，而是一整条确定性计算过程。

研究中把完整行为记为：

B_E(P).

B_E(P) 可以包含以下层级：

L0：输入方案结构
L1：Task / COPY 构造后的结构
L2：Step1 结果
L3：Step2 spill / backing / incarnation 等结果
L4：Step3 Pipe FIFO / memory dependency 等执行结构
L5：全局事件模拟轨迹
L6：最终 result

并非所有层都必须由现有 CLI 原生输出。

如果某层需要额外 instrumentation 才能观察，必须注明：

“这是对冻结官方语义的只读观测”

而不是修改官方语义。

==================================================
1. 官方映射
==================================================

【D01：Official Mapping / 官方映射】

在固定环境 E 下，定义官方映射：

F_E : P_E → B_E
                                           (CRG-01)

其中：

F_E(P) = 官方程序按冻结语义对 P 产生的完整行为。

因此，“官方映射”不是：

P → Makespan

这么一个标量函数。

Makespan 只是官方映射的一个投影：

M_E(P) = π_M(F_E(P)).
                                           (CRG-02)

其他诸如 spill bytes、COPY、Cache hit、release time、DDR contention 等也都是 F_E(P) 的不同观测投影。

除非特别说明，本项目后续说“研究官方映射”，指研究 F_E 的结构，而不是只拟合 M_E。

==================================================
2. 映射族
==================================================

【D02：Mapping Family / 映射族】

令 Θ 为一组允许变化的研究参数。

定义：

FAMILY(Θ) = { F_E : E ∈ Θ }.
                                           (CRG-03)

Θ 可以包含：

G：图结构轴
q：Q1/Q2/Q3 语义轴
k：核数轴
C：硬件/规则参数轴
H：实现版本轴

研究时必须说明当前映射族允许哪些轴变化、哪些冻结。

例如：

“固定 G,H,C，只改变 q,k”

与

“跨 100 个 G，同时改变 k”

不是同一个映射族实验。

==================================================
3. 行为观测与行为签名
==================================================

【D03：Observation Map / 行为观测映射】

定义一个显式选择的观测映射：

Φ : B_E → Z_1 × Z_2 × ... × Z_m.
                                           (CRG-04)

Φ 决定研究者实际比较哪些官方行为。

例如可以包含：

Task 数与边界
COPY 图
COPY bytes
Step1 sequence
spill victim
backing
incarnation
Step3 FIFO
memory dependencies
关键 release time
DDR busy intervals
Cache hit/miss
Makespan

不同研究问题允许使用不同 Φ。

禁止在没有指定 Φ 时说：

“两个方案行为一样”。

--------------------------------------------------

【D04：Behavior Signature / 行为签名】

定义：

σ_Φ(P) = Φ(F_E(P)).
                                           (CRG-05)

这是方案 P 在指定观测 Φ 下的行为签名。

行为签名可以是：

精确完整对象；
结构哈希；
分层特征；
压缩摘要。

如果使用压缩摘要，必须说明它是否可能发生碰撞或丢失未来行为信息。

==================================================
4. Regime 与 Guard
==================================================

【D05：Guard】

Guard 是官方映射内部或研究抽象中一个明确的离散条件：

g : state → {0,1,...}

其取值改变会导致：

控制流、
结构选择、
依赖关系、
资源处理方式、
或某种离散执行决策

发生变化。

例如：

是否 overflow
选择哪个 spill victim
是否生成某 COPY
某 Cache 请求 hit/miss
某 FIFO 队首是否可发射

都可以形成 guard。

单纯：

“某 Makespan 从 10000 变成 10001”

不是 guard crossing。

--------------------------------------------------

【D06：Regime】

首先选择一个离散决策签名：

ρ(P).

ρ(P) 由研究者明确指定的一组 guard / active-set / ordering decisions 构成。

定义一个 regime 为：

R_r = { P ∈ P_E : ρ(P)=r }.
                                           (CRG-06)

因此 regime 永远是：

“相对于某个 ρ 定义的 regime”。

不存在不说明分辨率的绝对 regime。

一个非常细的 ρ 可能导致每个方案单独成为一个 regime；
一个过粗的 ρ 又可能掩盖真正的切换。

这本身就是需要研究的问题。

--------------------------------------------------

【D07：Guard Boundary / 切换边界】

对于某个 guard g，如果方案空间中的局部编辑使：

g(P) ≠ g(P')

则称该编辑跨越了 g 的 guard boundary。

这里“边界”不要求方案空间具有连续欧氏几何。

它是离散方案图上的切换边界。

==================================================
5. Primitive Operation
==================================================

【D08：Primitive Operation / 底层操作】

Primitive operation 不是任意 heuristic。

定义一个 primitive a 为带类型的部分映射：

a : D_a ⊆ P_E → P_E
                                           (CRG-07)

其中 D_a 是它的适用域。

每个 primitive 必须定义：

1. 操作对象；
2. 前置条件；
3. D_a；
4. 确定性输入参数；
5. 输出方案；
6. 输出合法性条件；
7. 修改了哪些方案字段；
8. 是否有逆操作；
9. 构造成本；
10. provenance。

可能的候选包括：

split
merge
task/subgraph move
core reassignment
within-core insertion
adjacent swap
priority refinement

但这些只是候选，不预设为最终 primitive 集。

--------------------------------------------------

【D09：Cross-environment Operation】

改变环境本身的操作不能直接当作 D08 的同类 primitive。

例如：

k 核 → k+1 核

应记为：

c_k : P_Ek → P_E(k+1)

的跨环境 continuation operator。

后文单独定义。

==================================================
6. 编辑大小 / Operation Distance
==================================================

【D10：Edit Size】

为了定义“局部”和“敏感”，必须先定义编辑大小。

禁止只说“这是一个小改动”。

定义一个明确的编辑度量：

d(P,P')

或操作成本：

c(a;P).

它可以是多维的，例如：

改变的 op 数
改变的 subgraph 数
改变的 Task 数
改变的 core assignment 数
改变的 order relation 数
partition boundary 变化数

推荐保留多维 edit signature：

e(P,P') =
(e_partition,
 e_assignment,
 e_order,
 ...)

而不是一开始强行压成单个标量。

如果需要单标量，权重必须显式给出。

==================================================
7. 离散局部响应 / “离散雅可比”
==================================================

【D11：Local Response / 离散局部响应】

给定：

固定 E，
方案 P，
primitive a，
P ∈ D_a，
行为观测 Φ，

定义：

J_a^Φ(P)
=
Δ_Φ(
    Φ(F_E(P)),
    Φ(F_E(a(P)))
).
                                           (CRG-08)

这里 Δ_Φ 是针对每个观测对象显式定义的差异算子。

不同分量不能默认都做普通减法。

例如：

数值：
difference / ratio

集合：
symmetric difference

序列：
edit distance / changed positions

图：
edge/node delta

事件轨迹：
event alignment / causal diff

因此 J 不是普通连续 Jacobian。

“离散雅可比”只是本项目对：

一组 primitive 对一组行为观测的有限响应结构

的简称。

如果给定 primitive 集 A={a_1,...,a_n}，可以定义：

J_A^Φ(P)
=
{ J_a^Φ(P) : a ∈ A, P∈D_a }.
                                           (CRG-09)

它可以是稀疏表、张量或图，不要求是矩阵。

==================================================
8. 耦合度
==================================================

【D12：Coupling / 耦合】

耦合不允许只做语言判断。

建议至少分为三个量：

A. Layer coupling

设行为观测被分成 L 个机制层，
第 l 层变化度为 r_l。

给定阈值 τ_l，定义：

C_layer
=
[Σ_l w_l · 1(r_l > τ_l)]
/
[Σ_l w_l].
                                           (CRG-10)

B. Object coupling

衡量一次编辑影响到多少远端 Task/op/tensor/event。

例如：

C_object
=
|受显著影响且不在编辑局部邻域内的对象|
/
|可观察对象总数|.
                                           (CRG-11)

C. Propagation distance

在原始依赖图 / Task 图 / execution graph 中，

从直接编辑对象到最远显著响应对象的图距离。

因此推荐使用：

CouplingSignature =
(C_layer, C_object, C_distance, ...)

而不是一开始制造一个任意总分。

如果研究者希望定义其他 coupling metric，可以 amendment，但必须可计算。

==================================================
9. 敏感方向
==================================================

【D13：Sensitive Direction / 敏感方向】

敏感方向不是连续空间的真实向量。

定义一个操作族 A_s 在研究域 S 中是：

(ε,δ,α)-sensitive

当且仅当：

1. 编辑大小满足 c(a;P) ≤ ε；
2. 行为响应大小 R(J_a(P)) ≥ δ；
3. 上述现象在 S 中至少达到指定稳定度 α。

其中：

ε：
“小编辑”的阈值；

δ：
“显著行为变化”的阈值；

α：
稳定性要求，例如实例比例、邻域覆盖率或置信下界。

因此必须区分：

single-witness sensitivity
local sensitivity
cross-graph sensitivity
cross-core sensitivity
cross-q sensitivity

单个极端例子只能成为 sensitive-direction candidate，
不能自动称为稳定敏感方向。

==================================================
10. 行为等价
==================================================

【D14：Immediate Observational Equivalence】

给定 Φ：

P1 ≡_Φ P2

当且仅当：

Φ(F_E(P1)) = Φ(F_E(P2)).
                                           (CRG-12)

这只是“当前观测等价”。

它不保证未来经过编辑后仍然等价。

--------------------------------------------------

【D15：Behavioral Equivalence Relative to Future Operations】

给定：

观测 Φ，
允许未来操作集合 A，

定义：

P1 ~_(Φ,A) P2

要求：

对所有同时合法的有限操作序列

w = a_t ∘ ... ∘ a_1,
a_i ∈ A，

两边具有相同的可执行性结构，并满足：

Φ(F_E(w(P1)))
=
Φ(F_E(w(P2))).
                                           (CRG-13)

如果两边允许的下一步操作集合本身不同，也不能视为强行为等价。

这是一个接近 deterministic bisimulation / Nerode equivalence 的研究定义。

实际计算可能无法验证“所有有限 w”。

因此工程实验可以定义：

H-step behavioral equivalence

只检查长度 ≤ H 的 continuation，

但必须明确标为有限视野近似，不得冒充完整等价。

==================================================
11. 行为商
==================================================

【D16：Behavior Quotient】

给定等价关系 ~_(Φ,A)，定义：

Q_(Φ,A)
=
P_E / ~_(Φ,A).
                                           (CRG-14)

也就是把行为上无法由未来允许操作区分的方案归为同一类。

研究“行为商是否有价值”的关键量不是名字漂亮，而是：

compression ratio

例如：

κ =
|P_sample|
/
|Q_sample|.
                                           (CRG-15)

如果 κ≈1，则在当前观测和操作集下几乎没有压缩价值。

==================================================
12. 最小充分状态
==================================================

【D17：Sufficient State】

给定：

允许未来操作集 A，
未来观测 Φ，

状态映射：

S : P_E → Σ

称为充分状态，当：

S(P1)=S(P2)

足以推出：

P1 ~_(Φ,A) P2.
                                           (CRG-16)

也就是说，知道 S(P) 后，不需要保留完整历史方案，就足以预测所有允许 continuation 的未来可观察行为。

--------------------------------------------------

【D18：Minimal Sufficient State】

相对于固定 (Φ,A)：

最理想的抽象最小状态就是 D15 的行为等价类：

S_min(P)
=
[P]_(~_(Φ,A)).
                                           (CRG-17)

这在抽象意义上总可以定义。

但研究真正关心的是：

它是否存在一个比完整方案/完整执行历史明显更紧凑、可计算的 representation。

因此：

“抽象 quotient 存在”

绝不能被写成：

“我们已经发现了一个有用的最小充分状态”。

有用的 minimal sufficient representation 必须同时考虑：

压缩率、
构造成本、
更新成本、
未来预测能力。

==================================================
13. Local Evaluator Set
==================================================

【D19：Local Evaluator】

一个 local evaluator 不是全局黑盒 surrogate。

定义第 r 个局部评估器：

ĥ_r

附带：

适用域 detector D_r(P,a)
预测目标 T_r
误差/置信度模型 U_r

它可以预测：

ΔMakespan
候选 pair ranking
是否值得进入 E1/E0
某个局部机制量

而不必预测绝对 Makespan。

--------------------------------------------------

【D20：Local Evaluator Set】

定义：

L =
{ (D_r, ĥ_r, U_r) }_r.

必须包含 routing / abstention：

如果：

没有 detector 接受；
多个模型强烈冲突；
不确定性超过阈值；
检测到 guard crossing 风险；

则：

ABSTAIN

并回退到更精确 evaluator。

因此：

局部评估器集的正确性目标

不是“任何地方都给答案”，

而是：

在声明适用域内有高可靠性，
域外可靠拒答。

==================================================
14. 生成完备 / 可达完备
==================================================

【D21：State Graph】

给定 primitive 集 A，

构造有向方案图：

Γ_A = (P_E, E_A)

其中：

P → P'

当且仅当存在 a∈A，

a(P)=P'.

--------------------------------------------------

【D22：Pairwise Reachability Completeness】

如果任意：

P,Q ∈ P_E

都存在 Γ_A 中从 P 到 Q 的有限有向路径，

则称 A 对 P_E：

pairwise reachability complete。

这是很强的要求。

--------------------------------------------------

【D23：Rooted Generative Completeness】

如果存在一个或一组 canonical seeds S0，

使得任意 Q∈P_E 都能从某个 P0∈S0 到达，

则称 A：

root-generatively complete。

它比 D22 弱，但对 solver 可能已经足够。

--------------------------------------------------

【D24：Restricted Completeness】

如果只能覆盖：

P'_E ⊂ P_E，

必须显式写：

“A 对 P'_E 可达完备”。

禁止把受限空间的证明推广成完整官方方案空间。

--------------------------------------------------

注意：

生成完备是“表达能力”的概念。

它和：

实际搜索复杂度

完全不同。

一个生成完备 primitive 集仍然可以在线只探索极少的 macro。

==================================================
15. Macro Operation
==================================================

【D25：Macro Operation / 宏操作】

Macro 不是“把几个 heuristic 打包”。

定义 macro m 至少包括：

m =
(g_G,
 g_R,
 π,
 A_m,
 Ω_m)

其中：

g_G：
图结构适用条件；

g_R：
mapping regime / guard 条件；

π：
内部 primitive policy / composition；

A_m：
允许调用的 primitive；

Ω_m：
预期机制与可观测结果。

它仍然是 partial transformation。

Macro 必须能够回答：

为什么现在适用？
内部执行了什么？
预期改变哪个机制？
如果失败如何 rollback？

==================================================
16. 多核尺度轴
==================================================

【D26：Core-count Axis】

把：

k=1,2,3,4,5

看成映射族中的离散尺度轴。

不是五个互不相关的问题。

记：

E_k = (G,q,k,C,H).

研究目标包括：

方案结构如何随 k 变化；
敏感方向是否跨 k 稳定；
guard 在什么 k 翻转；
峰值机制是否随 k 保持。

--------------------------------------------------

【D27：Core-count Continuation】

定义一个 continuation：

C_k :
P_(E_k)
→
P_(E_(k+1)).
                                           (CRG-18)

它不是单纯重新运行 solver。

它利用已有 k 核方案结构产生 k+1 核初始方案。

一个最简单的 embedding 可以是：

保留原方案并加入空核，

前提是该问题语义和官方合法性允许。

随后再通过：

move
split
reorder
macro

释放新核的并行度。

必须区分：

“可行嵌入”

与

“性能改善”。

==================================================
17. 官方固定单核基准与 Speedup
==================================================

【D28：Official Single-core Baseline】

对于图 G，

官方 singlecore_evaluate.py 产生一个固定基准：

B(G).

其语义是：

所有 eligible 计算 op 合入一个子图 / 一个 Task，
放到 core0，
经过官方单核执行流程。

它不是：

算法能够得到的理论最优单核结果。

--------------------------------------------------

【D29：Official Speedup】

对于 q、k 和方案 P：

Speedup_q,k(G,P)
=
B(G)
/
M_(G,q,k,C,H)(P).
                                           (CRG-19)

因此出现：

Speedup > k

在数学上并不矛盾，

因为 B(G) 不是单核最优值。

多 case 平均 speedup 必须按官方题面规定：

先逐 case 算 speedup，
再做规定的汇总；

不要擅自改成 aggregate-Makespan ratio。

==================================================
18. Peak Witness
==================================================

【D30：Peak Witness / 峰值见证】

“峰值见证”和“峰值机制”必须严格区分。

定义一个峰值见证：

W =
(E, P, R_ref, y)

其中：

E：
具体环境；

P：
具体方案；

R_ref：
明确的参考集合/基线；

y：
观察到的高收益行为。

例如：

某 case，
Q3，
4 核，
resource-word plan，
Makespan=63768，
相对官方单核 baseline speedup>7

可以是一个 peak witness。

但它本身不是机制。

“高”必须相对于显式参考定义，例如：

top-p quantile
relative improvement ≥ δ
speedup ≥ threshold
相对同预算 baseline 的异常高收益

不得看到一个漂亮数字就自行叫峰值。

==================================================
19. Peak Mechanism
==================================================

【D31：Peak Mechanism / 峰值机制】

峰值机制不是某组参数，也不是某个 JSON。

它是一个条件性结构命题。

一个候选峰值机制 M 至少包含：

M =
(S_G,
 S_P,
 S_q,
 S_k,
 S_C,
 S_R,
 O,
 ΔY)

其中：

S_G：
图结构条件集合；

S_P：
方案 / 操作条件；

S_q：
问题语义适用集合；

S_k：
核数适用区间/集合；

S_C：
配置适用域；

S_R：
official-mapping regime 条件；

O：
触发的 primitive / macro；

ΔY：
稳定出现的高收益响应。

也就是说，它表达的是：

当图具有结构 S_G，
系统位于 regime S_R，
满足问题/核数/配置条件时，
执行 O 会通过某个可解释的官方映射变化产生显著收益。

--------------------------------------------------

一个单独的：

case008 + resource_word + k=4

只能支持：

“存在一个 witness”。

要升级成“mechanism”，至少应有：

1. counterfactual 邻居；
2. 可识别的行为变化；
3. 图结构条件；
4. 可证伪迁移预测；
5. 至少某种稳定性证据。

==================================================
20. 图结构特征
==================================================

【D32：Graph Feature】

图结构特征必须定义成：

x_i : G → X_i

的可计算函数。

例如：

DAG width
depth
fan-out distribution
tensor-size distribution
M/V workload ratio
repeated motif count
reuse topology
weak-component structure
critical-output structure

均必须有算法定义。

禁止把：

“这个图很规则”
“这个图很并行”
“这个图像流水线”

直接当 feature。

这些只能是提出 feature 的直觉。

==================================================
21. Structural / Local / Accidental Peak
==================================================

【D33：Structural Peak】

如果候选峰值机制在预先定义的图结构邻域、多个实例、多个核数或一片参数域中保持稳定，并达到指定迁移阈值，则称：

structural peak。

阈值必须预先给出。

--------------------------------------------------

【D34：Parameter-local Peak】

如果机制只在较窄：

k / config / regime

区域中稳定，

但在该区域内可重复，

称：

parameter-local peak。

它仍然可能很有价值。

--------------------------------------------------

【D35：Accidental Peak】

如果轻微改变：

图结构、
操作、
核数、
或局部 regime

就使收益不可重复，而且无法找到有预测力的条件变量，

则暂称：

accidental peak。

注意：

“尚未找到机制”

不等于已经证明是 accidental。

==================================================
22. Peak-to-Mechanism Distillation
==================================================

【D36：Peak-to-Mechanism Distillation】

定义研究流程：

Peak Witness
→ Counterfactual Neighborhood
→ Layer-wise Behavior Diff
→ Candidate Cause / Guard
→ Graph Structural Condition
→ Mechanism Hypothesis
→ Cross-instance / Cross-k / Cross-q Test
→ Guarded Macro Candidate.

这叫：

Peak-to-Mechanism Distillation。

最终产物不是“最优参数表”，

而是：

可识别条件
+
可执行操作
+
可证伪预测。

==================================================
23. Algorithm Distillation
==================================================

【D37：Research Solver】

Research solver 首要目标允许是：

可观测
可重放
可干预
可归因
可组合

而不一定是最快。

它可以记录：

operation provenance
intermediate signatures
behavior diff
evaluator route
rollback
counterfactuals

--------------------------------------------------

【D38：Algorithm Distillation】

Algorithm distillation 指：

把已经验证的：

primitive
guard
macro
regime detector
routing policy
缓存/索引结构

压缩成竞争版 solver。

它不是简单：

“把代码写快一点”。

一个有效 distillation 必须给出：

质量损失 ΔQ
运行时间变化 ΔT
内存变化 ΔM
失去的可解释能力

并有明确接受阈值。

==================================================
24. “少数敏感方向”假说
==================================================

【D39：Low-dimensional Sensitive Structure Hypothesis】

“官方映射存在少数敏感方向”

目前只是研究假说，不是事实。

它的可证伪版本应类似：

在指定方案邻域和 primitive 集 A 中，

只有较小比例的 operation classes

能够解释大部分显著 Makespan / behavior variance。

可以用例如：

前 r 类 operation 对响应能量/显著事件的解释比例

来测量。

如果需要接近完整 operation basis 才能解释变化，

则“少数敏感方向”假说失败。

==================================================
25. Coherent Framework 的关系链
==================================================

本项目当前提出以下待证伪关系：

Official Mapping
        ↓
Local Response / Discrete Jacobian
        ↓
Coupling + Guard Crossing
        ↓
Sensitive Directions
        ↓
Behavioral Equivalence / Quotient
        ↓
Compact Sufficient State?
        ↓
Mapping Family / Core-count Scaling
        ↓
Peak-to-Mechanism Distillation
        ↓
Local Evaluator Set
        ↓
Primitive + Guarded Macro
        ↓
Research Solver
        ↓
Algorithm Distillation.

重要：

这不是必须全部成立的理论体系。

任何箭头都允许被实验否定。

例如完全可能最终得到：

行为 quotient 没价值，
但 peak mechanism 很有价值；

或者：

Q1 强耦合，
Q2/Q3 局部结构明显；

或者：

局部 evaluator 不值得做，
但 exact batch + macro search 很有效。

这都属于成功研究结果。

==================================================
26. 统一证据等级
==================================================

后续请对所有关键结论标记证据等级。

建议：

E0：冻结官方 evaluator 直接确认的具体行为/成绩。

E1：
与官方语义严格对齐、已通过相应等价验收的精确加速 evaluator 结果。

FORMAL：
数学证明或代码语义直接推出的结论，并明确假设域。

EMP：
有限实验支持的经验命题。

HYP：
当前研究假说。

AUTHOR-REPORT：
仓库/其他 Pro 报告中存在，但本 session 未独立回读关键证据。

不要把不同等级混在同一句结论中。

==================================================
27. 三位 Pro 的共同研究纪律
==================================================

1. 所有关键词按本协议使用。

2. 不因为一个漂亮实例就宣称一般规律。

3. 不因为一个反例就错误否定一个有明确适用域的局部规律。

4. 所有“局部”“低维”“耦合”“敏感”“等价”“充分”“完备”“峰值”
都必须带明确域和度量。

5. Q1/Q2/Q3 不得被默认认为具有相同结构。

6. 1–5 核不得被默认认为只是同一个算法换 k。

7. 图 G 本身是一等研究变量。
尤其峰值研究必须同时研究：
图结构 × 操作 × q × k × config × regime。

8. 强制保存负例和反事实。

9. 代理量不能自动替代最终 Makespan。

10. 所有新理论最终至少要回答一个工程问题：

- 是否提高同预算 E0-confirmed 方案质量？
- 是否提高平均 speedup？
- 是否降低精确评价调用数？
- 是否降低达到同质量的时间？
- 是否增加候选覆盖？
- 是否获得跨图/跨核稳定机制？

==================================================
28. 本补充协议与你原任务的关系
==================================================

请在吸收以上定义后继续你原先被分配的专题：

Pro A：
官方映射结构、局部响应、耦合、guard、行为商、最小充分状态、局部评估器集。

Pro B：
映射族、图结构、多核尺度、Peak Witness、Peak Mechanism、Peak-to-Mechanism Distillation。

Pro C：
primitive partial transformations、生成完备性、操作组合结构、macro、research solver、algorithm distillation。

三位都必须理解全部定义，
但主要思考预算仍放在自己的专题。

最终输出时：

如果使用某个术语，
必须符合这里的定义。

如果你认为定义需要修改，
单独增加：

Definition Amendments

章节，

不得在正文中偷偷改变含义。
