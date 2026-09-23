# R4-Q1-A1：勘误影响重审与情况 A 可用性审查

## 0. 审查结论

本补丁不替换原 R4 报告、代码或实验身份。当前工作目标收束为第一问/情况 A。

**核心结论：R4-1/R4-2 的限定域零-spill证书没有被 backing 勘误推翻；能迁移到 Q1 的是“实际 Task 边界图＋官方 Step1 序列”的区间判定，不是 Q2/Q3 的 singleton 编排器。**

最应带入 Q1 的新增细节是：合并既改变边界COPY，也可能使一个有初始COPY_IN backing的Task输入变成没有该backing的内部计算结果。即使逻辑换入次数不变，spill字节也能改变。不能把边界节约直接当成总搬运节约。

本轮给出一条落地路线：**真实Task编译剖面驱动的有界拆分/cover合并构造**。其可证明护栏是联合DAG、cover条件、真实序列的零spill判定、按Task边界统计，以及纯计算加Task等待的下界。候选优先级与共享DDR时延估计仍是启发式，最终经E0确认。这里没有宣称已经实现并验收新的Q1强求解器。

## 1. 实际材料与身份

### 1.1 原交付保留

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| HuaweiCup_A_R4_Report.md | 23235 | `02e6cccc1df586fba9e58719c82a98a7aee0adbd86eae4bf74e49e469dbc2b6f` |
| HuaweiCup_A_R4_Evidence.zip | 33942056 | `878df15f4d66672bd625b43a59bbc8fc543febe61bfe778a24017a5f04a4c4d4` |

解压在独立审计工作目录。原包1664项payload全部通过原manifest核验。官方源码聚合哈希仍为：

`de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`

原包src与measured_source中3处差异均为打包后的路径替换；差异原文另存`results/legacy_packaging_only.diff`。不把打包版SHA冒称实际测量版SHA。

### 1.2 已通过授权GitHub连接完整读到

仓库`Vioano/huaweicup2026`，固定提交`e1575a1de5e3b921aef350e920720f0584fb1719`。未使用匿名网页或默认分支代替。

| 文件 | 返回的Git blob SHA |
|---|---|
| results/a/review/q1-form-65d6c0e/REVIEW.md | `d3a6a697d8e1ba773c2211de77d081addf0810a9` |
| src/review/q1_form_semantic_probes.py | `5615927b00b913235d2ab51e46af6cbd21ff8932` |
| results/a/review/q1-form-65d6c0e/probes-v2/summary.json | `c8f279e11aa2a202488d0423f7df39d020a9f26e` |

三份都取得完整文本。远端summary中的环境是Python3.12.13/macOS27 ARM；本次本地新实验是Python3.13.5/Linux x86_64，不混为同一环境。

### 1.3 仍只能依据转述/尚未取得

- 三路最新勘误自查意见来自用户本轮转述；没有下载它们的新代码或证据。本报告不以其一致意见代替证明。
- 远端原Mac运行的完整`spill.step2.json`、CLI JSON和trace没有下载来做跨环境逐字段比较。已读的summary报告这些字段一致；本地另用字节一致的图/plan进行了新CLI复验。
- 原R4主要成绩、合成标签本轮没有重新执行。这次做的是全部记录的哈希/JSON数值绑定检查；不能写成117次性能复现。
- 没有取得“在未暴露错误FORM的情况下会如何选研究方向”的反事实记录。无法排除方向偏置，也不凭此认定勘误已经造成某个损失。

### 1.4 本轮执行边界

17次Q1完整CLI：16成功，1有意联合环拒绝；对成功项，所有标准化函数字段与未插桩CLI对应字段相等。30次Task级Step2观察包含重复分区对照，25次零spill、5次有spill。代码和配置前后哈希不变。

没有新正式case性能运行，没有Q2/Q3新CLI，没有外部文献检索、训练、GPU或仓库写操作。

## 2. 逐项影响矩阵

