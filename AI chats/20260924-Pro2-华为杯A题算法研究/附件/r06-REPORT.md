# Pro B：映射族、多核尺度与 Peak-to-Mechanism Distillation

工作定义：用户提供的 Coherent Research Glossary v1（D00–D39）。本轮不修改定义，不宣称所有关系箭头都成立。

## 1. 实际读取 branch HEAD 与文件

所有仓库材料来自已授权 GitHub 连接 Vioano/huaweicup2026；没有以匿名网页判断私库可达性，没有使用旧上传包代替本次读取。

| 别名 | branch | 固定读取 HEAD |
|---|---|---|
| MAIN | main | f27ef37bb76dcf556f35d3f2328e405d92241d9c |
| Q1 | codex/q1-bounded-search-20260924 | 4dff90ef699fd51845cf482951e8477066f5f566 |
| Q2S | codex/q2-structure-nikolastarx | 74c46372faf5910b9b3cce6ad9a61a7e040b17aa |
| Q2B | codex/q2-budget-search-yuanzhifang | 0b58c123cccf02fc993b741d79dcd8511e4dd38f |
| Q3 | codex/q3-core-nikolastarx | a4e7ee13310d693ec4fb5cc236669ceb3b172d1f |
| EXACT | codex/q1-exact-batch-20260924 | 5bfe53a29c1ba05167239f51ea937e602f7f85b4 |
| NATIVE | codex/evaluator-native-probe-20260924 | 03f02e79de4b4bd6f55241385664b154f4332454 |

完整路径/读取范围见 READ_MANIFEST.json。特别阅读了 Q3 pilot metrics/REPORT/run、online REPORT、METHOD、AFFINE_LAG_EQUIVALENCE 和 construct.py；Q2S joint summary/metrics；Q2B STAGE_B、REPORT、metrics 与 candidates 前段；Q1 SEARCH、GUIDED_MOVES、PROFILE_REFINE、TRACE_EXPLANATION、TRACE_PROSPECTIVE 及关联摘要；EXACT 批量接口交付内容、NATIVE HANDOFF。

官方阅读包括 singlecore_evaluate 全文、Q1 核心范围1–380、Q2核心范围1–465、Q3核心范围1–704、Step1核心1–240、Step2核心78–273/294–490、Step3核心29–715，以及两类联合环验证和固定config。不是所有文件的逐行形式化证明。

FORM 使用固定65d6c0e6facee2ec8ce9694c30dd805de99abf7e的SPEC；勘误使用e1575a1de5e3b921aef350e920720f0584fb1719的REVIEW。读取MAIN的contract相关段和EVALUATOR_AMENDMENT全文。源码集合SHA256 de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0在已有manifest/运行记录中一致，但本轮没有重新计算整个集合。

### 本轮真正完成的独立检查

- 四份case008 plan的SHA256和Git blob SHA1都重算匹配。
- 三份Q3构造计划的有序mapping与操作核归属相同；只改变core_schedules。
- 两份压缩E0产物的前缀经base64解码、gzip流式解压，直接读到Q2/Q3的63768和相关头部字段；并未完成gzip CRC、完整JSON或Trace核验。
- 120个纯整数仿射排序模型、9600个参数点比较，区间条件与显式排序零差异。不是官方图或E0实验。
- 生成一个单插入反事实候选：core0把sg96从index14移到sg7前的index10。它尚未用G检查合法性、尚未评价。
- 新E0/E1调用为零；完整读取原始case JSON数为零。

### 读取缺口

原始图在15,375,730字节的data/raw/a/official-cases.zip中；已读取其Git树身份。授权fetch_file的base64内容为空，fetch_blob解UTF-8失败；这不是“ZIP不存在”。本轮没有恢复原始JSON，因此没有新跑singlecore，也没有独立检验全图结构分布。旧结果摘要的487605不能升级成本轮新跑的官方基准。

## 2. 精确术语表

以下是CRG v1的压缩索引，不另立工作定义。

| 术语 | 本轮使用含义 |
|---|---|
| 环境/合法域 | E固定G、q、k、C、H；区分P_plan、P_task、P_exec。执行失败不填零Makespan。 |
| 官方映射 | 两字段plan经Task/COPY、Step1、Step2、Step3、global simulation到完整行为/结果；Makespan只是投影。 |
| 映射族 | 明确允许变化的G/q/k/C/H轴的F_E集合；本轮H固定，G/q/k是主轴，C仅小量诊断变化。 |
| 观测/签名 | 每次指定Phi、差异算子、层级和精度。完整哈希与压缩摘要分开。 |
| guard/regime/边界 | guard是离散执行决定；regime相对于指定rho；固定E的局部编辑翻转guard才是D07边界，跨k/q/C是跨环境变化。 |
| primitive | 带参数和合法适用域的部分plan变换；split、merge、move、insert等只是候选规格。 |
| 编辑大小 | 保留分区、核归属、次序改变的多维数量；参数数目不是编辑大小。 |
| 离散局部响应 | primitive前后的指定观测差异；数值、集合、序列、图和事件分别比较，不当连续导数。 |
| 耦合度 | 按阈值计算层覆盖、远端对象比例及图传播距离；数据图不可达不代表资源耦合为零。 |
| 敏感方向 | 小编辑、显著响应、给定域稳定度同时成立；一个大macro的好结果不自动证明局部敏感。 |
| 行为等价/商 | 当前观测相同是D14；D15还要求未来操作可执行性与所有continuation不可区分。商的样本先去除相同plan。 |
| 充分/最小状态 | 对未来plan编辑充分，不只是仿真继续运行的checkpoint；抽象等价类存在不代表有廉价紧凑表示。 |
| 局部评估器集 | 每个模型有detector、目标、误差/不确定性；冲突、域外和guard风险时ABSTAIN并回退。 |
| 生成/可达完备 | root-generative、pairwise和restricted分开；本轮任何有限候选族均不宣称覆盖完整官方空间。 |
| macro | 图guard、regime guard、primitive policy、允许操作集与预期机制的部分变换；有失败回滚。 |
| 多核尺度/continuation | k是离散环境轴；利用旧plan迁移到k+1不同于冷启动重跑，也不同于保证更快。 |
| 单核基准/speedup | B(G)来自官方整图单Task单核固定启发式；CRG-19用B/M，Q3同k无Cache/有Cache比另列。 |
| 峰值见证/机制 | W是具体E/plan/reference/高收益；机制须同时约束G、P、q、k、C、rho并提出可迁移干预预测。 |
| 三类峰值 | 结构稳定、参数域局部稳定、暂定偶然都依赖预注册域/阈值；未知不等于偶然。 |
| 算法蒸馏 | 将验过的guard/primitive/macro/routing压成竞争程序，报告质量、时间、内存和可解释性损失。 |

