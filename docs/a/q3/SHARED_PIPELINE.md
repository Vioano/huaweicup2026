# 共享输入连续流水线构造

`src/q3/shared_pipeline.py` 是 Fang 已发表提交
`6bae8dfa317bc71226068344b59dd65d2612c32b` 的
`src/q3_yuanzhifang/pipeline_stages.py` 中连续分段 DP 的本线适配。
该构造没有在线评分、参数扫描或自动回退；不适用时抛出本线
`UnsupportedStructure`。它不是新的切点研究。

输入为本线 `Index` 和请求核数 `1..5`。从官方原始 tensor views 重新识别外部输入：
某 tensor 有合格操作消费者而没有合格操作生产者时，计入对应弱分量的输入。
仅当所有弱分量具有非空共同输入、每条拓扑序列的相邻操作有真实依赖边、
每个作业的 `(pipe, duration, 共同输入消费者)` 签名一致、位置数不超过 512、
作业数不少于请求核数时构造。共同 tensor 的真实 ID、size、生产者和消费者用于
元数据；不重写原图、COPY 节点或 Cache 身份。缺少必要 tensor size 时拒绝。

DP 对第一个作业的各位置正权重，求精确最小最大连续段和，复杂度
`O(k n²)`、空间 `O(k n)`。目标相等时选较小的前一切点，保留上游规则。
活跃核数为 `min(cores, positions)`；其余核给空优先级表。每个操作映射为
singleton 子图，各活跃核按作业顺序写入对应连续位置段，并用冻结官方
`derive_multicore_plan` 作结构推导。

`bottleneck_cycles` 和 `ideal_flowshop_cycles` 是无 COPY、每段单服务器的
flowshop 代理，**不是 E0 Makespan 的下界或上界**。
`shared_input_bytes_by_stage` 和跨 stage tensor net 字节为原始 tensor
视图的静态计数，不是 Cache 命中字节或真实 DDR 传输量。

2026-09-24 的零 E0 全100图结构普查中，该守卫识别8图：001、036具有3位置；
044、046、067、073、083、092具有124位置，分别11、8、71、39、31、142个作业。
编号仅为覆盖报告，算法不读取编号或历史成绩。源码适配还没有本机官方 E0 成绩。

新入口 `src.q3.pipeline_solve` 先运行同次调用的完整 calendar 算法，在请求
2–5核且上述守卫满足时仅追加一个连续分段候选。相同方案或已证下界不可能
改善时跳过评分；否则只在完整官方 Makespan 严格下降时采用。每次求解最多3次
在线E0（包括原算法至多2次），构造、下界和评分均计入端到端耗时。保持一核旧策略。
这不是任意枚举切法：DP直接解一个明确代理问题，然后只验证其唯一确定的方案。
这个策略保留当前算法的官方质量，代价是符合结构守卫的输入可能增加一次评分；
是否值得采用须同时报告真实质量与耗时。完整500验证尚未进行。

小图测试运行 `python3 -m unittest tests.q3.test_shared_pipeline -v`：
穷举正权重对照 DP、固定提交原函数同输入 parity、守卫拒绝、输入不变、
覆盖与官方结构推导。测试不调用 E0/E1/E2。
