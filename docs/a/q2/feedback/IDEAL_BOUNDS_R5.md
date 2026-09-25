# P2 固定方案的理想模型下界 R5

本会话 `yuanzhifang30-sudo/s-eb28fa11a5664fdfbdd29b3d6e38ca24` 新增独立模块 `src/q2/feedback/ideal_bounds.py`，不改已冻结待试的R4源码或构造入口。实现用于解释固定方案及研究廉价候选准入，尚未成为新的求解算法成绩。

## 已实现量与范围

对固定singleton方案B，在唯一原producer、无logical alias及R4已有整数数值域下，计算基础DDR服务和W、逐核逐Pipe eligible工作量P、真实tensor/direct依赖最长路径D，以及增加同核同Pipe相邻eligible FIFO弧后的最长路径D_FIFO。各跨核真实边权为两次COPY独占服务加固定等待，同核边权为0；多个输入和并行弧取max。最终取 `L_B=max(W,P,D_FIFO)`，同时保留物理路径D供诊断。

这是**固定方案、理想精确服务模型、成功执行条件下**的必要界。分核、FIFO、跨核COPY都依赖B，换成其他方案后这些工作和等待可以减少，故本量**不是全局最优Makespan的下界**，不能把`M/L_B`写成全局最优性gap。浮点退役、事件投影和成功返回仍需另外核验；未凭测试宣布机器严格证书。

根会话已阅读两份Sol审阅及对应冻结源码：[物理关键路径](CRITICAL_PATH_BOUND_R5_REVIEW.md)、[FIFO顺序与环边界](FIFO_LOWER_BOUND_R5_REVIEW.md)。原COPY链收缩的可达边不能直接当实际物理等待；同核不同Pipe的优先顺序不能整体串行化。同Pipe相邻eligible的0 lag弧来自Step2保持原op子序列、Step3固定逐Pipe投影及全局cursor在完成后推进。加入FIFO后重新拓扑检查，必要依赖有环则拒绝给有限下界；无环仍不证明完整E0成功。

数值诊断元数据`contracted_pairs_without_physical_arc`统计端点对的差集，不是被排除COPY路径数。Sol窄审指出旧命名可能混淆两者，已更正并注释。同核direct不再计算无用的COPY服务。复用service_profile已经完成的官方计划校验，避免同一函数再重复derive；这项减少调用不等于已实测求解器提速。

已有索引与计划验证后，物理弧构建、Pipe投影及两次拓扑最长路径扫描为O(V+E+I)，FIFO新增弧至多V，辅助空间同阶。服务统计的按核tensor对及官方计划验证、TensorIndex的构建/排序成本另计；不能把扫描复杂度称为整个求解器端到端复杂度。

## 检查与后续诊断

新增8项手算/反例检查，联同R4/F1为19项通过：509周期tensor路径及并行direct取max、504周期多输入汇合、不同Pipe不串行、原COPY链不产生假lag、同核传输无lag、FIFO把509加强到511、四节点跨核/FIFO等待环拒绝，以及别名/多producer/数值域拒绝。均0真实图构造、0 Step2/Step3/E0。Sol medium先做FIFO窄审（软预算4500 tokens），再做实现窄审（软预算3000）；未使用Astra、未递归；软预算不是工具级已核算token账单。

`results/a/q2-yuanzhifang/feedback-20260924/ideal-bound-r5-static/probe.py` 准备对100个已保存五核tensor/F1方案对做静态核验，核对图、配置、计划与结果哈希、基础COPY字节；记录理想界是否高于已有E0、旧/新判据能触发哪些保存方案对及容量证书。它不构造新方案、不调用Step2/3/E0，也不将事后选择保存方案的分数拼成新的算法均值。输入已用于研发，不能称留出或盲测。

P2核查03:15:54.4062372Z本人0评分进程且R4未START，并给P1暂让资源。P1随后回报03:16:57.6324379Z其RAM门未通过、0solver/0E0且释放窗口；P203:19:05.3946213Z实查空闲1163673600 B。静态诊断仍需派发时复核资源，实际结果另补，未运行前不预报增益；R4真实评分仍按原Issue33排程，不复活已封存预算。