## 3. 当前峰值事实与身份

### case008独立身份核对

| plan | SHA256 |
|---|---|
| component | c9e86dae0d8290112a9a8ec8a2fe1052f6edd18f0a1765706c7f0351cf70fdf9 |
| affine_eighth | 40ec77159696d284091f6926aab72b711ec682769434a32e14b54229b4ec7357 |
| resource_word | 1935d89ad16a59a52ad62b2e00b4b43f30e783ade40fe481fc6063d905da64ce |
| single_task，四槽位三空核 | 2d285913c029b56a5383d8624afb44ea4230ed1b3f480d65adf9856f74aa49ae |

同一Q3分支三方案都是864个singleton、每核216个。component到word有596个次序位置改变、1116对先后关系翻转；affine到word分别为720和3716。分数接近的64686不是只改一个primitive的邻居。新提出的单插入候选只改变5个位置/4对先后关系，但分数和执行合法性未知。

Q2 E0头部直接读到：word Makespan63768；每核Step3 local_makespan64215；每核570条memory dependencies；MTE2/MTE3/M/V条数为108/27/54/162；每核L1峰值55296、UB73920；COPY2654424、spill0、无跨核COPY。Q3头部直接读到63768、0 hit、432 miss。零spill不能推成无MEMORY_REUSE；local_makespan也不是自动有效的全局下界。

### 事实表

E0-read表示回读已归档官方产物的指定字段，不是本轮复跑。AUTHOR-REPORT表示报告/metrics/run已相互核对，但原始完整证据未在本轮独立回读。

| G/q/k | 基准/普通参考 | 当前候选 | 比例/改善 | 反事实状态 | 证据 |
|---|---|---|---|---|---|
|008/Q2/4|B记录487605；component123060|word63768|B/M约7.64655（基准待复跑）；普通/word约1.92981|affine64686非单primitive；新单插入未评价|word数值E0-read；基准AUTHOR-REPORT+源码等价条件|
|008/Q3/4|同上|同一word63768|与Q2相同，不能归功于Cache|0hit；同上|E0-read指定字段|
|008/Q1/4|B记录487605|另一个粗化plan113686|条件B/M约4.28905|不是word的Q1结果；近邻114685/122751为报告值|AUTHOR-REPORT|
|044/Q2/4|D125648|M2 69113|降低44.9947%|其他priority有74530/71242等，身份不同需分别绑定|AUTHOR-REPORT|
|002/Q2/4|D132209；M1 72415|joint-critical72056|相对M1降低0.4958%|同assignment的earliest_start92004|AUTHOR-REPORT|
|044/Q3/4|component89039|affine70261|降低21.0896%|hit率反而下降，spill也下降|AUTHOR-REPORT|
|080/Q2,Q3/4|component111466/90736|affine112445/83124|Q2变差0.8783%；Q3改善8.3892%|同plan跨q排名反转；新增spill229376|AUTHOR-REPORT|
|051/Q1/4|父338698|split336057|降低0.7798%|cut4/cut5；真正一次split；完整回读待PB00|AUTHOR-REPORT|
|044/Q1/4|父116227|好merge114443|降低1.5349%|坏merge126094；零spill split123168/123363|AUTHOR-REPORT|

基准487605见Q1 prototype single_task摘要，不是调用本次singlecore取得。四槽位plan已验字节；冻结Q1对最后追加空核的指标不变可由代码推导，但该证明不能替代基准数值的独立复跑。

## 4. 对峰值机制路线的总体评价

值得继续，但目前最强的是三个条件性机制候选，不是一个普适低维定理。