| 原结论/实际前提 | 勘误依赖链 | 结论 | 证明、反例与最小动作 |
|---|---|---|---|
| R4-1：Q2/Q3 singleton桶的原始张量闭区间给出无spill分配峰值。要求合法二部、至多单生产者、限定root/leaf COPY、合法局部优先序。 | 使用Q2边界COPY的桶归属与Step2分配/释放顺序；不使用spill重命名/写回分支。 | **保留限定域理论；收紧测量对象。** | 输入COPY在首消费者桶，输出COPY在生产者桶；每桶当前计算处同时包含该操作输入/输出。原56例比较的是spill前边界图序列，不是seq_ext。Q1改用实际Task原始Step1，不能套原桶式。 |
| R4-2：所有区间峰值不过容量 iff 无spill。 | 第一次溢出前没有任何pending spill，因而不依赖backing/version/新化身pos。 | **保留，右侧明确为成功返回且records为空。** | 第一溢出时刻归纳证明见§3。异常不能算“没有spill”；不得把证书失败当方案非法。 |
| 前沿压力与容量筛选可构造较好顺序。 | 当前前沿是无spill反事实；按容量而非真实backing回读代价优先。 | **保留为Q2启发式；Q1不迁移编排器。** | 没有发现固定spill2×size硬剪枝，但有真实的容量偏好/机会偏差风险。输入按core记忆仅适用于B的Task组织。Q1按Task重建，保留允许spill的候选。 |
| Banker检查保守安全完成。 | 私有profile固定、共享输入全程预留、独立作业可自由交错；未涉及spill展开。 | **保留抽象模型的充分条件；不作为Q1可提交完成证书。** | 见§5；Q1无法提交该模型任意作业内顺序。原实现共享预留拒绝不是E0非法。 |
| 整数增量前沿与原构造等价。 | 未见张量字节与引用数不变量；同一个近似候选评分，非E0状态。 | **保留整数不变量；有限运行等价不升级全域。** | §6；14组是已记载对照。整数表示范围与浮点有限性是实现前提。Q1可重用关联索引方法，不重用算子就绪决策。 |
| 60图240候选标签来自E0，MLP与非学习对照。 | 调用原样evaluate_scene_b，完整result取makespan/spill字段。 | **保留原Q2标签与实验身份；停止Q1迁移。** | 全240份JSON与标签绑定一致；仅7份正spill标签，不足以证明分支覆盖。无须重训；Q1新候选必须另取Q1标签。 |
| 62819/66901/77846等官方成绩及有限候选选优。 | E0源码未改变；候选规则可能有偏，而真值由E0决定。 | **数值保留；因果解释收紧。** | 117份CLI绑定核验：Q2 98、Q1 4、Q3 15。不能把Q2数值当Q1成绩；“搬运不变”只排除字节量解释，不独立证明M/V机制。 |
| R4程序有Q1入口，关闭singleton。 | Q1分支仍调用旧packet_assignment的B式500延迟与双Pipe代理。 | **入口兼容不等于Q1专用构造。必须重做这层代理。** | core.py中500及2ceil是跨核通信启发式不是spill规则。Q1整Task独占核，同核Task还要100等待，按Task读输入；仅替换500数字不够。 |

独立`certify_plan.py`含范围检查，但`Frontier.result()`、`banker_order()`内部同名`no_spill_certificate`未完整调用该护栏。后续调用必须明确场景/输入域，或将内部字段重命名为counterfactual_no_spill_profile。此项是接口边界审查，不改变旧E0结果。

F-EXEC-001的错误量词没有在本次检查的R4自写筛选器中作为“有空核就跳过”的实现出现。原评估始终交冻结官方函数。原24/44叙事也未进入R4计算工作下界。以上均只针对实际读取代码，不推断所有未留存研究思路。

## 3. 零spill证书：为什么与backing展开分支正交

### 3.1 对真实Step1序列的通用版本

对一个实际非空Task，在官方已经重建边界COPY后的图上，取官方Step1完整序列。对每个被触达的非DDR张量，按该序列记录生产/消费操作的首末位置；同一操作重复关联去重，单次使用的张量也参与本次峰值。

\[
M_{T,r}(i)=\sum_{t:\operatorname{pos}_T(t)=r}s_t\,
\mathbf1\{f_{T,t}\le i\le \ell_{T,t}\}.
\tag{R4A-01}
\]

这里的i包括生成的COPY，不是只数计算操作。pos取Task本地图，不能盲用原图；原DDR若已映射成UB，应按局部UB计数。DDR backing本身不计私有容量。

在Step2合法输入契约下：

