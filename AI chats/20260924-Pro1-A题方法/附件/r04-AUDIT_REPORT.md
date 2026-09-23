# A 题完整附件预研：源码、数据与实验审计

## 范围与证据等级

本报告仅针对本次上传的《通用神经网络处理器下的多核调度问题》附件版本。这里的实验是策略预研，不是最终参赛求解器或排名预测。

原始 ZIP SHA-256：`3112331344df7dcf2dcef2ff5f789669c0419e32cefbbc6e2742b9e36d5c43c9`。

已解压并核验 114 个文件：10 个 Python 文件、100 个 case JSON、2 个说明文档、README 和 config。原始文件均未修改；`official_manifest.json` 给出全部哈希。所有报告的官方 Makespan 都来自原样官方函数，不使用修改后的评分器。自行设计的构造器仅输出允许的两字段方案。

证据分为 SPEC（题面/配置）、CODE（本版实际实现）、MEASURED（本次运行）、DERIVED（本文推导）、HYPOTHESIS（待验证策略）。这些类别不可相互冒充。

## 已完成的实验

- 100/100 用例静态扫描；本次所有四核基线评估也通过官方输入校验。
- 100/100 四核场景 B：计算依赖弱连通分量完整保留，以总计算 cycles 做贪心装箱，同核所有分量合为一个子图。构造器名 `component_sum`。此构造器是简单的保守基线，不是成熟强算法。
- 同一批 100 个方案，100/100 在问题 3 下重评。故这是固定方案的 L2 硬件效果对照，不是 L2 专用优化的最终收益。
- 17 个用例上分别完成 cut2 场景 A、cut2 场景 B、unit 场景 B、component_unit 场景 B。每组 17 个，均成功返回。它们是针对机制的非随机选样，不能据此报告全体平均收益。
- 独立单核基准完成 76 个，随后停止本轮该批预研。剩余 24 个未记为失败或零；不据此计算全体平均加速比。完整覆盖见 `evidence/singlecore_coverage.json`。最终论文必须用原样 singlecore_evaluate 完成全部 100 个固定基准。
- 10 个微型机制实验，其中 3 个故意构造的等待环被预期拒绝。
- 一个 4 计算节点、2 核的微图，分别对三问完整枚举 308 个分区/核心分配/核内顺序编码；三问各自最优 Makespan 都是 64 cycles。有效方案分别 152、154、154 个。此“最优”仅适用于该微图完整搜索空间。
- 100 个用例计算头尾窗口负载下界，并与四核基线对照。下界是数学松弛，不是最优时间预测。

## 数据画像（全部 100 个）

| 项目 | 结果 |
|---|---:|
| 原始操作数 | 766—38,666 |
| 非 COPY 计算操作数 | 552—35,705 |
| 全体计算操作数 | 634,506 |
| 计算依赖弱连通分量数 | 1—2,666 |
| 计算依赖图仅一个弱连通分量 | 16 个用例 |
| 纯 Vector 用例 | 7 个 |
| 最大单输入消费者数 | 2,666 |
| 原始输入去重体积 | 35,622—13,400,064 bytes |
| 原始输入去重体积超过 1 MiB | 50 个用例 |
| 四核保守基线出现 SPILL 新增流量 | 31 个用例 |

前一轮上传的单独样例与正式 `case_010.json` 的 SHA-256 完全相同。此前关于它的静态描述不能推广至全体，特别是“缓存压力不大”“输入总量可装入 L2”。

## 关键源码语义

以下路径均相对于原始附件根目录。源代码事实与文档概述不一致时，不可默默混用；论文应注明研究采用的具体版本，并另行处理正式勘误。

### C01：最终执行遵循固定 Pipe FIFO，不是动态全局就绪优先级调度

`schedule_step3.py:274—291`：把 `seq_ext` 投影到各 Pipe，形成 `planned_pipe_orders`。

`schedule_step3.py:675—705`：`prepare_step3_execution` 返回 `execution_graph` 和 `pipe_ops`。

`multicore_cut_evaluate_problem_2.py:381—404`：只有当前 Pipe 队首操作才能进入就绪队列。不能跳过被跨核依赖挡住的队首，去执行同 Pipe 后面的独立操作。

### C02：局部存储申请约束通过内存复用边传递到全局

`schedule_step3.py:139—183`：维护可拆分虚拟字节额度，记录旧数据使用者到新输出生产者的依赖。

`schedule_step3.py:594—609` 附近：把这些 `MEMORY_REUSE` 关系写入执行图。全局多核循环装载该图，不重复执行局部的全局 allocation_order 门控。因此此前“最终全局阶段仍维护一个跨 Pipe 的 allocation_order”的解读过强，必须修正。