1. Q2/Q3资源重入交错：008同分区同分核的普通plan到word下降59292 cycles，恰等于运行报告中27个job的V工作总量。这个算术吻合支持“V等待被M工作覆盖”的待证伪解释，不证明DDR与memory dependencies贡献为零。源码word_descriptor仅校验计算链/时长，未校验完整Op–Tensor同构、输入共享、tensor size/pos。
2. Q1晚输入门控前缀分离：051的旧关键Task2722 cycles变为仍受晚输入门控的81-cycle尾部；前缀提前在6482–9674执行，尾部等到13007。旧路径其余119节点持续时间不变，2641-cycle差可做这条trace的精确账目。新排序在003/008/044三个前瞻池全为零，没有收益，所以应研究切点生成而不是继续调这个排序。
3. Q3共享输入/FIFO相位：080同一构造在Q2变差而Q3改善，是明确的场景交互线索。不能按Q2排名、零spill或hit率硬筛Q3；仍需完成准入/淘汰、backing与两带宽池逐事件对照。

044好坏merge是上述机制的强负对照：边界省得更多也可能更慢；旧backing复用规则要求把首次写回与后续reload分开，不允许固定双向spill计费。

本轮没有证实完整峰值见证集、跨图结构稳定性或全部核数稳定性。没有依据把尚未解释的峰值称为accidental。局部primitive全平也不能自动否定需要协同大编辑的macro；它只能否定相应小编辑敏感性主张。

## 5. 九条关键可证伪命题

|ID|命题与当前等级|最小反证/测量|任务|
|---|---|---|---|
|B1|重入链的资源词在图与mapping guard成立时，通过减少M队首等V的空隙产生可迁移收益。HYP，008有E0字段支持。|同工作量非重入负例；同计算链但共享输入/大tensor的反例；新匹配图。|PB01|
|B2|Q1 singleton屏障改变该编译机制，不能直接继承Q2/Q3理想流水收益。Task语义FORMAL，幅度HYP。|同一字节plan横跨q，观察Task数量、边界COPY、100/1000门控。|PB00/PB05|
|B3|具有晚到远端输入且存在不依赖它的前缀时，一次split可能把前缀移出关键等待。HYP。|前缀仍被本核前项卡住、生产者重定时或新增COPY抹掉收益。|PB02|
|B4|backing/pos/next-use比spill总字节更能定位merge/split guard变化，但不一定值得做代理。HYP；条件字节公式FORMAL。|成本模型仍系统误排、检测成本不抵评估节省。|PB03|
|B5|080排序翻转依赖实际FIFO准入相位与两池争用，可由执行前可计算条件在小域中预测。HYP。|同guard新邻居不翻转；只有事后hit率可解释。|PB04|
|B6|末尾追加空核在指定指标投影上保持旧执行；warm macro是否更好是另外命题。条件FORMAL。|保持全部旧ID/顺序仍产生时刻差则隔离域；warm比cold更贵则停用。|PB05|
|B7|固定G/k/assignment下，仿射完整排序的正整数lag原像是邻接比较约束的一个区间。FORMAL+9600纯排序检查。|边界±1出现字节不一致；强hash-dedup基线下没净构造收益。|PB06|
|B8|当前观测相同不保证未来primitive不可区分；只压相同lag-plan不能证明D16有价值。FORMAL定义后果。|对不同plan做有限continuation；若样本商压缩率接近1，停止该压缩路线。|PB00/Pro A|
|B9|少数预定义操作类能解释大部分响应，必须在未用于选变量的邻域稳定。HYP，不由一个macro峰值推出。|等编辑尺度/等抽样下仍需接近全操作类解释80%响应，则否定D39在该域的版本。|Pro A/C接口|

## 6. 图结构候选特征体系

所有纯图特征必须是G的可计算函数，实际Task压力/释放时间不是纯G特征。

|家族|算法定义/计算边界|用途与主要风险|
|---|---|---|
|深度/宽度|语义COPY收缩后DAG最长路；小图以传递闭包二部匹配求精确偏序宽度。大图只报规范Kahn前沿作为下界/代理。|宽且深不同于可资源重叠；最大层大小不自动等于width。|
|弱分量|无向化eligible邻接求分量，输出数目、大小分布、最大分量工作占比。|数据独立不等于DDR/Cache独立。|
|Pipe工作与重入|分Pipe累加max(1,cycles)；对真正串行分量读取压缩Pipe词与各阶段时长。|相同比率的非重入图为必要负对照。|
|重复结构|小型带Op/Tensor属性、端口、size/pos的同构核验；hash只用于预分桶。|现有word guard只证明计算时长模板一致。|
|共享support/输入束|输入tensor对应消费job集合，按精确集合分组并统计字节。|可压静态统计，不能合并真实cache key或访问次数。|
|fan-in/out|Op直接度数和tensor消费者数/字节加权分布分别统计。|度数不包含时序与源端MTE3逐目标成本。|
|size/pos|按L1/UB/DDR分布统计分位数、总量、同op输入输出并集。|归一化容量使用C，应标为混合环境特征。|
|关键出口|计算依赖图上的到出口最长尾工作量、出口覆盖；不是资源关键路径。|执行关键出口必须另由Phi_L5观测。|
|边界潜力|对固定、与分数无关的规范拓扑切线计算跨界tensor并集曲线。|只是G结构特征；实际Q1入口按Task，Q2按core计算。|
|驻留风险|规范拓扑下首次/末次touch闭区间前沿，按pos分开。|真实P下Step1/2/backing是另一个条件化状态，不能偷换。|
|乘积/grid|消费两个输入束的job作边，二着色+完整二部连接/重边/支撑闭合检查。|不是无约束最大biclique搜索；不匹配就退出。|
|复用拓扑/ID|support重叠、规范序列重用间隔、并列key下原ID顺序。|图同构不推出固定ID官方行为相同；ID扰动是新G。|