\[
\max_i M_{T,r}(i)\le C_r\quad\text{对所有私有内存类型成立}
\quad\Longleftrightarrow\quad
\text{Step2成功返回且spill\_records为空}.
\tag{R4A-02}
\]

**证明。** 第一步之前驻留为零。假设此前没有spill，则每个张量在首个关联操作分配，在末个关联操作执行后释放；当前操作分配后、释放前的驻留恰为闭区间和。因此若每一步不过容量，while分支永不进入，pending_spills一直为空，随后版本/backing展开循环也为空，返回无spill。

反向取反事实profile第一次超容量的位置。在此前归纳仍成立，没有可使轨迹分岔的spill；到达该位置时官方驻留也超容量。它必须进入spill分支，留下记录或报告无法分配，不可能成功返回空记录。已有backing只在后续将pending_spills展开为COPY/新化身时决定写回、ID和版本，不改变此前归纳。

这不是对任意调用错误、空图接口或非法pos的统一行为证明。证书成功也不证明Step3/全局执行成功或makespan最优。

### 3.2 原R4-1是该判据在singleton桶上的精确压缩

限定的Q2/Q3构图中，COPY_IN标到首个本核消费者桶，COPY_OUT标到唯一生产者桶。源张量有后续本核消费者时，其区间仍延伸到最后消费者；没有后续消费者时输出COPY只在生产者桶内延后释放。没有新增非DDR中间对象跨出这些桶。因此每个桶最大值在其计算操作分配后取得，计算位置的闭区间和与完整COPY序列峰值相等。

这段压缩需要原护栏；不需要UB恒定、新DDR、版本1或固定COPY对等错误规则。原56份观察支持的是这个限定命题，而不是spill后物理峰值预测。

### 3.3 Q1不能删除COPY端点——新反例

在观察到COPY端点差异后定点设计的`results/projection_false_negative/`严格二部合成图，单计算操作容量符合题面保证。在**同一个真实Q1 Step1顺序**上：

- 删除COPY后只按计算触达计，L1峰值393219 bytes，错误判断不过524288容量。
- 保留真实边界COPY，闭区间峰值524292 bytes，超过容量4 bytes。
- 官方Step2实际插入1条spill记录，spill字节262146；未改Q1 CLI makespan13134。

此处不是推翻原Q2桶证书，而是推翻它的无条件Q1迁移。实际COPY_OUT可以将末端延长；合并后Step1也会重排，不能拼接两个旧profile。

## 4. backing作用域与条件搬运：Q1合并必须新增的一项检查

### 4.1 准确的Step2字节恒等式

设m是某logical tensor在这个Task中的换入记录次数，B0是对**该Task传入Step2的边界图**运行_find_copy_in_backings得到的初始backing集合。冻结代码保证同一logical tensor初始无backing时最多新写回一次；以后复用。

\[
D^{\rm spill}_T
=\sum_{e\in\mathcal R_T}s_e(1+\mathbf1\{e\text{实际写回}\})
=\sum_t s_t\left[m_{T,t}+\mathbf1\{m_{T,t}>0,\ t\notin B_{0,T}\}\right].
\tag{R4A-03}
\]

这是字节统计恒等式，不是时延公式，也不允许删掉实际COPY节点、版本、pos、顺序与内存依赖。已有两次回读是两次size；无初始backing的两次回读是三次size，非四次。

### 4.2 状态不跨Task继承

Q1按子图重新生成独立局部graph；每个输入边界都有本Task自己的新DDR节点与COPY_IN。每次调用Step2重新建立type_active、pending_spills、backing_by_tid、current_incarnation、incarnation_version。前一个Task的Python字典不传给后一个Task。

记录中的`original_copy_in`意为“本次Step2输入图已有的COPY_IN”，未必是整张原图中的COPY_IN。计算中间结果跨Task进入消费者时，也能成为消费者Task里的这种初始backing。相同logical ID跨Task不等于同一驻留化身或同一backing字典。

_find_copy_in_backings只识别COPY_IN来源；不要因为已有一个输出边界COPY_OUT，就自动宣布该内部张量已有初始backing。

### 4.3 新合并对照

同一严格二部原图；tensor10002由计算操作1产生，之后在计算操作2至8中反复使用。只改划分：

