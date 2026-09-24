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