本轮只核验了这些特征的源码定义边界、已有报告中的实例值，以及计算模板守卫的不足；没有读取完整G后声称它们已具有统计预测力。下一步先只读扫描100G、不运行100例E0，再按预注册结构条件选少量匹配与反匹配实例。

## 7. 多核/Q1–Q3映射族研究设计

H与官方C0先固定，分开三种研究：固定G的q/k横向表；固定q/k的跨G迁移；极少独立诊断C变化。不同实验不能混成一个胜率。

### 核尺度

每一步保存冷构造、原plan追加空核、使用旧结构的一次continuation，且保留全部原ID/有序mapping。记录从k1开始的总成本与已有seed条件下的边际成本，不能把之前核数的研究当免费。

对008报告中的108个同质job，整job均衡分配的M工作下界随k1–5为250128、125064、83376、62532、50952；这些是条件性工作量界，不是本轮实测Makespan。每核job数、队列启动/收尾、输入支持复制和Cache首次miss相位都可随k改变。

### 横向q

Q1每sg一个Task，变化partition改变边界与屏障；固定partition改变assignment/order时局部编译可复用，但全局重放不能省。Q2/Q3每core一个Task，细sg可以控制优先级，但COPY归属和Step2/3都必须重建核验。相同P跨q不是同一个F_E，也不保证相同合法域。

Q3的CRG-19基准比与同plan、同k的Q2/Q3比单独保存。前者允许超过核数；后者才隔离给定计划下引入Cache的总效果。Cache hit率不等于其因果中介贡献。

### 数学语言

使用“带guard的参数化编译—离散事件系统”。rho至少分rho_compile（Task/COPY/Step1/spill-victim/backing/incarnation/FIFO/MEM）、rho_event（release决定者、退休/发射并列顺序、两资源池活跃集合、Cache决定）。有限相图只是这些rho投影的样本图；不宣称欧氏连续边界、全局分段线性或可微Jacobian。

同样Makespan可对应不同rho，rho改变也可因非关键分支而不改变Makespan。speedup曲线只能用来提出变点候选，需要行为签名确认。

### 参数轴的最早失效层

通过方案合法性检查后，还应区分哪些变化能复用局部编译、哪些必须重新准备：

|变化轴|最早可能改变的计算层|不可偷换的结论|
|---|---|---|
|Q1固定分区，仅分核/核序/Task wait|局部Task计算结构可复用；核心元数据、联合环和L5须重新处理|不是完整L1相同，也不是两个核的局部重放。|
|Q2同plan到Q3，DDR/L1/UB与复制同步参数相同|共享Task/COPY与Step1–3路径；差异进入Cache的L5|只在相同输入/源码行为下复用，不复用P2分数排名。|
|只改变Q3的L2容量/读带宽|L5准入、命中与两池事件|不是按命中率线性缩放。|
|改变L1/UB容量|L3 spill、L4内存复用与之后各层|不能只重算全局传输。|
|改变DDR带宽|L1 COPY参考属性、L4局部时刻/MEM及L5均可能变化|不能把已有Makespan按带宽倒数缩放。|
|改变分区或B场景子图优先级|L1边界/COPY所属或L2优先序，随后L3–L6|固定计算Pipe词不自动给出相同COPY/MEM行为。|

这些可复用层的条件，比笼统宣称“映射低维”更可执行。数据只给一次仿真checkpoint，不代表D17对未来plan edits充分。

## 8. 最小行为相图实验（提案，未运行）

全局最多64次新E0，含必要singlecore、只读观测对照、确认、失败。每项派发前从统一账本扣除；不是各模块各给64次。先回读可用原证据，能够复用的调用不重复；复用身份记录完整。

|模块|固定中心与比较|初始调用额度|
|---|---|---:|
|重入尺度|008普通/word，Q2/Q3，k1–5|20|
|Task屏障|008相同两份字节plan，Q1/k4|2|
|真正局部邻居|008两份已通过合法性检查的一次插入邻居，各Q2/Q3|4|
|入口门控|051父/cut4/cut5；两种独立等待诊断配置下的父/子|7|
|内存/backing|044父/好merge/坏merge/零spill坏split；两种临界容量诊断下父/子|8|
|FIFO相位|080两plan×Q2/Q3；两种L2临界容量诊断×两plan|8|
|固定单核|008/044/051/080各一次|4|
|只读观测/确认/失败预留|不得超总64，预算不足就保留unknown|11|

诊断配置只写独立副本、不修改官方C0；不是竞赛成绩。容量阈值由首轮trace给出候选，执行时若更早guard改变就更新解释为复合变化，不能假装只变了最终Cache淘汰。

每个W必须有显式普通参考、坏参考、单primitive候选、分层Phi与rho。当前保存的单插入是待验证种子，不把它的未评价状态填成0。

预注册高收益与稳定性例：资源词同核普通参考改善至少10%；Q1局部动作改善至少0.5%且至少1000cycles。用于未来结构性归类的规则建议：至少3个非简单复制的匹配图实例、至少3种核数，正域至少80%达到门槛；覆盖率、成本、最差回归同时报。这些是下一次试验的建议阈值，不是当前结论，也不能把同模板重命名的多个文件当独立图族。

如果仅一小段k/C/rho域稳定，记parameter-local；轻微扰动失败且预注册条件没有预测力，只能暂定该测试域内accidental。若没有足够测试，保持unclassified。

