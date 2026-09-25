P3 / 同一 session nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc / R10：请继续用 6 Pro 深入解决一个明确瓶颈：怎样安全打破“整条跨层轨道永远同核”的整数负载不均，而不丢掉 bypass 的真实依赖？请给一个新的直接构造及可检验证书，不要再重复 R9 综述，不跑官方 Task/Step/E0，也不做大量试参。

R9 已完成首次本机官方验证，你的结构主张取得了实证支持，但三项目标没有一起达成。005/K5 同一计划：M3 从 30642 降至 24522（-19.97%），M2 无 Cache 从 37327 降至 29026（-22.24%），G 从 1.2181646106651 降至 1.183671804909877。所有 4113 原 compute、1022 COPY、381 cross links、5763 memory dependencies 及 17905 条联合边通过 guard；spill=0，完整路径 crossing<=4。这个实例支持证书，不能当作所有图的证明。两mode都更快，没有靠劣化M2抬G。数据仅一格，正式同一固定算法全500仍 K5 mean(B/M3)=4.7576166788448955，meanG=1.082917172693062。

已有严格范围警告：100图只做静态识别/分解，22通过，其中5<=tracks<=10仅13图。若其他87图固定旧Forest、005/086固定你这两份计划，则把其他11图乐观取各自通用合法下界，该受限融合的均值上界仍仅4.994650520967255<5。这不是整个R9家族或全局不可达证明；它说明不能只补这两份计划并停在whole-track构造。

005轨道M/V总量：前五条各(9972,9306)，最后两条各(6876,7200)。现分组[0],[1],[2],[3,5],[4,6]，含共享op的本核M/V为(10107,9306),(9972,9306),(9972,9306),(16923,16506),(16908,16506)。固定计划M/V/FIFO/+500合法下界21636，比通用12777仍高很多，官方M3=24522。需要打破实际长路径/负载不均，不是只让负载代理数字变好。086保持静态未评分，无新官方成绩。

请基于原ZIP里的005/086原始图、官方源码及你上轮的证据，集中交付：
1. 一种图结构驱动、保留每个原op恰好一次的“有限迁移”构造：优先整段桥接/下一层轨道换核或其他可证明更合适的切点，不随意拆attention row内部。定义合法迁移切面，显式处理跨越不止一层的存活 bypass tensor（005的1294→1000001330→{1441,1442,2678}等）。不能使用仅DP[layer,current owner]的错误Markov状态，也不能把 nominal stage 当全局完成屏障。可以用有理由的确定性启发式+独立证书，不必声称代理或官方最优。请解释复杂度、候选数和为什么值得构造。
2. 对改变owner后的完整原边、输入/跨核COPY、四Pipe FIFO、内存边给出可检查的合法性/容量/remote-path证书。沿用 singleton 时哪些R9证明仍成立？跨核次数不能继续无条件声称<=4。跨层carry应按真实producer owner和每个destination core计费，不能按所有reachability边或每个consumer重复计费。若必须保留过多状态，请给一个可证伪的更小受限族及具体收益机制，而不是精确DP名义下丢状态。
3. 至多交两份新静态计划（优先005；第二份只有结构理由充分才给），保存原边/owner/carry核验、每池桶前沿、计算FIFO合法下界和完整路径crossing证据。若有效下界已不低于24522则停止这份计划，不拿不合法上界/代理剪枝。我们之后统一安排最少官方验证；不要自报M3/M2/G实测。新方案不能通过制造更慢M2获取G。

另给一个与迁移相互作用的具体Cache事实，供决定顺序时使用，不要求你另开一篇Cache研究：新计划tensor1000000048(9216B)在6100/6136/6155/6623/6626各miss，首次insert6735，无eviction；旧计划miss7944、insert8176，随后4hit。1471也五次请求早于首次insert14075。这是首次填充竞态，非容量驱逐。官方issue时查hit，retire完成后insert，且同一now先retire后issue；没有在途miss合并。只把follower MATMUL放晚并不延后它的MTE2 COPY。若你的迁移/排序能使真实pilot输入更早，请说明合法提交如何实现；不要添加COPY、sleep、假依赖或预取接口。我们本地另审计pilot连续singleton合桶，尚未验证有效，不请你重复该具体审计。

新增证据固定公开主库SHA 2c1e12ac4c55a920f62078d707d95fdf5f5eb100（组织/ Vioano镜像该分支已实际核同）。优先组织主库；受连接限制时改owner为Vioano，SHA/路径不变。请列实际读到的文件，读不到就明确说，不把链接存在算已读。
- 官方结果/限制：https://github.com/huaweibei123/huaweicup2026/blob/2c1e12ac4c55a920f62078d707d95fdf5f5eb100/results/a/q3-nikolastarx/layered-one-shot-20260925/RESULT_REPORT.md
- prepared完整原件入口：https://github.com/huaweibei123/huaweicup2026/tree/2c1e12ac4c55a920f62078d707d95fdf5f5eb100/results/a/q3-nikolastarx/layered-one-shot-20260925/run
- 精确cache事件与逐key差分：https://github.com/huaweibei123/huaweicup2026/blob/2c1e12ac4c55a920f62078d707d95fdf5f5eb100/results/a/q3-nikolastarx/layered-cache-delta-recovery-20260925/REPORT.md （同目录top-key-events.json/key-deltas.json）
- 受限融合上界独立复核：https://github.com/huaweibei123/huaweicup2026/blob/2c1e12ac4c55a920f62078d707d95fdf5f5eb100/results/a/q3-nikolastarx/layered-target-impact-20260925/INDEPENDENT_CEILING_REVIEW.md （该文在005官方评分前写成，文中“尚无005prepared”现已由本次结果补齐，086仍未测）
- 当前实现：https://github.com/huaweibei123/huaweicup2026/blob/2c1e12ac4c55a920f62078d707d95fdf5f5eb100/src/q3/layered_query_flow.py

原图与配置仍用这个chat先前上传且逐hash核过的ZIP；如果环境未保留请报告具体缺件，不自行造图。要的是能突破当前受限构造的数学/算法改动，而非承诺达到5或虚构最优证明。