| 项目 | producer单独Task，后续另Task | 合成一个Task |
|---|---:|---:|
| tensor10002换入版本 | 1、2 | 1、2 |
| 第一次记录 | original_copy_in，无COPY_OUT | new_spill_out，有COPY_OUT |
| 第二次记录 | original_copy_in，无COPY_OUT | reused_spill_out，无COPY_OUT |
| 该tensor换入/写回字节 | 524288 | 786432 |
| 全图partition_added_copy_bytes | 524288 | 0 |
| 全图spill_added_copy_bytes | 1572864 | 1835008 |
| 全图scheduled_copy_bytes | 2883584 | 2621440 |
| Q1 makespan | 48203 | 43729 |

合并节约边界524288，但增加spill262144；净搬运节约仅262144。该例合并仍更快，所以它不证明“失去backing必然不该合并”；它证明合并估价必须重算backing与真实Step1/Step2。时间差不能全部归因于某一项字节变化。

### 4.4 对队长反例的复验和输入域补充

按读到的脚本重建原反例，graph/plan字节SHA分别与远端summary中的`0ce778...e5d2`和`170e4f...a890`相同。本地新Q1 CLI得到43728，tensor10002的两个spill_out_id均None，L1版本1/2复用同backing，函数/CLI对应字段一致。

进一步检查发现，该原微图含两条Op→Op边，且有非DDR叶张量；所以它是冻结CLI可达机制反例，不能原样称为严格题面二部输入。本审计用允许的零字节L1张量替代直接边，并补三条最终COPY_OUT，得到另一张满足所检二部/DDR边界/单算子容量条件的合成图。该新图同样重复L1换入，恰也得到43728，但图、原始搬运量、ID均不同，绝不合并两份实验身份。

## 5. Banker：保留的是一个抽象模型充分条件

R4实现把共享张量按核全程预留；每个私有作业使用固定内部拓扑序，预计算每个前缀的当前分配和未来最大峰值。设共享预留为S，当前私有分配为A，未来最大私有峰值为R。在当前转移的瞬态分配也合法的前提下，若存在活动作业的完成排列，使逐个完成时都满足：

\[
\max(0,R_{j,r}-A_{j,r})
\le C_r-S_r-\sum_{h\in\mathcal A}A_{h,r}
+\sum_{h\text{已在该完成排列中完成}}A_{h,r},
\tag{R4A-04}
\]

则这个完成排列提供无spill的串行完成见证。完成一项后归还其私有分配，按排列归纳即可。未开始的作业可等所有活动项归还后逐个启动，前置的单作业＋共享预留容量检查保证可启动。该检查可保守：不能把未找到串行完成排列等同不存在任何更精细交错完成方式。

其证明不涉及spill重命名分支。但在Q1，Task内部操作顺序由官方产生；不同Task也不共享持续驻留，故该见证不是一般Q1可提交计划的安全证书。把job改名为Task不能修复此差异。当前停用其Q1候选筛除用途，不重新训练或扩展Banker。

## 6. 增量等价与筛选偏置

### 6.1 增量不变量

每个待选操作保存“尚未在本核seen集合出现的相关张量字节”。首次引入tensor时，沿其本核关联操作列表各减一次size；以后不再重复减。该值与原定义逐步相等；live、rem仍由相同Frontier.put更新，因此候选容量判断相等。

就绪短名单中的前驱结束最大值由边增量更新，与原扫描max相等。若IDs、tail、字节和度数均落在所用int64范围，时钟为有限binary64值，排序键/最终Python评分保持一致，则在唯一ID破同分的条件下，可对每次选出的操作作归纳。原14组是有限实测证据，不是替代这些表示前提的全域证明。

该结论证明两个近似构造器相同，不证明它们等于E0。Q1可以使用张量关联计数与区间事件索引，不应继续把Task内部ready_order当作可提交变量。

### 6.2 没有固定2×size硬剪枝，仍不排除偏置

core.py约第102行的`500+2*ceil(size/60)`出现在packet跨核放置代理，解释为B场景两端传输＋同步，不是按spill事件收费。ready_order、Banker、MLP标签读取均未使用“每次spill必有COPY对”的硬剪枝。