## 9. Codex /goal 候选任务

后面的任务卡为提案，不是已启动服务、已分配人员或授权长跑。完整机器可读版本见GOALS.json。PB00先补身份与反事实；PB01/PB02/PB03/PB04可在独立写域并行；PB05消费已冻结macro，trajectory内部顺序执行；PB06为次优先纯参数层工作。

本轮无需Definition Amendment。运行时、目录/文件名和数值编译设置额外固定为实验控制条件，不据它们未受控时的结果提出跨环境full等价。任何对这些控制的跨域扩展要另行声明。

---

# Pro B：Codex /goal 候选任务

状态：仅提出任务，未启动任何session、服务或新E0实验。术语采用CRG v1。

## PB00-WITNESS

### 命题

已有峰值能被固定计划、官方单核基准及真实单primitive反事实重放；不是同分不同plan或旧报告串接。

### 输入 / branch / commit

```json
{
  "Q3": "a4e7ee13310d693ec4fb5cc236669ceb3b172d1f",
  "Q1": "4dff90ef699fd51845cf482951e8477066f5f566",
  "Q2S": "74c46372faf5910b9b3cce6ad9a61a7e040b17aa",
  "Q2B": "0b58c123cccf02fc993b741d79dcd8511e4dd38f",
  "files": [
    "results/a/q3-nikolastarx/pilot-20260924/run.json",
    "results/a/q2-nikolastarx/joint-20260924/summary.json",
    "results/a/q2-yuanzhifang/stage-b-20260924-042906/candidates.csv",
    "results/a/q1-profile-refine-20260924/summary.json",
    "data/raw/a/official-cases.zip"
  ]
}
```

### 允许修改范围

research/peak_B/PB00-WITNESS/ 与 results/a/peak_B/PB00-WITNESS/<new-run>/；只读导入其他分支。

### 禁止修改范围

不得修改官方源码/原图/固定config原件、FORM与contract、既有实验记录；不得更改Cache/FIFO/带宽/等待语义，不提交等待/预取/重算；不得覆盖生产solver或其他session目录，不自动扩大预算。

### 实验协议

使用冻结commit和原字节SHA256，所有完整计划保留mapping插入序；协议先写盘并固定G/q/k/C/H、Phi/rho、primitive参数、edit signature、选择与停止规则。新输出独立目录，原版E0结果/Trace/日志完整保留；失败、超时、unsupported分别计账。只读观测器需同输入有/无观测全函数结果对照，并与未插桩CLI对应；成本全部计入。原配置成绩与研究配置/合成图分开。E1仅在相应已验收域使用，最终E0确认。任何曾见008/044/080/002/051/003/014/084/095都不是新封存图。 先提取并验源manifest。重算008/044/080/051的singlecore；核对008三个已验哈希plan；完整回读044合并、051拆分和080跨q记录，明确缺项才补E0。每个中心保存普通plan、较差plan以及按精确primitive定义生成的邻居；例如008仅在core0将sg96插入sg7前，是待校验候选，不预称合法。每类一个观测器无副作用回归；新增E0总上限32，研究墙钟上限20分钟。

### 输出

W.json、原图/plan/config/H/run身份、L0-L6检查点、所有反事实/失败及单核基线完整CLI产物。

### 验收指标

计划SHA256/Git blob一致；基准来源真正为singlecore；每个完成W至少一个单primitive边；观测未改变官方结果。缺失域明确标unknown，不能用摘要补full。

### 反证 / 停止条件

任一身份或原分数不一致即隔离该W，停止该域机制归纳；32次或20分钟耗尽停止。缺合法单primitive邻居不包装成已完整蒸馏。

### 依赖

无；消费现有primitive接口时先固定其定义，不等其他新研究。

### 可并行性

基线/证据校核可按图并行，但共享主账本防重复；计时比较串行。

### 预计资源

CPU 1 worker/子任务，建议2 GiB采样停止阈值；最多32 E0。工程时间估计半天，非承诺。

### 成功后解锁什么

其他任务共享可信W和基准；提供Pro A局部响应输入。

## PB01-REENTRY

### 命题

同质计算链M→V*→M在Q2/Q3的适当guard下，资源词通过隐藏V等待产生可迁移收益，而不是Cache或单个JSON巧合。

### 输入 / branch / commit

```json
{
  "Q3": "a4e7ee13310d693ec4fb5cc236669ceb3b172d1f",
  "files": [
    "src/q3/construct.py",
    "docs/a/q3/METHOD.md"
  ],
  "witness": "PB00/008"
}
```

### 允许修改范围

research/peak_B/PB01-REENTRY/ 与 results/a/peak_B/PB01-REENTRY/<new-run>/；只读导入其他分支。

### 禁止修改范围

不得修改官方源码/原图/固定config原件、FORM与contract、既有实验记录；不得更改Cache/FIFO/带宽/等待语义，不提交等待/预取/重算；不得覆盖生产solver或其他session目录，不自动扩大预算。

### 实验协议