`memory_peak_by_core` 在问题 2/3 的返回值中取自各核 Step3 局部运行，不是对多核时间线重新扫描得出的峰值。要声称实际全局生命周期峰值，应独立重演并区分指标来源。按官方字段报表时保留原值。

### C03：子图 DAG 无环不等于执行图无环

`evaluation_validation.py:217—245`：问题 1 检查子图依赖与同核 Task 顺序的组合；问题 2/3 检查局部数据/内存依赖、Pipe FIFO 和跨核 COPY 的组合。

`evidence/micro/wait_cycle_p2` 中的图和方案通过 `derive_multicore_plan`，但最终被 `validate_execution` 拒绝。异常 `cycle` 属性给出完整带类型环边。

保留两个阶段的可行性状态，禁止把“JSON/分区校验通过”标为“官方可执行”。

### C04：场景 B 的跨核多播不是源端只写一次

`multicore_cut_evaluate_problem_2.py:183—209`：对每一个实际 source-core / target-core 对分别插入一对 COPY_OUT/COPY_IN。

相反，场景 A 的 `multicore_cut_evaluate_problem_1.py:145—167` 在源 Task 为一个边界张量插入一个 COPY_OUT，各目标 Task 各自 COPY_IN。

在微图 `multicast` 中，一个 600-byte 中间张量送到两个远端核心：A 新增 1,800 bytes；B 新增 2,400 bytes。B 本例 Makespan 仍较低，不能由流量差异推断整体速度次序。不同真实硬件可能采取其他实现；本报告不将本版规则推广到所有 NPU。

### C05：子图是问题 2/3 的顺序控制变量，而非额外搬运的直接边界

`multicore_cut_evaluate_problem_2.py:43—59`：按 core_schedules 指定的子图顺序稳定分桶，桶内保留 Step1 顺序；再校验局部拓扑。

构造 Task 时，输入 COPY_IN 归入该核最早消费它的子图，输出 COPY_OUT 归入其源子图。改变子图粒度和顺序会改变各 Pipe 的投影顺序、存储驻留、SPILL 和等待；不能在模型中省略顺序维度。

细化为单操作子图并不意味着算法可自由改写所有 COPY 的位置，也不意味着性能一定提高。component_unit 对照已有退化结果。

### C06：L2 首次并发读取不合并；所有符合条件的 COPY_IN 都可查询

`multicore_cut_evaluate_problem_3.py:398—431, 532—590`：键为片上张量的 logical_tid（缺省其 id），COPY_IN 发射时查缓存；在途 miss 没有请求合并机制。源 COPY_OUT 不负责填充 Cache。

`retire` 对 COPY_IN 完成执行插入逻辑；已存在条目不刷新 FIFO。一个命中读取在完成前若其条目已被淘汰，完成后的插入逻辑也可能重新加入；这比“只有 miss 完成才写入”的文档概述更细，不要修改模拟器来消除差异。

机制实验：

| 同一图、同一核心分配，仅改变独立子图顺序 | 无 L2 | 有 L2 | 有 L2 的命中字节数 |
|---|---:|---:|---:|
| 共享输入同时首次读取 | 333 | 333 | 0 |
| 另一核先处理原图中已有的独立工作 | 333 | 261 | 6,000 |

未增加操作、未添加等待指令、未修改配置。这个实验验证时序机制，不代表正式数据的收益幅度。

### C07：问题 3 的 data_movement_bytes 是展开后搬运计数，不随 hit 路径扣减

`_build_scene_b_tasks` 在仿真之前构建 data_movement；`evaluate_problem_3` 原样把它写回结果。固定方案下问题 2 与问题 3 的该字段完全相同，尽管实际 DDR 服务流量可能不同。

应保留官方字段；另从 `memory_path`、张量大小、hit/miss 字节量统计实际 DDR 与 Cache 读流量。不能把 `added_copy_bytes` 的静态语义悄悄替换成另一指标。

### C08：COPY 工作量先逐操作向上取整

`schedule_step3.py:74—82`：COPY 参考工作量为数据量除以带宽后逐操作 ceil，且至少 1 cycle；随后进入共享带宽模拟。因此“所有字节相加再除以带宽”只能作为相应松弛，不与实际逐操作计算严格等价。

### C09：性能与缓存键的工程含义

官方单核入口实际调用场景 A 的整图单 Task 构造。`schedule_step3.py` 完成性检查有逐事件扫描；`multicore_cut_evaluate_problem_1.py:369—373` 又为活跃 Task 逐事件构造全部操作键列表并检查完成。因此某些大型单核参考评估明显慢于已分核的 B 评估。

`evidence/profile_case014_single_partial.txt` 是明确限制为 20 秒的诊断 profile，不是完整耗时测量，也不包含后续全部热点。不要用其耗时当成完整 case 评估成本。