但前沿对超容量和驻留压力有明确优先级，且没有真实backing状态。已有backing大输入的廉价回读，与内部计算结果首次写回不作区分；这可能降低一些好spill候选进入E0的机会。这个可能性由代码可见，不是已测损失量，也不能证明起因必是错误FORM。原case004的较快候选有spill，说明该流程并非把所有spill计划直接判死，但不证明没有偏好损失。

## 7. 原数字、标签与因果解释

全部117份CLI的plan/result哈希、makespan及五项搬运字段重新核对一致；其中Q1只有4次，都是跨场景失败边界对照：008的157796/553796、044的175649/257016。62819、66901、77846主要是Q2，不能当Q1质量证据。

60图240份合成结果的labels/spill逐项与完整E0 API JSON一致，标注代码调用Q2 evaluate_scene_b，未用旧FORM重写真值。正spill标签仅7份，完整backing分支覆盖未测。冻结结果，不因文档勘误重标旧标签，也不把它们改作Q1标签。

“同图、同归属、五项搬运相同、无spill”排除了新增字节和spill数量差异，却未固定COPY相位、内存复用边、队首等待、DDR重叠。故将“主要来自M/V流水”的解释下调为需要路径级分析的机制假说。固定构造器、只改压力参数的对照可说明该参数干预的总效应，但不独立识别“减少内存压力”这个中介的因果贡献。044/046两权重输出相同，不能给压力项归功。

原求解器只按实际E0结果选优，不使用证书值替代官方指标，因此勘误不自动改变已确认计划的数值；候选池外遗漏仍未知。

## 8. Q1真正能用的接口、表示与护栏

### 8.1 Task边界字节是按划分计算的精确量

对Task T和张量t，I表示在T有消费者但无生产者；O表示在T有生产者，且有外部计算消费者、原COPY_OUT消费者或无计算消费者。冻结Q1每个满足条件的Task—张量端点分别建一个COPY。

\[
B(\Pi)=\sum_{T\in\Pi}\sum_t s_t\,[I_{T,t}+O_{T,t}].
\tag{R4A-05}
\]

它是spill之前的scheduled COPY字节，与同一划分的分核/核序无关。减去原图COPY量才是partition_added。source输出只算实际创建的一个COPY_OUT；不能把它按每个消费者重复算。某条跨Task依赖合并时可能省2次size，也可能只省消费者的一次size；共享输入并组通常省一份输入读取。输出是否还被其他Task使用决定是否仍需写回。

在单生产者条件下，合并不会增加这份spill前边界量：输入端点集合只会去重/内化，输出的外部消费者集合只会收缩。但这不约束spill或时延。

即使同核两个Task共享同一输入，也分别重建输入COPY。新微图同核分两Task读取总16384 bytes，合并后12288；反向核序或把两Task放不同核都不改变这份边界统计。

### 8.2 Task门控不能换成逐边相加

全部真实前驱完成后，其门控时刻为：

\[
R_T=\max\left(0,\ f_{\mathrm{prev}(T)}+100\ \text{若存在同核前项},\
\max_{U\in\operatorname{pred}(T),\ c(U)\ne c(T)}(f_U+1000)\right).
\tag{R4A-06}
\]

100/1000来自本次固定配置；实现应读取配置，不隐藏硬编码。入边约束取max，不累加所有等待。远端消费者等**整个生产Task结束**，不是某个COPY_OUT一结束就启动。

两对新CLI对照（与此前类似机制数字不合并身份）：

| 机制 | 分开 | 合并 | 时间线证据 |
|---|---:|---:|---|
| 远端出口被延后 | 6014 | 11005 | 远端Task开始1012→6003；源Task结束12→5003 |
| 引入额外入口门控 | 9015 | 14005 | 原可0时刻开工的A合并后要等远端，合并Task开始9002 |

两对各自搬运五字段相同且零spill。这里结合Task门控代码和时间线证明了具体等待机制，不仅凭相关性归因。仍不声称全部时差只来自一项：入口对照中远端自身结束还因DDR争用从8003变成8002。

### 8.3 固定划分的局部准备不随核序/分核改变

固定原图、分区及sgid、官方版本/配置时，Q1先按sgid生成局部图、调用Step1/2/3，最后才附加core_id和pred_tasks元数据。由代码数据依赖可知：只改合法分核/Task核序，不改变局部图、Step1序列、spill和本地准备的运算部分。