使用冻结commit和原字节SHA256，所有完整计划保留mapping插入序；协议先写盘并固定G/q/k/C/H、Phi/rho、primitive参数、edit signature、选择与停止规则。新输出独立目录，原版E0结果/Trace/日志完整保留；失败、超时、unsupported分别计账。只读观测器需同输入有/无观测全函数结果对照，并与未插桩CLI对应；成本全部计入。原配置成绩与研究配置/合成图分开。E1仅在相应已验收域使用，最终E0确认。任何曾见008/044/080/002/051/003/014/084/095都不是新封存图。 固定ordinary component与resource_word同分区/分核，先分析008 M头阻塞与M/V区间交集。预登记小型同质正例与同工作量非重入、共享输入、变tensor-size反例；不改变原图字节。原正式图只读特征扫描后选2个未用于当前规则调参的匹配/反匹配样本；没有匹配样本如实报告。本任务主做跨G且k=4，跨k完整矩阵交PB05。新增E0≤32。

### 输出

graph guard（不能仅叫同构）、mapping guard、M/V/COPY/MEM差异、迁移表、原词的primitive分解及rollback。

### 验收指标

在预定正域中相对同核ordinary≥10%改善的比例≥80%，且新增图有非零覆盖；008账目中V阻塞减少预测经完整Trace核对。域外失败可预测并拒答。

### 反证 / 停止条件

仅008有效、相同guard新图反复回归>5%、解释需删除COPY/MEM，或guard成本不抵节省则降级；不可因b>2a被当前构造拒绝就声称所有资源词均无效。

### 依赖

PB00；Pro C提供primitive policy身份。

### 可并行性

可与PB02/PB03/PB04并行，独立写域；不抢同一性能测量主机。

### 预计资源

CPU 1 worker，2 GiB采样阈值；≤32 E0，每次30秒；工程估计0.5–1天。

### 成功后解锁什么

受图与regime守卫的资源词macro候选；不是通用最优solver。

## PB02-EARLY-PREFIX

### 命题

Q1 case051的收益来自隔离不依赖晚到输入的前缀；关键是生成这种切点，而非只重排已生成的零提前量切点。

### 输入 / branch / commit

```json
{
  "Q1": "4dff90ef699fd51845cf482951e8477066f5f566",
  "files": [
    "docs/a/Q1_TRACE_EXPLANATION.md",
    "docs/a/Q1_TRACE_PROSPECTIVE.md",
    "src/q1/profile_candidates.py",
    "results/a/q1-profile-refine-20260924/summary.json"
  ]
}
```

### 允许修改范围

research/peak_B/PB02-EARLY-PREFIX/ 与 results/a/peak_B/PB02-EARLY-PREFIX/<new-run>/；只读导入其他分支。

### 禁止修改范围

不得修改官方源码/原图/固定config原件、FORM与contract、既有实验记录；不得更改Cache/FIFO/带宽/等待语义，不提交等待/预取/重算；不得覆盖生产solver或其他session目录，不自动扩大预算。

### 实验协议

使用冻结commit和原字节SHA256，所有完整计划保留mapping插入序；协议先写盘并固定G/q/k/C/H、Phi/rho、primitive参数、edit signature、选择与停止规则。新输出独立目录，原版E0结果/Trace/日志完整保留；失败、超时、unsupported分别计账。只读观测器需同输入有/无观测全函数结果对照，并与未插桩CLI对应；成本全部计入。原配置成绩与研究配置/合成图分开。E1仅在相应已验收域使用，最终E0确认。任何曾见008/044/080/002/051/003/014/084/095都不是新封存图。 冻结051父计划/切点4和5，保留003/008/044零提前量负例。在父Task真实Step1前缀中依据晚输入依赖标出候选，不读取候选分数选阈值；与旧2split槽位生成器同4候选、同总时间比较，不只是重排。每次重新构造全部相关官方Task/COPY并验证联合环；新增E0≤40。

### 输出

新候选覆盖率、父trace门控与子trace对照、非局部DDR响应、按调用/墙钟的最优前缀曲线。

### 验收指标

至少2个未用于规则选择的父计划出现非零提前量候选；出现同预算净质量或达到同质量时间收益，且原incumbent未丢；门控账目残差为0但不得称候选时长固定。

### 反证 / 停止条件

仍全为0、producer时刻变化推翻预测、额外Task/COPY吞掉收益或只051成功，则不接默认。

### 依赖

PB00；沿用Q1真实profile与合法移动/拆分验证。

### 可并行性

独立于PB01/PB04，可并行研究；正式计时隔离。

### 预计资源

CPU 1，建议2 GiB；≤40 E0，单call30秒；工程估计半天至1天。

### 成功后解锁什么

Q1 late-entry prefix macro；同时提供有明确域的局部pair-ranking候选。

## PB03-BACKING-CLIFF

### 命题

Q1合并/拆分的好坏切换需要backing类别、实际pos和MEM/FIFO共同解释；零spill或预spill字节节约不是充分方向。

### 输入 / branch / commit

```json
{
  "Q1": "4dff90ef699fd51845cf482951e8477066f5f566",
  "MAIN": "f27ef37bb76dcf556f35d3f2328e405d92241d9c",
  "review": "e1575a1de5e3b921aef350e920720f0584fb1719",
  "files": [
    "docs/a/Q1_PROFILE_REFINE.md",
    "docs/a/Q1_TRACE_EXPLANATION.md",
    "data/raw/a/official/code/schedule_step2.py",
    "data/raw/a/official/code/schedule_step3.py"
  ]
}
```

### 允许修改范围

research/peak_B/PB03-BACKING-CLIFF/ 与 results/a/peak_B/PB03-BACKING-CLIFF/<new-run>/；只读导入其他分支。

### 禁止修改范围