建议固定基准离线一次计算并按材料/配置哈希保存；不要每次候选都重算。内部预测或等价加速实现必须与原样官方程序差分验证，最终结果仍由原样官方程序出具。

## 候选对照：仅用于确定研究方向

基线 `component_sum`：保留计算依赖分量，按总工作量贪心装箱，每核一个子图。

`cut2`：去掉由总张量大小不超过 2 bytes 的依赖连接后取弱连通块；商图中的 SCC 再合并以修复无环性；按照块级剩余路径优先级和简化通信代价分配。SCC 合并只合并分组，不改变计算。成本估计使用计算 cycles 总和，未充分刻画多 Pipe 重叠。

`unit`：计算操作作为单元，做相同思想的细粒度列表分配；没有结构化保护，因此通信与顺序可能退化。

`component_unit`：保持基线的核心归属，但改用单操作子图和另一合法优先顺序，隔离顺序/粒度因素。

四核场景 B，单位 cycles，越小越好：

| case | 基线 | cut2 | unit |
|---|---:|---:|---:|
| 001 | 58,984 | 58,984 | 78,028 |
| 002 | 261,945 | 261,945 | 111,212 |
| 010 | 29,918 | 24,566 | 64,978 |
| 044 | 124,268 | 156,394 | 70,260 |
| 048 | 222,220 | 222,220 | 110,334 |
| 051 | 607,628 | 188,224 | 188,732 |
| 094 | 24,640 | 25,350 | 57,192 |

完整 17 个对照见 `evidence/candidate_comparison_17.json`。不把这些构造器称为最终强基线，不把样本内最佳候选称为可部署选择器的实际成绩。

## 下界与资源优先级

定义每个计算操作的 head 为忽略通信和资源竞争的最早开始时间，tail 为该操作完成后的最长剩余计算路径。某类 Pipe 上，选取 head 不小于 a、tail 不小于 b 的非空操作集合。它们全部必须在区间 [a, T-b] 中完成，N 个对应 Pipe 在该区间最多提供 N 倍区间长度的计算容量。因此 T 至少为 a、b 与集合总 cycles 除以 N 三者之和。与计算关键路径、必需 DDR 冷读/最终写回下界取最大值仍是下界。

脚本使用 48×48 的离散阈值网格，未穷尽所有阈值；这是合法但可能较松的下界。证明不依赖强行串行化不同 Pipe，也不把可消除的 SPILL 计入所有方案的必需搬运。

本次四核基线有 24 个用例的相对最优性差距上界不超过 5%，32 个不超过 10%。例如 case_014 的基线为 4,551,951 cycles，下界 4,306,503 cycles，因此基线相对真正最优解的差距至多约 5.70%。这不是证明该下界可达到。

该证据支持研究资源分配：不按节点数最大或总 cycles 最大自动优先；优先考虑能够在多个同结构用例中验证的、高潜在收益且可解释的瓶颈。下界较松本身不证明有巨大可实现收益。

## L2 全体固定方案对照

100 个四核保守方案中，29 个在加入 L2 后 Makespan 下降，71 个不变；中位加速比为 1，最大约 1.39566。未观察到该组固定方案因 L2 变慢。50 个用例发生 FIFO 淘汰。

这只描述该保守方案族。它不证明 L2 无用，也不规定 L2 专用优化的收益上限。Cache 命中率高不等于 Makespan 必然大幅下降，应检查被省掉的传输是否位于关键等待链。

## 复现

这些脚本是预研工具，不是最终求解器。使用 Python 标准库。把原始附件解压至某个目录，以其 README、code、data、docs 直接位于根目录为准。

```bash
python scripts/scan_cases.py /path/to/official evidence/static_all100.json
python scripts/probe_runner.py /path/to/official /path/to/fresh_results --cases all --mode component_sum --problem 2 -n 4 --workers 4
python scripts/probe_runner.py /path/to/official /path/to/fresh_results --cases all --mode component_sum --problem 3 -n 4 --workers 4
python scripts/window_bounds.py /path/to/official/data evidence/window_bounds_all100.json
python scripts/microprobes.py /path/to/official /path/to/fresh_micro
python scripts/tiny_oracle.py /path/to/official /path/to/fresh_micro/wait_cycle_p2/graph.json /path/to/fresh_oracle
```

运行输出会写到显式传入目录，勿并发使用同一 case/mode/problem/N 的同一路径。正式协作 harness 应增加 job ID、代码版本哈希和超时控制。`profile_probe.py` 使用 POSIX SIGALRM，仅用于支持该信号的系统。

精简证据包保留全部摘要、输入/输出哈希和代表性原始运行结果；不是所有大型 Trace 的副本。完整大结果可用同一原始材料和脚本重建。运行秒数受当前宿主和并发影响，不是用户四台电脑的实测性能承诺。