新微图在反转Task顺序、分到两核、追加空核的三种变化下，局部图/Step1/完整Step2观察全部相同。该实验未单列完整Step3对象比较；对Step3的延伸依赖其输入固定与确定性，而非把本次实验写成已比较该层全部字段。

可先缓存不可变局部profile来给分核/顺序候选使用。不要缓存运行后已被修改的Task状态字典。**划分改变时另论**：全局边界ID游标可能使后面未改成员的Task也换ID，Step1破同分及Step2 spill ID可能随之变化。最低安全键是实际有序本地图字节＋配置＋源码；不能只按成员集合缓存或认为“只改这两个Task”。

## 9. 共同拓扑序、cover与可用核数

### 9.1 允许任意共同序并不缩小核序表示域

令H为Task数据依赖图加上每核相邻Task顺序边。

\[
H\text{是DAG}
\quad\Longleftrightarrow\quad
\exists\tau\in\operatorname{Top}(D_\Pi):\
\tau|_{c^{-1}(k)}=\sigma_k\quad\text{对每个核 }k.
\tag{R4A-07}
\]

向右：H任一拓扑序都保持每核链的全部相对次序，限制到该核恰为给定σ。向左：若存在该共同序，则数据边与核序边都向前，H不可能有环。

因此“用一个共同拓扑序表示计划”本身不是保守子族。**预先固定某个τ**再只投影它才限制了可选核序；以固定操作拓扑序做连续分块也限制可选划分。有限启发式产生的少数τ当然不等于穷尽全部，但限制来自生成器，而不是存在性表示。

本次混合长度核反例，商图与直接同核依赖检查通过，但联合环被官方拒绝；空核没有让它提前返回。

### 9.2 最优值与具体分配

在允许空核的官方域，给计划末尾追加一个空核不改变现有Task图、ID、分核、事件和带宽负载。故可行计划有保值嵌入：

\[
T^\star_{K+1}(G)\le T^\star_K(G).
\tag{R4A-08}
\]

这不表示某个重新分配的具体方案或某个启发式随核数单调改善，也不适用于额外要求每核必须非空的不同问题。本次同一计划追加空核396→396，只是有限回归；一般结论依赖上述嵌入证明，不依赖旧24/44。

### 9.3 相邻同核合并与拆分

在已为DAG的H中，相邻同核A、B有顺序边A→B。保持其他核序不变并把它们收缩，得到：

\[
H/(A,B)\text{是DAG}
\quad\Longleftrightarrow\quad
H\text{中不存在除直接边外、经过其他Task的 }A\leadsto B\text{路径}.
\tag{R4A-09}
\]

若存在替代路径，收缩成环；若收缩成环而原图无环，展开合并节点后只可能得到这样的A到B外部路径。是对**联合H**的cover检查，不是仅对数据商图检查。

反方向，把一个Task沿某个合法内部拓扑前缀拆为两个同核相邻Task，内部依赖只向前；任何新外部环投影回原H会成环，故结构合法。用于选拆分位置的Step1只定义成员前缀，最终两个Task仍需各自重新生成边界和官方Step1，不能提交截断的旧序列。

两条都是结构命题，不是性能单调性或全E0成功保证。

## 10. 直接可用的Q1硬剪枝：计算工作＋Task屏障下界

对给定计划P，每个Task的最短持续时间至少为本Task总M工作、总V工作及内部纯计算关键路径的最大值：

\[
\ell_T=\max\{W_{T,M},\ W_{T,V},\ CP_T^{\rm compute}\}.
\tag{R4A-10}
\]

在H上为同核相邻边设100、跨核真实依赖边设1000、同核数据依赖边设0；同一有序对多条约束取最大。按H的拓扑序递推：

\[
L_T=\ell_T+\max\left(0,\max_{U\to T\in H}(L_U+w_{UT})\right),\qquad
LB(P)=\max_T L_T\le E_0(G,P). 
\tag{R4A-11}
\]

证明对H归纳：实际Task持续时间不短于必做计算；每个实际开始时间满足相应Task完成等待。忽略COPY、spill和DDR只使该下界更小；无需把浮点流体DDR公式冒充E0下界。