不得修改官方源码/原图/固定config原件、FORM与contract、既有实验记录；不得更改Cache/FIFO/带宽/等待语义，不提交等待/预取/重算；不得覆盖生产solver或其他session目录，不自动扩大预算。

### 实验协议

使用冻结commit和原字节SHA256，所有完整计划保留mapping插入序；协议先写盘并固定G/q/k/C/H、Phi/rho、primitive参数、edit signature、选择与停止规则。新输出独立目录，原版E0结果/Trace/日志完整保留；失败、超时、unsupported分别计账。只读观测器需同输入有/无观测全函数结果对照，并与未插桩CLI对应；成本全部计入。原配置成绩与研究配置/合成图分开。E1仅在相应已验收域使用，最终E0确认。任何曾见008/044/080/002/051/003/014/084/095都不是新封存图。 固定044父计划、merge(6,8)、merge(8,10)和零spill劣split。把每条spill分为original_copy_in/new_spill_out/reused_spill_out，保存version/pos。在独立生成图中覆盖L1/UB、一次/重复reload；诊断容量只在副本C上变更。固定边界邻域比较byte-only、closed-pressure、backing-aware排序，不修改官方victim策略；≤32新E0。

### 输出

全部spill血缘链、L4 MEMORY_REUSE与FIFO差异、边界guard证据、好坏父子plan及有限排序对照。

### 验收指标

逐spill条件计费与官方总字段一致；guard阈值至少两个可复现边界；新排序须在冻结新池优于旧排序或可靠ABSTAIN，不要求强行得到正收益。

### 反证 / 停止条件

guard只能事后用winner标签定义、实际因果是ID/COPY顺序而模型忽略、新增特征成本超过收益则停止该代理；保留机制反例。

### 依赖

PB00；不依赖修改FORM，直接以冻结源码为准。

### 可并行性

可与PB01/PB02/PB04并行，独立研究目录。

### 预计资源

CPU 1，2 GiB建议阈值；≤32 E0，单call30秒；工程估计0.5–1天。

### 成功后解锁什么

Q1可用的backing-aware macro guard/abstention规则；为未来最小状态研究提供必要反例。

## PB04-CACHE-INVERSION

### 命题

080的Q2/Q3排序反转是共享输入准入相位与FIFO历史的可预测条件现象，不是命中率越高越好。

### 输入 / branch / commit

```json
{
  "Q3": "a4e7ee13310d693ec4fb5cc236669ceb3b172d1f",
  "files": [
    "results/a/q3-nikolastarx/pilot-20260924/metrics.csv",
    "results/a/q3-nikolastarx/pilot-20260924/run.json",
    "src/q3/construct.py"
  ]
}
```

### 允许修改范围

research/peak_B/PB04-CACHE-INVERSION/ 与 results/a/peak_B/PB04-CACHE-INVERSION/<new-run>/；只读导入其他分支。

### 禁止修改范围

不得修改官方源码/原图/固定config原件、FORM与contract、既有实验记录；不得更改Cache/FIFO/带宽/等待语义，不提交等待/预取/重算；不得覆盖生产solver或其他session目录，不自动扩大预算。

### 实验协议

使用冻结commit和原字节SHA256，所有完整计划保留mapping插入序；协议先写盘并固定G/q/k/C/H、Phi/rho、primitive参数、edit signature、选择与停止规则。新输出独立目录，原版E0结果/Trace/日志完整保留；失败、超时、unsupported分别计账。只读观测器需同输入有/无观测全函数结果对照，并与未插桩CLI对应；成本全部计入。原配置成绩与研究配置/合成图分开。E1仅在相应已验收域使用，最终E0确认。任何曾见008/044/080/002/051/003/014/084/095都不是新封存图。 同一字节plan分别Q2/Q3；以080两个plan为中心，008零hit、044命中率下降仍更快为负对照。记录每次查询、实际成功准入、在飞hit被逐出后重插、DDR/CACHE_READ活跃集。围绕一个预登记FIFO准入阈值在诊断C取阈值−1/+1，改变C必须重新执行；若先发生其他guard变更，原阈值模型不延伸。≤32新E0。

### 输出

跨q排序表、真实共享support结构、输入/缓存图与事件对齐、带guard的相位macro候选。

### 验收指标

反转可重放；能提前预测至少一个新相位邻居的排序或翻转边界；008 zero-hit下Cache不可归因；提供错误预测与ABSTAIN覆盖率。

### 反证 / 停止条件

只读命中率解释、同结构迁移失败、轻扰动无可预测边界、须改Cache策略才重现则降级；不可把P2较差方案从P3硬删。

### 依赖

PB00；PB01的private-key检查可共享但不必等待。

### 可并行性

独立于Q1线；同一机器的计时不可与其他压测并发。

### 预计资源

CPU 1，2 GiB建议阈值；≤32 E0；工程估计半天至1天。

### 成功后解锁什么

Q3-specific guarded macro与局部排名评估器候选；不默认跨Q2迁移。

## PB05-CORE-CONTINUATION

### 命题

沿1–5核保留方案结构再释放新核，比从头重构有更好的质量—成本；仅添加空核只给可行嵌入，不保证改善。

### 输入 / branch / commit

```json
{
  "Q1": "4dff90ef699fd51845cf482951e8477066f5f566",
  "Q3": "a4e7ee13310d693ec4fb5cc236669ceb3b172d1f",
  "EXACT": "5bfe53a29c1ba05167239f51ea937e602f7f85b4",
  "NATIVE": "03f02e79de4b4bd6f55241385664b154f4332454",
  "graphs": [
    "008/Q2",
    "051/Q1",
    "080/Q3"
  ]
}
```

