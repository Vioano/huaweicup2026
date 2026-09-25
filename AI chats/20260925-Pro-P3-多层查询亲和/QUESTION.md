P3 / session nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc / R9：请用当前 6 Pro 深入解决“多层 query affinity 的桥接节点归属与旁路依赖”这个具体数学构造问题。本新chat归本session，不接管Fang其他理论chat。不要长综述、不运行官方Task/Step/E0，不编造实验。

已附 p3-r9-layered-inputs.zip，554451字节，SHA256 c4bbc20854999ed402c2487de7521a67dd5bd776b9bfe1bb8c1e96729b464825。MANIFEST列100个文件及逐件hash，含未纳入Git的原始005/086/config、官方源码、当前q3源码和审计。请先读包内 results/a/q3-nikolastarx/layered-query-flow-audit-20260925/PRO_BRIEF.md、REPORT.md，再读原始图及相关源码；明确列实际读到的文件、缺失项。附件包含输入不是新的实测输出。

固定公开主库 c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43：
https://github.com/huaweibei123/huaweicup2026/blob/c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43/results/a/q3-nikolastarx/layered-query-flow-audit-20260925/PRO_BRIEF.md
https://github.com/huaweibei123/huaweicup2026/blob/c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43/src/q3/query_flow.py
https://github.com/huaweibei123/huaweicup2026/blob/c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43/results/a/q3-nikolastarx/query-flow-one-shot-20260925/RESULTS.md
若你的连接只能读Vioano，把上述owner替换为Vioano即可；总调度已实际核镜像同SHA。优先直接读附件，勿将链接存在当成已读。

真实进展：单层R8在071/K5经官方P3=5785（旧7782），其同计划P2无Cache=7070（旧8581），G由1.102673升至1.222126，spill0。两mode都更快，没有故意劣化P2。外资源监督器在两worker已exit0后终态身份校验failed，原件保留，后续独立ps无残存；不能称监督或冷solver效率验收。完整固定solver全500仍五核mean(B/M)=4.757617、meanG=1.082917；局部新结果未拼进全量。旧R8两份固定plan即便达到其合法静态界、其余98不动，mean也至多4.790505，说明必须扩大结构覆盖。

现在005/086不能直接套R8：原始边审计显示三层attention row，005每层14 rows/7个QKV原输入key，086每层16 rows/8 keys，每key两rows。不同层key互异；first-downstream row商图在0→1、0→2、1→2均完全稠密，且0→2路径确实避开中间层row，原始节点ID链已存。旧_decompose因此正确拒绝“row feeds another flow”；这不是删守卫能解决的bug。005旧P3=30642/G≈1.218165，086=32662/G≈1.244566。现有compute-only全局松界12777/15837不证明可达。

请交一套可实现的通用直接构造或有价值反例，集中回答：
1. 如何从原始DAG分解每层的私有流、桥接、共享join与bypass，给每个原op唯一归属，不丢边、不复制/融合原op？需要哪些可检查结构守卫？给005/086的实际节点/张量小证据，避免只凭“attention”名称推断。
2. 7–8流、5核、3层如何用有理由的状态压缩/DP或确定构造分组、保持或迁移核归属、生成每核优先级？要覆盖全部路径与FIFO，不能把单层最多2条remote边的证书直接沿用。给证明条件/复杂度，指出代理量何时不能筛掉候选。
3. 全部曾触及tensor的并集驻留是充分但过强的容量条件；若用活跃前沿替代，请依据官方Task/incarnation/分配/FIFO语义证明，不能假设任意内存分配或零开销跨核。如果尚不能证明，保留保守可验guard并量化覆盖损失。
4. 列出R8哪些结论保留、哪些仅单层成立、哪些需重证；给一个最小toy证明或反例，以及至多两份最有信息量的官方验证候选。目标是压低M3、改善G且不靠抬高M2；不能用命中率替代周期、不把比值高当更快。请指出你最不确定的数学/实现假设。

可提交输出只有node_to_subgraph和core_schedules。现阶段要一个可证伪的新构造，不要求你证明所有P3全局最优，也不请求再次广泛试参。