因此 **LB严格大于已确认incumbent makespan** 的候选可淘汰；相等时仍可能改善次要搬运，不因该下界直接淘汰。零spill失败不能充当此类合法硬剪枝。

`q1_guards.py`已实现。对已保存的15个成功微图计划检查均满足下界。出口坏合并的LB为11000，大于原6014；入口坏合并的LB为14000，大于原9015。这两例能在无需模拟候选DDR细节时就证明“不可能改善当前时延”。这不是普遍能识别所有坏合并：大量DDR主导候选的下界仍很松。

## 11. 只推荐这一条本地Q1路线

**路线名称：Task真实编译剖面驱动的有界拆分/cover合并。**

### 11.1 决策变量与种子

只输出非COPY算子划分、Task归属、每核Task顺序。串行包可以作为初始分区种子，但不是不可拆的同Task约束。初始共同Task拓扑序只是一个启发式起点，不宣称完整搜索空间被固定。

Q1列表分配应维护每核一个“整Task占用到何时”的时钟：用本Task官方局部准备时间作为候选估价，门控按100/1000的max规则。不同Task不可用跨Task的M/V虚拟交错来互相隐藏工作；M/V并行只发生在官方Task内部。输入COPY按Task计，不扣“本核以前读过”的字节。局部准备时间只作无跨核DDR争用的参考，非真实固定工期。

可以利用§8.3先把给定分区置于一个临时合法的单核Task拓扑序中准备局部profile，再独立选择实际分核与核序。临时顺序只用于提供合法编译上下文，不固定最终搜索中的共同拓扑序，也不是实际答案；准备成本必须计时。

种子先完整E0确认并写出；若种子失败或超预算，不能把未确认候选作为返回答案。

### 11.2 从一个确认计划提出少量有意义的改变

1. **拆分候选**：从实际Step1区间profile的高驻留位置、首次overflow前后、早产远端输出之后、晚到外部输入之前，提出极少量计算前缀切点。切点只决定分区成员。重新编译子Task，观察输入/输出COPY与backing是否变化。
2. **合并候选**：只看相邻同核Task，先做联合cover检查；优先检查大内部接口、重复输入或关键同核100等待的边。必须重建真实并集Task；不拼接旧Step1，不相加旧内存峰值。
3. 对候选计算式(R4A-11)；严格超incumbent则安全停止。其余用真实边界字节、入口/出口门控变化和Step2条件spill来排序。这些排序是启发式，不是收益证明。
4. 不以“证书失败”删除所有spill候选。至少给一个有已有backing/有限spill但可能减少门控或边界的候选机会；正/负内存风险只是标签。
5. 每轮仅将预定少量候选（例如最多4个）交完整E0，选择时延优先、同分看搬运，保留已确认基线。4是首版预算旋钮，不是数学常数或性能保证。限定轮数和父进程截止，不做遍历所有分区的暴力搜索。

核心变更与次要资源排名可以分开：固定分区先比较少数分核/Task核序，只复用已证明相同的局部profile；分区一变就失效相应实际编译签名，并始终完整E0确认。

### 11.3 已证明与未证明的分界

**已证明或直接来自源码：** 共同序表示；cover收缩和同核前缀拆分的联合DAG合法性；实际Step1的零spill判定；按Task边界字节；条件spill字节；固定分区局部输入独立于分核/核序；计算屏障下界。

**仍是启发式：** 初始包的粒度；可见切点选择；隔离Task时长加门控作为共享DDR估价；优先哪个merge；只评少量邻居能否获得有竞争力的正式成绩。

**缺的关键性能命题：** 尚未证明接口/profile分数能可靠预测共享DDR下的合并增益；尚未证明该有限邻域对实际大图足够，或整个编译/搜索能在全部单例预算内完成。不存在“合法＋少搬运＋零spill就不变差”的命题，本次入口/出口反例已否定这种闭合方式。

### 11.4 复杂度瓶颈

预先索引原图张量—操作关系，边界统计和区间扫描可按触达关联线性组织；联合DAG与下界是Task图线性扫描；单次cover可达性检查最坏线性于Task图。若每轮只检查b个邻居、固定R轮，这些护栏的可控部分约为初次索引加Rb次局部/Task图扫描。