### 允许修改范围

research/peak_B/PB05-CORE-CONTINUATION/ 与 results/a/peak_B/PB05-CORE-CONTINUATION/<new-run>/；只读导入其他分支。

### 禁止修改范围

不得修改官方源码/原图/固定config原件、FORM与contract、既有实验记录；不得更改Cache/FIFO/带宽/等待语义，不提交等待/预取/重算；不得覆盖生产solver或其他session目录，不自动扩大预算。

### 实验协议

使用冻结commit和原字节SHA256，所有完整计划保留mapping插入序；协议先写盘并固定G/q/k/C/H、Phi/rho、primitive参数、edit signature、选择与停止规则。新输出独立目录，原版E0结果/Trace/日志完整保留；失败、超时、unsupported分别计账。只读观测器需同输入有/无观测全函数结果对照，并与未插桩CLI对应；成本全部计入。原配置成绩与研究配置/合成图分开。E1仅在相应已验收域使用，最终E0确认。任何曾见008/044/080/002/051/003/014/084/095都不是新封存图。 各图从k=1开始，逐步比较保留旧标签追加空核、一次guarded continuation、一次cold固定构造。每个k只一份warm与一份cold候选，统一最终E0；total≤48新E0。记录整条trajectory成本及给定seed后的边际成本，不能把前核数搜索当免费。所有C/H冻结；只读缓存或native必须通过所在域验收才用，不假定热批倍率适用。

### 输出

各k的P/F签名与CRG19曲线、关键guard值、空核对照、非单调found-solver轨迹及Pareto成本。

### 验收指标

空核嵌入在指标投影上与父plan一致（full结果metadata可不同）；warm不得靠额外预算赢cold；至少一个跨k族有可复现质量或成本收益。

### 反证 / 停止条件

迁移立即失效、必须大改全部plan才能恢复、引入更多评估抵消收益则停止continuation推广；solver曲线下降不当作最优值单调性反例。

### 依赖

PB00，按图消费PB01/PB02/PB04已固定macro；没有通过的macro不纳入。

### 可并行性

三条trajectory可并行，trajectory内部顺序依赖；需统一CPU资源账本。

### 预计资源

CPU单trajectory 1worker，2 GiB建议阈值；≤48新E0；工程估计半天（宏已完成时）。

### 成功后解锁什么

多核尺度上的macro路由与热启动策略，以及regime transition图。

## PB06-LAG-CELLS

### 命题

仿射参数可以按精确排序区间跳跃，减少重复构造；这不等于不同plan的强行为商，也不证明谁更好。

### 输入 / branch / commit

```json
{
  "Q3": "a4e7ee13310d693ec4fb5cc236669ceb3b172d1f",
  "files": [
    "docs/a/q3/AFFINE_LAG_EQUIVALENCE.md",
    "src/q3/construct.py"
  ],
  "local_audit": "verify_audit.py中120纯整数夹具，9600比较"
}
```

### 允许修改范围

research/peak_B/PB06-LAG-CELLS/ 与 results/a/peak_B/PB06-LAG-CELLS/<new-run>/；只读导入其他分支。

### 禁止修改范围

不得修改官方源码/原图/固定config原件、FORM与contract、既有实验记录；不得更改Cache/FIFO/带宽/等待语义，不提交等待/预取/重算；不得覆盖生产solver或其他session目录，不自动扩大预算。

### 实验协议

使用冻结commit和原字节SHA256，所有完整计划保留mapping插入序；协议先写盘并固定G/q/k/C/H、Phi/rho、primitive参数、edit signature、选择与停止规则。新输出独立目录，原版E0结果/Trace/日志完整保留；失败、超时、unsupported分别计账。只读观测器需同输入有/无观测全函数结果对照，并与未插桩CLI对应；成本全部计入。原配置成绩与研究配置/合成图分开。E1仅在相应已验收域使用，最终E0确认。任何曾见008/044/080/002/051/003/014/084/095都不是新封存图。 新建研究专用参数接口，不改当前固定affine_eighth身份；明确使用每核lag向量还是公共分母。验证每个锚点区间两侧及区间内部的完整有序plan字节。以hash去重参数扫描为强基线，比较区间跳跃的构造次数/总时间，两个方法均不重复评价相同plan。最多12个新distinct plan做Q2/Q3配对，≤24 E0。

### 输出

可核查整数guard区间、参数到plan的去重率、跨边界edit signature、真正单primitive邻居与同时翻转多比较的区别、保留全部负例。

### 验收指标

区间字节一致性零差异；在冻结参数窗内至少减少一半构造或有净时间收益；相同distinct-plan集合的最好E0值不能损失。

### 反证 / 停止条件

不同plan近乎每个参数都变化、求区间更贵、独立多核组合爆炸则停；不因只去重参数就宣称D16行为商压缩率大于1。

### 依赖

PB00的图与身份；Pro A/C可以只读复用区间定义与primitive接口。

### 可并行性

与PB01–PB04独立；阶段性结果可向PB05提供固定相位候选。

### 预计资源

CPU1，通常不需GPU；≤24 E0，纯函数测试毫秒/秒量级需实测；工程估计半天。

### 成功后解锁什么

参数层去重器、mapping guard边界见证；为受限候选族省构造而非包装吞吐。