但这**不是整个求解器复杂度**。冻结Q1 builder对每个Task扫描全tensor表，直接用它准备许多细Task会有Task数乘tensor数的成本；Step1深度传播与Step2多次victim排序、Step3、全局事件都必须计入。分区改变引起全局生成ID移动，也限制了prepared缓存的简单局部失效。第一版应限制候选/Task数量与受影响块尺寸，端到端计时包括基线、局部编译、E0和落盘；不能先宣布线性或5分钟全域保证。

### 11.5 最少的否证检查与实施门槛

本补丁已经给出：混合核联合环；闭区间等于容量；删COPY导致错误零spill；重复初始backing；首次写回后复用；合并失去初始backing；按Task重复输入；入口/出口坏合并；下界拒绝坏合并。这些测试足以击穿对应的错误实现，不能替代正式质量比较。

实现这条路线后，首个质量检查只需预列三类小实例：独立共享输入、带远端入口/出口、容量临界且有backing重用。相同总单例预算下与Q1种子比较，记录完整E0调用、回退、超时、时延及搬运。若策略连这三类机制都无法按预期工作，先停并修正；不立即扩成100例或训练项目。正式图质量与最大图耗时仍待真正求解器完成后验证。

## 12. 最小交接接口

- `profile_task(actual_graph, actual_step1_seq, config)`：区间、真实COPY接口、初始backing与真实Step2记录；带图/序列/配置/源码hash，声明pre-spill而非物理峰值。
- `joint_guard(plan)`：联合DAG、共同拓扑见证；不能遇空核就跳过。
- `merge_guard(A,B)`：相邻同核cover条件；失败只说明该保持其他核序的合并不合法，不代表所有重排后合并都不合法。
- `candidate_bound(plan)`：式(R4A-11)，只作makespan下界。
- `evaluate_confirm(plan)`：未修改E0，独立输出目录；非法、异常、超时分开，保留原incumbent。

原R4的Q2排序器、Banker编排器和MLP不进入Q1主链。接下来的实现围绕以上五个接口，不再默认启动下一轮广泛检索或训练。

## 13. 证据与复现

- `PROVENANCE.json`：原件哈希、授权GitHub读取、环境与边界。
- `results/original_records_audit.json`：117 CLI、240标签和56/14记录的只读绑定核验。
- `results/probes_v1/summary.json`：前16次Q1 CLI、原始图/计划/完整结果/trace/log。
- `results/projection_false_negative/`：第17次CLI及实际/错误投影profile。
- `results/guard_checks.json`：对前15个成功计划的下界、cover及共同序检查；零新增E0调用。
- `results/gating_timelines.json`：从新完整结果抽取的入口/出口时间线，不另跑分。

在旧证据包解压目录含official/code和official/data/config.txt时，使用：

```bash
python -B verify_audit.py
python -B src/audit_original_records.py --evidence-root /path/to/HuaweiCup_A_R4_Evidence --output results/local-record-audit.json
python -B src/probes.py --evidence-root /path/to/HuaweiCup_A_R4_Evidence --output results/local-probes
python -B src/projection_counterexample.py --evidence-root /path/to/HuaweiCup_A_R4_Evidence --output results/local-projection
python -B src/check_guards.py --evidence-root /path/to/HuaweiCup_A_R4_Evidence --probe-results results/local-probes --output results/local-guards.json
```

新probe输出目录必须不存在。probe脚本不修改E0文件；完整结果与运行环境按本地新身份保存。审计数学命题可用于设计，但此包不是全FORM、E1/E2或Q1求解器验收。

## 源码定位（冻结原件）

- Q1 `_build_scene_a_tasks`：`multicore_cut_evaluate_problem_1.py:70–196`；边界110–167；Step1/2与条件字节173–187。
- Q1 Task门控：同文件318–329。
- 联合环：`evaluation_validation.py:217–224`。
- Step2 uses及初始backing：`schedule_step2.py:39–149`；分配/检查/释放224–289；backing/版本/位置304–352；条件插入约380–383。
- Q2桶压缩前提：`multicore_cut_evaluate_problem_2.py:43–59,160–229,237–278`。
- R4护栏：`src/certify_plan.py`；内部元数据及启发式：`src/core.py:92–186`；`src/banker.py`；`src/fast_construct.py`；`src/synthetic.py`；`src/solve.py`。
